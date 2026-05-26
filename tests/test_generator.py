import zipfile
import io
import pytest
from models import ModuloDefinicao
from generator import ModuloSEIGenerator

@pytest.fixture
def definicao_valida():
    return ModuloDefinicao(
        nome="Módulo de Teste",
        slug="mod_teste",
        namespace="mod_teste",
        descricao="Teste unitário",
        versao="1.0.0",
        sei_versao_min="4.0.0",
        autor="Testador",
        tabelas=[
            {
                "nome": "md_teste_tabela",
                "alias": "tst",
                "colunas": [
                    {
                        "nome": "id_teste",
                        "tipo": "int",
                        "chave_primaria": True,
                        "obrigatorio": True
                    }
                ]
            }
        ],
        recursos=[],
        menus=[],
        extras=[]
    )

def test_gerar_modulo_zip_estrutura(definicao_valida):
    generator = ModuloSEIGenerator()
    zip_bytes = generator.gerar_modulo(definicao_valida)
    
    assert isinstance(zip_bytes, bytes)
    
    with zipfile.ZipFile(io.BytesIO(zip_bytes), "r") as zf:
        nomes_arquivos = zf.namelist()
        
        # Estrutura básica esperada na raiz do modulo (procedural)
        assert "mod_teste/ModTesteIntegracao.php" in nomes_arquivos
        assert "mod_teste/README.md" in nomes_arquivos
        
        # Camada de banco de dados (BD) e RN
        assert "mod_teste/bd/ModTesteMdTesteTabelaBD.php" in nomes_arquivos
        assert "mod_teste/rn/ModTesteMdTesteTabelaRN.php" in nomes_arquivos
        assert "mod_teste/dto/ModTesteMdTesteTabelaDTO.php" in nomes_arquivos
        
        # Telas e Javascript
        assert "mod_teste/mod_teste_md_teste_tabela_listar.php" in nomes_arquivos
        assert "mod_teste/mod_teste_md_teste_tabela_cadastrar.php" in nomes_arquivos
        assert "mod_teste/js/mod_teste.js" in nomes_arquivos
        
        # Scripts
        assert "mod_teste/scripts/sei_atualizar.php" in nomes_arquivos
        assert "mod_teste/scripts/sip_atualizar.php" in nomes_arquivos

def test_renderizar_preview(definicao_valida):
    generator = ModuloSEIGenerator()
    preview = generator.renderizar_preview(definicao_valida)
    
    assert "ModTesteIntegracao.php" in preview
    assert "ModTesteMdTesteTabelaDTO.php" in preview
    assert "ModTesteMdTesteTabelaRN.php" in preview
    assert "ModTesteMdTesteTabelaBD.php" in preview
    assert "mod_teste_md_teste_tabela_listar.php" in preview
