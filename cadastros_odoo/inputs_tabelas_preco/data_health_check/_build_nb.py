#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import json, os

DIR = os.path.dirname(os.path.abspath(__file__))

def code(src):
    return {"cell_type":"code","source":src,"metadata":{},"outputs":[],"execution_count":None}

def md(src):
    return {"cell_type":"markdown","source":src,"metadata":{}}

# ── CÉLULA 1 — conexão e query ────────────────────────────────────────────────
C1 = '''\
from sqlalchemy import create_engine
import pandas as pd

engine = create_engine(
    "postgresql+psycopg2://consulta:consulta@10.1.57.244:5432/dwfocco"
)

# =====================================================================
# CONFIG
# =====================================================================
COD_PREVEN   = 155
PRODUTO_ALVO = "MESA REINO"   # None = todos os produtos da tabela
# =====================================================================

filtro = (
    f"AND REGEXP_REPLACE(TITENS.DESC_TECNICA, \'^MODELO\\\\s+\', \'\', \'i\') ILIKE \'{PRODUTO_ALVO}\'"
    if PRODUTO_ALVO else ""
)

query = f"""
WITH base AS (
    SELECT
        TPRECOSVEN_IT.ID           AS PRECO_FOCCO_ID,
        TITENS.COD_ITEM,
        TPRECOSVEN.COD_PREVEN,
        REGEXP_REPLACE(TITENS.DESC_TECNICA, \'^MODELO\\\\s+\', \'\', \'i\') AS PRODUTO,
        TCARACTERISTICAS.COD_CAR,
        TVARIAVEIS.MNEMONICO,
        TITENS_CAR.SEQ,
        TPRECOSVEN_IT.PRECO        AS PRECO
    FROM TPRECOSVEN_IT
    JOIN TPRECOSVEN       ON TPRECOSVEN.ID       = TPRECOSVEN_IT.TPRVEN_ID
    JOIN TITENS_COMERCIAL ON TITENS_COMERCIAL.ID = TPRECOSVEN_IT.ITCM_ID
    JOIN TITENS_EMPR      ON TITENS_EMPR.ID      = TITENS_COMERCIAL.ITEMPR_ID
    JOIN TITENS           ON TITENS.ID           = TITENS_EMPR.ITEM_ID
    LEFT JOIN TPRC_REGRAS_COM     ON TPRC_REGRAS_COM.TPRVEN_IT_ID   = TPRECOSVEN_IT.ID
    LEFT JOIN TCARACTERISTICAS    ON TCARACTERISTICAS.ID             = TPRC_REGRAS_COM.TCARAC_ID
    LEFT JOIN TITENS_CAR          ON TITENS_CAR.ITEMPR_ID            = TITENS_EMPR.ID
                                 AND TITENS_CAR.TCARAC_ID            = TPRC_REGRAS_COM.TCARAC_ID
    LEFT JOIN TPRC_REGRAS_VAR_COM ON TPRC_REGRAS_VAR_COM.REGRA_COM_ID = TPRC_REGRAS_COM.ID
    LEFT JOIN TVARIAVEIS          ON TVARIAVEIS.ID                   = TPRC_REGRAS_VAR_COM.TVAR_ID
    WHERE TPRECOSVEN_IT.SIT = 1
      AND TPRECOSVEN.COD_PREVEN = {COD_PREVEN}
      {filtro}
)
SELECT
    PRECO_FOCCO_ID, COD_ITEM, COD_PREVEN, PRODUTO,
    MAX(MNEMONICO) FILTER (WHERE COD_CAR = \'MODULACAO\')    AS MODULACAO,
    MAX(MNEMONICO) FILTER (WHERE COD_CAR = \'COMP_MODULO\')  AS COMP_MODULO,
    MAX(MNEMONICO) FILTER (WHERE COD_CAR = \'PROF_PRODUTO\') AS PROF_PRODUTO,
    MAX(MNEMONICO) FILTER (WHERE COD_CAR = \'ALT_MODULO\')   AS ALT_MODULO,
    REPLACE(MAX(MNEMONICO) FILTER (WHERE COD_CAR = \'FX_TEC\'), \'FX \', \'\') AS FAIXA,
    STRING_AGG(COD_CAR || \':\' || MNEMONICO, \'|\' ORDER BY SEQ)
        FILTER (WHERE COD_CAR IS NOT NULL AND MNEMONICO IS NOT NULL) AS RESP,
    PRECO
FROM base
GROUP BY PRECO_FOCCO_ID, COD_ITEM, COD_PREVEN, PRODUTO, PRECO
ORDER BY PRODUTO, MODULACAO, COMP_MODULO, PROF_PRODUTO, ALT_MODULO, FAIXA;
"""

df = pd.read_sql(query, engine)
engine.dispose()
print(f"Produto: {PRODUTO_ALVO or \'todos\'} | {len(df)} linhas | tabela {COD_PREVEN}")
df.head()
'''

