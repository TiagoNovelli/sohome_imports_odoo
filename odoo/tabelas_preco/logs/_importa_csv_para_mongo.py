"""Importa os CSVs já existentes em tabelas_preco/logs/ para a coleção 'atualizacoes' no MongoDB.

Migração única — depois disso o salva_log() do notebook grava direto no Mongo.
"""
import csv
import re
from pathlib import Path

from pymongo import MongoClient

MONGO_URI = "mongodb://admin:admin123@localhost:27017/?authSource=admin"
LOG_DIR = Path(__file__).parent

client = MongoClient(MONGO_URI)
col = client["tabelas_preco_logs"]["atualizacoes"]

NUM_FIELDS = {"cod_preven", "empresa_focco", "preco_focco_id"}
BOOL_FIELDS = {"valor_antes", "valor_depois"}
FILENAME_RE = re.compile(r"^atualiza_(\d+)_(\d+)_(\d+_\d+)_(\w+)\.csv$")


def _converte(campo, valor):
    if campo in NUM_FIELDS:
        return int(valor)
    if campo in BOOL_FIELDS and valor in ("True", "False"):
        return valor == "True"
    return valor


total_arquivos = total_docs = total_dup = 0

for csv_path in sorted(LOG_DIR.glob("atualiza_*.csv")):
    m = FILENAME_RE.match(csv_path.name)
    sufixo = m.group(4) if m else "desconhecido"

    with open(csv_path, encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        docs = []
        for row in reader:
            doc = {k: _converte(k, v) for k, v in row.items()}
            doc["sufixo"] = sufixo
            doc["arquivo_origem"] = csv_path.name
            docs.append(doc)

    if not docs:
        continue

    # Evita duplicar se o script rodar mais de uma vez para o mesmo arquivo
    ja_importado = col.count_documents({"arquivo_origem": csv_path.name}, limit=1)
    if ja_importado:
        print(f"  [pulado] {csv_path.name} já importado")
        total_dup += 1
        continue

    col.insert_many(docs)
    total_arquivos += 1
    total_docs += len(docs)
    print(f"  [ok] {csv_path.name}: {len(docs)} documentos")

print()
print(f"Arquivos importados: {total_arquivos} | já existiam: {total_dup} | total de documentos inseridos: {total_docs}")
print(f"Total na coleção agora: {col.count_documents({})}")
