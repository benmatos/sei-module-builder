from __future__ import annotations
import re
from typing import List, Optional, Literal
from pydantic import BaseModel, field_validator, model_validator


class ColunaFK(BaseModel):
    tabela_slug: str
    coluna: str
    coluna_pai: str
    colunas_exibir: List[str] = []


class ColunaDTO(BaseModel):
    nome: str
    tipo: Literal[
        "varchar(100)", "varchar(255)", "text",
        "int", "bigint", "decimal(15,2)",
        "date", "datetime", "char(1)"
    ]
    obrigatorio: bool = True
    chave_primaria: bool = False
    fk: Optional[ColunaFK] = None


class TabelaDTO(BaseModel):
    nome: str
    alias: str
    colunas: List[ColunaDTO]

    @field_validator("nome")
    @classmethod
    def nome_deve_comecar_com_md(cls, v: str) -> str:
        if not v.startswith("md_"):
            raise ValueError(f"Nome de tabela deve comecar com md_: {v}")
        return v


class RecursoDTO(BaseModel):
    nome: str
    descricao: str


class MenuDTO(BaseModel):
    titulo: str
    link: str
    icone: str
    perfil_requerido: str


class ModuloDefinicao(BaseModel):
    nome: str
    slug: str
    namespace: str
    descricao: str
    versao: str
    sei_versao_min: str
    autor: str
    tabelas: List[TabelaDTO]
    recursos: List[RecursoDTO]
    menus: List[MenuDTO]

    @field_validator("slug")
    @classmethod
    def slug_valido(cls, v: str) -> str:
        if not re.match(r"^[a-z][a-z0-9_]+$", v):
            raise ValueError("Slug deve ser alfanumerico com underscores")
        return v

    @field_validator("versao", "sei_versao_min")
    @classmethod
    def versao_semver(cls, v: str) -> str:
        if not re.match(r"^[0-9]+[.][0-9]+[.][0-9]+$", v):
            raise ValueError(f"Versao deve seguir semver (ex: 1.0.0): {v}")
        return v

    @model_validator(mode="after")
    def validar_aliases_unicos(self) -> "ModuloDefinicao":
        aliases = [t.alias for t in self.tabelas]
        if len(aliases) != len(set(aliases)):
            raise ValueError("Aliases de tabela devem ser unicos")
        return self

    @model_validator(mode="after")
    def validar_fks(self) -> "ModuloDefinicao":
        slugs_conhecidos = {t.nome for t in self.tabelas}
        tabelas_sei_nativas = {"usuario", "unidade", "tipo_processo", "serie", "contato"}
        for tabela in self.tabelas:
            for col in tabela.colunas:
                if col.fk:
                    slug_ref = col.fk.tabela_slug
                    if slug_ref.startswith("sei:"):
                        continue
                    if slug_ref not in slugs_conhecidos and slug_ref not in tabelas_sei_nativas:
                        raise ValueError(
                            f"FK em {tabela.nome}.{col.nome} referencia tabela nao declarada: {slug_ref}"
                        )
        return self
