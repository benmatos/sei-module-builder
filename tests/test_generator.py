import zipfile
import io
import pytest
from models import ModuloDefinicao
from generator import ModuloSEIGenerator

@pytest.fixture
def definicao_valida():
    return ModuloDefinicao(
        nome="Módulo de Teste",
        slug="md_teste",
        namespace="MdTeste",
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
        
        # Estrutura básica esperada na raiz do modulo
        assert "md_teste/MdTesteIntegracao.php" in nomes_arquivos
        assert "md_teste/README.md" in nomes_arquivos
        
        # Pastas obrigatórias (vazias) exigidas pelo GEMINI.md
        assert "md_teste/int/" in nomes_arquivos
        assert "md_teste/css/" in nomes_arquivos
        assert "md_teste/imagens/" in nomes_arquivos
        assert "md_teste/imagens/menu/" in nomes_arquivos
        assert "md_teste/ws/" in nomes_arquivos
        
        # Camada de banco de dados (BD) e RN
        assert "md_teste/bd/MdTesteMdTesteTabelaBD.php" in nomes_arquivos
        assert "md_teste/rn/MdTesteMdTesteTabelaRN.php" in nomes_arquivos
        assert "md_teste/dto/MdTesteMdTesteTabelaDTO.php" in nomes_arquivos
        
        # Telas e Javascript
        # Note que agora o nome do arquivo da tela é apenas o nome da tabela + ação
        assert "md_teste/md_teste_tabela_listar.php" in nomes_arquivos
        assert "md_teste/md_teste_tabela_cadastrar.php" in nomes_arquivos
        assert "md_teste/js/md_teste.js" in nomes_arquivos
        
        # Scripts
        assert "md_teste/scripts/sei_atualizar.php" in nomes_arquivos
        assert "md_teste/scripts/sip_atualizar.php" in nomes_arquivos

def test_renderizar_preview(definicao_valida):
    generator = ModuloSEIGenerator()
    preview = generator.renderizar_preview(definicao_valida)
    
    assert "MdTesteIntegracao.php" in preview
    assert "MdTesteMdTesteTabelaDTO.php" in preview
    assert "MdTesteMdTesteTabelaRN.php" in preview
    assert "MdTesteMdTesteTabelaBD.php" in preview
    assert "md_teste_tabela_listar.php" in preview
