import pytest
from pydantic import ValidationError
from models import ModuloDefinicao, TabelaDTO, ColunaDTO, RecursoDTO, MenuDTO

def test_modelo_valido():
    # Arrange
    dados = {
        "nome": "Módulo de Teste",
        "slug": "mod_teste",
        "namespace": "mod_teste",
        "descricao": "Teste unitário",
        "versao": "1.0.0",
        "sei_versao_min": "4.0.0",
        "autor": "Testador",
        "tabelas": [
            {
                "nome": "md_teste_tabela",
                "alias": "tst",
                "colunas": [
                    {
                        "nome": "id_teste",
                        "tipo": "int",
                        "chave_primaria": True,
                        "obrigatorio": True
                    },
                    {
                        "nome": "descricao",
                        "tipo": "varchar(255)",
                        "chave_primaria": False,
                        "obrigatorio": False
                    }
                ]
            }
        ],
        "recursos": [
            {"nome": "mod_teste_listar", "descricao": "Listar testes"}
        ],
        "menus": [
            {"titulo": "Testes", "link": "mod_teste_listar", "icone": "fa-list", "perfil_requerido": "Básico"}
        ],
        "extras": []
    }

    # Act
    modulo = ModuloDefinicao(**dados)

    # Assert
    assert modulo.slug == "mod_teste"
    assert len(modulo.tabelas) == 1
    assert modulo.tabelas[0].nome == "md_teste_tabela"

def test_modelo_invalido_slug_com_hifen():
    dados = {
        "nome": "Módulo de Teste",
        "slug": "mod-teste", # Ínvalido
        "namespace": "mod_teste",
        "descricao": "Teste unitário",
        "versao": "1.0.0",
        "sei_versao_min": "4.0.0",
        "autor": "Testador",
        "tabelas": [],
        "recursos": [],
        "menus": [],
        "extras": []
    }
    with pytest.raises(ValidationError):
        ModuloDefinicao(**dados)

def test_modelo_invalido_tabela_sem_md():
    dados = {
        "nome": "Módulo de Teste",
        "slug": "mod_teste",
        "namespace": "mod_teste",
        "descricao": "Teste unitário",
        "versao": "1.0.0",
        "sei_versao_min": "4.0.0",
        "autor": "Testador",
        "tabelas": [
            {
                "nome": "teste_tabela", # Invalido, tem que começar com md_
                "alias": "tst",
                "colunas": []
            }
        ],
        "recursos": [],
        "menus": [],
        "extras": []
    }
    with pytest.raises(ValidationError):
        ModuloDefinicao(**dados)

def test_modelo_invalido_tabela_sem_colunas():
    dados = {
        "nome": "Módulo de Teste",
        "slug": "mod_teste",
        "namespace": "mod_teste",
        "descricao": "Teste unitário",
        "versao": "1.0.0",
        "sei_versao_min": "4.0.0",
        "autor": "Testador",
        "tabelas": [
            {
                "nome": "md_tabela_vazia",
                "alias": "vaz",
                "colunas": [] # Inválido
            }
        ],
        "recursos": [],
        "menus": [],
        "extras": []
    }
    with pytest.raises(ValidationError) as excinfo:
        ModuloDefinicao(**dados)
    assert "A tabela deve ter pelo menos uma coluna" in str(excinfo.value)