# ── CÉLULA 2 — inspeciona chaves do RESP ──────────────────────────────────────
C2 = '''\
# Mostra todas as chaves COD_CAR presentes no RESP com seus valores.
# Use isso para configurar CARACTERISTICAS na próxima célula.
chaves = {}
for resp_str in df["RESP"].dropna():
    for part in str(resp_str).split("|"):
        if ":" in part:
            k, _, v = part.partition(":")
            chaves.setdefault(k.strip(), set()).add(v.strip())

print(f"{'COD_CAR':<28}  VALORES ENCONTRADOS")
print("-" * 72)
for k in sorted(chaves):
    vals = sorted(chaves[k])
    n    = len(df[df["RESP"].str.contains(k + ":", na=False)])
    print(f"  {k:<26}  ({n} linhas)  {vals[:6]}{'...' if len(vals) > 6 else ''}")
'''

# ── CÉLULA 3 — CARACTERISTICAS ────────────────────────────────────────────────
C3 = '''\
# =====================================================================
# CARACTERISTICAS — adapte com base nas chaves impressas acima
#
# chave_resp    -> COD_CAR exato do Focco
# hierarquia    -> valores em ordem CRESCENTE de preço
# iguais        -> pares/grupos com preço IGUAL esperado
# proporcionais -> [{"valor": V, "referencia": R, "fator": F}]
#                  preço(V) deve ser F × preço(R)
# =====================================================================

CARACTERISTICAS = [
    {
        "chave_resp": "MATERIAL_TAMPO",
        "nome": "Material do Tampo",
        "hierarquia": [
            "MADEIRA",
            "VIDRO",
            "VIDRO FOSCO",
            "VIDRO EXTRA CLEAR",
            "ESPELHO",
            "PEDRA MARMORE",
            "PEDRA GRANITO",
        ],
        "iguais": [],
        "proporcionais": [],
    },
    {
        "chave_resp": "MAT_PE_BASE",
        "nome": "Material Pé/Base",
        "hierarquia": ["MDF", "METAL", "ACO INOX"],
        "iguais": [],
        "proporcionais": [],
    },
    {
        "chave_resp": "FORMATO_MOD",
        "nome": "Formato",
        "hierarquia": ["QUADRADO", "RETANGULAR", "REDONDO", "OVAL"],
        "iguais": [["QUADRADO", "RETANGULAR"]],
        "proporcionais": [],
    },
    # {
    #     "chave_resp": "COD_CAR",
    #     "nome": "Nome",
    #     "hierarquia": ["A", "B"],
    #     "iguais": [],
    #     "proporcionais": [{"valor": "B", "referencia": "A", "fator": 1.10}],
    # },
]

IGUAIS_LIMIAR_PCT        = 0.00   # 0% = exato
PROPORCIONAIS_LIMIAR_PCT = 0.02   # 2% de desvio permitido
OUTLIER_LIMIAR           = 2.0    # σ para marcar outlier

print("Características configuradas:")
for c in CARACTERISTICAS:
    print(f"  {c[\'chave_resp\']:<28} -> {c[\'nome\']}")
'''

