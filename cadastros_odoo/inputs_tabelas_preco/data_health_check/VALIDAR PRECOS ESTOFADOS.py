#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Validação de Preços — Estofados (Focco)
========================================
Uso:
    python "VALIDAR PRECOS ESTOFADOS.py"                         # usa config abaixo
    python "VALIDAR PRECOS ESTOFADOS.py" ADANA                   # produto específico
    python "VALIDAR PRECOS ESTOFADOS.py" ADANA 155               # produto + tabela
"""

import sys, os, re, statistics, webbrowser
from collections import defaultdict
from datetime import datetime
from sqlalchemy import create_engine
import pandas as pd

# ===========================================================================
# ★  CONFIG  ★
# ===========================================================================
COD_PREVEN   = 155
PRODUTO_ALVO = None        # None = todos os produtos da tabela

# Ordem crescente de preço para faixas de tecido
FAIXA_ORDEM = ["A", "B", "C", "D", "E", "F", "G", "H", "I", "J"]

# FORNECIDO: deve ser igual a qual faixa? None = ignorar
FORNECIDO_IGUAL_A_FAIXA = "B"

# Hierarquia de acabamento. None = sem validação
ACAB_ORDEM = None
# ACAB_ORDEM = ["PINTURA FOSCA", "PINTURA MTX", "PINTURA METALIZADO"]

# Tolerâncias
IGUAIS_LIMIAR_PCT        = 0.00   # 0% = exato
PROPORCIONAIS_LIMIAR_PCT = 0.02
OUTLIER_LIMIAR           = 2.0    # σ para marcar outlier

# Paleta
COR_P  = "#484c40"
COR_PE = "#2d3027"
COR_PL = "#6b7060"
COR_BG = "#f4f4f2"

# Focco
DB_URL = "postgresql+psycopg2://consulta:consulta@10.1.57.244:5432/dwfocco"
# ===========================================================================


def comp_total(s):
    """'1.00M + 0.80M' → 1.80"""
    if not s:
        return 0.0
    nums = re.findall(r"\d+[.,]\d+", str(s).replace(",", "."))
    try:
        return round(sum(float(n) for n in nums), 4)
    except ValueError:
        return 0.0


def faixa_rank(f, ordem=FAIXA_ORDEM):
    f = str(f).strip().upper()
    if f in ordem:
        return ordem.index(f)
    return 9999


def safe(v):
    return str(v).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


# ---------------------------------------------------------------------------
# QUERY
# ---------------------------------------------------------------------------

def carregar_dados(cod_preven, produto_alvo):
    filtro = (
        f"AND REGEXP_REPLACE(TITENS.DESC_TECNICA, '^MODELO\\s+', '', 'i') ILIKE '{produto_alvo}'"
        if produto_alvo else ""
    )

    query = f"""
    WITH base AS (
        SELECT
            TPRECOSVEN_IT.ID           AS PRECO_FOCCO_ID,
            TITENS.COD_ITEM,
            TPRECOSVEN.COD_PREVEN,
            TPRECOSVEN.DESCRICAO       AS TABELA_DESCRICAO,
            REGEXP_REPLACE(TITENS.DESC_TECNICA, '^MODELO\\s+', '', 'i') AS PRODUTO,
            TCARACTERISTICAS.COD_CAR,
            TVARIAVEIS.MNEMONICO,
            TITENS_CAR.SEQ,
            TPRECOSVEN_IT.PRECO        AS PRECO
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
          AND TPRECOSVEN.COD_PREVEN = {cod_preven}
          {filtro}
    )
    SELECT
        PRECO_FOCCO_ID, COD_ITEM, COD_PREVEN, TABELA_DESCRICAO, PRODUTO,
        MAX(MNEMONICO) FILTER (WHERE COD_CAR = 'MODULACAO')     AS MODULACAO,
        MAX(MNEMONICO) FILTER (WHERE COD_CAR = 'COMP_MODULO')   AS COMP_MODULO,
        MAX(MNEMONICO) FILTER (WHERE COD_CAR = 'PROF_PRODUTO')  AS PROF_PRODUTO,
        MAX(MNEMONICO) FILTER (WHERE COD_CAR = 'TIPO_ACAB')     AS TIPO_ACAB,
        MAX(MNEMONICO) FILTER (WHERE COD_CAR = 'EMBAL_REFORCADA') AS EMBALAGEM,
        MAX(MNEMONICO) FILTER (WHERE COD_CAR = 'BASE_PE')       AS BASE_PE,
        REPLACE(
            MAX(MNEMONICO) FILTER (WHERE COD_CAR = 'FX_TEC'),
            'FX ', ''
        ) AS FAIXA,
        PRECO
    FROM base
    GROUP BY PRECO_FOCCO_ID, COD_ITEM, COD_PREVEN, TABELA_DESCRICAO, PRODUTO, PRECO
    ORDER BY PRODUTO, MODULACAO, COMP_MODULO, FAIXA, TIPO_ACAB, EMBALAGEM;
    """

    engine = create_engine(DB_URL)
    df = pd.read_sql(query, engine)
    engine.dispose()
    return df


def build_rows(df):
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

        def s(col):
            v = str(row.get(col, "")).strip()
            return "" if v == "nan" else v

        faixa = s("FAIXA")
        mod   = s("MODULACAO") or prod
        comp  = s("COMP_MODULO")
        prof  = s("PROF_PRODUTO")
        acab  = s("TIPO_ACAB")
        emb   = s("EMBALAGEM")
        base  = s("BASE_PE")
        tab   = s("TABELA_DESCRICAO")

        rows.append({
            "produto":   prod,
            "tabela":    tab,
            "modulacao": mod,
            "comp":      comp,
            "comp_m":    comp_total(comp),
            "prof":      prof,
            "acab":      acab,
            "emb":       emb,
            "base_pe":   base,
            "faixa":     faixa,
            "faixa_rank": faixa_rank(faixa),
            "preco":     preco,
        })
    return rows


# ---------------------------------------------------------------------------
# ANÁLISE
# ---------------------------------------------------------------------------

def analisar(rows):
    def gf(r):   # grupo faixa
        return (r["produto"], r["modulacao"], r["comp"], r["prof"],
                r["acab"], r["emb"], r["base_pe"])

    def gc(r):   # grupo comp
        return (r["produto"], r["modulacao"], r["faixa"],
                r["acab"], r["emb"], r["base_pe"])

    # 1. Progressão de faixa
    grupos_faixa = defaultdict(list)
    for r in rows:
        if 0 <= r["faixa_rank"] < 9999:
            grupos_faixa[gf(r)].append(r)

    viol_faixa          = []
    delta_por_transicao = defaultdict(list)

    for chave, grp in grupos_faixa.items():
        if len(grp) < 2:
            continue
        grp_s = sorted(grp, key=lambda r: r["faixa_rank"])
        for i in range(len(grp_s) - 1):
            r1, r2 = grp_s[i], grp_s[i + 1]
            if r1["faixa_rank"] == r2["faixa_rank"]:
                continue
            pct = (r2["preco"] - r1["preco"]) / r1["preco"] * 100 if r1["preco"] else 0
            delta_por_transicao[(r1["faixa"], r2["faixa"])].append(pct)
            if r2["preco"] < r1["preco"]:
                viol_faixa.append({
                    "tipo": "FAIXA",
                    "produto": r1["produto"], "mod": r1["modulacao"],
                    "comp": r1["comp"], "acab": r1["acab"], "emb": r1["emb"],
                    "f1": r1["faixa"], "p1": r1["preco"],
                    "f2": r2["faixa"], "p2": r2["preco"], "pct": pct,
                })

    # 2. FORNECIDO
    viol_fornecido = []
    if FORNECIDO_IGUAL_A_FAIXA:
        for rf in [r for r in rows if r["faixa"].upper() == "FORNECIDO"]:
            ref_rows = [r for r in grupos_faixa.get(gf(rf), [])
                        if r["faixa"] == FORNECIDO_IGUAL_A_FAIXA]
            if not ref_rows:
                continue
            rr  = ref_rows[0]
            mp  = max(rf["preco"], rr["preco"])
            dp  = abs(rf["preco"] - rr["preco"]) / mp if mp else 0
            pct = (rf["preco"] - rr["preco"]) / rr["preco"] * 100 if rr["preco"] else 0
            if dp > IGUAIS_LIMIAR_PCT:
                viol_fornecido.append({
                    "produto": rf["produto"], "mod": rf["modulacao"],
                    "comp": rf["comp"], "acab": rf["acab"],
                    "p_forn": rf["preco"], "p_ref": rr["preco"],
                    "faixa_ref": FORNECIDO_IGUAL_A_FAIXA, "pct": pct,
                })

    # 3. Progressão de comp
    grupos_comp = defaultdict(list)
    for r in rows:
        if r["comp_m"] > 0:
            grupos_comp[gc(r)].append(r)

    viol_comp      = []
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

    # 4. Acabamento
    viol_acab      = []
    delta_acab_pcts = defaultdict(list)

    if ACAB_ORDEM:
        def ga(r):
            return (r["produto"], r["modulacao"], r["comp"],
                    r["faixa"], r["emb"], r["base_pe"])
        grupos_acab = defaultdict(list)
        for r in rows:
            if r["acab"] in ACAB_ORDEM:
                grupos_acab[ga(r)].append(r)
        for _, grp in grupos_acab.items():
            if len(grp) < 2:
                continue
            grp_s = sorted(grp, key=lambda r: ACAB_ORDEM.index(r["acab"]))
            for i in range(len(grp_s) - 1):
                r1, r2 = grp_s[i], grp_s[i + 1]
                pct = (r2["preco"] - r1["preco"]) / r1["preco"] * 100 if r1["preco"] else 0
                delta_acab_pcts[(r1["acab"], r2["acab"])].append(pct)
                if r2["preco"] < r1["preco"]:
                    viol_acab.append({
                        "produto": r1["produto"], "mod": r1["modulacao"],
                        "comp": r1["comp"], "faixa": r1["faixa"],
                        "a1": r1["acab"], "p1": r1["preco"],
                        "a2": r2["acab"], "p2": r2["preco"], "pct": pct,
                    })

    # 5. Outliers de faixa
    outliers = []
    for (f1, f2), pcts in delta_por_transicao.items():
        if len(pcts) < 3:
            continue
        try:
            med = statistics.mean(pcts)
            std = statistics.stdev(pcts)
            if std == 0:
                continue
        except statistics.StatisticsError:
            continue
        for chave, grp in grupos_faixa.items():
            rows_f2 = [r for r in grp if r["faixa"] == f2]
            rows_f1 = [r for r in grp if r["faixa"] == f1]
            if not rows_f2 or not rows_f1:
                continue
            r2, r1 = rows_f2[0], rows_f1[0]
            pct = (r2["preco"] - r1["preco"]) / r1["preco"] * 100 if r1["preco"] else 0
            desvios = (pct - med) / std
            if abs(desvios) > OUTLIER_LIMIAR:
                outliers.append({
                    "produto": r1["produto"], "mod": r1["modulacao"],
                    "comp": r1["comp"], "acab": r1["acab"],
                    "f1": f1, "p1": r1["preco"],
                    "f2": f2, "p2": r2["preco"],
                    "pct": pct, "med": med, "std": std, "desvios": desvios,
                    "is_viol": r2["preco"] < r1["preco"],
                })

    return {
        "viol_faixa":          viol_faixa,
        "viol_fornecido":      viol_fornecido,
        "viol_comp":           viol_comp,
        "viol_acab":           viol_acab,
        "outliers":            sorted(outliers, key=lambda x: abs(x["desvios"]), reverse=True),
        "delta_transicao":     dict(delta_por_transicao),
        "delta_comp_pcts":     delta_comp_pcts,
        "delta_acab_pcts":     dict(delta_acab_pcts),
        "grupos_faixa":        grupos_faixa,
    }


# ---------------------------------------------------------------------------
# HTML
# ---------------------------------------------------------------------------

CSS = f"""
*{{margin:0;padding:0;box-sizing:border-box}}
body{{font-family:"Segoe UI",Tahoma,sans-serif;background:{COR_BG};color:{COR_PE};padding:24px}}
.wrap{{max-width:1500px;margin:0 auto}}
.header{{background:linear-gradient(135deg,{COR_PE},{COR_P});color:#fff;
         padding:32px 40px;border-radius:12px 12px 0 0}}
