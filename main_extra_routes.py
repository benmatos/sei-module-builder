# Rotas adicionais para export/import JSON — adicionar ao main.py existente
# Inserir antes do bloco "# ── API ────"

import json as _json
from fastapi import UploadFile, File
from fastapi.responses import Response


# ── Export/Import JSON ────────────────────────────────────────────────────────

@app.get("/projetos/{projeto_id}/exportar")
async def projeto_exportar(projeto_id: int):
    """Retorna o ModuloDefinicao do projeto como download de arquivo JSON."""
    projeto = carregar_projeto(projeto_id)
    if not projeto:
        return JSONResponse({"erro": "Projeto não encontrado"}, status_code=404)
    filename = f"{projeto['slug']}_v{projeto['definicao']['versao']}.json"
    content  = _json.dumps(projeto["definicao"], ensure_ascii=False, indent=2)
    return Response(
        content=content,
        media_type="application/json",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


@app.get("/importar", response_class=HTMLResponse)
async def importar_get(request: Request):
    return templates.TemplateResponse("projetos/importar.html", {
        "request": request,
        "flashes": get_flashes(request),
    })


@app.post("/importar", response_class=RedirectResponse)
async def importar_post(request: Request, json_file: UploadFile = File(...)):
    """Importa ModuloDefinicao a partir de arquivo JSON e carrega no wizard."""
    try:
        conteudo = await json_file.read()
        dados    = _json.loads(conteudo)
        definicao = ModuloDefinicao(**dados)
    except Exception as e:
        flash(request, f"Arquivo inválido: {e}")
        return RedirectResponse("/importar", status_code=303)
    return _carregar_definicao_na_sessao(request, definicao)


@app.post("/importar/texto", response_class=RedirectResponse)
async def importar_texto(request: Request, json_texto: str = Form(...)):
    """Importa ModuloDefinicao a partir de JSON colado na textarea."""
    try:
        dados     = _json.loads(json_texto)
        definicao = ModuloDefinicao(**dados)
    except Exception as e:
        flash(request, f"JSON inválido: {e}")
        return RedirectResponse("/importar", status_code=303)
    return _carregar_definicao_na_sessao(request, definicao)


def _carregar_definicao_na_sessao(request: Request, definicao: ModuloDefinicao):
    """Carrega um ModuloDefinicao validado na sessão do wizard."""
    d = definicao.model_dump()
    request.session["step1"] = {
        k: d[k] for k in ("nome", "slug", "namespace", "descricao",
                           "versao", "sei_versao_min", "autor", "extras")
    }
    request.session["step2"]          = [t.model_dump() for t in definicao.tabelas]
    request.session["step3_recursos"] = [r.model_dump() for r in definicao.recursos]
    request.session["step3_menus"]    = [m.model_dump() for m in definicao.menus]
    flash(request, f"Projeto '{definicao.nome}' importado com sucesso.", "success")
    return RedirectResponse("/wizard/4", status_code=303)