# ── CÉLULA 4 — build rows ─────────────────────────────────────────────────────
C4 = '''\
import re

def parse_resp(s):
    r = {}
    if not s or str(s) == "nan":
        return r
    for part in str(s).split("|"):
        if ":" in part:
            k, _, v = part.partition(":")
            r[k.strip()] = v.strip()
    return r

def to_float(s):
    if not s:
        return 0.0
    try:
        return float(re.sub(r"[Mm\\s]", "", str(s)).replace(",", "."))
    except ValueError:
        return 0.0

chaves_caracs = {c["chave_resp"] for c in CARACTERISTICAS}

rows = []
for _, row in df.iterrows():
    prod = str(row["PRODUTO"]).strip()
    if not prod or prod == "nan":
        continue
    try:
        preco = float(row["PRECO"])
    except (ValueError, TypeError):
        continue
    if preco <= 0:
        continue

    resp  = parse_resp(row["RESP"])
    comp  = str(row["COMP_MODULO"]).strip() if str(row["COMP_MODULO"]) != "nan" else ""
    prof  = str(row["PROF_PRODUTO"]).strip() if str(row["PROF_PRODUTO"]) != "nan" else ""
    alt   = str(row["ALT_MODULO"]).strip()  if str(row["ALT_MODULO"])  != "nan" else ""
    faixa = str(row["FAIXA"]).strip()        if str(row["FAIXA"])       != "nan" else "UNICO"
    mod   = str(row["MODULACAO"]).strip()    if str(row["MODULACAO"])   != "nan" else prod
    if not mod:
        mod = prod

    caracs = {k: v for k, v in resp.items() if k in chaves_caracs}

    rows.append({
        "produto":   prod,
        "modulacao": mod,
        "comp": comp, "prof": prof, "alt": alt,
        "dims_str": " x ".join(filter(None, [comp, prof, alt])),
        "faixa":  faixa,
        "caracs": caracs,
        "preco":  preco,
    })

print(f"{len(rows)} linhas validas")
print()
for c in CARACTERISTICAS:
    k    = c["chave_resp"]
    vals = sorted({r["caracs"][k] for r in rows if k in r["caracs"]})
    n    = sum(1 for r in rows if k in r["caracs"])
    status = "OK" if vals else "NAO ENCONTRADO — verifique a chave"
    print(f"  {k:<28} {n}/{len(rows)} linhas  {status}")
    if vals:
        print(f"  {\'\':<28} valores: {vals}")
'''

# ── CÉLULA 5 — análise ────────────────────────────────────────────────────────
C5 = '''\
import statistics
from collections import defaultdict

def rank(v, hier, iguais):
    if v not in hier:
        return 9999
    idx = hier.index(v)
    for g in iguais:
        if v in g:
            return min(hier.index(x) for x in g if x in hier)
    return idx

violacoes_carac  = {}
stats_transicoes = {}
caracs_presentes = set()
for r in rows:
    caracs_presentes.update(r["caracs"].keys())

for carac in CARACTERISTICAS:
    cr    = carac["chave_resp"]
    hier  = carac["hierarquia"]
    igu   = carac.get("iguais", [])
    props = carac.get("proporcionais", [])

    if cr not in caracs_presentes:
        violacoes_carac[cr] = []
        continue

    outras = [c["chave_resp"] for c in CARACTERISTICAS
              if c["chave_resp"] != cr and c["chave_resp"] in caracs_presentes]

    def chave(r, cr=cr, outras=outras):
        return (r["modulacao"], r["comp"], r["prof"], r["alt"],
                r["faixa"]) + tuple(r["caracs"].get(o,"") for o in outras)

    grupos = defaultdict(list)
    for r in rows:
        if cr in r["caracs"]:
            grupos[chave(r)].append(r)

    violacoes  = []
    trans_pcts = defaultdict(list)
    hier_adj   = {(hier[i], hier[i+1]) for i in range(len(hier)-1)}

    for _, grp in grupos.items():
        if len(grp) < 2:
            continue
        grp_s = sorted(grp, key=lambda r: rank(r["caracs"].get(cr,""), hier, igu))
        vtrow = {rr["caracs"].get(cr,""): rr for rr in grp_s}

        for i in range(len(grp_s)-1):
            r1, r2 = grp_s[i], grp_s[i+1]
            v1 = r1["caracs"].get(cr,"")
            v2 = r2["caracs"].get(cr,"")
            if v1 not in hier or v2 not in hier:
                continue
            e1  = rank(v1, hier, igu)
            e2  = rank(v2, hier, igu)
            pct = (r2["preco"] - r1["preco"]) / r1["preco"] * 100 if r1["preco"] else 0

            if e1 == e2:
                mp = max(r1["preco"], r2["preco"])
                dp = abs(r1["preco"] - r2["preco"]) / mp if mp else 0
                if dp > IGUAIS_LIMIAR_PCT:
                    violacoes.append({
                        "tipo": "IGUAL",
                        "mod": r1["modulacao"], "dims": r1["dims_str"],
                        "v1": v1, "p1": r1["preco"],
                        "v2": v2, "p2": r2["preco"], "pct": pct,
                    })
                continue
            if e1 > e2:
                continue
            if r2["preco"] < r1["preco"]:
                violacoes.append({
                    "tipo": "ORDEM",
                    "mod": r1["modulacao"], "dims": r1["dims_str"],
                    "v1": v1, "p1": r1["preco"],
                    "v2": v2, "p2": r2["preco"], "pct": pct,
                })
            if (v1, v2) in hier_adj:
                trans_pcts[(v1, v2)].append(pct)

        for prop in props:
            rv = vtrow.get(prop["valor"])
            rr = vtrow.get(prop["referencia"])
            if not rv or not rr or rr["preco"] <= 0:
                continue
            esp    = prop["fator"] * rr["preco"]
            desvio = abs(rv["preco"] - esp) / rr["preco"]
            pct_r  = (rv["preco"] / rr["preco"] - 1) * 100
            if desvio > PROPORCIONAIS_LIMIAR_PCT:
                violacoes.append({
                    "tipo": "PROPORCIONAL",
                    "mod": rv["modulacao"], "dims": rv["dims_str"],
                    "v1": prop["referencia"], "p1": rr["preco"],
                    "v2": prop["valor"],      "p2": rv["preco"],
                    "pct": pct_r,
                    "esperado": esp, "fator": prop["fator"],
                })

    violacoes_carac[cr]  = violacoes
    stats_transicoes[cr] = dict(trans_pcts)

# análise dimensional
violacoes_dim  = {}
stats_dim_pcts = {}
for dv in ("comp", "prof", "alt"):
    do = [d for d in ("comp","prof","alt") if d != dv]
    def chave_d(r, dv=dv, do=do):
        return (r["modulacao"], r["faixa"]) + tuple(r.get(d,"") for d in do) + tuple(sorted(r["caracs"].items()))
    grupos_d = defaultdict(list)
    for r in rows:
        if r.get(dv):
            grupos_d[chave_d(r)].append(r)
    viol_d, pcts_d = [], []
    for _, grp in grupos_d.items():
        if len(grp) < 2:
            continue
        grp_s = sorted(grp, key=lambda r: to_float(r.get(dv,"")))
        for i in range(len(grp_s)-1):
            r1, r2 = grp_s[i], grp_s[i+1]
            if to_float(r1[dv]) >= to_float(r2[dv]):
                continue
            pct = (r2["preco"] - r1["preco"]) / r1["preco"] * 100 if r1["preco"] else 0
            pcts_d.append(pct)
            if r2["preco"] < r1["preco"]:
                viol_d.append({
                    "mod": r1["modulacao"],
                    "dim1": r1[dv], "p1": r1["preco"],
                    "dim2": r2[dv], "p2": r2["preco"], "pct": pct,
                })
    violacoes_dim[dv]  = viol_d
    stats_dim_pcts[dv] = pcts_d

tvc = sum(len(v) for v in violacoes_carac.values())
tvd = sum(len(v) for v in violacoes_dim.values())
print(f"Analise concluida: {tvc} violacoes de caracteristica | {tvd} violacoes de dimensao")
'''

