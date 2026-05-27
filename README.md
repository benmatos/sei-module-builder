# SEI Module Builder

Gerador de módulos para o **SEI (Sistema Eletrônico de Informações)** — cria automaticamente a estrutura completa de diretórios e arquivos PHP de um novo módulo, seguindo os padrões e especificações do **manual oficial Versão 5.0**.

---

## Visão Geral

O SEI Module Builder elimina o trabalho repetitivo de scaffolding, reduz erros de convenção e padroniza a criação de módulos InfraPHP. O desenvolvedor preenche um wizard e obtém um módulo completo — com DTOs, RNs, BDs, controllers, views, scripts de banco e documentação — pronto para instalação e em total conformidade com o **SDD (Spec-Driven Development)** do SEI.

---

## Funcionalidades e Conformidade (GEMINI.md)

| Funcionalidade | Descrição |
|---|---|
| **Arquitetura 5.0** | Gera pastas obrigatórias: `bd/`, `dto/`, `rn/`, `int/`, `css/`, `js/`, `imagens/`, `scripts/`, `ws/`. |
| **Validação SDD** | Enforce rigoroso de prefixos: `id_` (PK/FK), `sin_`/`sta_` (char 1), `dta_` (date), `dth_` (datetime), `din_` (decimal). |
| **Namespace SEI** | Garante o uso do prefixo `Md` em Namespaces (ex: `MdMgi`). |
| **Ações & Recursos** | Geração automática de recursos SIP (`listar`, `cadastrar`, `salvar`, `alterar`, `excluir`) para cada tabela. |
| **Wizard Proativo** | Validação em tempo real em cada passo do wizard para evitar inconsistências arquiteturais. |
| **Módulos de Interface** | Suporte total para módulos sem tabelas próprias (ex: Dashboards que consomem dados nativos). |
| **Auto-deploy local** | Backup, extração, patch de configuração e execução de scripts de banco automáticos no SEI dev. |
| **Preview de código** | Visualização dos arquivos `.php` gerados antes da confirmação final. |

---

## Arquitetura do Projeto

```
sei-module-builder/
├── main.py            # FastAPI — rotas wizard, projetos, API e auto-deploy
├── models.py          # Modelos Pydantic com validação rigorosa SEI 5.0
├── generator.py       # ModuloSEIGenerator — lógica de scaffolding e pacotes ZIP
├── deploy.py          # DeployLocal — automação de instalação no SEI local
├── database.py        # SQLite — persistência de projetos e histórico
├── utils.py           # Filtros Jinja2 e utilitários de nomenclatura
├── GEMINI.md          # Especificação técnica e padrões de desenvolvimento
├── templates/
│   ├── base.html
│   ├── wizard/        # step1–step4
│   └── modulo/        # Templates baseados no framework Infra do SEI
└── tests/             # Suíte de testes unitários e de integração
```

---

## Mapeamento de Tipos e Prefixos Obrigatórios

O builder garante que o modelo de dados siga estritamente as convenções do SEI:

| Tipo | Prefixo | Exemplo | Tipo SQL |
| :--- | :--- | :--- | :--- |
| **PK / FK** | `id_` | `id_pedido` | `int` / `bigint` |
| **Sinalizador** | `sin_` | `sin_ativo` | `char(1)` ('S' ou 'N') |
| **Status** | `sta_` | `sta_pedido` | `char(1)` |
| **Data** | `dta_` | `dta_entrega` | `date` |
| **Data e Hora** | `dth_` | `dth_registro` | `datetime` |
| **Monetário** | `din_` | `din_valor` | `decimal(15,2)` |

---

## Instalação e Uso

**Requisitos:** Python 3.11+, PHP CLI disponível no PATH.

```bash
git clone https://github.com/benmatos/sei-module-builder.git
cd sei-module-builder
pip install -r requirements.txt
cp deploy.cfg.example deploy.cfg # Opcional: para deploy local
uvicorn main:app --reload
```

### Fluxo de Trabalho:
1. Acesse `http://localhost:8000`
2. **Passo 1**: Defina metadados (Namespace deve começar com `Md`).
3. **Passo 2**: Defina tabelas (Opcional). O Builder valida prefixos de colunas automaticamente.
4. **Passo 3**: Escolha o Menu Pai. Recursos de segurança são gerados automaticamente.
5. **Passo 4**: Revise o código e baixe o ZIP ou execute o Deploy.

---

## Scripts SIP e Limpeza de Menus

Os scripts gerados realizam a limpeza automática de itens de menu antigos antes de recriá-los, facilitando o ciclo de desenvolvimento e evitando "lixo" no banco de dados do SIP durante testes repetitivos.

---

## Roadmap ✅

- [x] Conformidade total com SEI Versão 5.0
- [x] Validação rigorosa de prefixos (SDD)
- [x] Suporte a módulos sem tabelas
- [x] Geração automática de recursos de auditoria e segurança
- [x] Limpeza de menus e permissões no SIP
- [x] Auto-deploy com Rollback
- [x] Exportação de projetos em JSON

---

## Licença

MIT
