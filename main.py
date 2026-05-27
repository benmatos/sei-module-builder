from __future__ import annotations
import json, os, io
from typing import Optional, List
from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware
from pydantic import ValidationError
from models import ModuloDefinicao
from generator import ModuloSEIGenerator
from database import init_db, salvar_projeto, listar_projetos, carregar_projeto, excluir_projeto, registrar_geracao
from deploy import DeployLocal, DeployConfig

SECRET_KEY  = os.getenv("SECRET_KEY", "dev-insecure-key-change-in-production")
SESSION_TTL = int(os.getenv("SESSION_TTL_SECONDS", "7200"))
DEBUG       = os.getenv("DEBUG", "false").lower() == "true"

app = FastAPI(title="SEI Module Builder", debug=DEBUG)
app.add_middleware(SessionMiddleware, secret_key=SECRET_KEY, max_age=SESSION_TTL)
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

def flash(request, msg, cat="error"):
    request.session.setdefault("_flashes", []).append({"msg": msg, "cat": cat})

def get_flashes(request):
    return request.session.pop("_flashes", [])

def get_deploy_cfg() -> DeployConfig | None:
    return DeployConfig.from_file("deploy.cfg")

@app.on_event("startup")
async def startup():
    init_db()

# ── Wizard ────────────────────────────────────────────────────────────────────

@app.get("/", response_class=RedirectResponse)
async def root(): return RedirectResponse("/wizard/1")

@app.get("/wizard/1", response_class=HTMLResponse)
async def w1_get(request: Request):
    return templates.TemplateResponse(request, "wizard/step1.html", context={
        "flashes": get_flashes(request),
        "data": request.session.get("step1", {})
    })

@app.post("/wizard/1", response_class=RedirectResponse)
async def w1_post(request: Request, nome: str = Form(...), slug: str = Form(...),
                   namespace: str = Form(...), descricao: str = Form(...),
                   versao: str = Form(...), sei_versao_min: str = Form(...), 
                   autor: str = Form(...), extras: List[str] = Form([])):
    request.session["step1"] = dict(nome=nome, slug=slug, namespace=namespace,
                                     descricao=descricao, versao=versao,
                                     sei_versao_min=sei_versao_min, autor=autor,
                                     extras=extras)
    return RedirectResponse("/wizard/2", status_code=303)

@app.get("/wizard/2", response_class=HTMLResponse)
async def w2_get(request: Request):
    return templates.TemplateResponse(request, "wizard/step2.html", context={
        "flashes": get_flashes(request),
        "tabelas_json": json.dumps(request.session.get("step2", []))
    })

@app.post("/wizard/2", response_class=RedirectResponse)
async def w2_post(request: Request, tabelas_json: str = Form(...)):
    try:
        request.session["step2"] = json.loads(tabelas_json)
    except Exception as e:
        flash(request, f"Erro ao processar tabelas: {e}")
        return RedirectResponse("/wizard/2", status_code=303)
    return RedirectResponse("/wizard/3", status_code=303)

@app.get("/wizard/3", response_class=HTMLResponse)
async def w3_get(request: Request):
    return templates.TemplateResponse(request, "wizard/step3.html", context={
        "flashes": get_flashes(request),
        "recursos_json": json.dumps(request.session.get("step3_recursos", [])),
        "menus_json":    json.dumps(request.session.get("step3_menus", []))
    })

@app.post("/wizard/3", response_class=RedirectResponse)
async def w3_post(request: Request, recursos_json: str = Form(...), menu_pai: str = Form(...), extra_dashboard: Optional[str] = Form(None)):
    try:
        request.session["step3_recursos"] = json.loads(recursos_json)
        request.session["menu_pai"] = menu_pai
        
        # Gerencia extras: preserva os do passo 1 e adiciona/remove dashboard do passo 3
        step1 = request.session.get("step1", {})
        extras = step1.get("extras", [])
        
        if extra_dashboard == "true":
            if "dashboard" not in extras: extras.append("dashboard")
        else:
            if "dashboard" in extras: 
                try: extras.remove("dashboard")
                except ValueError: pass
            
        step1["extras"] = extras
        request.session["step1"] = step1
        
    except Exception as e:
        flash(request, f"Erro: {e}")
        return RedirectResponse("/wizard/3", status_code=303)
    return RedirectResponse("/wizard/4", status_code=303)

@app.get("/wizard/4", response_class=HTMLResponse)
async def w4_get(request: Request):
    deploy_cfg = get_deploy_cfg()
    deploy_ativo = deploy_cfg is not None and deploy_cfg.auto_deploy
    valido, motivo = deploy_cfg.valido() if deploy_cfg else (False, "deploy.cfg não encontrado")
    return templates.TemplateResponse(request, "wizard/step4.html", context={
        "flashes":      get_flashes(request),
        "step1":        request.session.get("step1", {}),
        "tabelas":      request.session.get("step2", []),
        "recursos":     request.session.get("step3_recursos", []),
        "menus":        request.session.get("step3_menus", []),
        "menu_pai":     request.session.get("menu_pai", "0"),
        "deploy_ativo": deploy_ativo and valido,
        "deploy_aviso": motivo if not valido else "",
    })