# ── CÉLULA 6 — resultados ─────────────────────────────────────────────────────
C6 = '''\
import statistics

SEP  = "=" * 70
SEP2 = "-" * 70

tvc = sum(len(v) for v in violacoes_carac.values())
tvd = sum(len(v) for v in violacoes_dim.values())
tv  = tvc + tvd

print(SEP)
print(f"RESULTADO: {'SEM VIOLACOES' if tv == 0 else f'{tv} VIOLACAO(ES)'}")
print(f"  Caracteristicas : {tvc}")
print(f"  Dimensoes       : {tvd}")
print(SEP)

# Violações por característica
for carac in CARACTERISTICAS:
    cr   = carac["chave_resp"]
    nome = carac["nome"]
    hier = carac["hierarquia"]
    viol = violacoes_carac.get(cr, [])
    stat = stats_transicoes.get(cr, {})

    print(f"\n{SEP2}")
    print(f"CARACTERISTICA: {nome} ({cr})")
    print(SEP2)

    # Valores encontrados
    vals_enc = sorted({r["caracs"][cr] for r in rows if cr in r["caracs"]})
    fora     = [v for v in vals_enc if v not in hier]
    print(f"Hierarquia: {' < '.join(hier)}")
    print(f"Encontrado: {vals_enc}")
    if fora:
        print(f"Fora da hierarquia (nao analisados): {fora}")

    # Acréscimos médios por transição
    hier_adj = {(hier[i], hier[i+1]) for i in range(len(hier)-1)}
    trans_adj = {pair: pcts for pair, pcts in stat.items() if pair in hier_adj}
    if trans_adj:
        print("\nAcrescimo medio por transicao:")
        for i in range(len(hier)-1):
            p = (hier[i], hier[i+1])
            ps = trans_adj.get(p)
            if not ps:
                continue
            med = statistics.mean(ps)
            mn  = min(ps)
            mx  = max(ps)
            print(f"  {p[0]:<30} -> {p[1]:<30}  media={med:+.1f}%  min={mn:+.1f}%  max={mx:+.1f}%  n={len(ps)}")

    # Violações
    if not viol:
        print("OK — todos os precos respeitam a hierarquia.")
    else:
        print(f"\n*** {len(viol)} VIOLACAO(ES) ***")
        for v in sorted(viol, key=lambda x: (x["mod"], x["dims"])):
            if v["tipo"] == "PROPORCIONAL":
                print(f"  [{v['tipo']}] {v['mod']} | {v['dims']}")
                print(f"    Esperado {v['v2']} = {v['fator']}x {v['v1']} => R${v['esperado']:,.2f}")
                print(f"    Real:    R${v['p2']:,.2f}  ({v['pct']:+.1f}%)")
            else:
                print(f"  [{v['tipo']}] {v['mod']} | {v['dims']}")
                print(f"    {v['v1']:<25} R${v['p1']:>10,.2f}")
                print(f"    {v['v2']:<25} R${v['p2']:>10,.2f}  ({v['pct']:+.1f}%)")

# Violações dimensionais
print(f"\n{SEP2}")
print("PROGRESSAO DIMENSIONAL")
print(SEP2)
for dv, dl in (("comp","Comprimento"), ("prof","Profundidade"), ("alt","Altura")):
    vd  = violacoes_dim.get(dv, [])
    pd_ = stats_dim_pcts.get(dv, [])
    if not pd_:
        continue
    med = statistics.mean(pd_)
    std = statistics.stdev(pd_) if len(pd_) > 1 else 0
    print(f"\n{dl}: acrescimo medio={med:+.1f}%  sigma={std:.1f}%  n={len(pd_)}")
    if vd:
        print(f"  *** {len(vd)} VIOLACAO(ES) ***")
        for v in vd:
            print(f"    {v['mod']} | {v['dim1']} R${v['p1']:,.2f} -> {v['dim2']} R${v['p2']:,.2f} ({v['pct']:+.1f}%)")
    else:
        print("  OK — precos crescem com a dimensao.")
'''

