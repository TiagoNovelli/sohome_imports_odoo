# sohome_imports_odoo

Ferramentas de automação e integração com Odoo para gestão de leads, cadastros e tabelas de preço da Sohome.

## Estrutura

```
├── odoo/
│   ├── cadastros/          # Cadastro de clientes, produtos e representantes no Odoo
│   ├── tabelas_preco/      # Carga e atualização incremental de tabelas de preço (Focco → Odoo)
│   └── validacao/          # Data health check das tabelas de preço
```

## odoo/tabelas_preco/

Notebooks para sincronização das tabelas de preço entre o Focco (PostgreSQL `dwfocco`) e o módulo `calculadora_sohome` no Odoo.

### Fluxo de uso

| Situação | Notebook |
|---|---|
| Tabela nova (primeira carga) | `cria_tabela_preco.ipynb` |
| Atualização incremental | `atualiza_tabela_preco.ipynb` |
| Remover tabela e suas linhas | `drop_tabela_preco.ipynb` |
| Exploração/exportação de dados | `faixa_caixa.ipynb` |

### Conexões

- **Focco**: PostgreSQL `10.1.57.244:5432/dwfocco` (usuário `consulta`)
- **Odoo**: XML-RPC em `https://<host>/xmlrpc/2/` — configurar `ODOO_URL`, `ODOO_DB`, `ODOO_USER`, `ODOO_PASS` na célula de conexão de cada notebook

### Modelo Odoo: `calculadora.price.line`

Campos aceitos (compatibilidade verificada com o módulo `calculadora_sohome`):

| Campo | Tipo | Obrigatório | Notas |
|---|---|---|---|
| `preco_focco_id` | Integer | ✅ | Chave estável entre Focco e Odoo |
| `cod_item` | Char | — | Código do item no Focco |
| `cod_preven` | Integer | — | Liga a linha à tabela (`calculadora.price.table`) |
| `tabela_descricao` | Char | — | Descrição da tabela (metadado) |
| `produto` | Char | ✅ | |
| `marca` | Char | — | Preenchida via `calculadora.price.table.brand_id`; não vem do Focco |
| `categoria` | Char | — | |
| `modulacao` | Char | — | |
| `comp_modulo` | Char | — | |
| `prof_produto` | Char | — | |
| `faixa` | Char | — | Armazenada sem o prefixo "FX " |
| `tipo_acab` | Char | — | |
| `embalagem` | Char | — | |
| `configuracao` | Text | — | Não populado pelos notebooks; não usado pelo payload JS |
| `formula` | Text | — | |
| `resp` | Text | — | String `CHAVE:VALOR` separada por `\|` |
| `qtde_tec` | Integer | — | |
| `qtde_tec_cx` | Integer | — | |
| `preco` | Float | ✅ | |

> **Campos removidos dos notebooks** (não existem no modelo atual):
> - `price_table_id` — a ligação linha↔tabela é feita via `cod_preven`, não por Many2one
> - `resp_extras` — campo removido do modelo; o payload JS deriva os extras de `resp` em tempo de execução via `_parse_resp`

### Observações de compatibilidade

#### `marca`
O modelo lê a marca preferencialmente via `calculadora.price.table.brand_id`. O campo `marca` na linha serve de fallback. Como o Focco não fornece este dado, as linhas importadas ficam com `marca` vazio — comportamento esperado enquanto a tabela tiver `brand_id` preenchido.

#### `resp` e `_RESP_KEYS_COVERED`
O modelo define internamente:
```python
_RESP_KEYS_COVERED = frozenset({
    "MODULACAO", "COMP_MODULO", "PROF_PRODUTO",
    "FX_TEC", "TIPO_ACAB", "EMBAL_REFORCADA",
})
```
Chaves fora desse conjunto (ex: `ALT_MODULO`, `MATERIAL_TAMPO`) são tratadas como `extras` e aparecem no payload do frontend. O conteúdo de `resp` deve ser a string completa do Focco — o modelo faz o parsing.

#### `cod_item` e `tabela_descricao` não rastreados no UPDATE
Em `atualiza_tabela_preco.ipynb`, esses campos são enviados no INSERT mas não estão em `CAMPOS_COMPARADOS`, portanto não são atualizados se mudarem no Focco. Para `tabela_descricao` isso é intencional (metadado da tabela). Para `cod_item`, avaliar se mudanças de código de item precisam ser propagadas.

#### Comparação de `preco`
O limiar de diferença é `0.01` (1 centavo). Diferenças menores são tratadas como ruído de ponto flutuante e ignoradas.

#### Comparação de `resp`
A comparação usa `frozenset` dos segmentos `CHAVE:VALOR` para ignorar diferenças de ordem — mudança de sequência no `STRING_AGG` do Focco não gera falso positivo.

#### Performance do UPDATE
O notebook `atualiza_tabela_preco.ipynb` agrupa registros com alterações idênticas (mesmo conjunto de campos e valores) em uma única chamada `write([ids], vals)`, com sub-lotes de 500 IDs. Isso reduz drasticamente o número de chamadas XML-RPC quando há atualizações em massa de preço.
