# SEI Module Builder

Gerador de módulos para o **SEI (Sistema Eletrônico de Informações)** — cria automaticamente a estrutura completa de diretórios e arquivos PHP de um novo módulo, seguindo a arquitetura oficial do guia SEI-Modulos-v3.0.

---

## Visão Geral

O SEI Module Builder elimina o trabalho repetitivo de scaffolding, reduz erros de convenção e padroniza a criação de módulos InfraPHP. O desenvolvedor preenche um wizard de 4 passos e obtém um módulo completo — com DTOs, RNs, controllers, views, scripts de banco e documentação — pronto para instalação.

Em ambiente de desenvolvimento, o módulo pode ser **deployado automaticamente** no SEI local logo após a geração, sem nenhuma etapa manual.

---

## Funcionalidades

| Funcionalidade | Descrição |
|---|---|
| Wizard 4 passos | Metadados → Tabelas → Recursos/Menus → Revisão |
| Drag-and-drop | Reordenação de tabelas e colunas no passo 2 (SortableJS) |
| Preview de código | Syntax highlight dos arquivos gerados antes de confirmar (highlight.js) |
| Geração de ZIP | Módulo completo com estrutura `mod-sei-pen`-compatível |
| Auto-deploy local | Deploy automático no SEI de desenvolvimento após a geração |
| Persistência SQLite | Histórico de projetos e gerações com carregamento/reutilização |
| Export/Import JSON | Salve e restaure definições de módulos em arquivos JSON |
| Limpeza de Menus | Remoção automática de itens de menu antigos no SIP antes da recriação |
| API REST | Endpoints `/api/gerar`, `/api/validar` e `/api/preview` para integração |

---

## Arquitetura

```
sei-module-builder/
├── main.py            # FastAPI — rotas wizard, projetos, API e auto-deploy
├── models.py          # Modelos Pydantic (ModuloDefinicao, TabelaDTO, ColunaFK…)
├── generator.py       # ModuloSEIGenerator — renderiza Jinja2 e empacota ZIP
├── deploy.py          # DeployLocal — instala módulo direto no SEI dev
├── database.py        # SQLite — projetos e histórico de gerações
├── utils.py           # Filtros Jinja2: pascalcase, camelcase, tipo_infrabanco
├── deploy.cfg.example # Configuração de caminhos do SEI local
├── requirements.txt
├── templates/
│   ├── base.html
│   ├── wizard/        # step1–step4
│   ├── projetos/      # index, detalhe, importar
│   ├── deploy/        # resultado
│   └── modulo/        # Templates .php.j2 e .md.j2 de saída
└── static/
```

### Fluxo de geração + deploy

```
Wizard (4 passos)
      │
      ▼ POST /gerar
ModuloDefinicao (Pydantic)
      │
      ├─► ModuloSEIGenerator → ZIP em memória
      │         │
      │         └─► DeployLocal.deploy_from_bytes()
      │                   ├── Backup do módulo existente
      │                   ├── Extração no modulos_dir
      │                   ├── Patch ConfiguracaoSEI.php
      │                   ├── php sei_atualizar.php
      │                   └── php sip_atualizar.php (com limpeza de menus)
      │
      └─► /deploy/resultado  (ou download do ZIP se deploy inativo)
```

---

## Instalação

**Requisitos:** Python 3.11+, PHP CLI disponível no PATH (para deploy local).

```bash
git clone https://github.com/benmatos/sei-module-builder.git
cd sei-module-builder
pip install -r requirements.txt
```

**Configurar deploy local (opcional):**

```bash
cp deploy.cfg.example deploy.cfg
# Editar modulos_dir e configuracao_sei com os caminhos do SEI local
```

**Iniciar:**

```bash
uvicorn main:app --reload
# Acesse http://localhost:8000
```

---

## Uso

### Wizard (interface web)

1. Acesse `http://localhost:8000`
2. **Passo 1 (Metadados)**: Nome, slug, namespace e seleção de templates opcionais (Workflow, Exportação, Dashboard, etc).
3. **Passo 2 (Tabelas)**: Definição da estrutura de dados com drag-and-drop para ordenação.
4. **Passo 3 (Recursos/Menus)**: Definição de recursos obrigatórios, seleção do Menu Pai (**Relatórios** ou **Administração**) e submenus opcionais.
5. **Passo 4 (Revisão)**: Validação final dos dados e preview do código gerado.
6. Clique **Gerar e Deployar** (com deploy ativo) ou **Gerar Módulo (ZIP)**.

### Exportação e Importação

Agora é possível salvar o estado do seu projeto em um arquivo JSON:
- No Passo 1, use o link "ou importar JSON de projeto existente".
- Na lista de projetos, utilize o botão de exportação para baixar o arquivo JSON do módulo.

---

## Scripts SIP e Limpeza de Menus

Os scripts de atualização do SIP gerados pelo Builder possuem inteligência para:
- **Evitar duplicidade**: Antes de criar um item de menu, o script verifica se ele já existe e o remove (limpando também as permissões associadas).
- **Hierarquia dinâmica**: O item de menu principal é criado sob o menu pai selecionado no wizard.

---

## Mapeamento de tipos

| Tipo SQL | Constante InfraBanco |
|---|---|
| `varchar(100)` / `varchar(255)` | `InfraBanco::TIPO_TEXTO_CURTO` |
| `text` | `InfraBanco::TIPO_TEXTO_LONGO` |
| `int` / `bigint` | `InfraBanco::TIPO_INTEIRO` |
| `decimal(15,2)` | `InfraBanco::TIPO_DECIMAL` |
| `date` | `InfraBanco::TIPO_DATA` |
| `datetime` | `InfraBanco::TIPO_DATA_HORA` |
| `char(1)` | `InfraBanco::TIPO_TEXTO_FIXO` |

---

## Roadmap

### Concluído ✅

- [x] Wizard 4 passos com validação Pydantic
- [x] Seleção de Menu Pai (Relatórios/Administração) no Passo 3
- [x] Limpeza automática de menus no `sip_atualizar.php`
- [x] Export/import de `ModuloDefinicao` como JSON
- [x] Drag-and-drop para reordenação de tabelas e colunas (SortableJS)
- [x] Preview de código com syntax highlight antes da geração
- [x] Auto-deploy local no SEI de desenvolvimento
- [x] Persistência SQLite com histórico de projetos e gerações
- [x] API REST (`/api/gerar`, `/api/validar`, `/api/preview`)

### Próximas evoluções 🚀

- [ ] Geração de testes PHP básicos (unitários para RN, funcionais para controller)
- [ ] Validação semântica de nomenclatura SEI
- [ ] Diagrama ER automático a partir das tabelas definidas
- [ ] Canvas de modelagem visual no passo 2
- [ ] Deploy via SSH para ambientes de homologação

---

## Referências

- Guia oficial SEI-Modulos-v3.0 (PDF)
- Módulo de referência: [mod-sei-pen](https://github.com/pengovbr/mod-sei-pen)
- [Processo Eletrônico Nacional](https://www.gov.br/gestao/pt-br/assuntos/processo-eletronico-nacional)

---

## Licença

MIT
