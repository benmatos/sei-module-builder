#!/usr/bin/env python3
"""
deploy.py — Deploy local de módulos SEI gerados pelo SEI Module Builder.
Executa diretamente no filesystem do ambiente SEI de desenvolvimento.
Chamado automaticamente pelo main.py após geração, ou manualmente:

    python deploy.py --zip mod_manifestacao_v1.0.0.zip
    python deploy.py --rollback mod_manifestacao --tag 20260523_143201
    python deploy.py --rollback mod_manifestacao --list-backups
"""
from __future__ import annotations

import argparse
import configparser
import io
import os
import re
import shutil
import subprocess
import sys
import textwrap
import zipfile
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

# ── Resultado do deploy ───────────────────────────────────────────────────────

@dataclass
class DeployResult:
    slug: str
    versao: str
    sucesso: bool
    backup_tag: str = ""
    backup_path: str = ""
    etapas: list[dict] = field(default_factory=list)
    erros: list[str]   = field(default_factory=list)

    def adicionar_etapa(self, nome: str, ok: bool, detalhe: str = ""):
        self.etapas.append({"nome": nome, "ok": ok, "detalhe": detalhe})

    def to_dict(self) -> dict:
        return {
            "slug":        self.slug,
            "versao":      self.versao,
            "sucesso":     self.sucesso,
            "backup_tag":  self.backup_tag,
            "backup_path": self.backup_path,
            "etapas":      self.etapas,
            "erros":       self.erros,
        }


# ── Config ────────────────────────────────────────────────────────────────────

@dataclass
class DeployConfig:
    modulos_dir:     str
    configuracao_sei: str
    php_bin:         str = "/usr/bin/php"
    backup_dir:      str = "/var/backups/sei-modulos"
    auto_deploy:     bool = True
    verbose:         bool = True

    @classmethod
    def from_file(cls, path: str = "deploy.cfg") -> "DeployConfig | None":
        if not os.path.exists(path):
            return None
        cfg = configparser.ConfigParser()
        cfg.read(path, encoding="utf-8")
        s = cfg["sei"]
        return cls(
            modulos_dir      = s.get("modulos_dir", ""),
            configuracao_sei = s.get("configuracao_sei", ""),
            php_bin          = s.get("php_bin", "/usr/bin/php"),
            backup_dir       = s.get("backup_dir", "/var/backups/sei-modulos"),
            auto_deploy      = s.get("auto_deploy", "true").lower() == "true",
            verbose          = s.get("verbose", "true").lower() == "true",
        )

    def valido(self) -> tuple[bool, str]:
        if not self.modulos_dir:
            return False, "modulos_dir não configurado"
        if not self.configuracao_sei:
            return False, "configuracao_sei não configurado"
        if not os.path.isdir(self.modulos_dir):
            return False, f"modulos_dir não existe: {self.modulos_dir}"
        if not os.path.isfile(self.configuracao_sei):
            return False, f"ConfiguracaoSEI.php não encontrado: {self.configuracao_sei}"
        return True, ""


# ── DeployLocal ───────────────────────────────────────────────────────────────

