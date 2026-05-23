#!/usr/bin/env python3
"""
deploy.py — Script de deploy de módulos SEI gerados pelo SEI Module Builder.

Uso:
    python deploy.py --zip mod_manifestacao_v1.0.0.zip
    python deploy.py --zip mod_manifestacao_v1.0.0.zip --dry-run
    python deploy.py --zip mod_manifestacao_v1.0.0.zip --no-db
    python deploy.py --rollback mod_manifestacao --list-backups
    python deploy.py --rollback mod_manifestacao --tag 20260523_143201

Requerimentos no ambiente local:
    - Python 3.11+
    - ssh e scp disponíveis no PATH (OpenSSH)
    - Acesso SSH ao servidor SEI com permissão de escrita em modulos_dir

Requerimentos no servidor SEI:
    - PHP CLI instalado
    - tar, unzip disponíveis
"""
from __future__ import annotations

import argparse
import configparser
import os
import re
import subprocess
import sys
import textwrap
import zipfile
from datetime import datetime
from pathlib import Path

# ── Cores para terminal ───────────────────────────────────────────────────────
GREEN  = "\033[92m"
YELLOW = "\033[93m"
RED    = "\033[91m"
BOLD   = "\033[1m"
RESET  = "\033[0m"

def ok(msg):    print(f"{GREEN}  ✔ {msg}{RESET}")
def warn(msg):  print(f"{YELLOW}  ⚠ {msg}{RESET}")
def err(msg):   print(f"{RED}  ✘ {msg}{RESET}")
def info(msg):  print(f"  → {msg}")
def title(msg): print(f"\n{BOLD}{msg}{RESET}")

# ── Config ────────────────────────────────────────────────────────────────────

class DeployConfig:
    def __init__(self, cfg_path: str = "deploy.cfg"):
        if not os.path.exists(cfg_path):
            err(f"Arquivo de configuração não encontrado: {cfg_path}")
            err("Copie deploy.cfg.example para deploy.cfg e ajuste os valores.")
            sys.exit(1)
        cfg = configparser.ConfigParser()
        cfg.read(cfg_path, encoding="utf-8")
        s = cfg["sei"]
        self.host         = s.get("host")
        self.port         = int(s.get("port", "22"))
        self.user         = s.get("user", "deploy")
        self.ssh_key      = os.path.expanduser(s.get("ssh_key", ""))
        self.modulos_dir  = s.get("modulos_dir").rstrip("/")
        self.config_sei   = s.get("configuracao_sei")
        self.php_bin      = s.get("php_bin", "/usr/bin/php")
        self.backup_dir   = s.get("backup_dir", "/var/backups/sei-modulos")
        self.web_user     = s.get("web_user",  "apache")
        self.web_group    = s.get("web_group", "apache")

    def ssh_opts(self) -> list[str]:
        opts = ["-p", str(self.port), "-o", "StrictHostKeyChecking=accept-new",
                "-o", "ConnectTimeout=10", "-o", "BatchMode=yes"]
        if self.ssh_key:
            opts += ["-i", self.ssh_key]
        return opts

    def ssh_target(self) -> str:
        return f"{self.user}@{self.host}"


# ── SSH/SCP helpers ───────────────────────────────────────────────────────────

def ssh_run(cfg: DeployConfig, cmd: str, capture: bool = True, check: bool = True) -> subprocess.CompletedProcess:
    full = ["ssh"] + cfg.ssh_opts() + [cfg.ssh_target(), cmd]
    return subprocess.run(full, capture_output=capture, text=True, check=check)

def scp_upload(cfg: DeployConfig, local: str, remote: str):
    cmd = ["scp"] + cfg.ssh_opts() + [local, f"{cfg.ssh_target()}:{remote}"]
    subprocess.run(cmd, check=True)

def ssh_read(cfg: DeployConfig, cmd: str) -> str:
    return ssh_run(cfg, cmd, capture=True).stdout.strip()


# ── Validações locais ─────────────────────────────────────────────────────────

def validar_zip(zip_path: str) -> tuple[str, str]:
    """Retorna (slug, versao) extraídos do nome do ZIP."""
    nome = Path(zip_path).stem  # ex: mod_manifestacao_v1.0.0
    m = re.match(r"^(.+)_v(\d+\.\d+\.\d+)$", nome)
    if not m:
        err(f"Nome do ZIP deve seguir o padrão {{slug}}_v{{versao}}.zip: {nome}")
        sys.exit(1)
    return m.group(1), m.group(2)

