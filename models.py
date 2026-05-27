from __future__ import annotations
import re
from typing import List, Literal, Optional
from pydantic import BaseModel, field_validator, model_validator


class ColunaFK(BaseModel):
    tabela_slug: str
    coluna: str
    coluna_desc: Optional[str] = None


class ColunaDTO(BaseModel):
    nome: str
    tipo: Literal["int", "bigint", "varchar(100)", "varchar(255)", "text", "decimal(15,2)", "date", "datetime", "char(1)"]
    chave_primaria: bool = False
    obrigatorio: bool = True
    fk: Optional[ColunaFK] = None


class TabelaDTO(BaseModel):
    nome: str
    alias: str
    colunas: List[ColunaDTO]

    @field_validator("colunas")
    @classmethod
    def tabela_deve_ter_colunas(cls, v: List[ColunaDTO]) -> List[ColunaDTO]:
        if not v:
            raise ValueError("A tabela deve ter pelo menos uma coluna")
        return v

    @field_validator("nome")
    @classmethod
    def validar_nome_tabela(cls, v: str) -> str:
        if not re.match(r"^md_[a-z0-9_]+$", v):
            raise ValueError("O nome da tabela deve começar com 'md_' e conter apenas minúsculas, números e sublinhados")
        return v


class RecursoDTO(BaseModel):
    nome: str
    descricao: str
    caminho: Optional[str] = None # Tornar opcional, mas vamos preencher se possível


class MenuDTO(BaseModel):
    titulo: str
    link: str
    icone: str = "pasta"
    perfil_requerido: str = "Todos"


class ModuloDefinicao(BaseModel):
    nome: str
    slug: str
    namespace: str
    descricao: str
    versao: str
    sei_versao_min: str = "4.0.0"
    autor: str = "SEI Module Builder"
    tabelas: List[TabelaDTO] = []
    recursos: List[RecursoDTO] = []
    menus: List[MenuDTO] = []
    extras: List[str] = []
    menu_pai: int = 0

    @field_validator("slug")
    @classmethod
    def validar_slug(cls, v: str) -> str:
        if not re.match(r"^mod_[a-z0-9_]+$", v):
            raise ValueError("O slug do módulo deve começar com 'mod_' e conter apenas minúsculas, números e sublinhados")
        return v

    @model_validator(mode="after")
    def validar_fks_e_extras(self) -> "ModuloDefinicao":
        tabelas_validas = {t.nome for t in self.tabelas}
        tabelas_sei_nativas = {"documento", "procedimento", "unidade", "usuario", "protocolo"}

        # 1. Validar Dashboard (exige tabelas)
        if "dashboard" in self.extras and not self.tabelas:
            raise ValueError("O recurso de Dashboard exige a definição de pelo menos uma tabela para gerar os indicadores.")

        # 2. Garantir Recurso do Dashboard
        if "dashboard" in self.extras:
            existe = any(r.nome == "md_dashboard_visualizar" for r in self.recursos)
            if not existe:
                self.recursos.append(RecursoDTO(
                    nome="md_dashboard_visualizar",
                    descricao=f"Visualizar Dashboard do módulo {self.nome}"
                ))

        # 3. Validar FKs
        for tabela in self.tabelas:
            for col in tabela.colunas:
                if col.fk:
                    slug_ref = col.fk.tabela_slug
                    if slug_ref not in tabelas_validas and slug_ref not in tabelas_sei_nativas:
                        raise ValueError(
                            f"FK em {tabela.nome}.{col.nome} referencia tabela não declarada: {slug_ref}"
                        )
        return self
