# search_cnpj_by_cnae_pandas

Ferramentas de automação e integração com Odoo para gestão de leads, cadastros, tabelas de preço e visão computacional aplicada a móveis.

## Estrutura

```
├── leads/                  # Busca de CNPJs ativos por CNAE via Minha Receita API
├── odoo/
│   ├── cadastros/          # Cadastro de clientes, produtos e representantes no Odoo
│   ├── tabelas_preco/      # Input e atualização de tabelas de preço por fornecedor
│   └── validacao/          # Data health check das tabelas de preço
├── visao_computacional/    # Detecção de móveis com YOLOv8 (integração Instagram/Odoo)
├── calculadora/            # Atualização da base de dados da calculadora de preços
└── exploratorio/           # Notebooks de exploração e experimentos
```

## Módulos

### `leads/`
Busca incorporadoras ativas por estado usando CNAE 4110-7/00 via [Minha Receita API](https://minhareceita.org/). Inclui análise de rede de sócios para identificar empresas relacionadas.

### `odoo/cadastros/`
Automação do cadastro de clientes, produtos e representantes no Odoo ERP. Consome dados dos arquivos Excel de representantes e do banco de dados master.

### `odoo/tabelas_preco/`
Scripts de input de tabelas de preço por fornecedor/segmento (FOCCO, Century, Corporativo, EstudioBola Saccaro, OVOO, PV, Tok&Stok). Suporte a cotação em dólar.

### `odoo/validacao/`
Validação de integridade das tabelas de preço (estofados, wood, FOCCO) com data health check.

### `visao_computacional/`
Modelo YOLOv8 para detecção e classificação de móveis em imagens. Planejado para integração com catálogo do Odoo e assistente de vendas via Instagram.

### `calculadora/`
Atualização da base de dados JavaScript usada pela calculadora de preços web.