def verificar_ssh(cfg: DeployConfig) -> bool:
    try:
        r = ssh_run(cfg, "echo OK", check=False)
        return r.returncode == 0 and r.stdout.strip() == "OK"
    except Exception:
        return False


# ── Backup ────────────────────────────────────────────────────────────────────

def fazer_backup(cfg: DeployConfig, slug: str, tag: str) -> str | None:
    """Cria tarball do módulo no servidor. Retorna caminho do backup ou None."""
    modulo_path = f"{cfg.modulos_dir}/{slug}"
    backup_path = f"{cfg.backup_dir}/{slug}_{tag}.tar.gz"
    r = ssh_run(cfg, f"test -d {modulo_path} && echo exists", check=False)
    if "exists" not in r.stdout:
        info("Módulo não existe ainda — backup não necessário.")
        return None
    ssh_run(cfg, f"mkdir -p {cfg.backup_dir}")
    ssh_run(cfg, f"tar -czf {backup_path} -C {cfg.modulos_dir} {slug}")
    ok(f"Backup criado: {backup_path}")
    return backup_path

def restaurar_backup(cfg: DeployConfig, slug: str, tag: str):
    backup_path = f"{cfg.backup_dir}/{slug}_{tag}.tar.gz"
    r = ssh_run(cfg, f"test -f {backup_path} && echo exists", check=False)
    if "exists" not in r.stdout:
        err(f"Backup não encontrado: {backup_path}")
        sys.exit(1)
    ssh_run(cfg, f"rm -rf {cfg.modulos_dir}/{slug}")
    ssh_run(cfg, f"tar -xzf {backup_path} -C {cfg.modulos_dir}")
    ok(f"Módulo restaurado a partir de {backup_path}")

def listar_backups(cfg: DeployConfig, slug: str):
    r = ssh_run(cfg, f"ls {cfg.backup_dir}/{slug}_*.tar.gz 2>/dev/null || echo NENHUM", check=False)
    linhas = r.stdout.strip().splitlines()
    if linhas == ["NENHUM"] or not linhas:
        warn(f"Nenhum backup encontrado para {slug}")
        return
    print(f"\nBackups disponíveis para {BOLD}{slug}{RESET}:")
    for linha in linhas:
        nome = Path(linha).stem
        tag  = nome.replace(f"{slug}_", "")
        print(f"  {tag}   ({linha})")


# ── Patch ConfiguracaoSEI.php ─────────────────────────────────────────────────

def patch_configuracao_sei(cfg: DeployConfig, slug: str, namespace_pascal: str, dry_run: bool):
    """
    Insere o registro do módulo em ConfiguracaoSEI.php se ainda não estiver presente.
    Estratégia: localiza o último InfraModulo::adicionarModulo() existente e insere após.
    Se não houver nenhum, insere antes do último '}' do método inicializarObjInfraModulo.
    Cria backup do arquivo antes de modificar.
    """
    linha_nova = (
        f"        InfraModulo::adicionarModulo("
        f"new {namespace_pascal}Integracao(), "
        f"dirname(dirname(__FILE__)) . '/{slug}');"
    )

    # Verificar se já está registrado
    r = ssh_run(cfg, f"grep -c '{namespace_pascal}Integracao' {cfg.config_sei} 2>/dev/null || echo 0", check=False)
    if r.stdout.strip() != "0":
        ok("Módulo já registrado em ConfiguracaoSEI.php — nenhuma alteração necessária.")
        return

    if dry_run:
        info(f"[DRY-RUN] Linha a inserir em ConfiguracaoSEI.php:")
        info(f"  {linha_nova}")
        return

    # Backup do ConfiguracaoSEI.php
    bk = f"{cfg.config_sei}.bak.{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    ssh_run(cfg, f"cp {cfg.config_sei} {bk}")
    ok(f"Backup do ConfiguracaoSEI.php: {bk}")

    # Inserção usando awk: após o último adicionarModulo existente
    awk_script = (
        "awk '/"
        "InfraModulo::adicionarModulo"
        "/{last=NR} "
        "NR==last{print; print linha; next} "
        "{print}' "
        f"linha=\'{linha_nova}\' "
        f"{cfg.config_sei} > /tmp/_cfg_sei_tmp.php "
        f"&& mv /tmp/_cfg_sei_tmp.php {cfg.config_sei}"
    )
    # Fallback: se não houver nenhum adicionarModulo, inserir antes do fechamento do método
    r2 = ssh_run(cfg, f"grep -c 'adicionarModulo' {cfg.config_sei} 2>/dev/null || echo 0", check=False)
    if r2.stdout.strip() == "0":
        warn("Nenhum adicionarModulo encontrado. Inserção manual necessária em ConfiguracaoSEI.php.")
        warn(f"Adicione manualmente dentro de inicializarObjInfraModulo():")
        warn(f"  {linha_nova}")
        return

    ssh_run(cfg, awk_script)
    ok("ConfiguracaoSEI.php atualizado com sucesso.")


