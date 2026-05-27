import pytest
from pydantic import ValidationError
from models import ModuloDefinicao, TabelaDTO, ColunaDTO, RecursoDTO, MenuDTO

def test_modelo_valido():
    # Arrange
    dados = {
        "nome": "Módulo de Teste",
        "slug": "md_teste",
        "namespace": "MdTeste",
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
        "recursos": [],
        "menus": [],
        "extras": []
    }

    # Act
    modulo = ModuloDefinicao(**dados)

    # Assert
    assert modulo.slug == "md_teste"
    assert modulo.namespace == "MdTeste"
    assert len(modulo.tabelas) == 1
    # Verifica auto-geração de recursos
    nomes_recursos = [r.nome for r in modulo.recursos]
    assert "md_teste_tabela_listar" in nomes_recursos
    assert "md_teste_tabela_cadastrar" in nomes_recursos

def test_validacao_prefixos_colunas():
    # PK/FK deve ser id_
    with pytest.raises(ValidationError) as excinfo:
        ColunaDTO(nome="teste", tipo="int", chave_primaria=True)
    assert "deve começar com 'id_'" in str(excinfo.value)

    # char(1) deve ser sin_ ou sta_
    with pytest.raises(ValidationError) as excinfo:
        ColunaDTO(nome="ativo", tipo="char(1)")
    assert "deve começar com 'sin_' ou 'sta_'" in str(excinfo.value)

    # date deve ser dta_
    with pytest.raises(ValidationError) as excinfo:
        ColunaDTO(nome="vencimento", tipo="date")
    assert "deve começar com 'dta_'" in str(excinfo.value)

    # datetime deve ser dth_
    with pytest.raises(ValidationError) as excinfo:
        ColunaDTO(nome="registro", tipo="datetime")
    assert "deve começar com 'dth_'" in str(excinfo.value)

    # decimal deve ser din_
    with pytest.raises(ValidationError) as excinfo:
        ColunaDTO(nome="valor", tipo="decimal(15,2)")
    assert "deve começar com 'din_'" in str(excinfo.value)

def test_modelo_valido_sem_tabelas():
    # Módulos puramente de interface ou dashboard podem não ter tabelas
    dados = {
        "nome": "Módulo de Interface",
        "slug": "md_interface",
        "namespace": "MdInterface",
        "descricao": "Apenas interface",
        "versao": "1.0.0",
        "tabelas": []
    }
    modulo = ModuloDefinicao(**dados)
    assert modulo.slug == "md_interface"
    assert len(modulo.tabelas) == 0

def test_modelo_invalido_namespace_sem_md():
    dados = {
        "nome": "Módulo de Teste",
        "slug": "md_teste",
        "namespace": "Teste", # Invalido, deve começar com Md
        "descricao": "Teste unitário",
        "versao": "1.0.0",
        "tabelas": []
    }
    with pytest.raises(ValidationError) as excinfo:
        ModuloDefinicao(**dados)
    assert "O namespace do módulo deve começar com 'Md'" in str(excinfo.value)

def test_modelo_invalido_slug_com_hifen():
    dados = {
        "nome": "Módulo de Teste",
        "slug": "md-teste", # Ínvalido
        "namespace": "MdTeste",
        "descricao": "Teste unitário",
        "versao": "1.0.0",
        "tabelas": []
    }
    with pytest.raises(ValidationError):
        ModuloDefinicao(**dados)

def test_modelo_invalido_tabela_sem_md():
    dados = {
        "nome": "Módulo de Teste",
        "slug": "md_teste",
        "namespace": "MdTeste",
        "descricao": "Teste unitário",
        "versao": "1.0.0",
        "tabelas": [
            {
                "nome": "teste_tabela", # Invalido, tem que começar com md_
                "alias": "tst",
                "colunas": [{"nome": "id_tst", "tipo": "int", "chave_primaria": True}]
            }
        ]
    }
    with pytest.raises(ValidationError):
        ModuloDefinicao(**dados)

def test_modelo_invalido_tabela_sem_colunas():
    dados = {
        "nome": "Módulo de Teste",
        "slug": "md_teste",
        "namespace": "MdTeste",
        "descricao": "Teste unitário",
        "versao": "1.0.0",
        "tabelas": [
            {
                "nome": "md_tabela_vazia",
                "alias": "vaz",
                "colunas": [] # Inválido
            }
        ]
    }
    with pytest.raises(ValidationError) as excinfo:
        ModuloDefinicao(**dados)
    assert "A tabela deve ter pelo menos uma coluna" in str(excinfo.value)
