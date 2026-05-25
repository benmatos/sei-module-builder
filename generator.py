from __future__ import annotations
import io, zipfile, os
from models import ModuloDefinicao
from utils import get_jinja_env, to_pascal_case

TEMPLATES_DIR        = os.path.join(os.path.dirname(__file__), "templates", "modulo")
EXTRAS_TEMPLATES_DIR = os.path.join(TEMPLATES_DIR, "extras")

class ModuloSEIGenerator:
    def __init__(self):
        self.env         = get_jinja_env(TEMPLATES_DIR)
        self.env_extras  = get_jinja_env(EXTRAS_TEMPLATES_DIR)
        self.ultimo_arquivo_count: list[str] = []

    def gerar_modulo(self, definicao: ModuloDefinicao) -> bytes:
        buf = io.BytesIO()
        self.ultimo_arquivo_count = []
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            self._adicionar_integracao(zf, definicao)
            self._adicionar_dtos(zf, definicao)
            self._adicionar_rns(zf, definicao)
            self._adicionar_controllers(zf, definicao)
            self._adicionar_views(zf, definicao)
            self._adicionar_scripts(zf, definicao)
            self._adicionar_docs(zf, definicao)
            self._adicionar_config(zf, definicao)
            if definicao.extras:
                self._adicionar_extras(zf, definicao)
        buf.seek(0)
        return buf.read()

    def renderizar_preview(self, definicao: ModuloDefinicao) -> dict[str, str]:
        ns = to_pascal_case(definicao.namespace)
        resultado: dict[str, str] = {}
        resultado[f"{ns}Integracao.php"] = self._render("integracao.php.j2", d=definicao, ns=ns)
        for t in definicao.tabelas:
            tn = to_pascal_case(t.nome)
            resultado[f"{ns}{tn}DTO.php"]        = self._render("dto.php.j2",        d=definicao, ns=ns, tabela=t, tnome=tn)
            resultado[f"{ns}{tn}RN.php"]         = self._render("rn.php.j2",         d=definicao, ns=ns, tabela=t, tnome=tn)
            resultado[f"{ns}{tn}Controller.php"] = self._render("controller.php.j2", d=definicao, ns=ns, tabela=t, tnome=tn)
        resultado["sei_atualizar.php"]           = self._render("sei_atualizar.php.j2",    d=definicao)
        resultado["ConfiguracaoSEI.exemplo.php"] = self._render("configuracao_sei.php.j2", d=definicao, ns=ns)
        resultado["README.md"]                   = self._render("README.md.j2", d=definicao)
        if definicao.extras:
            t0  = definicao.tabelas[0] if definicao.tabelas else None
            tn0 = to_pascal_case(t0.nome) if t0 else "Tabela"
            for _, tmpl, label in self._extra_templates(definicao, t0, tn0, ns):
                try:
                    resultado[label] = self.env_extras.get_template(tmpl).render(
                        d=definicao, ns=ns, tabela=t0, tnome=tn0
                    )
                except Exception:
                    pass
        return resultado

    # ── Extras ────────────────────────────────────────────────────────────────

    def _adicionar_extras(self, zf: zipfile.ZipFile, d: ModuloDefinicao):
        ns  = to_pascal_case(d.namespace)
        t0  = d.tabelas[0] if d.tabelas else None
        tn0 = to_pascal_case(t0.nome) if t0 else "Tabela"
        for _, tmpl, label in self._extra_templates(d, t0, tn0, ns):
            try:
                content = self.env_extras.get_template(tmpl).render(
                    d=d, ns=ns, tabela=t0, tnome=tn0
                )
                self._write(zf, f"{d.slug}/src/extras/{label}", content)
            except Exception:
                pass

    def _extra_templates(self, d, tabela, tnome, ns):
        items = []
        if "workflow" in d.extras:
            items += [
                ("workflow", "workflow_rn.php.j2",   f"{ns}WorkflowRN.php"),
                ("workflow", "workflow_view.php.j2",  f"{d.slug}_workflow_aprovacao.php"),
            ]
        if "exportacao" in d.extras:
            items += [
                ("exportacao", "exportacao_controller.php.j2", f"{ns}ExportacaoController.php"),
                ("exportacao", "exportacao_view.php.j2",       f"{d.slug}_exportacao.php"),
            ]
        if "dashboard" in d.extras:
            items += [
                ("dashboard", "dashboard_controller.php.j2", f"{ns}DashboardController.php"),
                ("dashboard", "dashboard_view.php.j2",       f"{d.slug}_dashboard.php"),
            ]
        if "job" in d.extras:
            items += [
                ("job", "job.php.j2",        f"{ns}Job.php"),
                ("job", "job_config.php.j2", f"{d.slug}_job_config.exemplo.php"),
            ]
        if "sip" in d.extras:
            items += [
                ("sip", "sip_avancado.php.j2", "sip_atualizar_avancado.php"),
            ]
        return items

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _render(self, name, **ctx):
        return self.env.get_template(name).render(**ctx)

    def _write(self, zf, path, content):
        self.ultimo_arquivo_count.append(path)
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
                self._write(zf, f"{d.slug}/src/web/view/{d.slug}_{t.nome}_{view}.php",
                            self._render(f"view_{view}.php.j2", d=d, ns=ns, tabela=t, tnome=tn))
        self._write(zf, f"{d.slug}/src/web/js/{d.slug}.js", self._render("js.js.j2", d=d))

    def _adicionar_scripts(self, zf, d):
        for s in ("sei_atualizar", "sip_atualizar"):
            self._write(zf, f"{d.slug}/src/scripts/{s}.php", self._render(f"{s}.php.j2", d=d))

    def _adicionar_docs(self, zf, d):
        for doc in ("README", "INSTALL", "USAGE"):
            self._write(zf, f"{d.slug}/{doc}.md", self._render(f"{doc}.md.j2", d=d))

    def _adicionar_config(self, zf, d):
        ns = to_pascal_case(d.namespace)
        self._write(zf, f"{d.slug}/config/ConfiguracaoSEI.exemplo.php",
                    self._render("configuracao_sei.php.j2", d=d, ns=ns))