# ── Scripts de banco ──────────────────────────────────────────────────────────

def executar_script_php(cfg: DeployConfig, slug: str, script: str, dry_run: bool) -> bool:
    caminho = f"{cfg.modulos_dir}/{slug}/src/scripts/{script}"
    r_exists = ssh_run(cfg, f"test -f {caminho} && echo exists", check=False)
    if "exists" not in r_exists.stdout:
        warn(f"Script não encontrado: {caminho} — ignorando.")
        return True
    if dry_run:
        info(f"[DRY-RUN] Executaria: {cfg.php_bin} {caminho}")
        return True
    info(f"Executando {script}...")
    r = ssh_run(cfg, f"{cfg.php_bin} {caminho} 2>&1", check=False)
    saida = r.stdout.strip()
    if saida:
        for linha in saida.splitlines():
            info(f"  PHP: {linha}")
    if r.returncode != 0:
        err(f"{script} retornou código {r.returncode}")
        return False
    ok(f"{script} executado com sucesso.")
    return True


# ── Verificação pós-deploy ────────────────────────────────────────────────────

def verificar_deploy(cfg: DeployConfig, slug: str, namespace_pascal: str) -> bool:
    arquivos_criticos = [
        f"{cfg.modulos_dir}/{slug}/src/{namespace_pascal}Integracao.php",
        f"{cfg.modulos_dir}/{slug}/src/scripts/sei_atualizar.php",
    ]
    tudo_ok = True
    for arq in arquivos_criticos:
        r = ssh_run(cfg, f"test -f {arq} && echo exists", check=False)
        if "exists" not in r.stdout:
            err(f"Arquivo esperado não encontrado: {arq}")
            tudo_ok = False

    # php -l no arquivo de integração
    integracao = f"{cfg.modulos_dir}/{slug}/src/{namespace_pascal}Integracao.php"
    r_lint = ssh_run(cfg, f"{cfg.php_bin} -l {integracao} 2>&1", check=False)
    if "No syntax errors" not in r_lint.stdout:
        err(f"Erro de sintaxe PHP em {namespace_pascal}Integracao.php:")
        for l in r_lint.stdout.splitlines():
            err(f"  {l}")
        tudo_ok = False
    else:
        ok("Verificação de sintaxe PHP: OK")

    return tudo_ok


# ── Permissões ────────────────────────────────────────────────────────────────

def ajustar_permissoes(cfg: DeployConfig, slug: str, dry_run: bool):
    cmd = (f"chown -R {cfg.web_user}:{cfg.web_group} {cfg.modulos_dir}/{slug} && "
           f"find {cfg.modulos_dir}/{slug} -type d -exec chmod 755 {{}} \; && "
           f"find {cfg.modulos_dir}/{slug} -type f -exec chmod 644 {{}} \;")
    if dry_run:
        info(f"[DRY-RUN] Ajustaria permissões: {cfg.web_user}:{cfg.web_group}")
        return
    r = ssh_run(cfg, cmd, check=False)
    if r.returncode == 0:
        ok("Permissões ajustadas.")
    else:
        warn(f"Permissões não ajustadas (pode ser necessário sudo): {r.stderr.strip()[:80]}")


# ── Extrair namespace do ZIP ──────────────────────────────────────────────────