@app.post("/gerar")
async def gerar_wizard(request: Request):
    try:
        payload = {
            **request.session.get("step1", {}),
            "tabelas":  request.session.get("step2", []),
            "recursos": request.session.get("step3_recursos", []),
            "menus":    request.session.get("step3_menus", []),
            "menu_pai": request.session.get("menu_pai", 0),
        }
        print("[DEBUG] Payload para ModuloDefinicao:", payload)
        definicao = ModuloDefinicao(**payload)
        # menu_pai pode ser passado separadamente para o template, se necessário
        request.session["menu_pai"] = request.session.get("menu_pai")
    except ValidationError as e:
        print("[VALIDATION ERROR]", e)
        print("[VALIDATION DETAILS]", e.errors())
        print("[DEBUG] Payload com erro:", payload)
        flash(request, f"Dados inválidos: {e.error_count()} erro(s). Revise os passos anteriores.")
        return RedirectResponse("/wizard/4", status_code=303)

    gen       = ModuloSEIGenerator()
    zip_bytes = gen.gerar_modulo(definicao)

    # Persistir projeto
    try:
        pid = salvar_projeto(definicao.model_dump())
        registrar_geracao(pid, definicao.versao, len(gen.ultimo_arquivo_count))
    except Exception:
        pass

    # ── Auto-deploy ───────────────────────────────────────────────────────────
    deploy_result = None
    deploy_cfg = get_deploy_cfg()
    if deploy_cfg and deploy_cfg.auto_deploy:
        valido, _ = deploy_cfg.valido()
        if valido:
            deployer     = DeployLocal(deploy_cfg)
            deploy_result = deployer.deploy_from_bytes(zip_bytes, definicao.slug, definicao.versao)
            request.session["ultimo_deploy"] = deploy_result.to_dict()

    for k in ("step1", "step2", "step3_recursos", "step3_menus"):
        request.session.pop(k, None)

    # Se deploy ativo, redireciona para página de resultado
    if deploy_result:
        return RedirectResponse("/deploy/resultado", status_code=303)

    # Sem deploy: retorna ZIP para download direto
    filename = f"{definicao.slug}_v{definicao.versao}.zip"
    return StreamingResponse(
        io.BytesIO(zip_bytes),
        media_type="application/zip",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )

# ── Resultado do deploy ───────────────────────────────────────────────────────

@app.get("/deploy/resultado", response_class=HTMLResponse)
async def deploy_resultado(request: Request):
    result_data = request.session.pop("ultimo_deploy", None)
    if not result_data:
        return RedirectResponse("/", status_code=303)
    return templates.TemplateResponse(request, "deploy/resultado.html", context={
        "r":       result_data,
    })

# ── Projetos ──────────────────────────────────────────────────────────────────

@app.get("/projetos", response_class=HTMLResponse)
async def projetos_list(request: Request):
    return templates.TemplateResponse(request, "projetos/index.html", context={
        "flashes":  get_flashes(request),
        "projetos": listar_projetos(),
    })

@app.get("/projetos/{projeto_id}", response_class=HTMLResponse)
async def projeto_detalhe(request: Request, projeto_id: int):
    projeto = carregar_projeto(projeto_id)
    if not projeto:
        flash(request, "Projeto não encontrado.")
        return RedirectResponse("/projetos", status_code=303)
    return templates.TemplateResponse(request, "projetos/detalhe.html", context={
        "flashes": get_flashes(request), "projeto": projeto,
    })

@app.post("/projetos/{projeto_id}/carregar", response_class=RedirectResponse)
async def projeto_carregar(request: Request, projeto_id: int):
    projeto = carregar_projeto(projeto_id)
    if not projeto:
        flash(request, "Projeto não encontrado.")
        return RedirectResponse("/projetos", status_code=303)
    d = projeto["definicao"]
    request.session["step1"]          = {k: d[k] for k in ("nome","slug","namespace","descricao","versao","sei_versao_min","autor","extras")}
    request.session["step2"]          = d.get("tabelas", [])
    request.session["step3_recursos"] = d.get("recursos", [])
    request.session["step3_menus"]    = d.get("menus", [])
    flash(request, f"Projeto '{d['nome']}' carregado.", "success")
    return RedirectResponse("/wizard/1", status_code=303)

@app.post("/projetos/{projeto_id}/excluir", response_class=RedirectResponse)
async def projeto_excluir(request: Request, projeto_id: int):
    excluir_projeto(projeto_id)
    flash(request, "Projeto excluído.", "success")
    return RedirectResponse("/projetos", status_code=303)

# ── API ───────────────────────────────────────────────────────────────────────

@app.post("/api/gerar")
async def api_gerar(definicao: ModuloDefinicao):
    gen       = ModuloSEIGenerator()
    zip_bytes = gen.gerar_modulo(definicao)
    filename  = f"{definicao.slug}_v{definicao.versao}.zip"
    return StreamingResponse(io.BytesIO(zip_bytes), media_type="application/zip",
                              headers={"Content-Disposition": f"attachment; filename={filename}"})

@app.post("/api/validar")
async def api_validar(definicao: ModuloDefinicao):
    return {"valid": True, "slug": definicao.slug, "tabelas": len(definicao.tabelas)}

@app.post("/api/preview")
async def api_preview(request: Request):
    try:
        payload = {
            **request.session.get("step1", {}),
            "tabelas":  request.session.get("step2", []),
            "recursos": request.session.get("step3_recursos", []),
            "menus":    request.session.get("step3_menus", []),
            "menu_pai": request.session.get("menu_pai", 0),
        }
        definicao = ModuloDefinicao(**payload)
    except ValidationError as e:
        return JSONResponse({"error": str(e)}, status_code=422)
    gen     = ModuloSEIGenerator()
    arquivos = gen.renderizar_preview(definicao)
    return JSONResponse(arquivos)

@app.get("/api/projetos")
async def api_projetos():
    return listar_projetos()
