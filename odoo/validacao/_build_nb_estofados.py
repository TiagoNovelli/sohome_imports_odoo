#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import json, os

DIR = os.path.dirname(os.path.abspath(__file__))

def code(src):
    return {"cell_type":"code","source":src,"metadata":{},"outputs":[],"execution_count":None}

def md(src):
    return {"cell_type":"markdown","source":src,"metadata":{}}

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
PRODUTO_ALVO = "ADANA"   # None = todos os produtos da tabela
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
        TPRECOSVEN_IT.PRECO AS PRECO
    FROM TPRECOSVEN_IT
    JOIN TPRECOSVEN       ON TPRECOSVEN.ID       = TPRECOSVEN_IT.TPRVEN_ID
    JOIN TITENS_COMERCIAL ON TITENS_COMERCIAL.ID = TPRECOSVEN_IT.ITCM_ID
    JOIN TITENS_EMPR      ON TITENS_EMPR.ID      = TITENS_COMERCIAL.ITEMPR_ID
    JOIN TITENS           ON TITENS.ID           = TITENS_EMPR.ITEM_ID
    LEFT JOIN TPRC_REGRAS_COM     ON TPRC_REGRAS_COM.TPRVEN_IT_ID    = TPRECOSVEN_IT.ID
    LEFT JOIN TCARACTERISTICAS    ON TCARACTERISTICAS.ID              = TPRC_REGRAS_COM.TCARAC_ID
    LEFT JOIN TITENS_CAR          ON TITENS_CAR.ITEMPR_ID             = TITENS_EMPR.ID
                                 AND TITENS_CAR.TCARAC_ID             = TPRC_REGRAS_COM.TCARAC_ID
    LEFT JOIN TPRC_REGRAS_VAR_COM ON TPRC_REGRAS_VAR_COM.REGRA_COM_ID = TPRC_REGRAS_COM.ID
    LEFT JOIN TVARIAVEIS          ON TVARIAVEIS.ID                    = TPRC_REGRAS_VAR_COM.TVAR_ID
    WHERE TPRECOSVEN_IT.SIT = 1
      AND TPRECOSVEN.COD_PREVEN = {COD_PREVEN}
      {filtro}
)
SELECT
    PRECO_FOCCO_ID, COD_ITEM, COD_PREVEN, PRODUTO,
    MAX(MNEMONICO) FILTER (WHERE COD_CAR = \'MODULACAO\')    AS MODULACAO,
    MAX(MNEMONICO) FILTER (WHERE COD_CAR = \'COMP_MODULO\')  AS COMP_MODULO,
    MAX(MNEMONICO) FILTER (WHERE COD_CAR = \'PROF_PRODUTO\') AS PROF_PRODUTO,
    MAX(MNEMONICO) FILTER (WHERE COD_CAR = \'TIPO_ACAB\')    AS TIPO_ACAB,
    MAX(MNEMONICO) FILTER (WHERE COD_CAR = \'EMBAL_REFORCADA\') AS EMBALAGEM,
    MAX(MNEMONICO) FILTER (WHERE COD_CAR = \'BASE_PE\')      AS BASE_PE,
    REPLACE(MAX(MNEMONICO) FILTER (WHERE COD_CAR = \'FX_TEC\'), \'FX \', \'\') AS FAIXA,
    PRECO
FROM base
GROUP BY PRECO_FOCCO_ID, COD_ITEM, COD_PREVEN, PRODUTO, PRECO
ORDER BY PRODUTO, MODULACAO, COMP_MODULO, FAIXA, TIPO_ACAB, EMBALAGEM;
"""

df = pd.read_sql(query, engine)
engine.dispose()
print(f"Produto: {PRODUTO_ALVO or \'todos\'} | {len(df)} linhas | tabela {COD_PREVEN}")
df.head()
'''

C2 = '''\
# Visão geral dos dados — faixas, módulos, acabamentos encontrados
print("=== FAIXAS ENCONTRADAS ===")
print(sorted(df["FAIXA"].dropna().unique()))

print("\n=== MODULACOES ===")
print(sorted(df["MODULACAO"].dropna().unique()))

print("\n=== TIPO_ACAB ===")
print(sorted(df["TIPO_ACAB"].dropna().unique()))

print("\n=== EMBALAGEM ===")
print(sorted(df["EMBALAGEM"].dropna().unique()))

print("\n=== BASE_PE ===")
print(sorted(df["BASE_PE"].dropna().unique()))

print("\n=== COMP_MODULO (exemplos) ===")
print(sorted(df["COMP_MODULO"].dropna().unique())[:20])
'''

C3 = '''\
# =====================================================================
# CONFIG DA VALIDACAO — adapte conforme os valores impressos acima
# =====================================================================

# Ordem crescente de preço para cada faixa de tecido.
# FORNECIDO é especial: normalmente igual à faixa B (cliente fornece o tecido).
FAIXA_ORDEM = ["A", "B", "C", "D", "E", "F", "G", "H", "I", "J"]

# FORNECIDO: None = ignorar, "B" = deve ser igual à faixa B, "A" = igual à A, etc.
FORNECIDO_IGUAL_A_FAIXA = "B"

# Hierarquia de acabamento (None = sem validação de acabamento).
# Exemplo: PINTURA FOSCA < PINTURA MTX < PINTURA METALIZADO
ACAB_ORDEM = None
# ACAB_ORDEM = ["PINTURA FOSCA", "PINTURA MTX", "PINTURA METALIZADO"]

# Tolerância para considerar preços "iguais" (ex: FORNECIDO = FX B)
IGUAIS_LIMIAR_PCT = 0.0   # 0% = exato

# Tolerância de progressão de tamanho: mínimo esperado de acréscimo por CM.
# None = só verifica que preco maior > preco menor, sem mínimo.
MIN_PCT_POR_CM = None      # ex: 0.5 = espera pelo menos 0.5% por cm adicional

# Quantos σ para marcar outlier na progressão de faixas
OUTLIER_LIMIAR = 2.0

print("Config:")
print(f"  Faixas em ordem: {FAIXA_ORDEM}")
print(f"  FORNECIDO igual a faixa: {FORNECIDO_IGUAL_A_FAIXA}")
print(f"  Acabamento em ordem: {ACAB_ORDEM}")
'''

C4 = '''\
import re

def comp_total(s):
    """\'1.00M + 0.80M\' -> 1.80  |  \'1.10M\' -> 1.10"""
    if not s or str(s) == "nan":
        return 0.0
    nums = re.findall(r"\\d+[.,]\\d+", str(s).replace(",", "."))
    try:
        return round(sum(float(n) for n in nums), 4)
    except ValueError:
        return 0.0

def faixa_rank(f, ordem=FAIXA_ORDEM):
    f = str(f).strip().upper()
    if f in ordem:
        return ordem.index(f)
    if f == "FORNECIDO":
        return -1   # tratado separadamente
    return 9999

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

    faixa = str(row["FAIXA"]).strip()   if str(row["FAIXA"])    != "nan" else ""
    mod   = str(row["MODULACAO"]).strip() if str(row["MODULACAO"]) != "nan" else ""
    comp  = str(row["COMP_MODULO"]).strip() if str(row["COMP_MODULO"]) != "nan" else ""
    prof  = str(row["PROF_PRODUTO"]).strip() if str(row["PROF_PRODUTO"]) != "nan" else ""
    acab  = str(row["TIPO_ACAB"]).strip()   if str(row["TIPO_ACAB"])    != "nan" else ""
    emb   = str(row["EMBALAGEM"]).strip()   if str(row["EMBALAGEM"])    != "nan" else ""
    base  = str(row["BASE_PE"]).strip()     if str(row["BASE_PE"])      != "nan" else ""

    rows.append({
        "produto": prod,
        "modulacao": mod,
        "comp": comp,
        "comp_m": comp_total(comp),   # comprimento numérico para comparação
        "prof": prof,
        "acab": acab,
        "emb": emb,
        "base_pe": base,
        "faixa": faixa,
        "faixa_rank": faixa_rank(faixa),
        "preco": preco,
        "focco_id": row["PRECO_FOCCO_ID"],
    })

print(f"{len(rows)} linhas validas")
print(f"  Produtos   : {sorted({r[\'produto\'] for r in rows})}")
print(f"  Modulacoes : {sorted({r[\'modulacao\'] for r in rows})}")
print(f"  Faixas     : {sorted({r[\'faixa\'] for r in rows if r[\'faixa_rank\'] >= 0})}")
print(f"  Acabamentos: {sorted({r[\'acab\'] for r in rows if r[\'acab\']})}")
'''

C5 = '''\
import statistics
from collections import defaultdict

# ── 1. Progressão de faixa de tecido ─────────────────────────────────────────
# Grupo: (produto, modulacao, comp, prof, acab, emb, base_pe)
# Dentro do grupo: faixa B < C < D < E < ...

def grupo_faixa(r):
    return (r["produto"], r["modulacao"], r["comp"], r["prof"],
            r["acab"], r["emb"], r["base_pe"])

grupos_faixa = defaultdict(list)
for r in rows:
    if r["faixa_rank"] >= 0:   # ignora FORNECIDO por ora
        grupos_faixa[grupo_faixa(r)].append(r)

viol_faixa = []
delta_por_transicao = defaultdict(list)  # (fx1, fx2) -> [pct]

for chave, grp in grupos_faixa.items():
    if len(grp) < 2:
        continue
    grp_s = sorted(grp, key=lambda r: r["faixa_rank"])
    for i in range(len(grp_s) - 1):
        r1, r2 = grp_s[i], grp_s[i + 1]
        if r1["faixa_rank"] == r2["faixa_rank"]:
            continue
        pct = (r2["preco"] - r1["preco"]) / r1["preco"] * 100 if r1["preco"] else 0
        trans = (r1["faixa"], r2["faixa"])
        delta_por_transicao[trans].append(pct)
        if r2["preco"] < r1["preco"]:
            viol_faixa.append({
                "tipo": "FAIXA",
                "produto": r1["produto"], "mod": r1["modulacao"],
                "comp": r1["comp"], "acab": r1["acab"], "emb": r1["emb"],
                "f1": r1["faixa"], "p1": r1["preco"],
                "f2": r2["faixa"], "p2": r2["preco"], "pct": pct,
            })

# ── 2. FORNECIDO deve ser igual à faixa de referência ────────────────────────
viol_fornecido = []
if FORNECIDO_IGUAL_A_FAIXA:
    fornecido_rows = [r for r in rows if r["faixa"].upper() == "FORNECIDO"]
    for rf in fornecido_rows:
        chave = grupo_faixa(rf)
        ref_rows = [r for r in grupos_faixa.get(chave, [])
                    if r["faixa"] == FORNECIDO_IGUAL_A_FAIXA]
        if not ref_rows:
            continue
        rr = ref_rows[0]
        mp  = max(rf["preco"], rr["preco"])
        dp  = abs(rf["preco"] - rr["preco"]) / mp if mp else 0
        pct = (rf["preco"] - rr["preco"]) / rr["preco"] * 100 if rr["preco"] else 0
        if dp > IGUAIS_LIMIAR_PCT:
            viol_fornecido.append({
                "produto": rf["produto"], "mod": rf["modulacao"],
                "comp": rf["comp"], "acab": rf["acab"],
                "p_fornecido": rf["preco"], "p_ref": rr["preco"],
                "faixa_ref": FORNECIDO_IGUAL_A_FAIXA, "pct": pct,
            })

# ── 3. Progressão de comp_modulo ─────────────────────────────────────────────
# Grupo: (produto, modulacao, faixa, acab, emb, base_pe)
# Dentro: comp_m maior = preco maior

def grupo_comp(r):
    return (r["produto"], r["modulacao"], r["faixa"],
            r["acab"], r["emb"], r["base_pe"])

grupos_comp = defaultdict(list)
for r in rows:
    if r["comp_m"] > 0:
        grupos_comp[grupo_comp(r)].append(r)

viol_comp = []
delta_comp_pcts = []

for chave, grp in grupos_comp.items():
    if len(grp) < 2:
        continue
    grp_s = sorted(grp, key=lambda r: r["comp_m"])
    for i in range(len(grp_s) - 1):
        r1, r2 = grp_s[i], grp_s[i + 1]
        if r1["comp_m"] >= r2["comp_m"]:
            continue
        pct = (r2["preco"] - r1["preco"]) / r1["preco"] * 100 if r1["preco"] else 0
        delta_comp_pcts.append(pct)
        if r2["preco"] < r1["preco"]:
            viol_comp.append({
                "produto": r1["produto"], "mod": r1["modulacao"],
                "faixa": r1["faixa"], "acab": r1["acab"],
                "comp1": r1["comp"], "p1": r1["preco"],
                "comp2": r2["comp"], "p2": r2["preco"], "pct": pct,
            })

# ── 4. Progressão de acabamento ───────────────────────────────────────────────
viol_acab = []
delta_acab_pcts = defaultdict(list)

if ACAB_ORDEM:
    def grupo_acab(r):
        return (r["produto"], r["modulacao"], r["comp"],
                r["faixa"], r["emb"], r["base_pe"])

    grupos_acab = defaultdict(list)
    for r in rows:
        if r["acab"] in ACAB_ORDEM:
            grupos_acab[grupo_acab(r)].append(r)

    for chave, grp in grupos_acab.items():
        if len(grp) < 2:
            continue
        grp_s = sorted(grp, key=lambda r: ACAB_ORDEM.index(r["acab"]))
        for i in range(len(grp_s) - 1):
            r1, r2 = grp_s[i], grp_s[i + 1]
            if ACAB_ORDEM.index(r1["acab"]) == ACAB_ORDEM.index(r2["acab"]):
                continue
            pct = (r2["preco"] - r1["preco"]) / r1["preco"] * 100 if r1["preco"] else 0
            delta_acab_pcts[(r1["acab"], r2["acab"])].append(pct)
            if r2["preco"] < r1["preco"]:
                viol_acab.append({
                    "produto": r1["produto"], "mod": r1["modulacao"],
                    "comp": r1["comp"], "faixa": r1["faixa"],
                    "a1": r1["acab"], "p1": r1["preco"],
                    "a2": r2["acab"], "p2": r2["preco"], "pct": pct,
                })

tv = len(viol_faixa) + len(viol_fornecido) + len(viol_comp) + len(viol_acab)
print(f"Analise concluida: {tv} violacoes no total")
print(f"  Faixa        : {len(viol_faixa)}")
print(f"  FORNECIDO    : {len(viol_fornecido)}")
print(f"  Comp modulo  : {len(viol_comp)}")
print(f"  Acabamento   : {len(viol_acab)}")
'''

C6 = '''\
import statistics

SEP  = "=" * 72
SEP2 = "-" * 72

tv = len(viol_faixa) + len(viol_fornecido) + len(viol_comp) + len(viol_acab)
print(SEP)
print(f"RESULTADO: {\'SEM VIOLACOES\' if tv == 0 else f\'{tv} VIOLACAO(ES)\'}")
print(f"  Faixa de tecido  : {len(viol_faixa)}")
print(f"  FORNECIDO        : {len(viol_fornecido)}")
print(f"  Comp do modulo   : {len(viol_comp)}")
print(f"  Acabamento       : {len(viol_acab)}")
print(SEP)

# ── Acréscimos médios por transição de faixa ─────────────────────────────────
print("\n=== ACRESCIMO MEDIO POR TRANSICAO DE FAIXA ===")
print(f"  {\'TRANSICAO\':<12} {'MEDIA':>8} {'MIN':>8} {'MAX':>8} {'N':>5}  STATUS")
print(SEP2)
for i in range(len(FAIXA_ORDEM) - 1):
    f1, f2 = FAIXA_ORDEM[i], FAIXA_ORDEM[i + 1]
    pcts = delta_por_transicao.get((f1, f2), [])
    if not pcts:
        continue
    med = statistics.mean(pcts)
    mn  = min(pcts)
    mx  = max(pcts)
    std = statistics.stdev(pcts) if len(pcts) > 1 else 0
    status = "OK" if mn >= 0 else f"ATENCAO: {sum(1 for p in pcts if p < 0)} negativos"
    print(f"  {f1} -> {f2:<8} {med:>+7.1f}% {mn:>+7.1f}% {mx:>+7.1f}%  {len(pcts):>4}  {status}")

# ── Outliers de faixa ────────────────────────────────────────────────────────
print("\n=== OUTLIERS DE FAIXA (>{OUTLIER_LIMIAR}σ) ===")
outliers = []
for (f1, f2), pcts in delta_por_transicao.items():
    if len(pcts) < 3:
        continue
    try:
        med = statistics.mean(pcts)
        std = statistics.stdev(pcts)
        if std == 0:
            continue
        for r in rows:
            if r["faixa"] != f2:
                continue
            grp = [rr for rr in rows if grupo_faixa(rr) == grupo_faixa(r) and rr["faixa"] == f1]
            if not grp:
                continue
            r1 = grp[0]
            pct = (r["preco"] - r1["preco"]) / r1["preco"] * 100 if r1["preco"] else 0
            if abs(pct - med) > OUTLIER_LIMIAR * std:
                outliers.append({
                    "produto": r["produto"], "mod": r["modulacao"],
                    "comp": r["comp"], "acab": r["acab"],
                    "f1": f1, "p1": r1["preco"], "f2": f2, "p2": r["preco"],
                    "pct": pct, "med": med, "std": std,
                    "desvios": (pct - med) / std,
                })
    except statistics.StatisticsError:
        continue

if not outliers:
    print("  Nenhum outlier detectado.")
else:
    print(f"  {len(outliers)} outlier(s):")
    for o in sorted(outliers, key=lambda x: abs(x["desvios"]), reverse=True)[:20]:
        print(f"  {o[\'produto\']} | {o[\'mod\']} | {o[\'comp\']} | {o[\'acab\']}")
        print(f"    {o[\'f1\']} R${o[\'p1\']:,.2f} -> {o[\'f2\']} R${o[\'p2\']:,.2f}  ({o[\'pct\']:+.1f}%)  media={o[\'med\']:+.1f}%  {o[\'desvios\']:+.1f}σ")

# ── Violações de faixa ───────────────────────────────────────────────────────
if viol_faixa:
    print(f"\n=== VIOLACOES DE FAIXA ({len(viol_faixa)}) ===")
    for v in sorted(viol_faixa, key=lambda x: (x["produto"], x["mod"], x["comp"])):
        print(f"  {v[\'produto\']} | {v[\'mod\']} | COMP:{v[\'comp\']} | ACAB:{v[\'acab\']} | EMB:{v[\'emb\']}")
        print(f"    Faixa {v[\'f1\']}: R${v[\'p1\']:,.2f}  ->  Faixa {v[\'f2\']}: R${v[\'p2\']:,.2f}  ({v[\'pct\']:+.1f}%)")
else:
    print("\n=== FAIXA: SEM VIOLACOES ===")

# ── FORNECIDO ────────────────────────────────────────────────────────────────
if FORNECIDO_IGUAL_A_FAIXA:
    if viol_fornecido:
        print(f"\n=== FORNECIDO != FX {FORNECIDO_IGUAL_A_FAIXA} ({len(viol_fornecido)} casos) ===")
        for v in sorted(viol_fornecido, key=lambda x: abs(x["pct"]), reverse=True):
            print(f"  {v[\'produto\']} | {v[\'mod\']} | COMP:{v[\'comp\']} | ACAB:{v[\'acab\']}")
            print(f"    FORNECIDO R${v[\'p_fornecido\']:,.2f}  vs  FX {v[\'faixa_ref\']} R${v[\'p_ref\']:,.2f}  ({v[\'pct\']:+.1f}%)")
    else:
        print(f"\n=== FORNECIDO = FX {FORNECIDO_IGUAL_A_FAIXA}: SEM VIOLACOES ===")

# ── Progressão de comp ───────────────────────────────────────────────────────
if delta_comp_pcts:
    med = statistics.mean(delta_comp_pcts)
    std = statistics.stdev(delta_comp_pcts) if len(delta_comp_pcts) > 1 else 0
    print(f"\n=== PROGRESSAO DE COMP_MODULO ===")
    print(f"  Acrescimo medio por degrau de tamanho: {med:+.1f}%  (σ={std:.1f}%, n={len(delta_comp_pcts)})")
if viol_comp:
    print(f"  *** {len(viol_comp)} VIOLACAO(ES) — comp maior com preco menor ***")
    for v in sorted(viol_comp, key=lambda x: x["pct"])[:20]:
        print(f"  {v[\'produto\']} | {v[\'mod\']} | FX:{v[\'faixa\']} | ACAB:{v[\'acab\']}")
        print(f"    {v[\'comp1\']} R${v[\'p1\']:,.2f}  ->  {v[\'comp2\']} R${v[\'p2\']:,.2f}  ({v[\'pct\']:+.1f}%)")
else:
    print("\n=== COMP: SEM VIOLACOES ===")

# ── Acabamento ────────────────────────────────────────────────────────────────
if ACAB_ORDEM:
    if viol_acab:
        print(f"\n=== VIOLACOES DE ACABAMENTO ({len(viol_acab)}) ===")
        for v in sorted(viol_acab, key=lambda x: x["pct"])[:20]:
            print(f"  {v[\'produto\']} | {v[\'mod\']} | COMP:{v[\'comp\']} | FX:{v[\'faixa\']}")
            print(f"    {v[\'a1\']} R${v[\'p1\']:,.2f}  ->  {v[\'a2\']} R${v[\'p2\']:,.2f}  ({v[\'pct\']:+.1f}%)")
    else:
        print("\n=== ACABAMENTO: SEM VIOLACOES ===")
'''

C7 = '''\
# Tabela de progressão por faixa — para cada combinação (modulacao, comp, acab, emb)
# mostra os preços por faixa lado a lado e os deltas.

print("=== TABELA DE PROGRESSAO POR FAIXA ===")
print("Produto: " + (PRODUTO_ALVO or "todos") + f"  |  Tabela: {COD_PREVEN}")
print()

SEP = "-" * 90

faixas_disp = [f for f in FAIXA_ORDEM if any(r["faixa"] == f for r in rows)]

# Agrupa por (produto, modulacao, comp, prof, acab, emb, base_pe)
from collections import defaultdict
grupos = defaultdict(dict)
for r in rows:
    chave = (r["produto"], r["modulacao"], r["comp"], r["prof"],
             r["acab"], r["emb"], r["base_pe"])
    grupos[chave][r["faixa"]] = r["preco"]

# Ordena: produto, modulacao, comp_m, acab, emb
def sort_grupo(chave):
    from __main__ import comp_total
    return (chave[0], chave[1], comp_total(chave[2]), chave[4], chave[5])

cabecalho = f"  {'MOD':<20} {'COMP':<22} {'ACAB':<22} {'EMB':<16} {'BASE':<14} " + \
            "".join(f"  FX{f:<3}" for f in faixas_disp)
print(cabecalho)
print(SEP)

prev_prod = None
for chave in sorted(grupos.keys(), key=sort_grupo):
    prod, mod, comp, prof, acab, emb, base = chave
    if prod != prev_prod:
        print(f"\n  PRODUTO: {prod}")
        prev_prod = prod
    precos = grupos[chave]
    linha  = f"  {mod:<20} {comp:<22} {acab:<22} {emb:<16} {base:<14} "
    for f in faixas_disp:
        p = precos.get(f)
        linha += f"  {int(p):>5}" if p else f"  {'---':>5}"
    print(linha)

# Linha FORNECIDO separada
print()
grupos_forn = defaultdict(dict)
for r in rows:
    if r["faixa"].upper() == "FORNECIDO":
        chave = (r["produto"], r["modulacao"], r["comp"], r["prof"],
                 r["acab"], r["emb"], r["base_pe"])
        grupos_forn[chave]["FORNECIDO"] = r["preco"]

if grupos_forn:
    print("  FORNECIDO:")
    for chave in sorted(grupos_forn.keys(), key=sort_grupo):
        prod, mod, comp, prof, acab, emb, base = chave
        p = grupos_forn[chave].get("FORNECIDO", "")
        ref_p = grupos[chave].get(FORNECIDO_IGUAL_A_FAIXA or "B", "")
        delta  = ""
        if p and ref_p:
            pct = (p - ref_p) / ref_p * 100 if ref_p else 0
            delta = f"  (vs FX {FORNECIDO_IGUAL_A_FAIXA}: {pct:+.1f}%)"
        print(f"    {mod:<20} {comp:<22} {acab:<22} R${p:>8,.2f}{delta}")
'''

nb = {
    "nbformat": 4,
    "nbformat_minor": 5,
    "metadata": {
        "kernelspec": {"display_name":"Python 3","language":"python","name":"python3"},
        "language_info": {"name":"python"}
    },
    "cells": [
        md("# Validação de Preços — Estofados (Focco)\n\nValida:\n1. **Faixa de tecido**: A < B < C < D < E < F < G < H < I < J\n2. **FORNECIDO** = FX B (ou outra faixa de referência)\n3. **Comp do módulo**: tamanho maior = preço maior\n4. **Acabamento**: hierarquia opcional (FOSCA < MTX < METALIZADO)"),
        code(C1),
        code(C2),
        code(C3),
        code(C4),
        code(C5),
        code(C6),
        code(C7),
    ]
}

out = os.path.join(DIR, "VALIDAR PRECOS ESTOFADOS.ipynb")
with open(out, "w", encoding="utf-8") as f:
    json.dump(nb, f, ensure_ascii=False, indent=1)
print(f"Criado: {out}")