def inferir_namespace(zip_path: str, slug: str) -> str:
    """Tenta ler o namespace do arquivo de integração dentro do ZIP."""
    try:
        with zipfile.ZipFile(zip_path) as zf:
            # Procura {slug}/src/*Integracao.php
            for nome in zf.namelist():
                if re.match(rf"{re.escape(slug)}/src/\w+Integracao\.php", nome):
                    conteudo = zf.read(nome).decode("utf-8", errors="ignore")
                    m = re.search(r"class (\w+)Integracao", conteudo)
                    if m:
                        return m.group(1)
    except Exception:
        pass
    # Fallback: PascalCase do slug
    return "".join(p.capitalize() for p in slug.split("_"))


# ── Deploy principal ──────────────────────────────────────────────────────────

def deploy(args, cfg: DeployConfig):
    zip_path = args.zip
    if not os.path.exists(zip_path):
        err(f"ZIP não encontrado: {zip_path}")
        sys.exit(1)

    slug, versao       = validar_zip(zip_path)
    namespace_pascal   = inferir_namespace(zip_path, slug)
    tag_backup         = datetime.now().strftime("%Y%m%d_%H%M%S")
    dry_run            = args.dry_run
    executar_db        = not args.no_db

    title(f"SEI Module Builder — Deploy")
    print(textwrap.dedent(f"""
      Módulo   : {slug}
      Versão   : {versao}
      Namespace: {namespace_pascal}
      Servidor : {cfg.user}@{cfg.host}:{cfg.port}
      Destino  : {cfg.modulos_dir}/{slug}
      Dry-run  : {"SIM" if dry_run else "NÃO"}
      Scripts  : {"SIM" if executar_db else "NÃO (--no-db)"}
    """).strip())

    if not dry_run:
        resp = input("\nConfirmar deploy? [s/N] ").strip().lower()
        if resp != "s":
            print("Deploy cancelado.")
            sys.exit(0)

    # 1. Verificar conectividade SSH
    title("1. Verificando conectividade SSH")
    if not verificar_ssh(cfg):
        err(f"Não foi possível conectar a {cfg.ssh_target()}")
        err("Verifique host, porta, usuário e chave SSH em deploy.cfg")
        sys.exit(1)
    ok(f"Conexão SSH OK: {cfg.ssh_target()}")

    # 2. Pre-flight
    title("2. Pre-flight checks")
    php_ver = ssh_read(cfg, f"{cfg.php_bin} -r 'echo PHP_VERSION;' 2>/dev/null || echo ERRO")
    if "ERRO" in php_ver or not php_ver:
        err(f"PHP CLI não encontrado em {cfg.php_bin}")
        sys.exit(1)
    ok(f"PHP: {php_ver}")

    r_dir = ssh_run(cfg, f"test -d {cfg.modulos_dir} && echo ok", check=False)
    if "ok" not in r_dir.stdout:
        err(f"Diretório de módulos não existe: {cfg.modulos_dir}")
        sys.exit(1)
    ok(f"Diretório de módulos: {cfg.modulos_dir}")

    r_cfg = ssh_run(cfg, f"test -f {cfg.config_sei} && echo ok", check=False)
    if "ok" not in r_cfg.stdout:
        err(f"ConfiguracaoSEI.php não encontrado: {cfg.config_sei}")
        sys.exit(1)
    ok(f"ConfiguracaoSEI.php encontrado")

    # 3. Backup
    title("3. Backup do módulo existente")
    backup_path = fazer_backup(cfg, slug, tag_backup)

    # 4. Upload e extração
    title("4. Upload e extração")
    remote_zip = f"/tmp/{slug}_v{versao}.zip"
    if not dry_run:
        info(f"Enviando {zip_path} → {remote_zip}")
        scp_upload(cfg, zip_path, remote_zip)
        ok("Upload concluído")
        ssh_run(cfg, f"rm -rf {cfg.modulos_dir}/{slug}")
        ssh_run(cfg, f"unzip -q {remote_zip} -d {cfg.modulos_dir}")
        ssh_run(cfg, f"rm -f {remote_zip}")
        ok(f"Módulo extraído em {cfg.modulos_dir}/{slug}")
    else:
        info(f"[DRY-RUN] Enviaria {zip_path} e extrairia em {cfg.modulos_dir}/{slug}")

    # 5. Ajustar permissões
    title("5. Permissões")
    ajustar_permissoes(cfg, slug, dry_run)

    # 6. Patch ConfiguracaoSEI.php
    title("6. ConfiguracaoSEI.php")
    try:
        patch_configuracao_sei(cfg, slug, namespace_pascal, dry_run)
    except Exception as e:
        warn(f"Erro ao atualizar ConfiguracaoSEI.php: {e}")
        warn("Adicione manualmente a linha de registro do módulo.")

    # 7. Scripts de banco
    if executar_db:
        title("7. Scripts de banco")
        ok_sei = executar_script_php(cfg, slug, "sei_atualizar.php", dry_run)
        ok_sip = executar_script_php(cfg, slug, "sip_atualizar.php", dry_run)
        if not (ok_sei and ok_sip) and not dry_run:
            err("Scripts de banco falharam. Iniciando rollback automático...")
            if backup_path:
                restaurar_backup(cfg, slug, tag_backup)
                ok("Rollback concluído.")
            sys.exit(1)
    else:
        title("7. Scripts de banco — IGNORADOS (--no-db)")
        warn("Execute manualmente no servidor:")
        warn(f"  {cfg.php_bin} {cfg.modulos_dir}/{slug}/src/scripts/sei_atualizar.php")
        warn(f"  {cfg.php_bin} {cfg.modulos_dir}/{slug}/src/scripts/sip_atualizar.php")

    # 8. Verificação pós-deploy
    if not dry_run:
        title("8. Verificação pós-deploy")
        if not verificar_deploy(cfg, slug, namespace_pascal):
            err("Verificação falhou. Iniciando rollback automático...")
            if backup_path:
                restaurar_backup(cfg, slug, tag_backup)
                ok("Rollback concluído.")
            sys.exit(1)

    # 9. Resumo
    print(f"\n{BOLD}{GREEN}{'='*50}")
    print(f"  Deploy concluído com sucesso!")
    print(f"  Módulo : {slug} v{versao}")
    print(f"  Backup : {backup_path or 'N/A'} (tag: {tag_backup})")
    if dry_run:
        print(f"  ⚠  DRY-RUN: nenhuma alteração foi feita")
    print(f"{'='*50}{RESET}\n")

    if not dry_run:
        print(f"Para rollback:")
        print(f"  python deploy.py --rollback {slug} --tag {tag_backup}\n")


