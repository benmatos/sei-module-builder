from __future__ import annotations
import json, os, io
from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware
from pydantic import ValidationError
from models import ModuloDefinicao
from generator import ModuloSEIGenerator

SECRET_KEY = os.getenv("SECRET_KEY", "dev-insecure-key-change-in-production")
SESSION_TTL = int(os.getenv("SESSION_TTL_SECONDS", "7200"))
DEBUG = os.getenv("DEBUG", "false").lower() == "true"

app = FastAPI(title="SEI Module Builder", debug=DEBUG)
app.add_middleware(SessionMiddleware, secret_key=SECRET_KEY, max_age=SESSION_TTL)
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

def flash(request, msg, cat="error"):
    request.session.setdefault("_flashes", []).append({"msg": msg, "cat": cat})

def get_flashes(request):
    return request.session.pop("_flashes", [])

@app.get("/", response_class=RedirectResponse)
async def root(): return RedirectResponse("/wizard/1")

@app.get("/wizard/1", response_class=HTMLResponse)
async def w1_get(request: Request):
    return templates.TemplateResponse("wizard/step1.html", {"request": request, "flashes": get_flashes(request), "data": request.session.get("step1", {})})

@app.post("/wizard/1", response_class=RedirectResponse)
async def w1_post(request: Request, nome: str = Form(...), slug: str = Form(...), namespace: str = Form(...), descricao: str = Form(...), versao: str = Form(...), sei_versao_min: str = Form(...), autor: str = Form(...)):
    request.session["step1"] = dict(nome=nome, slug=slug, namespace=namespace, descricao=descricao, versao=versao, sei_versao_min=sei_versao_min, autor=autor)
    return RedirectResponse("/wizard/2", status_code=303)

@app.get("/wizard/2", response_class=HTMLResponse)
async def w2_get(request: Request):
    return templates.TemplateResponse("wizard/step2.html", {"request": request, "flashes": get_flashes(request), "tabelas_json": json.dumps(request.session.get("step2", []))})

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
    return templates.TemplateResponse("wizard/step3.html", {"request": request, "flashes": get_flashes(request), "recursos_json": json.dumps(request.session.get("step3_recursos", [])), "menus_json": json.dumps(request.session.get("step3_menus", []))})

@app.post("/wizard/3", response_class=RedirectResponse)
async def w3_post(request: Request, recursos_json: str = Form(...), menus_json: str = Form(...)):
    try:
        request.session["step3_recursos"] = json.loads(recursos_json)
        request.session["step3_menus"] = json.loads(menus_json)
    except Exception as e:
        flash(request, f"Erro: {e}")
        return RedirectResponse("/wizard/3", status_code=303)
    return RedirectResponse("/wizard/4", status_code=303)

@app.get("/wizard/4", response_class=HTMLResponse)
async def w4_get(request: Request):
    return templates.TemplateResponse("wizard/step4.html", {"request": request, "flashes": get_flashes(request), "step1": request.session.get("step1", {}), "tabelas": request.session.get("step2", []), "recursos": request.session.get("step3_recursos", []), "menus": request.session.get("step3_menus", [])})

@app.post("/gerar")
async def gerar_wizard(request: Request):
    try:
        payload = {**request.session.get("step1", {}), "tabelas": request.session.get("step2", []), "recursos": request.session.get("step3_recursos", []), "menus": request.session.get("step3_menus", [])}
        definicao = ModuloDefinicao(**payload)
    except ValidationError as e:
        flash(request, f"Dados invalidos: {e.error_count()} erro(s). Revise os passos anteriores.")
        return RedirectResponse("/wizard/4", status_code=303)
    zip_bytes = ModuloSEIGenerator().gerar_modulo(definicao)
    for k in ("step1", "step2", "step3_recursos", "step3_menus"):
        request.session.pop(k, None)
    filename = f"{definicao.slug}_v{definicao.versao}.zip"
    return StreamingResponse(io.BytesIO(zip_bytes), media_type="application/zip", headers={"Content-Disposition": f"attachment; filename={filename}"})

@app.post("/api/gerar")
async def api_gerar(definicao: ModuloDefinicao):
    zip_bytes = ModuloSEIGenerator().gerar_modulo(definicao)
    filename = f"{definicao.slug}_v{definicao.versao}.zip"
    return StreamingResponse(io.BytesIO(zip_bytes), media_type="application/zip", headers={"Content-Disposition": f"attachment; filename={filename}"})

@app.post("/api/validar")
async def api_validar(definicao: ModuloDefinicao):
    return {"valid": True, "slug": definicao.slug, "tabelas": len(definicao.tabelas)}