class DeployLocal:
    def __init__(self, cfg: DeployConfig):
        self.cfg = cfg

    # ── Ponto de entrada principal ────────────────────────────────────────────

    def deploy_from_bytes(self, zip_bytes: bytes, slug: str, versao: str) -> DeployResult:
        """Chamado diretamente pelo main.py com os bytes do ZIP já em memória."""
        return self._executar(io.BytesIO(zip_bytes), slug, versao)

    def deploy_from_file(self, zip_path: str) -> DeployResult:
        """Chamado via CLI com caminho de arquivo ZIP."""
        slug, versao = self._parsear_nome_zip(zip_path)
        with open(zip_path, "rb") as f:
            return self._executar(io.BytesIO(f.read()), slug, versao)

    # ── Fluxo principal ───────────────────────────────────────────────────────

    def _executar(self, zip_buf: io.BytesIO, slug: str, versao: str) -> DeployResult:
        tag    = datetime.now().strftime("%Y%m%d_%H%M%S")
        result = DeployResult(slug=slug, versao=versao, sucesso=False, backup_tag=tag)
        cfg    = self.cfg

        try:
            # 1. Backup do módulo existente
            destino = Path(cfg.modulos_dir) / slug
            if destino.exists():
                bk_path = self._fazer_backup(slug, tag)
                result.backup_path = str(bk_path)
                result.adicionar_etapa("Backup", True, str(bk_path))
            else:
                result.adicionar_etapa("Backup", True, "Módulo novo — backup não necessário")

            # 2. Extrair ZIP
            self._extrair_zip(zip_buf, slug)
            result.adicionar_etapa("Extração do ZIP", True, str(destino))

            # 3. Patch ConfiguracaoSEI.php
            ns = self._inferir_namespace(zip_buf, slug)
            patched, msg = self._patch_configuracao_sei(slug, ns)
            result.adicionar_etapa("ConfiguracaoSEI.php", patched, msg)

            # 4. sei_atualizar.php
            ok_sei, out_sei = self._executar_php(slug, "sei_atualizar.php")
            result.adicionar_etapa("sei_atualizar.php", ok_sei, out_sei)
            if not ok_sei:
                result.erros.append(f"sei_atualizar.php falhou: {out_sei}")
                self._rollback(slug, tag, result)
                return result

            # 5. sip_atualizar.php
            ok_sip, out_sip = self._executar_php(slug, "sip_atualizar.php")
            result.adicionar_etapa("sip_atualizar.php", ok_sip, out_sip)
            if not ok_sip:
                result.erros.append(f"sip_atualizar.php falhou: {out_sip}")
                self._rollback(slug, tag, result)
                return result

            result.sucesso = True

        except Exception as e:
            result.erros.append(str(e))
            result.adicionar_etapa("Erro inesperado", False, str(e))
            self._rollback(slug, tag, result)

        return result

    # ── Backup e rollback ─────────────────────────────────────────────────────

    def _fazer_backup(self, slug: str, tag: str) -> Path:
        bk_dir = Path(self.cfg.backup_dir)
        bk_dir.mkdir(parents=True, exist_ok=True)
        destino = Path(self.cfg.modulos_dir) / slug
        bk_path = bk_dir / f"{slug}_{tag}"
        shutil.copytree(str(destino), str(bk_path))
        return bk_path

    def _rollback(self, slug: str, tag: str, result: DeployResult):
        bk_path = Path(self.cfg.backup_dir) / f"{slug}_{tag}"
        destino = Path(self.cfg.modulos_dir) / slug
        if bk_path.exists():
            if destino.exists():
                shutil.rmtree(str(destino))
            shutil.copytree(str(bk_path), str(destino))
            result.adicionar_etapa("Rollback automático", True, f"Restaurado de {bk_path}")
        else:
            result.adicionar_etapa("Rollback automático", False, "Backup não encontrado — módulo pode estar incompleto")

    # ── Extração ──────────────────────────────────────────────────────────────

    def _extrair_zip(self, zip_buf: io.BytesIO, slug: str):
        destino_base = Path(self.cfg.modulos_dir)
        destino_modulo = destino_base / slug
        if destino_modulo.exists():
            shutil.rmtree(str(destino_modulo))
        zip_buf.seek(0)
        with zipfile.ZipFile(zip_buf) as zf:
            zf.extractall(str(destino_base))

    # ── Patch ConfiguracaoSEI.php ─────────────────────────────────────────────

    def _patch_configuracao_sei(self, slug: str, ns: str) -> tuple[bool, str]:
        cfg_path = Path(self.cfg.configuracao_sei)
        conteudo = cfg_path.read_text(encoding="utf-8", errors="ignore")

        # Já registrado?
        if f"{ns}Integracao" in conteudo:
            return True, "Módulo já registrado — sem alteração"

        # Backup antes de modificar
        bk = cfg_path.with_suffix(f".php.bak.{datetime.now().strftime('%Y%m%d_%H%M%S')}")
        shutil.copy2(str(cfg_path), str(bk))

        linha_nova = (
            f"        InfraModulo::adicionarModulo("
            f"new {ns}Integracao(), "
            f"dirname(dirname(__FILE__)) . '/{slug}');"
        )

        # Inserir após o último adicionarModulo existente
        padrao = r"([ \t]*InfraModulo::adicionarModulo\([^;]+;)"
        ocorrencias = list(re.finditer(padrao, conteudo))
        if ocorrencias:
            ultima = ocorrencias[-1]
            pos = ultima.end()
            novo_conteudo = conteudo[:pos] + "\n" + linha_nova + conteudo[pos:]
            cfg_path.write_text(novo_conteudo, encoding="utf-8")
            return True, f"Linha inserida após registro existente (backup: {bk.name})"

        # Fallback: inserir antes do fechamento de inicializarObjInfraModulo
        m = re.search(r"(function inicializarObjInfraModulo[^{]*\{[^}]*)(\})", conteudo, re.DOTALL)
        if m:
            novo_conteudo = conteudo[:m.start(2)] + linha_nova + "\n    " + conteudo[m.start(2):]
            cfg_path.write_text(novo_conteudo, encoding="utf-8")
            return True, f"Linha inserida em inicializarObjInfraModulo (backup: {bk.name})"

        return False, "Ponto de inserção não encontrado — adicione manualmente"

    # ── PHP scripts ───────────────────────────────────────────────────────────

    def _executar_php(self, slug: str, script: str) -> tuple[bool, str]:
        caminho = Path(self.cfg.modulos_dir) / slug / "src" / "scripts" / script
        if not caminho.exists():
            return True, f"{script} não encontrado — ignorado"
        r = subprocess.run(
            [self.cfg.php_bin, str(caminho)],
            capture_output=True, text=True, timeout=120
        )
        saida = (r.stdout + r.stderr).strip()
        return r.returncode == 0, saida or "OK"

    # ── Helpers ───────────────────────────────────────────────────────────────

    @staticmethod
    def _parsear_nome_zip(zip_path: str) -> tuple[str, str]:
        nome = Path(zip_path).stem
        m = re.match(r"^(.+)_v(\d+\.\d+\.\d+)$", nome)
        if not m:
            print(f"Nome do ZIP fora do padrão {{slug}}_v{{versao}}.zip: {nome}")
            sys.exit(1)
        return m.group(1), m.group(2)

    @staticmethod
    def _inferir_namespace(zip_buf: io.BytesIO, slug: str) -> str:
        try:
            zip_buf.seek(0)
            with zipfile.ZipFile(zip_buf) as zf:
                for nome in zf.namelist():
                    if re.search(rf"{re.escape(slug)}/src/\w+Integracao\.php$", nome):
                        conteudo = zf.read(nome).decode("utf-8", errors="ignore")
                        m = re.search(r"class (\w+)Integracao", conteudo)
                        if m:
                            return m.group(1)
        except Exception:
            pass
        return "".join(p.capitalize() for p in slug.split("_"))

    # ── Backups CLI ───────────────────────────────────────────────────────────

    def listar_backups(self, slug: str) -> list[str]:
        bk_dir = Path(self.cfg.backup_dir)
        if not bk_dir.exists():
            return []
        return sorted(
            [d.name for d in bk_dir.iterdir() if d.is_dir() and d.name.startswith(f"{slug}_")],
            reverse=True
        )

    def rollback_manual(self, slug: str, tag: str) -> bool:
        bk_path = Path(self.cfg.backup_dir) / f"{slug}_{tag}"
        destino = Path(self.cfg.modulos_dir) / slug
        if not bk_path.exists():
            print(f"Backup não encontrado: {bk_path}")
            return False
        if destino.exists():
            shutil.rmtree(str(destino))
        shutil.copytree(str(bk_path), str(destino))
        return True