.header h1{{font-size:1.8rem;margin-bottom:6px}}
.header p{{opacity:.85;font-size:.9rem}}
.status{{color:#fff;padding:14px 40px;font-size:1.1rem;font-weight:700}}
.info-bar{{background:#fff;padding:16px 40px;border-bottom:3px solid #e4e4e0;
           display:flex;gap:12px;flex-wrap:wrap}}
.card{{background:{COR_BG};border-left:4px solid {COR_P};padding:9px 13px;
       border-radius:6px;min-width:115px}}
.card-label{{font-size:.69rem;color:{COR_PL};text-transform:uppercase;
             letter-spacing:.5px;margin-bottom:2px}}
.card-value{{font-size:1rem;font-weight:700}}
.content{{background:#fff;padding:30px 40px}}
.section{{margin-bottom:48px}}
.sec-title{{font-size:1.2rem;color:{COR_PE};padding-bottom:7px;
            border-bottom:3px solid {COR_P};margin-bottom:18px;font-weight:700}}
.sub-title{{font-size:.95rem;color:{COR_PE};margin:18px 0 8px;font-weight:600}}
.alert-ok{{background:#d5ead5;border-left:5px solid #27ae60;padding:11px 14px;
           border-radius:6px;margin:8px 0;font-size:.88rem}}
.alert-err{{background:#fdedec;border-left:5px solid #c0392b;padding:11px 14px;
            border-radius:6px;margin:8px 0}}
.alert-warn{{background:#fef9e7;border-left:5px solid #e67e22;padding:11px 14px;
             border-radius:6px;margin:8px 0}}
.badge-ok{{background:#27ae60;color:#fff;padding:2px 8px;border-radius:10px;
           font-size:.72rem;font-weight:600;white-space:nowrap}}
.badge-err{{background:#c0392b;color:#fff;padding:2px 8px;border-radius:10px;
            font-size:.72rem;font-weight:600;white-space:nowrap}}
.badge-warn{{background:#e67e22;color:#fff;padding:2px 8px;border-radius:10px;
             font-size:.72rem;font-weight:600;white-space:nowrap}}
table{{width:100%;border-collapse:collapse;font-size:.83rem;margin-top:8px}}
thead{{background:{COR_P};color:#fff}}
th{{padding:7px 10px;text-align:left;font-weight:600}}
td{{padding:6px 10px;border-bottom:1px solid #ebebeb;vertical-align:top}}
tr:hover td{{background:#f8f8f6}}
.num{{text-align:right;font-variant-numeric:tabular-nums}}
.viol-row{{background:#fdedec}}
.warn-row{{background:#fffbe6}}
.pct-ok{{color:#27ae60;font-weight:600}}
.pct-neg{{color:#c0392b;font-weight:700}}
.pct-warn{{color:#e67e22;font-weight:700}}
.pct-dash{{color:#ccc}}
/* carrossel */
.carousel-nav{{display:flex;align-items:center;gap:10px;margin-bottom:10px;flex-wrap:wrap}}
.btn-nav{{background:{COR_P};color:#fff;border:none;padding:7px 14px;border-radius:6px;
          cursor:pointer;font-size:.95rem;font-weight:700;transition:background .15s}}
.btn-nav:hover{{background:{COR_PE}}}
.btn-nav:disabled{{background:#ccc;cursor:default}}
.carousel-dots{{display:flex;gap:7px}}
.dot{{width:9px;height:9px;border-radius:50%;background:#ccc;cursor:pointer;transition:background .2s}}
.dot.active{{background:{COR_P}}}
.slide-counter{{font-size:.84rem;color:{COR_PL}}}
.slide{{display:none}}.slide.active{{display:block}}
.slide-head{{background:{COR_P};color:#fff;padding:9px 16px;
             border-radius:8px 8px 0 0;font-weight:700;font-size:.92rem}}
.slide-body{{border:1px solid #ddd;border-top:none;border-radius:0 0 8px 8px;overflow-x:auto}}
/* tabela pivot de faixas */
.pivot-tbl{{width:auto;min-width:100%;border-collapse:collapse;font-size:.8rem}}
.pivot-tbl thead{{background:{COR_PE};color:#fff}}
.pivot-tbl th{{padding:7px 10px;font-weight:600;white-space:nowrap;text-align:center}}
.pivot-tbl th.left{{text-align:left}}
.pivot-tbl td{{padding:6px 10px;border-bottom:1px solid #ebebeb;white-space:nowrap}}
.pivot-tbl tr:hover td{{background:#f8f8f6}}
.pivot-tbl td.comp-cell{{font-weight:600;color:{COR_PE};text-align:left}}
.pivot-tbl td.acab-cell{{color:{COR_PL};font-size:.77rem;text-align:left}}
.pivot-tbl td.preco-cell{{text-align:right;font-variant-numeric:tabular-nums}}
.pivot-tbl td.preco-ok{{}}
.pivot-tbl td.preco-viol{{background:#fdedec;color:#c0392b;font-weight:700}}
.pivot-tbl td.preco-warn{{background:#fffbe6;color:#e67e22;font-weight:600}}
.pivot-tbl td.preco-forn{{background:#eaf0fb;color:#2260a0;font-style:italic}}
.pivot-tbl td.preco-empty{{color:#ccc;text-align:center}}
.delta-row td{{font-size:.74rem;color:{COR_PL};border-bottom:2px solid #ddd;
               text-align:center;padding:3px 10px;background:#fafaf8}}
.delta-ok{{color:#27ae60}}.delta-neg{{color:#c0392b;font-weight:700}}
.delta-warn{{color:#e67e22;font-weight:600}}
.footer{{background:{COR_PE};color:#fff;padding:12px 40px;text-align:center;
         font-size:.81rem;border-radius:0 0 12px 12px;opacity:.93}}
"""


def gerar_html(rows, resultado, produto_nome, tabela_nome):
    vf  = resultado["viol_faixa"]
    vfn = resultado["viol_fornecido"]
    vc  = resultado["viol_comp"]
    va  = resultado["viol_acab"]
    out = resultado["outliers"]
    dt  = resultado["delta_transicao"]
    dcp = resultado["delta_comp_pcts"]
    gf  = resultado["grupos_faixa"]

    tv      = len(vf) + len(vfn) + len(vc) + len(va)
    n_out   = len(out)
    status_cor = "#27ae60" if tv == 0 else "#c0392b"
    status_str = ("✓ TODOS OS PREÇOS CONSISTENTES" if tv == 0
                  else f"⚠ {tv} INCONSISTÊNCIA(S) ENCONTRADA(S)")

    mods_disp = sorted({r["modulacao"] for r in rows})
    faixas_disp = [f for f in FAIXA_ORDEM if any(r["faixa"] == f for r in rows)]
    tem_fornecido = any(r["faixa"].upper() == "FORNECIDO" for r in rows)

    # conjunto de (chave_grupo, faixa) com violação
    chaves_viol = set()
    for v in vf:
        chaves_viol.add((v["produto"], v["mod"], v["comp"], v["acab"], v["emb"], v["f2"]))
    chaves_out = set()
    for o in out:
        chaves_out.add((o["produto"], o["mod"], o["comp"], o["acab"], o["f2"]))

    html = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width,initial-scale=1.0">
  <title>Análise de Preços — {safe(produto_nome)}</title>
  <style>{CSS}</style>
</head>
<body>
<div class="wrap">
  <div class="header">
    <h1>🛋 Análise de Preços — {safe(produto_nome)}</h1>
    <p>{safe(tabela_nome)} &nbsp;·&nbsp; {len(rows)} configurações
       &nbsp;·&nbsp; Gerado em {datetime.now().strftime('%d/%m/%Y às %H:%M')}</p>
  </div>
  <div class="status" style="background:{status_cor}">{status_str}</div>
  <div class="info-bar">
    <div class="card"><div class="card-label">Configurações</div>
      <div class="card-value">{len(rows)}</div></div>
    <div class="card"><div class="card-label">Modulações</div>
      <div class="card-value">{len(mods_disp)}</div></div>
    <div class="card"><div class="card-label">Faixas</div>
      <div class="card-value">{len(faixas_disp)}</div></div>
    <div class="card"><div class="card-label">Viol. faixa</div>
      <div class="card-value" style="color:{'#c0392b' if vf else '#27ae60'}">{len(vf)}</div></div>
    <div class="card"><div class="card-label">Viol. tamanho</div>
      <div class="card-value" style="color:{'#c0392b' if vc else '#27ae60'}">{len(vc)}</div></div>
    <div class="card"><div class="card-label">FORNECIDO</div>
      <div class="card-value" style="color:{'#c0392b' if vfn else '#27ae60'}">{len(vfn)} dif.</div></div>
    <div class="card"><div class="card-label">Outliers</div>
      <div class="card-value" style="color:{'#e67e22' if n_out else '#27ae60'}">{n_out}</div></div>
  </div>
  <div class="content">
"""

    # ── Seção 1: acréscimos médios por transição de faixa ────────────────────
    html += '<div class="section">\n'
    html += f'<h2 class="sec-title">1. Progressão de Faixa de Tecido</h2>\n'

    trans_com_dados = [(FAIXA_ORDEM[i], FAIXA_ORDEM[i+1])
                       for i in range(len(FAIXA_ORDEM)-1)
                       if (FAIXA_ORDEM[i], FAIXA_ORDEM[i+1]) in dt]

    if trans_com_dados:
        html += ('<table><thead><tr>'
                 '<th>Transição</th>'
                 '<th class="num">Média</th>'
                 '<th class="num">Mín</th>'
                 '<th class="num">Máx</th>'
                 '<th class="num">σ</th>'
                 '<th class="num">n</th>'
                 '<th>Status</th>'
                 '</tr></thead><tbody>\n')
        for f1, f2 in trans_com_dados:
            pcts   = dt.get((f1, f2), [])
            med    = statistics.mean(pcts)
            mn     = min(pcts)
            mx     = max(pcts)
            std    = statistics.stdev(pcts) if len(pcts) > 1 else 0
            n_neg  = sum(1 for p in pcts if p < 0)
            status = (f'<span class="badge-err">{n_neg} negativo(s)</span>'
                      if n_neg else '<span class="badge-ok">OK</span>')
            cls_med = "pct-ok" if med >= 0 else "pct-neg"
            cls_mn  = "pct-ok" if mn >= 0 else "pct-neg"
            html += (f'<tr>'
                     f'<td><strong>FX {f1} → FX {f2}</strong></td>'
                     f'<td class="num {cls_med}">{med:+.2f}%</td>'
                     f'<td class="num {cls_mn}">{mn:+.2f}%</td>'
                     f'<td class="num pct-ok">{mx:+.2f}%</td>'
                     f'<td class="num">{std:.2f}%</td>'
                     f'<td class="num">{len(pcts)}</td>'
                     f'<td>{status}</td>'
                     f'</tr>\n')
        html += '</tbody></table>\n'

    if not vf:
        html += '<div class="alert-ok" style="margin-top:12px"><strong>✓ Todos os preços seguem a hierarquia de faixas.</strong></div>\n'
    else:
        html += f'<div class="alert-err" style="margin-top:12px"><strong>⚠ {len(vf)} violação(ões) de hierarquia de faixa:</strong>\n'
        html += ('<table style="margin-top:8px"><thead><tr>'
                 '<th>Produto</th><th>Modulação</th><th>Comp</th><th>Acabamento</th><th>Emb</th>'
                 '<th>Faixa A</th><th class="num">Preço A</th>'
                 '<th>Faixa B</th><th class="num">Preço B</th>'
                 '<th class="num">Var.</th>'
                 '</tr></thead><tbody>\n')
        for v in sorted(vf, key=lambda x: (x["produto"], x["mod"], x["comp"])):
            html += (f'<tr class="viol-row">'
                     f'<td>{safe(v["produto"])}</td><td>{safe(v["mod"])}</td>'
                     f'<td>{safe(v["comp"])}</td><td>{safe(v["acab"])}</td><td>{safe(v["emb"])}</td>'
                     f'<td>FX {v["f1"]}</td><td class="num">R${v["p1"]:,.2f}</td>'
                     f'<td>FX {v["f2"]}</td><td class="num">R${v["p2"]:,.2f}</td>'
                     f'<td class="num pct-neg">{v["pct"]:+.1f}%</td>'
                     f'</tr>\n')
        html += '</tbody></table></div>\n'

    # FORNECIDO
    if FORNECIDO_IGUAL_A_FAIXA:
        html += f'<h3 class="sub-title">FORNECIDO (deve = FX {FORNECIDO_IGUAL_A_FAIXA})</h3>\n'
        if not vfn:
            html += '<div class="alert-ok"><strong>✓ FORNECIDO igual à faixa de referência em todos os casos.</strong></div>\n'
        else:
            html += f'<div class="alert-warn"><strong>⚠ {len(vfn)} caso(s) com diferença:</strong>\n'
            html += ('<table style="margin-top:8px"><thead><tr>'
                     '<th>Produto</th><th>Mod</th><th>Comp</th><th>Acab</th>'
                     f'<th class="num">FORNECIDO</th><th class="num">FX {FORNECIDO_IGUAL_A_FAIXA}</th>'
                     '<th class="num">Δ%</th></tr></thead><tbody>\n')
            for v in sorted(vfn, key=lambda x: abs(x["pct"]), reverse=True):
                cls = "pct-neg" if v["pct"] < 0 else "pct-warn"
                html += (f'<tr class="warn-row">'
                         f'<td>{safe(v["produto"])}</td><td>{safe(v["mod"])}</td>'
                         f'<td>{safe(v["comp"])}</td><td>{safe(v["acab"])}</td>'
                         f'<td class="num">R${v["p_forn"]:,.2f}</td>'
                         f'<td class="num">R${v["p_ref"]:,.2f}</td>'
                         f'<td class="num {cls}">{v["pct"]:+.1f}%</td>'
                         f'</tr>\n')
            html += '</tbody></table></div>\n'

    html += '</div>\n'

    # ── Seção 2: progressão de tamanho ───────────────────────────────────────
    html += '<div class="section">\n'
    html += f'<h2 class="sec-title">2. Progressão de Tamanho (Comp do Módulo)</h2>\n'

    if dcp:
        med = statistics.mean(dcp)
        std = statistics.stdev(dcp) if len(dcp) > 1 else 0
        cls = "pct-ok" if med >= 0 else "pct-neg"
        html += (f'<p style="font-size:.88rem;margin-bottom:10px">'
                 f'Acréscimo médio por degrau de tamanho: '
                 f'<strong class="{cls}">{med:+.1f}%</strong>'
                 f' &nbsp;(σ={std:.1f}%, n={len(dcp)})</p>\n')

    if not vc:
        html += '<div class="alert-ok"><strong>✓ Módulos maiores têm preços maiores em todos os casos.</strong></div>\n'
    else:
        html += f'<div class="alert-err"><strong>⚠ {len(vc)} caso(s): módulo maior com preço menor:</strong>\n'
        html += ('<table style="margin-top:8px"><thead><tr>'
                 '<th>Produto</th><th>Mod</th><th>Faixa</th><th>Acab</th>'
                 '<th>Comp menor</th><th class="num">Preço</th>'
                 '<th>Comp maior</th><th class="num">Preço</th>'
                 '<th class="num">Var.</th></tr></thead><tbody>\n')
        for v in sorted(vc, key=lambda x: x["pct"]):
            html += (f'<tr class="viol-row">'
                     f'<td>{safe(v["produto"])}</td><td>{safe(v["mod"])}</td>'
                     f'<td>FX {v["faixa"]}</td><td>{safe(v["acab"])}</td>'
                     f'<td>{safe(v["comp1"])}</td><td class="num">R${v["p1"]:,.2f}</td>'
                     f'<td>{safe(v["comp2"])}</td><td class="num">R${v["p2"]:,.2f}</td>'
                     f'<td class="num pct-neg">{v["pct"]:+.1f}%</td>'
                     f'</tr>\n')
        html += '</tbody></table></div>\n'

    # Acabamento
    if ACAB_ORDEM and (va or resultado["delta_acab_pcts"]):
        html += f'<h3 class="sub-title">Progressão de Acabamento</h3>\n'
        dap = resultado["delta_acab_pcts"]
        if dap:
            html += ('<table style="width:auto"><thead><tr>'
                     '<th>Transição</th><th class="num">Média</th>'
                     '<th class="num">Mín</th><th class="num">Máx</th><th class="num">n</th>'
                     '</tr></thead><tbody>\n')
            for i in range(len(ACAB_ORDEM)-1):
                pair = (ACAB_ORDEM[i], ACAB_ORDEM[i+1])
                pcts = dap.get(pair, [])
                if not pcts:
                    continue
                med = statistics.mean(pcts)
                html += (f'<tr><td>{pair[0]} → {pair[1]}</td>'
                         f'<td class="num {"pct-ok" if med>=0 else "pct-neg"}">{med:+.1f}%</td>'
                         f'<td class="num">{min(pcts):+.1f}%</td>'
                         f'<td class="num">{max(pcts):+.1f}%</td>'
                         f'<td class="num">{len(pcts)}</td></tr>\n')
            html += '</tbody></table>\n'
        if not va:
            html += '<div class="alert-ok"><strong>✓ Acabamentos respeitam a hierarquia.</strong></div>\n'

    html += '</div>\n'

    # ── Seção 3: outliers ─────────────────────────────────────────────────────
    html += '<div class="section">\n'
    html += f'<h2 class="sec-title">3. Outliers de Faixa (&gt;{OUTLIER_LIMIAR:.0f}σ)</h2>\n'

    if not out:
        html += '<div class="alert-ok"><strong>✓ Nenhum outlier detectado nas transições de faixa.</strong></div>\n'
    else:
        html += (f'<p style="font-size:.84rem;color:{COR_PL};margin-bottom:10px">'
                 f'Transições cujo acréscimo % desvia mais de {OUTLIER_LIMIAR:.0f}σ da média.</p>\n')
        html += ('<table><thead><tr>'
                 '<th>Produto</th><th>Mod</th><th>Comp</th><th>Acab</th>'
                 '<th>Transição</th>'
                 '<th class="num">Preço A</th><th class="num">Preço B</th>'
                 '<th class="num">Δ%</th><th class="num">Média</th><th class="num">Desvios</th>'
                 '</tr></thead><tbody>\n')
        for o in out[:50]:
            row_cls = "viol-row" if o["is_viol"] else "warn-row"
            cls_pct = "pct-neg" if o["pct"] < 0 else "pct-warn"
            html += (f'<tr class="{row_cls}">'
                     f'<td>{safe(o["produto"])}</td><td>{safe(o["mod"])}</td>'
                     f'<td>{safe(o["comp"])}</td><td>{safe(o["acab"])}</td>'
                     f'<td>FX {o["f1"]} → FX {o["f2"]}</td>'
                     f'<td class="num">R${o["p1"]:,.2f}</td>'
                     f'<td class="num">R${o["p2"]:,.2f}</td>'
                     f'<td class="num {cls_pct}">{o["pct"]:+.1f}%</td>'
                     f'<td class="num">{o["med"]:+.1f}%</td>'
                     f'<td class="num {"pct-neg" if abs(o["desvios"]) > 3 else "pct-warn"}">'
                     f'{o["desvios"]:+.1f}σ</td>'
                     f'</tr>\n')
        html += '</tbody></table>\n'

    html += '</div>\n'

    # ── Seção 4: carrossel por modulação (tabela pivot) ───────────────────────
    html += '<div class="section">\n'
    html += '<h2 class="sec-title">4. Preços por Modulação — Tabela por Faixa</h2>\n'

    faixas_cabecalho = faixas_disp + (["FORN"] if tem_fornecido else [])
    mods_js = ", ".join(f'"{safe(m)}"' for m in mods_disp)

    html += '<div class="carousel-nav">\n'
    html += '  <button class="btn-nav" id="c-prev" onclick="moveSlide(-1)" disabled>◀ Anterior</button>\n'
    html += '  <div class="carousel-dots" id="c-dots">\n'
    for i, m in enumerate(mods_disp):
        html += f'    <div class="dot{"  active" if i==0 else ""}" onclick="goSlide({i})" title="{safe(m)}"></div>\n'
    html += '  </div>\n'
    next_dis = ' disabled' if len(mods_disp) <= 1 else ''
    html += f'  <button class="btn-nav" id="c-next" onclick="moveSlide(1)"{next_dis}>Próximo ▶</button>\n'
    html += '  <span class="slide-counter" id="c-label"></span>\n'
    html += '</div>\n'

    for idx, mod in enumerate(mods_disp):
        # filtra linhas desta modulação e ordena por comp_m, acab, emb
        mod_rows = [r for r in rows if r["modulacao"] == mod]
        chaves_mod = sorted(
            {(r["comp"], r["comp_m"], r["prof"], r["acab"], r["emb"], r["base_pe"])
             for r in mod_rows},
            key=lambda x: (x[1], x[2], x[3], x[4], x[5])
        )

        html += f'<div class="slide{"  active" if idx==0 else ""}" id="slide_{idx}">\n'
        html += f'<div class="slide-head">📦 {safe(mod)} &nbsp;·&nbsp; {len(chaves_mod)} variantes</div>\n'
        html += '<div class="slide-body">\n'
        html += '<table class="pivot-tbl"><thead><tr>\n'
        html += f'  <th class="left">Comp</th>\n'
        html += f'  <th class="left">Acabamento</th>\n'
        html += f'  <th class="left">Emb</th>\n'
        if any(r["base_pe"] for r in mod_rows):
            html += f'  <th class="left">Base/Pé</th>\n'
        for f in faixas_disp:
            html += f'  <th>FX {f}</th>\n'
        if tem_fornecido:
            html += f'  <th>FORN.</th>\n'
        html += '</tr></thead>\n<tbody>\n'

        tem_base = any(r["base_pe"] for r in mod_rows)
        prev_comp = None

        for (comp, comp_m, prof, acab, emb, base) in chaves_mod:
            # linha separadora quando muda o comp
            if prev_comp is not None and comp != prev_comp:
                ncols = 3 + (1 if tem_base else 0) + len(faixas_cabecalho)
                html += f'<tr><td colspan="{ncols}" style="border-top:2px solid #ddd;padding:0"></td></tr>\n'
            prev_comp = comp

            # preços para esta chave
            precos_linha = {}
            for r in mod_rows:
                if (r["comp"] == comp and r["prof"] == prof
                        and r["acab"] == acab and r["emb"] == emb
                        and r["base_pe"] == base):
                    fk = "FORN" if r["faixa"].upper() == "FORNECIDO" else r["faixa"]
                    precos_linha[fk] = r["preco"]

            html += '<tr>\n'
            html += f'  <td class="comp-cell">{safe(comp)}</td>\n'
            html += f'  <td class="acab-cell">{safe(acab)}</td>\n'
            html += f'  <td class="acab-cell">{safe(emb)}</td>\n'
            if tem_base:
                html += f'  <td class="acab-cell">{safe(base)}</td>\n'

            prev_preco = None
            for f in faixas_disp:
                preco = precos_linha.get(f)
                if preco is None:
                    html += '  <td class="preco-cell preco-empty">—</td>\n'
                else:
                    is_viol = (safe(mod), safe(comp), safe(acab), f) in {
                        (v["mod"], v["comp"], v["acab"], v["f2"]) for v in vf
                    }
                    is_out = (safe(mod), safe(comp), safe(acab), f) in {
                        (o["mod"], o["comp"], o["acab"], o["f2"]) for o in out
                    }
                    cls = ("preco-viol" if is_viol else
                           "preco-warn" if is_out else "preco-ok")
                    delta = ""
                    if prev_preco is not None:
                        pct = (preco - prev_preco) / prev_preco * 100 if prev_preco else 0
                        cls_d = "delta-neg" if pct < 0 else ("delta-ok" if pct > 0 else "")
                        delta = f'<br><small class="{cls_d}">{pct:+.1f}%</small>'
                    html += f'  <td class="preco-cell {cls}">R${preco:,.0f}{delta}</td>\n'
                    prev_preco = preco

            if tem_fornecido:
                preco_forn = precos_linha.get("FORN")
                if preco_forn is None:
                    html += '  <td class="preco-cell preco-empty">—</td>\n'
                else:
                    is_viol_forn = any(
                        v["produto"] == mod_rows[0]["produto"]
                        and v["mod"] == mod and v["comp"] == comp and v["acab"] == acab
                        for v in vfn
                    )
                    cls = "preco-viol" if is_viol_forn else "preco-forn"
                    html += f'  <td class="preco-cell {cls}">R${preco_forn:,.0f}</td>\n'

            html += '</tr>\n'

        html += '</tbody></table>\n'
        html += '</div></div>\n'

    # JS carrossel
    html += f"""
<script>
(function(){{
  var cur    = 0;
  var slides = document.querySelectorAll('.slide');
  var dots   = document.querySelectorAll('.dot');
  var prev   = document.getElementById('c-prev');
  var next   = document.getElementById('c-next');
  var lbl    = document.getElementById('c-label');
  var mods   = [{mods_js}];
  function upd(){{
    slides.forEach(function(s,i){{ s.classList.toggle('active', i===cur); }});
    dots.forEach(function(d,i){{ d.classList.toggle('active', i===cur); }});
    prev.disabled = cur === 0;
    next.disabled = cur === slides.length - 1;
    lbl.textContent = (cur+1) + ' / ' + slides.length + '  —  ' + mods[cur];
  }}
  window.moveSlide = function(d) {{ cur = Math.max(0, Math.min(slides.length-1, cur+d)); upd(); }};
  window.goSlide   = function(i) {{ cur = i; upd(); }};
  upd();
}})();
</script>
"""

    html += '</div>\n'  # /section 4

    html += f"""
  </div><!-- content -->
  <div class="footer">
    Análise de Preços · {safe(produto_nome)} · {safe(tabela_nome)} ·
    Gerado em {datetime.now().strftime('%d/%m/%Y %H:%M')}
  </div>
</div><!-- wrap -->
</body></html>
"""
    return html


# ---------------------------------------------------------------------------
# ENTRY POINT
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    # args CLI opcionais
    if len(sys.argv) >= 2:
        PRODUTO_ALVO = sys.argv[1]
    if len(sys.argv) >= 3:
        COD_PREVEN = int(sys.argv[2])

    print(f"Carregando dados... produto={PRODUTO_ALVO or 'todos'}, tabela={COD_PREVEN}")
    df = carregar_dados(COD_PREVEN, PRODUTO_ALVO)
    print(f"{len(df)} linhas carregadas.")

    if df.empty:
        print("Nenhum dado encontrado. Verifique COD_PREVEN e PRODUTO_ALVO.")
        sys.exit(1)

    rows = build_rows(df)
    if not rows:
        print("Nenhuma linha válida após filtragem.")
        sys.exit(1)

    tabela_nome = df["TABELA_DESCRICAO"].iloc[0] if "TABELA_DESCRICAO" in df.columns else f"Tabela {COD_PREVEN}"
    produto_nome = PRODUTO_ALVO or f"Tabela {COD_PREVEN} — Todos os Produtos"

    print("Analisando...")
    resultado = analisar(rows)

    tv = (len(resultado["viol_faixa"]) + len(resultado["viol_fornecido"])
          + len(resultado["viol_comp"]) + len(resultado["viol_acab"]))
    print(f"Resultado: {'SEM VIOLACOES' if tv == 0 else f'{tv} VIOLACAO(ES)'}")
    print(f"  Faixa   : {len(resultado['viol_faixa'])}")
    print(f"  Forn.   : {len(resultado['viol_fornecido'])}")
    print(f"  Tamanho : {len(resultado['viol_comp'])}")
    print(f"  Acab.   : {len(resultado['viol_acab'])}")
    print(f"  Outliers: {len(resultado['outliers'])}")

    html = gerar_html(rows, resultado, produto_nome, tabela_nome)

    slug        = (PRODUTO_ALVO or f"tabela_{COD_PREVEN}").replace(" ", "_")
    nome_saida  = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                               f"analise_{slug}_{COD_PREVEN}.html")
    with open(nome_saida, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"\nRelatório: {nome_saida}")
    webbrowser.open(f"file:///{nome_saida}")
