from __future__ import annotations
import io, zipfile, os
from models import ModuloDefinicao
from utils import get_jinja_env, to_pascal_case

TEMPLATES_DIR = os.path.join(os.path.dirname(__file__), "templates", "modulo")

class ModuloSEIGenerator:
    def __init__(self):
        self.env = get_jinja_env(TEMPLATES_DIR)

    def gerar_modulo(self, definicao: ModuloDefinicao) -> bytes:
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            self._adicionar_integracao(zf, definicao)
            self._adicionar_dtos(zf, definicao)
            self._adicionar_rns(zf, definicao)
            self._adicionar_controllers(zf, definicao)
            self._adicionar_views(zf, definicao)
            self._adicionar_scripts(zf, definicao)
            self._adicionar_docs(zf, definicao)
            self._adicionar_config(zf, definicao)
        buf.seek(0)
        return buf.read()

    def _render(self, name, **ctx):
        return self.env.get_template(name).render(**ctx)

    def _write(self, zf, path, content):
        zf.writestr(path, content.encode("utf-8"))

    def _adicionar_integracao(self, zf, d):
        ns = to_pascal_case(d.namespace)
        self._write(zf, f"{d.slug}/src/{ns}Integracao.php", self._render("integracao.php.j2", d=d, ns=ns))

    def _adicionar_dtos(self, zf, d):
        ns = to_pascal_case(d.namespace)
        for t in d.tabelas:
            tn = to_pascal_case(t.nome)
            self._write(zf, f"{d.slug}/src/db/dto/{ns}{tn}DTO.php", self._render("dto.php.j2", d=d, ns=ns, tabela=t, tnome=tn))

    def _adicionar_rns(self, zf, d):
        ns = to_pascal_case(d.namespace)
        for t in d.tabelas:
            tn = to_pascal_case(t.nome)
            self._write(zf, f"{d.slug}/src/db/rn/{ns}{tn}RN.php", self._render("rn.php.j2", d=d, ns=ns, tabela=t, tnome=tn))

    def _adicionar_controllers(self, zf, d):
        ns = to_pascal_case(d.namespace)
        for t in d.tabelas:
            tn = to_pascal_case(t.nome)
            self._write(zf, f"{d.slug}/src/web/controller/{ns}{tn}Controller.php", self._render("controller.php.j2", d=d, ns=ns, tabela=t, tnome=tn))

    def _adicionar_views(self, zf, d):
        ns = to_pascal_case(d.namespace)
        for t in d.tabelas:
            tn = to_pascal_case(t.nome)
            for view in ("listar", "cadastrar"):
                self._write(zf, f"{d.slug}/src/web/view/{d.slug}_{t.nome}_{view}.php", self._render(f"view_{view}.php.j2", d=d, ns=ns, tabela=t, tnome=tn))
        self._write(zf, f"{d.slug}/src/web/js/{d.slug}.js", self._render("js.js.j2", d=d))

    def _adicionar_scripts(self, zf, d):
        for s in ("sei_atualizar", "sip_atualizar"):
            self._write(zf, f"{d.slug}/src/scripts/{s}.php", self._render(f"{s}.php.j2", d=d))

    def _adicionar_docs(self, zf, d):
        for doc in ("README", "INSTALL", "USAGE"):
            self._write(zf, f"{d.slug}/{doc}.md", self._render(f"{doc}.md.j2", d=d))

    def _adicionar_config(self, zf, d):
        ns = to_pascal_case(d.namespace)
        self._write(zf, f"{d.slug}/config/ConfiguracaoSEI.exemplo.php", self._render("configuracao_sei.php.j2", d=d, ns=ns))