# ── Rollback CLI ──────────────────────────────────────────────────────────────

def rollback(args, cfg: DeployConfig):
    slug = args.rollback
    if args.list_backups:
        listar_backups(cfg, slug)
        return
    if not args.tag:
        err("Informe --tag para rollback. Use --list-backups para ver as opções.")
        sys.exit(1)
    title(f"Rollback: {slug} → tag {args.tag}")
    resp = input("Confirmar rollback? [s/N] ").strip().lower()
    if resp != "s":
        print("Rollback cancelado.")
        sys.exit(0)
    restaurar_backup(cfg, slug, args.tag)
    ok("Rollback concluído.")


# ── CLI ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Deploy de módulos SEI gerados pelo SEI Module Builder",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""
          Exemplos:
            python deploy.py --zip mod_manifestacao_v1.0.0.zip
            python deploy.py --zip mod_manifestacao_v1.0.0.zip --dry-run
            python deploy.py --zip mod_manifestacao_v1.0.0.zip --no-db
            python deploy.py --rollback mod_manifestacao --list-backups
            python deploy.py --rollback mod_manifestacao --tag 20260523_143201
        """)
    )
    parser.add_argument("--zip",          help="Caminho para o ZIP gerado pelo SEI Module Builder")
    parser.add_argument("--config",       default="deploy.cfg", help="Arquivo de configuração (padrão: deploy.cfg)")
    parser.add_argument("--dry-run",      action="store_true",  help="Simula o deploy sem fazer alterações")
    parser.add_argument("--no-db",        action="store_true",  help="Pula os scripts sei_atualizar e sip_atualizar")
    parser.add_argument("--rollback",     metavar="SLUG",       help="Restaura módulo a partir de backup")
    parser.add_argument("--tag",          metavar="TAG",        help="Tag do backup para rollback (ex: 20260523_143201)")
    parser.add_argument("--list-backups", action="store_true",  help="Lista backups disponíveis para o slug")

    args = parser.parse_args()

    if not args.zip and not args.rollback:
        parser.print_help()
        sys.exit(0)

    cfg = DeployConfig(args.config)

    if args.rollback:
        rollback(args, cfg)
    else:
        deploy(args, cfg)

if __name__ == "__main__":
    main()
