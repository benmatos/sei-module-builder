from __future__ import annotations
import sqlite3, json, os
from datetime import datetime
from contextlib import contextmanager

DB_PATH = os.getenv("DB_PATH", "sei_builder.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS projetos (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    slug         TEXT NOT NULL,
    nome         TEXT NOT NULL,
    definicao    TEXT NOT NULL,   -- JSON completo de ModuloDefinicao
    criado_em    TEXT NOT NULL,
    atualizado_em TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS geracoes (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    projeto_id   INTEGER NOT NULL REFERENCES projetos(id) ON DELETE CASCADE,
    versao       TEXT NOT NULL,
    arquivos     INTEGER NOT NULL DEFAULT 0,
    gerado_em    TEXT NOT NULL
);
"""

@contextmanager
def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

def init_db():
    with get_conn() as conn:
        conn.executescript(SCHEMA)

# ── Projetos ──────────────────────────────────────────────────────────────────

def salvar_projeto(definicao_dict: dict) -> int:
    slug = definicao_dict["slug"]
    nome = definicao_dict["nome"]
    agora = datetime.utcnow().isoformat()
    with get_conn() as conn:
        row = conn.execute("SELECT id FROM projetos WHERE slug = ?", (slug,)).fetchone()
        if row:
            conn.execute(
                "UPDATE projetos SET nome=?, definicao=?, atualizado_em=? WHERE id=?",
                (nome, json.dumps(definicao_dict, ensure_ascii=False), agora, row["id"])
            )
            return row["id"]
        cur = conn.execute(
            "INSERT INTO projetos (slug, nome, definicao, criado_em, atualizado_em) VALUES (?,?,?,?,?)",
            (slug, nome, json.dumps(definicao_dict, ensure_ascii=False), agora, agora)
        )
        return cur.lastrowid

def listar_projetos() -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            """SELECT p.id, p.slug, p.nome, p.atualizado_em,
                      COUNT(g.id) AS total_geracoes
               FROM projetos p
               LEFT JOIN geracoes g ON g.projeto_id = p.id
               GROUP BY p.id ORDER BY p.atualizado_em DESC"""
        ).fetchall()
        return [dict(r) for r in rows]

def carregar_projeto(projeto_id: int) -> dict | None:
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM projetos WHERE id = ?", (projeto_id,)).fetchone()
        if not row:
            return None
        projeto = dict(row)
        projeto["definicao"] = json.loads(projeto["definicao"])
        projeto["geracoes"] = [
            dict(g) for g in conn.execute(
                "SELECT * FROM geracoes WHERE projeto_id = ? ORDER BY gerado_em DESC",
                (projeto_id,)
            ).fetchall()
        ]
        return projeto

def excluir_projeto(projeto_id: int):
    with get_conn() as conn:
        conn.execute("DELETE FROM projetos WHERE id = ?", (projeto_id,))

def registrar_geracao(projeto_id: int, versao: str, arquivos: int):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO geracoes (projeto_id, versao, arquivos, gerado_em) VALUES (?,?,?,?)",
            (projeto_id, versao, arquivos, datetime.utcnow().isoformat())
        )
