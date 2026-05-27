# Spec-Driven Development (SDD) - Módulos SEI (Padrão Versão 5.0)

Este documento define os padrões e especificações para o desenvolvimento de novos módulos para o SEI (Sistema Eletrônico de Informações), consolidando as diretrizes do manual oficial Versão 5.0.

## 1. Arquitetura e Estrutura de Diretórios

Os módulos seguem uma arquitetura em camadas baseada no framework Infra do SEI.

```text
/meu-modulo
├── bd/                    # Camada de Acesso a Dados (Business Data)
├── dto/                   # Objetos de Transferência de Dados (Data Transfer Objects)
├── rn/                    # Camada de Regras de Negócio (Rules/Business Logic)
├── int/                   # Classes de Integração/Utilitários (Interfaces)
├── css/                   # Estilos CSS específicos do módulo
├── js/                    # Scripts JavaScript específicos do módulo
├── imagens/               # Ativos de imagem e ícones
│   └── menu/              # Ícones específicos para o menu do SEI
├── scripts/               # Scripts de banco de dados (instalação/atualização)
├── ws/                    # Classes de Web Services <ServicoWS.php>
├── MdMeuModuloIntegracao.php # Classe principal de integração com o SEI
└── meu_modulo_acao.php    # Scripts de "Controller/View" (InfraPagina)
```

### 1.1 Regras de Comunicação entre Camadas
*   **DTO Único:** Todo o tráfego de dados entre as camadas deve ser feito obrigatoriamente utilizando DTOs.
*   **Isolamento de RN:** Toda comunicação ocorre apenas entre RNs. Uma RN não pode chamar uma BD de outra classe.
*   **Isolamento de BD:** Não deve haver comunicação direta entre classes BD. Uma BD não pode persistir ou atualizar dados em mais de uma tabela.

## 2. Padrão de Modelagem de Dados

### 2.1 Nomenclatura de Tabelas
*   Utilizar substantivos no singular, letras minúsculas, sem preposições.
*   **Prefixo:** `md_` + [prefixo_inst] + `_` + [nome_tabela] (Ex: `md_mgi_pedido`).
*   **Relacionamentos (n x n):** Prefixo `md_` + [inst] + `_rel_` + [tabelas] (Ex: `md_mgi_rel_pedido_item`).

### 2.2 Nomenclatura de Colunas (Prefixos Obrigatórios)
| Prefixo | Significado | Tipo de Dado |
| :--- | :--- | :--- |
| `id_` | Chave Primária ou Estrangeira | Integer / Numeric |
| `sin_` | Sinalizador (Flag) | Char(1) 'S' ou 'N' |
| `sta_` | Status (Multi-valorado) | Char(1) |
| `dta_` | Data | Date |
| `dth_` | Data e Hora | Timestamp / Datetime |
| `din_` | Valores Monetários | Numeric(15,2) |

### 2.3 Constraints e Índices
*   **PK:** `pk_` + [nome_tabela].
*   **FK:** `fk_` + [nome_tabela_origem] + `_` + [nome_tabela_destino].
*   **Índices:** `i` + [01-99] + `_` + [nome_tabela].

## 3. Especificações das Camadas

### 3.1 DTO (Data Transfer Object)
Estende `InfraDTO`. Define a estrutura da tabela e atributos usando os prefixos de tipo do framework.

```php
<?php
require_once DIR_SEI_WEB.'/SEI.php';

class Md[Prefixo][Entidade]DTO extends InfraDTO {
    public function getStrNomeTabela() {
        return 'md_[prefixo]_[entidade]';
    }

    public function montar() {
        // Usar constantes de prefixo: NUM, STR, DTA, DTH, DIN, BOL, DBL
        $this->adicionarAtributoTabela(InfraDTO::$PREFIXO_STR, 'NomeCampo', 'nome_campo_bd');
        $this->adicionarAtributoTabela(InfraDTO::$PREFIXO_NUM, 'IdEntidade', 'id_entidade');
        
        $this->configurarPK('IdEntidade', InfraDTO::$TIPO_PK_NATIVA); // Ou SEQUENCIAL/INFORMADO
        $this->configurarFK('IdEntidade', 'tabela_origem', 'campo_origem');
    }
}
```

### 3.2 RN (Rules/Business Logic)
Estende `InfraRN`. Implementa a lógica de negócio, validações e controle transacional.

*   **Conectado:** Abre conexão se não estiver aberta.
*   **Controlado:** Abre conexão **e transação** se não estiverem abertas.
*   **Auditoria:** Usar `SessaoSEI::getInstance()->validarAuditarPermissao(...)` obrigatoriamente para operações de escrita.

### 3.3 Interface (InfraPagina / Scripts na Raiz)
*   **Parâmetro `acao`:** Toda URL deve conter o parâmetro `acao` (ex: `md_modulo_entidade_listar`).
*   **Validação:** Sempre validar link e permissão no topo do script.
*   **PHP 8:** Utilizar `InfraErroPHP` para gerenciar Warnings que se tornaram erros no PHP 8.

## 4. Classes API
A troca de informações entre o módulo e o núcleo do SEI ou outros sistemas deve ser feita preferencialmente através das classes API (localizadas em `sei/web/api`):
*   `DocumentoAPI`, `ProcedimentoAPI`, `UnidadeAPI`, `UsuarioAPI`, etc.

## 5. Padrões de Código

*   **Tags PHP:** Usar sempre `<?php`.
*   **Encoding:** ISO-8859-1 conforme legado SEI (atentar para `utf8_encode/decode` se necessário).
*   **Nomenclatura de Métodos:** Verbos no infinitivo, camelCase (ex: `cadastrarPedido`).
*   **Nomenclatura de Variáveis:** Prefixo de tipo + Qualificador (ex: `$strNomeUsuario`, `$numIdUnidade`).

## 6. Fluxo de Geração de Novos Recursos

1.  Definir o modelo de dados (Tabela com prefixos corretos).
2.  Criar o **DTO** configurando atributos e chaves.
3.  Criar o **BD** (extensão simples de `InfraBD`).
4.  Criar a **RN** com métodos `Controlados/Conectados`.
5.  Registrar a ação na classe de **Integracao** (`processarControlador`).
6.  Criar o arquivo da **Ação** na raiz.
7.  Configurar permissões, menus e regras de auditoria no SIP.