# ── Resultado em texto (para CLI) ─────────────────────────────────────────────

def imprimir_resultado(result: DeployResult):
    print()
    for etapa in result.etapas:
        icone = "✔" if etapa["ok"] else "✘"
        cor   = "\033[92m" if etapa["ok"] else "\033[91m"
        print(f"  {cor}{icone}\033[0m {etapa['nome']}", end="")
        if etapa["detalhe"]:
            print(f"  →  {etapa['detalhe']}", end="")
        print()
    print()
    if result.sucesso:
        print(f"\033[1m\033[92m  Deploy OK — {result.slug} v{result.versao}\033[0m")
        if result.backup_tag:
            print(f"  Rollback: python deploy.py --rollback {result.slug} --tag {result.backup_tag}")
    else:
        print(f"\033[1m\033[91m  Deploy FALHOU — {result.slug}\033[0m")
        for e in result.erros:
            print(f"  ✘ {e}")
    print()


# ── CLI ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Deploy local de módulos SEI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""
          Exemplos:
            python deploy.py --zip mod_manifestacao_v1.0.0.zip
            python deploy.py --rollback mod_manifestacao --list-backups
            python deploy.py --rollback mod_manifestacao --tag 20260523_143201
        """)
    )
    parser.add_argument("--zip",          help="Caminho para o ZIP gerado")
    parser.add_argument("--config",       default="deploy.cfg")
    parser.add_argument("--rollback",     metavar="SLUG")
    parser.add_argument("--tag",          metavar="TAG")
    parser.add_argument("--list-backups", action="store_true")
    args = parser.parse_args()

    if not args.zip and not args.rollback:
        parser.print_help()
        sys.exit(0)

    cfg = DeployConfig.from_file(args.config)
    if not cfg:
        print(f"deploy.cfg não encontrado. Copie deploy.cfg.example para deploy.cfg.")
        sys.exit(1)

    valido, motivo = cfg.valido()
    if not valido:
        print(f"Configuração inválida: {motivo}")
        sys.exit(1)

    deployer = DeployLocal(cfg)

    if args.rollback:
        if args.list_backups:
            backups = deployer.listar_backups(args.rollback)
            if backups:
                print(f"\nBackups para {args.rollback}:")
                for b in backups:
                    tag = b.replace(f"{args.rollback}_", "")
                    print(f"  {tag}")
            else:
                print("Nenhum backup encontrado.")
            return
        if not args.tag:
            print("Informe --tag. Use --list-backups para ver as opções.")
            sys.exit(1)
        ok = deployer.rollback_manual(args.rollback, args.tag)
        print("Rollback OK" if ok else "Rollback FALHOU")
        return

    result = deployer.deploy_from_file(args.zip)
    imprimir_resultado(result)
    sys.exit(0 if result.sucesso else 1)


if __name__ == "__main__":
    main()
