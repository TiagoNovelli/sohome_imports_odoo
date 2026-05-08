# 🏢 Buscador de Incorporadoras Ativas

Script Python para consultar CNPJs de incorporadoras ativas (CNAE 4110-7/00) diretamente na API pública [Minha Receita](https://minhareceita.org/), retornando os resultados organizados em um DataFrame do Pandas.

---

## 📋 Pré-requisitos

- Python 3.7+
- Pip

## 📦 Instalação das dependências

```bash
pip install requests pandas
```

---

## 🚀 Como usar

### Importando a função

```python
from seu_arquivo import buscar_incorporadoras_ativas_dataframe

# Buscar por estado
df = buscar_incorporadoras_ativas_dataframe(uf="SP", limit=100)

# Buscar em todo o Brasil
df = buscar_incorporadoras_ativas_dataframe(limit=500)
```

### Executando diretamente

```bash
python seu_arquivo.py
```

O script já traz exemplos de busca para **São Paulo** e **Rio de Janeiro** com 10 resultados cada.

---

## ⚙️ Parâmetros

| Parâmetro | Tipo | Padrão | Descrição |
|-----------|------|--------|-----------|
| `uf` | `str` | `None` | Sigla do estado (ex: `"SP"`, `"RJ"`, `"PR"`). Se omitido, busca em todo o Brasil. |
| `limit` | `int` | `100` | Quantidade de resultados por página (máximo: 1000). |

---

## 📊 Colunas retornadas no DataFrame

| Coluna | Descrição |
|--------|-----------|
| `CNPJ` | Número do CNPJ |
| `Razão Social` | Nome jurídico da empresa |
| `Nome Fantasia` | Nome comercial |
| `Situação Cadastral` | Descrição da situação (ex: "ATIVA") |
| `UF` | Estado |
| `Município` | Cidade |
| `CNAE Fiscal` | Descrição do CNAE principal |
| `Data Início Atividade` | Data de abertura da empresa |

> Apenas empresas com **situação cadastral ATIVA** (código `2`) são incluídas no resultado.

---

## 💾 Exportando os dados

```python
df = buscar_incorporadoras_ativas_dataframe(uf="SP", limit=200)

# Salvar em CSV
df.to_csv("incorporadoras_sp.csv", index=False)

# Salvar em Excel
df.to_excel("incorporadoras_sp.xlsx", index=False)
```

---

## 🌐 API utilizada

[**Minha Receita**](https://minhareceita.org/) — API pública e gratuita que disponibiliza dados da Receita Federal do Brasil (CNPJ).

---

## ⚠️ Observações

- O filtro de empresas ativas é feito **localmente** após o retorno da API, ou seja, o `limit` se refere ao total de registros buscados, não ao total de ativas.
- Para grandes volumes de dados, considere implementar paginação iterando sobre os resultados com múltiplas chamadas.
- A API pode ter instabilidades pontuais; erros de conexão são tratados e retornam um DataFrame vazio.