from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

def test_api_validar_definicao_valida():
    dados = {
        "nome": "Módulo de Teste",
        "slug": "md_teste",
        "namespace": "MdTeste",
        "descricao": "Teste unitário",
        "versao": "1.0.0",
        "sei_versao_min": "4.0.0",
        "autor": "Testador",
        "tabelas": [],
        "recursos": [],
        "menus": [],
        "extras": []
    }
    response = client.post("/api/validar", json=dados)
    assert response.status_code == 200
    assert response.json()["valid"] == True

def test_api_validar_definicao_invalida():
    dados = {
        "nome": "Módulo de Teste",
        "slug": "md-teste", # invalido
        "namespace": "MdTeste",
        "descricao": "Teste unitário",
        "versao": "1.0.0",
        "sei_versao_min": "4.0.0",
        "autor": "Testador",
        "tabelas": [],
        "recursos": [],
        "menus": [],
        "extras": []
    }
    response = client.post("/api/validar", json=dados)
    assert response.status_code == 422 # FastAPI Pydantic Validation Error

def test_api_gerar_modulo():
    dados = {
        "nome": "Módulo de Teste",
        "slug": "md_teste",
        "namespace": "MdTeste",
        "descricao": "Teste unitário",
        "versao": "1.0.0",
        "sei_versao_min": "4.0.0",
        "autor": "Testador",
        "tabelas": [],
        "recursos": [],
        "menus": [],
        "extras": []
    }
    response = client.post("/api/gerar", json=dados)
    assert response.status_code == 200
    assert response.headers["content-type"] in ["application/zip", "application/x-zip-compressed"]
    assert "attachment; filename=" in response.headers["content-disposition"]
