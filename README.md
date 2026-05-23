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
| API REST | Endpoints `/api/gerar` e `/api/validar` para integração programática |

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
│   ├── projetos/      # index, detalhe
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
      │                   └── php sip_atualizar.php
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
2. Preencha os 4 passos: metadados, tabelas/colunas, recursos/menus, revisão
3. No passo 4, visualize o preview do código gerado com syntax highlight
4. Clique **Gerar e Deployar** (com deploy ativo) ou **Gerar Módulo (ZIP)**

### API REST

**Gerar módulo (retorna ZIP):**

```bash
curl -X POST http://localhost:8000/api/gerar \
  -H "Content-Type: application/json" \
  -d @definicao.json \
  --output mod_manifestacao_v1.0.0.zip
```

**Validar definição:**

```bash
curl -X POST http://localhost:8000/api/validar \
  -H "Content-Type: application/json" \
  -d @definicao.json
# {"valid": true, "slug": "mod_manifestacao", "tabelas": 2}
```

**Estrutura do JSON de entrada:**

```json
{
  "nome": "Módulo de Manifestação",
  "slug": "mod_manifestacao",
  "namespace": "ModManifestacao",
  "descricao": "Gerencia manifestações de usuários",
  "versao": "1.0.0",
  "sei_versao_min": "3.1.0",
  "autor": "Nome / Equipe",
  "tabelas": [
    {
      "nome": "md_manifestacao",
      "alias": "man",
      "colunas": [
        { "nome": "id_manifestacao", "tipo": "int",          "chave_primaria": true,  "obrigatorio": true },
        { "nome": "descricao",       "tipo": "varchar(255)", "chave_primaria": false, "obrigatorio": true },
        { "nome": "id_usuario",      "tipo": "int",          "chave_primaria": false, "obrigatorio": true,
          "fk": { "tabela_slug": "sei:usu", "coluna": "id_usuario",
                  "coluna_pai": "id_usuario", "colunas_exibir": ["nome"] } }
      ]
    }
  ],
  "recursos": [
    { "nome": "md_manifestacao_listar", "descricao": "Listar manifestações" }
  ],
  "menus": [
    { "titulo": "Manifestações", "link": "md_manifestacao_listar",
      "icone": "fa-list", "perfil_requerido": "Básico" }
  ]
}
```

### Deploy local via CLI

```bash
# Deploy direto (sem wizard)
python deploy.py --zip mod_manifestacao_v1.0.0.zip

# Ver backups disponíveis
python deploy.py --rollback mod_manifestacao --list-backups

# Rollback para versão anterior
python deploy.py --rollback mod_manifestacao --tag 20260523_143201
```

---

## Estrutura do ZIP gerado

```
{slug}/
├── src/
│   ├── {Namespace}Integracao.php
│   ├── db/
│   │   ├── dto/{Namespace}{Tabela}DTO.php
│   │   └── rn/{Namespace}{Tabela}RN.php
│   ├── web/
│   │   ├── controller/{Namespace}{Tabela}Controller.php
│   │   ├── view/{slug}_{tabela}_{listar|cadastrar}.php
│   │   └── js/{slug}.js
│   └── scripts/
│       ├── sei_atualizar.php
│       └── sip_atualizar.php
├── config/
│   └── ConfiguracaoSEI.exemplo.php
├── README.md
├── INSTALL.md
└── USAGE.md
```

> **Nenhum SQL explícito** nos arquivos gerados. Toda interação com banco usa `InfraDTO`/`InfraRN`. Scripts de instalação usam `InfraBanco::criarTabela()`.

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

## Variáveis de ambiente

| Variável | Padrão | Descrição |
|---|---|---|
| `SECRET_KEY` | `dev-insecure-...` | Chave de assinatura da sessão (obrigatório em produção) |
| `SESSION_TTL_SECONDS` | `7200` | TTL da sessão do wizard (2h) |
| `DEBUG` | `false` | Ativa reload automático e logs detalhados |
| `DB_PATH` | `sei_builder.db` | Caminho do banco SQLite |


---

## Roadmap

### Concluído ✅

- [x] Wizard 4 passos com validação Pydantic
- [x] Drag-and-drop para reordenação de tabelas e colunas (SortableJS)
- [x] Preview de código com syntax highlight antes da geração (highlight.js)
- [x] Geração de ZIP com estrutura `mod-sei-pen`-compatível
- [x] Auto-deploy local no SEI de desenvolvimento
- [x] Backup automático com rollback via CLI
- [x] Persistência SQLite com histórico de projetos e gerações
- [x] API REST (`/api/gerar`, `/api/validar`, `/api/preview`)

---

### Próximas evoluções

#### Completar escopo original
- [ ] Export/import explícito do `ModuloDefinicao` como JSON — compartilhamento entre times e repositórios
- [ ] Templates para jobs agendados, envio de e-mails e integração SIP avançada

#### Qualidade do código gerado
- [ ] Geração de testes PHP básicos (unitários para RN, funcionais para controller)
- [ ] Validação semântica — convenções de nomenclatura SEI, coerência entre alias e tabela, conflito com tabelas nativas do sistema

#### Modelagem visual
- [ ] Diagrama ER automático a partir das tabelas e FKs definidas
- [ ] Canvas de modelagem no passo 2 como alternativa ao formulário

#### Deploy e ciclo de vida
- [ ] Diff entre gerações — exibir o que mudou de v1.0.0 para v1.1.0 antes de deployar
- [ ] Deploy via SSH para ambientes de homologação e produção
- [ ] Integração com Git — commit automático do módulo gerado no repositório do projeto

#### Ecossistema
- [ ] Templates customizáveis pela interface — editar `.php.j2` sem mexer nos arquivos do servidor
- [ ] Suporte a módulos com dependência entre si (módulo A referencia tabelas do módulo B)
- [ ] Geração de documentação Markdown/Confluence a partir da definição do módulo
---

## Referências

- Guia oficial SEI-Modulos-v3.0 (PDF)
- Módulo de referência: [mod-sei-pen](https://github.com/pengovbr/mod-sei-pen)
- [Processo Eletrônico Nacional](https://www.gov.br/gestao/pt-br/assuntos/processo-eletronico-nacional)

---

## Licença

MIT