# ── CÉLULA 7 — progressão por modulação ──────────────────────────────────────
C7 = '''\
# Imprime a tabela de progressão de preços para cada modulação.
# Útil para inspecionar sequências específicas.

import statistics

def sort_row(r):
    dim = tuple(to_float(r[d]) for d in ("comp","prof","alt"))
    car = tuple(
        rank(r["caracs"].get(c["chave_resp"],""), c["hierarquia"], c.get("iguais",[]))
        for c in CARACTERISTICAS
    )
    return dim + car

mods = sorted({r["modulacao"] for r in rows})
SEP  = "=" * 70

for mod in mods:
    grp = sorted([r for r in rows if r["modulacao"] == mod], key=sort_row)
    print(f"\n{SEP}")
    print(f"MODULACAO: {mod}  ({len(grp)} configuracoes)")
    print(f"{SEP}")
    print(f"  {'#':<4} {'DIMS':<18} {'FAIXA':<8} {'CARACS':<40} {'PRECO':>10}  DELTA")
    print("-" * 90)
    prev_preco = None
    prev_dims  = None
    for i, r in enumerate(grp):
        caracs_str = "  ".join(f"{k}:{v}" for k,v in r["caracs"].items())[:38]
        delta = ""
        if prev_preco and r["dims_str"] == prev_dims:
            pct = (r["preco"] - prev_preco) / prev_preco * 100 if prev_preco else 0
            delta = f"{pct:+.1f}%"
        elif i > 0:
            delta = "---"
        print(f"  {i+1:<4} {r[\'dims_str\']:<18} {r[\'faixa\']:<8} {caracs_str:<40} R${r[\'preco\']:>9,.2f}  {delta}")
        prev_preco = r["preco"]
        prev_dims  = r["dims_str"]
'''

nb = {
    "nbformat": 4,
    "nbformat_minor": 5,
    "metadata": {
        "kernelspec": {"display_name":"Python 3","language":"python","name":"python3"},
        "language_info": {"name":"python"}
    },
    "cells": [
        md("# Validação de Preços — Mesas (Focco)\n\nValida consistência de preços lendo diretamente o campo `RESP` estruturado do Focco.\nSaída apenas no notebook — sem geração de HTML."),
        code(C1),
        code(C2),
        code(C3),
        code(C4),
        code(C5),
        code(C6),
        code(C7),
    ]
}

out = os.path.join(DIR, "VALIDAR PRECOS FOCCO.ipynb")
with open(out, "w", encoding="utf-8") as f:
    json.dump(nb, f, ensure_ascii=False, indent=1)
print(f"Criado: {out}")
