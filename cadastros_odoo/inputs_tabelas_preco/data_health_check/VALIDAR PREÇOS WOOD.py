#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script de Análise de Preços de Produtos em Madeira
===================================================
Uso: python analisar_precos_madeira.py <arquivo.xlsx>
     python analisar_precos_madeira.py   (usa o único .xlsx da pasta)
"""

import pandas as pd
import sys
import os
import re
import statistics
from datetime import datetime
from collections import defaultdict, OrderedDict

# ===========================================================================
# ★  CONFIGURAÇÃO DE CARACTERÍSTICAS  ★
#
#  CAMPOS POR ITEM:
#
#  'nome'                → rótulo exibido no relatório
#
#  'identificacao'       → keyword PRINCIPAL. Detecta automaticamente:
#                            • 'KEYWORD: VALOR'  → captura VALOR
#                            • 'SEM KEYWORD'     → captura 'SEM KEYWORD'
#
#  'identificacoes_extras' → lista de keywords ALTERNATIVAS com a mesma lógica.
#                            Exemplo: ['TOPO INFERIOR', 'T.INF']
#                            ⚠ IMPORTANTE: o parser usa TODOS os identificadores
#                            de TODAS as características como terminadores de valor,
#                            evitando que "BASE: MDF SEM TOPO" capture "SEM TOPO"
#                            como parte do valor de BASE.
#
#  'mapeamentos_literais'  → dict: texto exato na descrição → valor da hierarquia.
#                            Use para padrões que NÃO seguem 'KEYWORD: X' nem
#                            'SEM KEYWORD'.
#                            Exemplo: {'SEM TOPO': 'SEM TOPO'}
#
#  'hierarquia'          → valores em ordem crescente de preço (mais barato → mais caro)
#
#  'iguais'              → grupos de valores com PREÇO IGUAL esperado.
#                          Não gera violação de ORDEM entre eles, mas alerta se
#                          os preços diferirem.
#                          Exemplo: [['MARMORE POLIDO', 'MARMORE LEVIGADO']]
#
#  'proporcionais'       → regras de proporcionalidade de preço.
#                          Cada item: {'valor': V, 'referencia': R, 'fator': F}
#                          → preco(V) deve ser F × preco(R), fixando as demais
#                          características e dimensões.
#                          Exemplo: {'valor':'MARMORE FORNECIDO',
#                                    'referencia':'SEM TOPO', 'fator': 0.92}
#
#  TOLERÂNCIAS GLOBAIS:
#    IGUAIS_LIMIAR_PCT        — % máx de diferença aceita em grupos 'iguais'
#    PROPORCIONAIS_LIMIAR_PCT — % máx de desvio aceito em regras 'proporcionais'
#
#  Para ADICIONAR nova característica: copie um bloco antes do comentário final.
# ===========================================================================
CARACTERISTICAS = [
    {
        'nome': 'MATERIAL DA BASE/PE',
        'identificacao': 'BASE',
        'identificacoes_extras': [],
        'mapeamentos_literais': {},
        'hierarquia': [
            'MDF',
            'METAL',
        ],
        'iguais': [],
        'proporcionais': [],
    },
    {
        'nome': 'ACABAMENTO DO TOPO',
        'identificacao': 'TOPO',
        'identificacoes_extras': [],
        # Textos que aparecem LITERALMENTE na descrição sem o padrão 'KEYWORD: X'
        'mapeamentos_literais': {
            'SEM TOPO': 'SEM TOPO',
        },
        'hierarquia': [
            'MARMORE FORNECIDO',
            'SEM TOPO',
            'VIDRO',
            'VIDRO FOSCO',
            'VIDRO EXTRA CLEAR',
            'ESPELHO',
            'MARMORE POLIDO',
            'MARMORE LEVIGADO',
            'MARMORE ESCOVADO',
            'MARMORE POLIDO ESP',
            'MARMORE LEVIGADO ESP',
            'MARMORE ESCOVADO ESP',
        ],
        'iguais': [
            ['MARMORE ESCOVADO',     'MARMORE LEVIGADO'],
            ['MARMORE ESCOVADO ESP', 'MARMORE LEVIGADO ESP'],
        ],
        'proporcionais': [
            # preco(MARMORE FORNECIDO) deve ser 0.92 × preco(SEM TOPO)
            {'valor': 'MARMORE FORNECIDO', 'referencia': 'SEM TOPO', 'fator': 0.92},
        ],
    },
    {
        'nome': 'ACABAMENTO DO TOPO INFERIOR',
        'identificacao': 'TOPO INF',
        'identificacoes_extras': ['TOPO INFERIOR'],
        'mapeamentos_literais': {
            'SEM TOPO INF':      'SEM TOPO',
            'SEM TOPO INFERIOR': 'SEM TOPO',
        },
        'hierarquia': [
            'MARMORE FORNECIDO',
            'SEM TOPO',
            'VIDRO',
            'VIDRO FOSCO',
            'VIDRO EXTRA CLEAR',
            'ESPELHO',
            'MARMORE POLIDO',
            'MARMORE LEVIGADO',
            'MARMORE ESCOVADO',
            'MARMORE POLIDO ESP',
            'MARMORE LEVIGADO ESP',
            'MARMORE ESCOVADO ESP',
        ],
        'iguais': [
            ['MARMORE ESCOVADO',     'MARMORE LEVIGADO'],
            ['MARMORE ESCOVADO ESP', 'MARMORE LEVIGADO ESP'],
        ],
        'proporcionais': [
            {'valor': 'MARMORE FORNECIDO', 'referencia': 'SEM TOPO', 'fator': 0.92},
        ],
    },
    {
        'nome': 'ACABAMENTO DO TOPO SUPERIOR',
        'identificacao': 'TOPO SUP',
        'identificacoes_extras': ['TOPO SUPERIOR'],
        'mapeamentos_literais': {
            'SEM TOPO SUP':      'SEM TOPO',
            'SEM TOPO SUPERIOR': 'SEM TOPO',
        },
        'hierarquia': [
            'MARMORE FORNECIDO',
            'SEM TOPO',
            'VIDRO',
            'VIDRO FOSCO',
            'VIDRO EXTRA CLEAR',
            'ESPELHO',
            'MARMORE POLIDO',
            'MARMORE LEVIGADO',
            'MARMORE ESCOVADO',
            'MARMORE POLIDO ESP',
            'MARMORE LEVIGADO ESP',
            'MARMORE ESCOVADO ESP',
        ],
        'iguais': [
            ['MARMORE ESCOVADO',     'MARMORE LEVIGADO'],
            ['MARMORE ESCOVADO ESP', 'MARMORE LEVIGADO ESP'],
        ],
        'proporcionais': [
            {'valor': 'MARMORE FORNECIDO', 'referencia': 'SEM TOPO', 'fator': 0.92},
        ],
    },
    {
        'nome': 'DETALHE',
        'identificacao': 'DETALHE',
        'identificacoes_extras': [],
        'mapeamentos_literais': {},
        'hierarquia': [
            'LAQUEADA METALIZADO',
            'LAQUEADA',
            'LAMINADO',
            'LAMINADO LAQUEADO',
            'LAMINADO ESPECIAL',
            'MARMORE POLIDO',
            'MARMORE LEVIGADO',
            'MARMORE ESCOVADO',
            'MARMORE POLIDO ESP',
            'MARMORE LEVIGADO ESP',
            'MARMORE ESCOVADO ESP',
        ],
        'iguais': [
            ['MARMORE ESCOVADO',     'MARMORE LEVIGADO'],
            ['MARMORE ESCOVADO ESP', 'MARMORE LEVIGADO ESP'],
            ['LAMINADO', 'LAMINADO ESPECIAL'],
        ],
        'proporcionais': [],
    },
    {
        'nome': 'ACABAMENTO DO TAMPO',
        'identificacao': 'TAMPO',
        'identificacoes_extras': [],
        'mapeamentos_literais': {},
        'hierarquia': [
            'LAQUEADA METALIZADO',
            'LAQUEADA',
            'LAMINADO',
            'LAMINADO LAQUEADO',
            'LAMINADO ESPECIAL',
        ],
        'iguais': [
            ['LAMINADO', 'LAMINADO ESPECIAL'],
        ],
        'proporcionais': [],
    },
    {
        'nome': 'ACABAMENTO DA MOLDURA',
        'identificacao': 'MOLDURA',
        'identificacoes_extras': [],
        'mapeamentos_literais': {},
        'hierarquia': [
            'LAQUEADA METALIZADO',
            'LAQUEADA',
            'LAMINADO',
            'LAMINADO LAQUEADO',
            'LAMINADO ESPECIAL',
        ],
        'iguais': [
            ['LAMINADO', 'LAMINADO ESPECIAL'],
        ],
        'proporcionais': [],
    },
    {
        'nome': 'MATERIAL DA BASE/PE',
        'identificacao': 'BASE/PE',
        'identificacoes_extras': [],
        'mapeamentos_literais': {},
        'hierarquia': [
            'LAQUEADA METALIZADO',
            'LAQUEADA',
            'LAMINADO',
            'LAMINADO LAQUEADO',
            'LAMINADO ESPECIAL',
        ],
        'iguais': [
            ['LAMINADO', 'LAMINADO ESPECIAL'],
        ],
        'proporcionais': [],
    },
    {
        'nome': 'OPÇÃO BANDEJA GIRATÓRIA',
        'identificacao': 'COM TAMPO GIRATÓRIO',
        'identificacoes_extras': [],
        'mapeamentos_literais': {},
        'hierarquia': [
            'COM TAMPO GIRATÓRIO'
        ],
        'iguais': [],
        'proporcionais': [],
    },
    # ─── Adicione novas características abaixo ───────────────────────────────
    # {
    #     'nome': 'NOME DA CARACTERISTICA',
    #     'identificacao': 'KEYWORD_PRINCIPAL',
    #     'identificacoes_extras': [],         # keywords alternativas
    #     'mapeamentos_literais': {},           # {'TEXTO EXATO NA DESC': 'VALOR'}
    #     'hierarquia': ['MAIS_BARATO', 'MAIS_CARO'],
    #     'iguais': [],
    #     'proporcionais': [],
    # },
]

# Tolerância % para "preços iguais" (0 = exato, 0.01 = 1%)
IGUAIS_LIMIAR_PCT = 0.0

# Tolerância % para regras proporcionais (0.02 = 2% de desvio permitido)
PROPORCIONAIS_LIMIAR_PCT = 0.02

# Quantos σ definem um outlier na tabela de progressão
OUTLIER_LIMIAR = 2.0

# Paleta
COR_PRIMARIA     = '#484c40'
COR_PRIMARIA_ESC = '#2d3027'
COR_PRIMARIA_CLR = '#6b7060'
COR_BG           = '#f4f4f2'


# ===========================================================================
# PADRÃO GLOBAL DE TERMINADORES
# Usado para evitar que "BASE: MDF SEM TOPO" capture "SEM TOPO" como valor de BASE.
# Construído automaticamente a partir de TODOS os identificadores declarados.
# ===========================================================================

def _build_terminator_pattern():
    """
    Constrói um padrão regex que reconhece o INÍCIO de qualquer outra
    característica, incluindo:
      • 'KEYWORD:'       (início de um valor explícito)
      • 'SEM KEYWORD'    (valor implícito negativo)
    """
    patterns = []
    for c in CARACTERISTICAS:
        for kw in ([c['identificacao']] + list(c.get('identificacoes_extras', []))):
            kw_up   = kw.strip().upper()
            kw_words = kw_up.split()
            # Terminador "KEYWORD:"
            patterns.append(re.escape(kw_up) + r'\s*:')
            # Terminador "SEM KEYWORD"
            if len(kw_words) == 1:
                patterns.append(r'SEM\s+' + re.escape(kw_up)
                                 + r'(?!\s+(?:INF|SUP|INFERIOR|SUPERIOR)\b)')
            else:
                patterns.append(r'SEM\s+' + re.escape(kw_up) + r'(?!\w)')
        # Adiciona também mapeamentos literais como terminadores
        for lit in c.get('mapeamentos_literais', {}):
            patterns.append(re.escape(lit.strip().upper()))
    # Remove duplicatas preservando ordem
    seen, unique = set(), []
    for p in patterns:
        if p not in seen:
            seen.add(p)
            unique.append(p)
    return '(?:' + '|'.join(unique) + ')' if unique else r'XXXXXX_NEVER'


# Construído uma vez na importação do módulo
_TERMINATOR_PAT = None   # inicializado em _get_terminator()

def _get_terminator():
    global _TERMINATOR_PAT
    if _TERMINATOR_PAT is None:
        _TERMINATOR_PAT = _build_terminator_pattern()
    return _TERMINATOR_PAT


# ===========================================================================
# HELPERS DE PARSING
# ===========================================================================

def normalizar(val):
    if val is None:
        return ''
    v = str(val).strip().upper()
    v = re.sub(r'\s+', ' ', v)
    v = v.replace('EXTRACLEAR', 'EXTRA CLEAR').replace('EXTRA  CLEAR', 'EXTRA CLEAR')
    return v


def dim_para_float(dim_str):
    if not dim_str:
        return 0.0
    d = re.sub(r'[Mm\s]', '', str(dim_str)).replace(',', '.')
    try:
        return float(d)
    except ValueError:
        return 0.0


def extrair_dimensoes(texto):
    pat = re.compile(r'(\d+[\.,]\d+\s*[Mm]|\d+\s*[Mm])')
    return [(normalizar(m.group()), m.start(), m.end()) for m in pat.finditer(texto)]


def _tentar_identificador(ident, texto_up):
    """
    Tenta capturar o valor de uma característica no texto usando a keyword `ident`.
    Retorna o valor normalizado ou None.
    O valor termina ao encontrar qualquer outro terminador conhecido (evita
    capturar "SEM TOPO" como parte do valor de "BASE").
    """
    ident_words = ident.split()
    term        = _get_terminator()

    # Padrão 'KEYWORD: VALOR' — valor termina no próximo terminador ou fim
    pat_colon = (re.escape(ident) + r'\s*:\s*'
                 + r'(.+?)(?=\s+' + term + r'|\s*$)')
    m = re.search(pat_colon, texto_up)
    if m:
        return normalizar(m.group(1))

    # Padrão 'SEM KEYWORD'
    if len(ident_words) == 1:
        pat_sem = (r'(?<!\w)SEM\s+' + re.escape(ident)
                   + r'(?!\s+(?:INF|SUP|INFERIOR|SUPERIOR)\b)')
    else:
        pat_sem = r'(?<!\w)SEM\s+' + re.escape(ident) + r'(?!\w)'

    if re.search(pat_sem, texto_up):
        return 'SEM ' + ident_words[0]

    return None


def parse_descricao(descricao, produto_nome):
    desc    = str(descricao).strip()
    prod_up = produto_nome.upper().strip()
    desc_up = desc.upper()

    if desc_up.startswith(prod_up):
        resto = desc[len(prod_up):].strip()
    else:
        idx   = desc_up.find(prod_up)
        resto = desc[idx + len(prod_up):].strip() if idx >= 0 else desc

    dims         = extrair_dimensoes(resto)
    comp = prof = alt = None
    pos_fim_dims = len(resto)

    if len(dims) >= 3:
        comp, prof, alt = dims[0][0], dims[1][0], dims[2][0]
        pos_fim_dims    = dims[2][2]
    elif len(dims) == 2:
        comp, prof   = dims[0][0], dims[1][0]
        pos_fim_dims = dims[1][2]
    elif len(dims) == 1:
        comp         = dims[0][0]
        pos_fim_dims = dims[0][2]

    modulacao   = resto[:dims[0][1]].strip() if dims else resto
    texto_chars = resto[pos_fim_dims:].strip()
    texto_up    = texto_chars.upper()

    caracs_encontradas = {}

    # Ordena por comprimento decrescente do identificador principal para evitar
    # capturas parciais (ex.: "TOPO INF" antes de "TOPO")
    sorted_caracs = sorted(CARACTERISTICAS, key=lambda c: len(c['identificacao']), reverse=True)

    for carac in sorted_caracs:
        nome_c = carac['nome']
        if nome_c in caracs_encontradas:
            continue

        # 1. Mapeamentos literais têm prioridade máxima (quando não há 'KEYWORD: X')
        #    Verifica que o keyword principal NÃO aparece com ":" (senão é valor explícito)
        ident_principal = carac['identificacao'].upper()
        if not re.search(re.escape(ident_principal) + r'\s*:', texto_up):
            for texto_lit, valor_lit in carac.get('mapeamentos_literais', {}).items():
                pat_lit = r'(?<!\w)' + re.escape(texto_lit.upper()) + r'(?!\w)'
                if re.search(pat_lit, texto_up):
                    caracs_encontradas[nome_c] = normalizar(valor_lit)
                    break
        if nome_c in caracs_encontradas:
            continue

        # 2. Identificador principal
        val = _tentar_identificador(ident_principal, texto_up)
        if val:
            caracs_encontradas[nome_c] = val
            continue

        # 3. Identificadores extras (na ordem de declaração)
        for ident_extra in carac.get('identificacoes_extras', []):
            val = _tentar_identificador(ident_extra.upper(), texto_up)
            if val:
                caracs_encontradas[nome_c] = val
                break

    return {
        'produto':      produto_nome,
        'modulacao':    modulacao,
        'comp':         comp,
        'prof':         prof,
        'alt':          alt,
        'dims_str':     ' x '.join(filter(None, [comp, prof, alt])),
        'texto_chars':  texto_chars,
        'caracs':       caracs_encontradas,
    }


# ===========================================================================
# HELPERS DE HIERARQUIA
# ===========================================================================

def rank_efetivo(v, hierarquia, iguais):
    """Rank considerando grupos iguais (todos recebem o menor índice do grupo)."""
    if v not in hierarquia:
        return 9999
    idx = hierarquia.index(v)
    for grupo in iguais:
        if v in grupo:
            idxs = [hierarquia.index(g) for g in grupo if g in hierarquia]
            return min(idxs) if idxs else idx
    return idx


def sort_key_row(r):
    """
    Ordenação canônica para a Seção 3:
      1. Dimensões (comp → prof → alt) - Agrupa primeiro pelo tamanho.
      2. Características na ordem declarada em CARACTERISTICAS (ordena 
         pela hierarquia dentro de cada agrupamento de tamanho).
    """
    dim_k = (
        dim_para_float(r.get('comp') or ''),
        dim_para_float(r.get('prof') or ''),
        dim_para_float(r.get('alt') or ''),
    )
    carac_k = tuple(
        rank_efetivo(r['caracs'].get(c['nome'], ''), c['hierarquia'], c.get('iguais', []))
        for c in CARACTERISTICAS
    )
    # Retorna as dimensões primeiro, depois as características
    return dim_k + carac_k


def identificar_transicao(r_prev, r_curr):
    partes = []
    for carac in CARACTERISTICAS:
        n  = carac['nome']
        v1 = r_prev['caracs'].get(n, '')
        v2 = r_curr['caracs'].get(n, '')
        if v1 != v2:
            partes.append(f"{n}: {v1}→{v2}")
    for dim in ['comp', 'prof', 'alt']:
        d1, d2 = r_prev.get(dim, ''), r_curr.get(dim, '')
        if d1 != d2:
            partes.append(f"{dim.upper()}: {d1}→{d2}")
    return ' | '.join(partes) if partes else 'IGUAL'


# ===========================================================================
# TABELA DE DIMENSÕES
# ===========================================================================

def render_dim_table_modulo(mod, combos_set):
    combos_ord = sorted(
        combos_set,
        key=lambda t: (dim_para_float(t[1]), dim_para_float(t[2]), dim_para_float(t[0])))

    agrupado  = OrderedDict()
    for c, p, a in combos_ord:
        agrupado.setdefault((p, a), []).append(c)

    tem_prof = any(p for _, p, _ in combos_set)
    tem_alt  = any(a for _, _, a in combos_set)

    out  = '<div class="dim-mod-wrap">\n'
    out += f'<div class="dim-mod-title">{mod}</div>\n'
    out += '<table class="dim-group-tbl" style="width:auto;min-width:270px">\n'
    out += '<thead><tr><th>COMP</th>'
    if tem_prof: out += '<th>PROF</th>'
    if tem_alt:  out += '<th>ALT</th>'
    out += '</tr></thead>\n<tbody>\n'

    for (prof, alt), comps in agrupado.items():
        n = len(comps)
        for i, comp in enumerate(comps):
            out += '<tr>'
            out += f'<td class="dim-comp">{comp}</td>'
            if i == 0:
                if tem_prof: out += f'<td class="dim-shared" rowspan="{n}">{prof or "–"}</td>'
                if tem_alt:  out += f'<td class="dim-shared" rowspan="{n}">{alt or "–"}</td>'
            out += '</tr>\n'

    out += '</tbody></table>\n</div>\n'
    return out


# ===========================================================================
# PROGRESSÃO DIMENSIONAL CRUZADA (Seção 3, coluna Δ dim.)
# ===========================================================================

def construir_indice_rows(rows):
    """Índice: (mod, comp, prof, alt, caracs_frozen) → row"""
    idx = {}
    for r in rows:
        k = (r['modulacao'], r['comp'], r['prof'], r['alt'],
             tuple(sorted(r['caracs'].items())))
        idx[k] = r
    return idx


def encontrar_ref_dimensional(r, idx_rows, rows_mod):
    """
    Retorna (row_referencia, dim_variada) onde row_referencia tem a dimensão
    IMEDIATAMENTE ANTERIOR à de `r`, fixando todas as demais.
    Prioridade: COMP → PROF → ALT.
    """
    mod           = r['modulacao']
    caracs_frozen = tuple(sorted(r['caracs'].items()))

    for dim_var in ['comp', 'prof', 'alt']:
        dim_outras = [d for d in ['comp', 'prof', 'alt'] if d != dim_var]

        vals_dim = sorted(
            set(rr[dim_var] for rr in rows_mod
                if rr[dim_var]
                and all(rr[d] == r[d] for d in dim_outras)
                and tuple(sorted(rr['caracs'].items())) == caracs_frozen),
            key=dim_para_float)

        cur_val = r[dim_var]
        if not cur_val or cur_val not in vals_dim:
            continue
        ci = vals_dim.index(cur_val)
        if ci == 0:
            continue

        prev_val = vals_dim[ci - 1]
        chave    = (mod,
                    prev_val if dim_var == 'comp' else r['comp'],
                    prev_val if dim_var == 'prof' else r['prof'],
                    prev_val if dim_var == 'alt'  else r['alt'],
                    caracs_frozen)
        ref_row = idx_rows.get(chave)
        if ref_row:
            return ref_row, dim_var

    return None, None


# ===========================================================================
# ANÁLISE PRINCIPAL
# ===========================================================================

def analisar_e_gerar_html(arquivo_excel):
    if not os.path.exists(arquivo_excel):
        print(f"Erro: Arquivo '{arquivo_excel}' nao encontrado!")
        sys.exit(1)

    # Força a re-construção do padrão de terminadores
    global _TERMINATOR_PAT
    _TERMINATOR_PAT = None

    produto_nome = os.path.splitext(os.path.basename(arquivo_excel))[0].strip().upper()

    xl         = pd.ExcelFile(arquivo_excel)
    sheet_name = xl.sheet_names[0]
    df_raw     = pd.read_excel(arquivo_excel, sheet_name=sheet_name, header=0)
    cols       = df_raw.columns.tolist()
    col_config = cols[1] if len(cols) > 1 else cols[0]
    col_preco  = cols[2] if len(cols) > 2 else cols[1]

    rows = []
    for i, row in df_raw.iterrows():
        config_val = str(row[col_config]).strip() if pd.notna(row[col_config]) else ''
        preco_val  = row[col_preco] if pd.notna(row[col_preco]) else None
        if config_val.upper() in {'CONFIGURAÇÃO', 'CONFIGURACAO', 'NAN', ''} or preco_val is None:
            continue
        try:
            preco = float(preco_val)
        except (ValueError, TypeError):
            continue
        parsed = parse_descricao(config_val, produto_nome)
        rows.append({'excel_row': i + 2, 'configuracao': config_val, 'preco': preco, **parsed})

    if not rows:
        print("Erro: Nenhuma linha de dados valida encontrada!")
        sys.exit(1)

    print(f"Produto: {produto_nome} — {len(rows)} configuracoes carregadas.")

    # ── Seção 1: inventário ──────────────────────────────────────────────────
    caracs_presentes = set()
    for r in rows:
        caracs_presentes.update(r['caracs'].keys())

    caracs_info = {}
    for carac in CARACTERISTICAS:
        nome_c = carac['nome']
        if nome_c not in caracs_presentes:
            continue
        iguais = carac.get('iguais', [])

        valores_globais = set()
        por_modulacao   = defaultdict(set)
        por_mod_tam     = defaultdict(set)

        for r in rows:
            val = r['caracs'].get(nome_c)
            if val:
                valores_globais.add(val)
                por_modulacao[r['modulacao']].add(val)
                por_mod_tam[(r['modulacao'], r['dims_str'])].add(val)

        hier_presentes  = [v for v in carac['hierarquia'] if v in valores_globais]
        fora_hierarquia = sorted(valores_globais - set(carac['hierarquia']))

        inconsistencias_opcoes = []
        for (mod, tam), vals_mt in sorted(por_mod_tam.items()):
            faltam = [v for v in hier_presentes if v not in vals_mt]
            if faltam:
                inconsistencias_opcoes.append({
                    'modulacao': mod, 'dims': tam,
                    'valores': sorted(vals_mt), 'faltam': faltam,
                })

        caracs_info[nome_c] = {
            'hierarquia':             carac['hierarquia'],
            'iguais':                 iguais,
            'proporcionais':          carac.get('proporcionais', []),
            'valores_globais':        sorted(valores_globais),
            'fora_hierarquia':        fora_hierarquia,
            'hier_presentes':         hier_presentes,
            'por_modulacao':          {k: sorted(v) for k, v in sorted(por_modulacao.items())},
            'inconsistencias_opcoes': inconsistencias_opcoes,
        }

    modulacoes_disponiveis = sorted(set(r['modulacao'] for r in rows))
    tam_por_mod = defaultdict(set)
    for r in rows:
        tam_por_mod[r['modulacao']].add((r['comp'] or '', r['prof'] or '', r['alt'] or ''))

    # ── Seção 2A: progressão de características ──────────────────────────────
    violacoes_carac  = {}
    stats_transicoes = {}
    stats_proporcionais = {}   # nome_c → {(val, ref): [pct_reais]}

    for carac in CARACTERISTICAS:
        nome_c      = carac['nome']
        if nome_c not in caracs_presentes:
            continue
        hierarquia    = carac['hierarquia']
        iguais        = carac.get('iguais', [])
        proporcionais = carac.get('proporcionais', [])
        hier_adj      = {(hierarquia[i], hierarquia[i + 1])
                         for i in range(len(hierarquia) - 1)}

        outras = [c['nome'] for c in CARACTERISTICAS
                  if c['nome'] != nome_c and c['nome'] in caracs_presentes]

        def chave_carac(r, outras=outras, nome_c=nome_c):
            return ((r['modulacao'], r['comp'], r['prof'], r['alt'])
                    + tuple(r['caracs'].get(o, '') for o in outras))

        grupos = defaultdict(list)
        for r in rows:
            if nome_c in r['caracs']:
                grupos[chave_carac(r)].append(r)

        violacoes  = []
        trans_pcts = defaultdict(list)
        prop_pcts  = defaultdict(list)

        for _chave, grp in grupos.items():
            if len(grp) < 2:
                continue
            grp_sorted = sorted(
                grp, key=lambda r: rank_efetivo(r['caracs'].get(nome_c, ''), hierarquia, iguais))
            val_to_row = {rr['caracs'].get(nome_c, ''): rr for rr in grp_sorted}

            for i in range(len(grp_sorted) - 1):
                r1, r2 = grp_sorted[i], grp_sorted[i + 1]
                v1 = r1['caracs'].get(nome_c, '')
                v2 = r2['caracs'].get(nome_c, '')
                if v1 not in hierarquia or v2 not in hierarquia:
                    continue

                eff1 = rank_efetivo(v1, hierarquia, iguais)
                eff2 = rank_efetivo(v2, hierarquia, iguais)

                if eff1 == eff2:
                    # Grupo de iguais — verifica se preços são realmente iguais
                    max_p    = max(r1['preco'], r2['preco'])
                    diff_pct = abs(r1['preco'] - r2['preco']) / max_p if max_p > 0 else 0
                    if diff_pct > IGUAIS_LIMIAR_PCT:
                        pct = (r2['preco'] - r1['preco']) / r1['preco'] * 100 if r1['preco'] else 0
                        violacoes.append({
                            'tipo': 'igual',
                            'config1': r1['configuracao'], 'preco1': r1['preco'], 'val1': v1,
                            'config2': r2['configuracao'], 'preco2': r2['preco'], 'val2': v2,
                            'dims': r1['dims_str'], 'modulacao': r1['modulacao'],
                            'pct': pct,
                            'motivo': f'Esperado preco igual entre "{v1}" e "{v2}". Diferença: {pct:+.1f}%',
                        })
                    continue

                if eff1 > eff2:
                    continue

                pct = (r2['preco'] - r1['preco']) / r1['preco'] * 100 if r1['preco'] else 0
                if r2['preco'] < r1['preco']:
                    violacoes.append({
                        'tipo': 'ordem',
                        'config1': r1['configuracao'], 'preco1': r1['preco'], 'val1': v1,
                        'config2': r2['configuracao'], 'preco2': r2['preco'], 'val2': v2,
                        'dims': r1['dims_str'], 'modulacao': r1['modulacao'],
                        'pct': pct,
                        'motivo': f'Esperado {v2} >= {v1}. Variação: {pct:+.1f}%',
                    })

                if (v1, v2) in hier_adj:
                    trans_pcts[(v1, v2)].append(pct)

            # ── Regras de proporcionalidade ────────────────────────────────
            for prop in proporcionais:
                r_val = val_to_row.get(prop['valor'])
                r_ref = val_to_row.get(prop['referencia'])
                if not r_val or not r_ref or r_ref['preco'] <= 0:
                    continue
                pct_real     = (r_val['preco'] / r_ref['preco'] - 1) * 100
                pct_esperado = (prop['fator'] - 1) * 100
                esperado     = prop['fator'] * r_ref['preco']
                desvio       = abs(r_val['preco'] - esperado) / r_ref['preco']

                prop_pcts[(prop['valor'], prop['referencia'])].append(pct_real)

                if desvio > PROPORCIONAIS_LIMIAR_PCT:
                    violacoes.append({
                        'tipo': 'proporcional',
                        'config1': r_ref['configuracao'], 'preco1': r_ref['preco'],
                        'val1':    prop['referencia'],
                        'config2': r_val['configuracao'], 'preco2': r_val['preco'],
                        'val2':    prop['valor'],
                        'dims':    r_val['dims_str'], 'modulacao': r_val['modulacao'],
                        'pct':     pct_real,
                        'motivo':  (f'Esperado {prop["valor"]} = {prop["fator"]}×{prop["referencia"]} '
                                    f'(R$ {esperado:,.2f}, {pct_esperado:+.1f}%). '
                                    f'Real: R$ {r_val["preco"]:,.2f} ({pct_real:+.1f}%)'),
                    })

        violacoes_carac[nome_c]    = violacoes
        stats_transicoes[nome_c]   = dict(trans_pcts)
        stats_proporcionais[nome_c] = dict(prop_pcts)

    # ── Seção 2B: progressão dimensional ────────────────────────────────────
    violacoes_dim  = {}
    stats_dim_pcts = {}

    for dim_var in ['comp', 'prof', 'alt']:
        dim_outras = [d for d in ['comp', 'prof', 'alt'] if d != dim_var]

        def chave_dim(r, dim_outras=dim_outras):
            return ((r['modulacao'],)
                    + tuple(r.get(d, '') for d in dim_outras)
                    + tuple(sorted(r['caracs'].items())))

        grupos_d = defaultdict(list)
        for r in rows:
            if r.get(dim_var):
                grupos_d[chave_dim(r)].append(r)

        viol_d = []
        pcts_d = []
        for _chave, grp in grupos_d.items():
            if len(grp) < 2:
                continue
            grp_s = sorted(grp, key=lambda r: dim_para_float(r.get(dim_var, '')))
            for i in range(len(grp_s) - 1):
                r1, r2 = grp_s[i], grp_s[i + 1]
                if dim_para_float(r1[dim_var]) >= dim_para_float(r2[dim_var]):
                    continue
                pct = (r2['preco'] - r1['preco']) / r1['preco'] * 100 if r1['preco'] else 0
                pcts_d.append(pct)
                if r2['preco'] < r1['preco']:
                    viol_d.append({
                        'config1':   r1['configuracao'], 'preco1': r1['preco'], 'dim1': r1[dim_var],
                        'config2':   r2['configuracao'], 'preco2': r2['preco'], 'dim2': r2[dim_var],
                        'modulacao': r1['modulacao'], 'pct': pct,
                        'motivo':    f'Esperado {dim_var.upper()} {r2[dim_var]} >= {r1[dim_var]}. Variação: {pct:+.1f}%',
                    })

        violacoes_dim[dim_var]  = viol_d
        stats_dim_pcts[dim_var] = pcts_d

    # ── Seção 3: carrossel ───────────────────────────────────────────────────
    pares_viol = set()
    for nome_c, vlist in violacoes_carac.items():
        for v in vlist:
            pares_viol.add((v['config1'], v['config2']))
            pares_viol.add((v['config2'], v['config1']))
    for _d, vlist in violacoes_dim.items():
        for v in vlist:
            pares_viol.add((v['config1'], v['config2']))
            pares_viol.add((v['config2'], v['config1']))

    grupos_mod = defaultdict(list)
    for r in rows:
        grupos_mod[r['modulacao']].append(r)

    slides = []
    for mod in modulacoes_disponiveis:
        grp = sorted(grupos_mod[mod], key=sort_key_row)

        # Progressão sequencial — só dentro do mesmo grupo (mesmo dims_str)
        progs = [None]
        for i in range(1, len(grp)):
            prev_r, curr_r = grp[i - 1], grp[i]
            if curr_r['dims_str'] != prev_r['dims_str']:
                progs.append(None)
            else:
                prev_p = prev_r['preco']
                progs.append((curr_r['preco'] - prev_p) / prev_p * 100 if prev_p else None)

        # Progressão dimensional cruzada (Δ dim.)
        idx_mod   = construir_indice_rows(grp)
        dim_progs = []
        for r in grp:
            ref_row, dim_var = encontrar_ref_dimensional(r, idx_mod, grp)
            if ref_row and ref_row['preco']:
                pct_dim = (r['preco'] - ref_row['preco']) / ref_row['preco'] * 100
                dim_progs.append((pct_dim, ref_row['configuracao'], dim_var))
            else:
                dim_progs.append((None, None, None))

        # Outlier detection
        tipos_pcts = defaultdict(list)
        for i in range(1, len(grp)):
            pct = progs[i]
            if pct is not None:
                tipos_pcts[identificar_transicao(grp[i - 1], grp[i])].append(pct)

        cores_slide = [None]
        for i in range(1, len(grp)):
            pct  = progs[i]
            prev = grp[i - 1]
            curr = grp[i]
            if pct is None:
                cores_slide.append(None)
                continue
            if (prev['configuracao'], curr['configuracao']) in pares_viol:
                cores_slide.append('red')
                continue
            tipo      = identificar_transicao(prev, curr)
            pcts_tipo = tipos_pcts.get(tipo, [])
            if len(pcts_tipo) >= 3:
                try:
                    media  = statistics.mean(pcts_tipo)
                    desvio = statistics.stdev(pcts_tipo)
                    if desvio > 0 and abs(pct - media) > OUTLIER_LIMIAR * desvio:
                        cores_slide.append('yellow')
                        continue
                except statistics.StatisticsError:
                    pass
            cores_slide.append(None)

        slides.append((mod, grp, progs, dim_progs, cores_slide))

    # ── Totais ───────────────────────────────────────────────────────────────
    total_viol_carac = sum(len(v) for v in violacoes_carac.values())
    total_viol_dim   = sum(len(v) for v in violacoes_dim.values())
    total_viol       = total_viol_carac + total_viol_dim
    status_ok        = total_viol == 0
    status_cor       = '#27ae60' if status_ok else '#c0392b'
    status_texto     = ('✓ TODOS OS PREÇOS CONSISTENTES' if status_ok
                        else f'⚠ {total_viol} INCONSISTÊNCIA(S) ENCONTRADA(S)')
    n_red    = sum(1 for _, _, _, _, cs in slides for c in cs if c == 'red')
    n_yellow = sum(1 for _, _, _, _, cs in slides for c in cs if c == 'yellow')

    # ══════════════════════════════════════════════════════════════════════════
    # HTML
    # ══════════════════════════════════════════════════════════════════════════
    html = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width,initial-scale=1.0">
  <title>Análise de Preços – {produto_nome}</title>
  <style>
    *{{margin:0;padding:0;box-sizing:border-box}}
    body{{font-family:'Segoe UI',Tahoma,sans-serif;background:{COR_BG};color:#2d3027;padding:24px}}
    .wrap{{max-width:1440px;margin:0 auto}}
    .header{{background:linear-gradient(135deg,{COR_PRIMARIA_ESC},{COR_PRIMARIA});
             color:#fff;padding:36px 40px;border-radius:12px 12px 0 0}}
    .header h1{{font-size:1.9rem;margin-bottom:6px}}
    .header p{{opacity:.85;font-size:.93rem}}
    .status{{background:{status_cor};color:#fff;padding:16px 40px;
             font-size:1.2rem;font-weight:700;letter-spacing:.4px}}
    .info-bar{{background:#fff;padding:20px 40px;border-bottom:3px solid #e4e4e0;
               display:flex;gap:14px;flex-wrap:wrap}}
    .card{{background:{COR_BG};border-left:4px solid {COR_PRIMARIA};
           padding:11px 16px;border-radius:6px;min-width:130px}}
    .card-label{{font-size:.7rem;color:#6b7060;text-transform:uppercase;
                 letter-spacing:.5px;margin-bottom:3px}}
    .card-value{{font-size:1.05rem;font-weight:700;color:#2d3027}}
    .content{{background:#fff;padding:36px 40px}}
    .section{{margin-bottom:52px}}
    .sec-title{{font-size:1.3rem;color:{COR_PRIMARIA_ESC};padding-bottom:8px;
                border-bottom:3px solid {COR_PRIMARIA};margin-bottom:20px;font-weight:700}}
    .sub-title{{font-size:1rem;color:{COR_PRIMARIA_ESC};margin:22px 0 10px;font-weight:600}}

    /* Dim table */
    .dim-grid-container{{display:grid;grid-template-columns:repeat(auto-fill,minmax(270px,1fr));
                          gap:16px;margin:14px 0 28px}}
    .dim-mod-wrap{{background:#fff;border:1px solid #d8d9d4;border-radius:10px;
                   overflow:hidden;box-shadow:0 2px 5px rgba(0,0,0,.05)}}
    .dim-mod-title{{background:{COR_PRIMARIA};color:#fff;font-weight:700;font-size:.9rem;
                    padding:9px 14px;text-transform:uppercase;letter-spacing:.3px}}
    .dim-group-tbl{{width:100%;border-collapse:collapse;font-size:.83rem}}
    .dim-group-tbl thead th{{background:#f8f8f6;color:{COR_PRIMARIA};padding:7px 10px;
                              text-align:center;border-bottom:2px solid #e4e4e0;font-weight:700}}
    .dim-group-tbl tbody td{{padding:6px 10px;border:1px solid #f0f0ee;text-align:center}}
    .dim-comp{{background:{COR_BG};font-weight:600;color:{COR_PRIMARIA_ESC};text-align:right}}
    .dim-shared{{background:#fff;font-weight:500;vertical-align:middle}}

    /* Carac blocks */
    .carac-block{{border:1px solid #ddd;border-radius:8px;margin-bottom:20px;overflow:hidden}}
    .carac-header{{background:{COR_PRIMARIA};color:#fff;padding:10px 17px;
                   display:flex;justify-content:space-between;align-items:center}}
    .carac-header h3{{font-size:.92rem;font-weight:600}}
    .carac-body{{padding:15px 19px}}
    .hier-list{{display:flex;flex-wrap:wrap;align-items:center;gap:5px;margin:7px 0 11px}}
    .hier-pill{{background:{COR_PRIMARIA};color:#fff;padding:4px 10px;border-radius:16px;
                font-size:.78rem;font-weight:500;cursor:default}}
    .hier-pill.igual{{background:{COR_PRIMARIA_CLR};outline:2px dashed rgba(255,255,255,.6);
                      outline-offset:-2px}}
    .hier-pill.prop{{background:#6b4c1a;outline:2px dotted rgba(255,220,120,.8);outline-offset:-2px}}
    .hier-pill.inativo{{opacity:.3}}
    .hier-arrow{{color:#b2b8a8;font-size:.9rem}}
    .hier-igual{{color:{COR_PRIMARIA};font-weight:700;padding:0 3px;font-size:.9rem}}
    .tag{{display:inline-block;padding:2px 9px;border-radius:12px;font-size:.76rem;
          margin:2px;background:#e4e4e0;color:#2d3027}}
    .tag.hier{{background:#d5ead5;color:#1e5c1e}}
    .tag.extra{{background:#fde8d8;color:#8b3500}}
    table{{width:100%;border-collapse:collapse;font-size:.84rem;margin-top:9px}}
    thead{{background:{COR_PRIMARIA};color:#fff}}
    th{{padding:8px 11px;text-align:left;font-weight:600}}
    td{{padding:7px 11px;border-bottom:1px solid #ebebeb;vertical-align:top}}
    tr:hover td{{background:#f8f8f6}}
    .num{{text-align:right;font-variant-numeric:tabular-nums}}
    .alert-ok{{background:#d5ead5;border-left:5px solid #27ae60;padding:12px 15px;
               border-radius:6px;margin:9px 0;font-size:.87rem}}
    .alert-err{{background:#fdedec;border-left:5px solid #c0392b;padding:12px 15px;
                border-radius:6px;margin:9px 0}}
    .alert-warn{{background:#fef9e7;border-left:5px solid #e67e22;padding:12px 15px;
                 border-radius:6px;margin:9px 0}}
    .alert-info{{background:#e8f4fd;border-left:5px solid #2980b9;padding:12px 15px;
                 border-radius:6px;margin:9px 0}}
    .badge-ok{{background:#27ae60;color:#fff;padding:2px 8px;border-radius:10px;
               font-size:.72rem;font-weight:600;white-space:nowrap}}
    .badge-err{{background:#c0392b;color:#fff;padding:2px 8px;border-radius:10px;
                font-size:.72rem;font-weight:600;white-space:nowrap}}
    .badge-warn{{background:#e67e22;color:#fff;padding:2px 8px;border-radius:10px;
                 font-size:.72rem;font-weight:600;white-space:nowrap}}
    .badge-prop{{background:#6b4c1a;color:#fff;padding:2px 8px;border-radius:10px;
                 font-size:.72rem;font-weight:600;white-space:nowrap}}

    /* Violation table */
    .viol-tbl{{width:100%;border-collapse:collapse;font-size:.82rem;margin-top:9px}}
    .viol-tbl thead{{background:{COR_PRIMARIA_ESC};color:#fff}}
    .viol-tbl th{{padding:7px 10px;font-weight:600;text-align:left}}
    .viol-tbl td{{padding:8px 10px;border-bottom:1px solid #ebebeb;vertical-align:top}}
    .viol-config{{font-family:'Courier New',monospace;font-size:.73rem;color:#555;word-break:break-all}}
    .viol-preco{{font-weight:700;white-space:nowrap}}
    .viol-motivo{{color:#7a2010;font-style:italic;font-size:.77rem;margin-top:3px}}

    /* Carousel */
    .carousel-nav{{display:flex;align-items:center;gap:12px;margin-bottom:12px;flex-wrap:wrap}}
    .btn-nav{{background:{COR_PRIMARIA};color:#fff;border:none;padding:7px 15px;
              border-radius:6px;cursor:pointer;font-size:.95rem;font-weight:700;
              transition:background .15s}}
    .btn-nav:hover{{background:{COR_PRIMARIA_ESC}}}
    .btn-nav:disabled{{background:#ccc;cursor:default}}
    .carousel-dots{{display:flex;gap:7px;align-items:center}}
    .dot{{width:10px;height:10px;border-radius:50%;background:#ccc;cursor:pointer;
          transition:background .2s,transform .2s}}
    .dot:hover{{transform:scale(1.3)}}
    .dot.active{{background:{COR_PRIMARIA}}}
    .slide-counter{{font-size:.85rem;color:#6b7060}}
    .slide{{display:none}}
    .slide.active{{display:block}}
    .slide-head{{background:{COR_PRIMARIA};color:#fff;padding:9px 17px;
                 border-radius:8px 8px 0 0;font-weight:700;font-size:.92rem}}
    .slide-body{{border:1px solid #ddd;border-top:none;border-radius:0 0 8px 8px;overflow:hidden}}

    /* Progress table */
    .tbl-prog{{width:100%;border-collapse:collapse;font-size:.82rem}}
    .tbl-prog thead{{background:{COR_PRIMARIA_ESC};color:#fff}}
    .tbl-prog th{{padding:8px 11px;font-weight:600;text-align:left}}
    .tbl-prog td{{padding:7px 11px;border-bottom:1px solid #ebebeb;vertical-align:middle}}
    .tbl-prog tr.viol-red td{{background:#fdedec!important}}
    .tbl-prog tr.viol-yellow td{{background:#fffbe6!important}}
    .tbl-prog tr.dim-break td{{border-top:3px solid {COR_PRIMARIA};padding-top:9px}}
    .config-cell{{font-family:'Courier New',monospace;font-size:.73rem;color:#555;word-break:break-all}}
    .preco-cell{{font-weight:700;text-align:right;white-space:nowrap}}
    .pct-red{{color:#c0392b;font-weight:700}}
    .pct-yellow{{color:#e67e22;font-weight:700}}
    .pct-ok{{color:#27ae60;font-weight:600}}
    .pct-neg{{color:#c0392b;font-weight:700}}
    .pct-dash{{color:#ccc}}

    /* Dimensional cross-progress tooltip */
    abbr.dim-ref{{cursor:help;border-bottom:1px dashed currentColor;text-decoration:none}}
    .pct-dim-ok{{color:#1a6db5;font-weight:600}}
    .pct-dim-neg{{color:#8b3500;font-weight:700}}
    .dim-label{{font-size:.66rem;color:#888;margin-left:2px}}
    .th-dim{{font-size:.78rem;font-weight:400;color:#9bb8d8}}

    .inconsist-note{{font-size:.74rem;color:#7a8069;margin-top:3px;font-style:italic}}
    code{{background:#f0f0ee;padding:1px 5px;border-radius:3px;font-size:.83em}}
    .footer{{background:{COR_PRIMARIA_ESC};color:#fff;padding:14px 40px;
             text-align:center;font-size:.82rem;border-radius:0 0 12px 12px;opacity:.93}}
  </style>
</head>
<body>
<div class="wrap">
  <div class="header">
    <h1>🔍 Análise de Preços — {produto_nome}</h1>
    <p>Gerado em {datetime.now().strftime('%d/%m/%Y às %H:%M')}
       &nbsp;·&nbsp; {os.path.basename(arquivo_excel)}</p>
  </div>
  <div class="status">{status_texto}</div>
  <div class="info-bar">
    <div class="card"><div class="card-label">Configurações</div>
      <div class="card-value">{len(rows)}</div></div>
    <div class="card"><div class="card-label">Modulações</div>
      <div class="card-value">{len(modulacoes_disponiveis)}</div></div>
    <div class="card"><div class="card-label">Tamanhos únicos</div>
      <div class="card-value">{len(set(r['dims_str'] for r in rows))}</div></div>
    <div class="card"><div class="card-label">Caracts. analisadas</div>
      <div class="card-value">{len(caracs_info)}</div></div>
    <div class="card"><div class="card-label">Violações caract.</div>
      <div class="card-value" style="color:{'#c0392b' if total_viol_carac else '#27ae60'}">
        {total_viol_carac}</div></div>
    <div class="card"><div class="card-label">Violações dimensão</div>
      <div class="card-value" style="color:{'#c0392b' if total_viol_dim else '#27ae60'}">
        {total_viol_dim}</div></div>
  </div>
  <div class="content">
"""

    # ════════════════════════════════════════════════════════════════════
    # SEÇÃO 1
    # ════════════════════════════════════════════════════════════════════
    html += '<div class="section"><h2 class="sec-title">1. Características Encontradas nas Configurações</h2>\n'
    html += '<h3 class="sub-title">Dimensões Disponíveis por Modulação</h3>\n'
    html += '<div class="dim-grid-container">\n'
    for mod in modulacoes_disponiveis:
        html += render_dim_table_modulo(mod, tam_por_mod[mod])
    html += '</div>\n'

    html += '<h3 class="sub-title" style="margin-top:28px">Características que Influenciam o Preço</h3>\n'
    if not caracs_info:
        html += '<div class="alert-warn">Nenhuma característica reconhecida nas descrições.</div>\n'
    else:
        for nome_c, info in caracs_info.items():
            carac_cfg = next((c for c in CARACTERISTICAS if c['nome'] == nome_c), {})
            n_viol    = len(violacoes_carac.get(nome_c, []))
            badge     = (f'<span class="badge-err">{n_viol} violação(ões)</span>'
                         if n_viol else '<span class="badge-ok">OK</span>')

            html += (f'<div class="carac-block">'
                     f'<div class="carac-header"><h3>{nome_c}</h3>{badge}</div>\n'
                     f'<div class="carac-body">\n')

            # Identificadores
            ident_html = f'<code>{carac_cfg.get("identificacao","")}</code>'
            extras     = carac_cfg.get('identificacoes_extras', [])
            if extras:
                ident_html += ' + ' + ' + '.join(f'<code>{e}</code>' for e in extras)
            mapas = carac_cfg.get('mapeamentos_literais', {})
            if mapas:
                mapa_txt = ', '.join(f'"{k}" → {v}' for k, v in mapas.items())
                ident_html += f'&nbsp; <span style="font-size:.74rem;color:#6b7060">Literais: {mapa_txt}</span>'
            html += f'<p style="font-size:.77rem;color:#6b7060;margin-bottom:5px">Identificadores: {ident_html}</p>\n'

            # Hierarquia visual
            hier   = info['hierarquia']
            iguais = info['iguais']
            props  = info.get('proporcionais', [])
            prop_map = {p['valor']: p for p in props}
            grupos_iguais_map = {v: tuple(sorted(g)) for g in iguais for v in g}
            grupos_mostrados  = set()

            html += '<p style="font-size:.8rem;color:#6b7060;margin-bottom:4px">Hierarquia (menor → maior preço):</p>\n'
            html += '<div class="hier-list">\n'
            for i, v in enumerate(hier):
                presente = v in set(info['valores_globais'])
                g_key    = grupos_iguais_map.get(v)
                ja_tinha = g_key and g_key in grupos_mostrados
                is_prop  = v in prop_map

                if i > 0:
                    html += ('<span class="hier-igual">=</span>\n' if ja_tinha
                             else '<span class="hier-arrow">→</span>\n')

                cls = 'hier-pill'
                if ja_tinha:     cls += ' igual'
                elif is_prop:    cls += ' prop'
                if not presente: cls += ' inativo'

                title_attr = ''
                if is_prop:
                    p_f = prop_map[v]['fator']
                    p_r = prop_map[v]['referencia']
                    title_attr = f' title="Esperado = {p_f}× {p_r}"'

                html += f'<div class="{cls}"{title_attr}>{i+1}. {v}</div>\n'
                if g_key:
                    grupos_mostrados.add(g_key)
            html += '</div>\n'

            # Legenda iguais / proporcionais
            legenda = []
            if iguais:
                legenda.append('⚑ Iguais: ' + ' &nbsp; '.join('[' + ' = '.join(g) + ']' for g in iguais))
            if props:
                legenda.append('⊙ Proporcionais (tolerância '
                               + f'{PROPORCIONAIS_LIMIAR_PCT*100:.0f}%): '
                               + ' &nbsp; '.join(
                                   f'[{p["valor"]} = {p["fator"]}×{p["referencia"]}]'
                                   for p in props))
            if legenda:
                html += f'<p class="inconsist-note">{" &nbsp;|&nbsp; ".join(legenda)}</p>\n'

            # Valores encontrados
            html += '<p style="margin:9px 0 3px;font-size:.81rem"><strong>Valores encontrados:</strong></p><div>\n'
            for v in info['valores_globais']:
                cls = 'tag hier' if v in set(hier) else 'tag extra'
                html += f'<span class="{cls}">{v}</span>'
            html += '</div>\n'
            if info['fora_hierarquia']:
                html += (f'<p class="inconsist-note">⚠ Fora da hierarquia: '
                         f'{", ".join(info["fora_hierarquia"])} (não entram na análise)</p>\n')

            # Valores por modulação
            html += '<p style="margin:11px 0 3px;font-size:.81rem"><strong>Valores por modulação:</strong></p>\n'
            html += '<table><thead><tr><th>Modulação</th><th>Valores</th><th>Status</th></tr></thead><tbody>\n'
            for mod, vals in info['por_modulacao'].items():
                missing = [v for v in info['hier_presentes'] if v not in set(vals)]
                st_mod  = (f'<span class="badge-err">Faltam: {", ".join(missing)}</span>'
                           if missing else '<span class="badge-ok">Completo</span>')
                tags = ''.join(
                    f'<span class="tag {"hier" if v in set(hier) else "extra"}">{v}</span>'
                    for v in vals)
                html += f'<tr><td><strong>{mod}</strong></td><td>{tags}</td><td>{st_mod}</td></tr>\n'
            html += '</tbody></table>\n'

            if info['inconsistencias_opcoes']:
                html += (f'<div class="alert-warn" style="margin-top:11px">'
                         f'<strong>⚠ {len(info["inconsistencias_opcoes"])} tamanho(s) com opções incompletas:</strong><br>\n')
                html += '<table style="margin-top:7px"><thead><tr><th>Modulação</th><th>Tamanho</th><th>Presentes</th><th>Faltam</th></tr></thead><tbody>\n'
                for inc in info['inconsistencias_opcoes']:
                    tags = ''.join(
                        f'<span class="tag {"hier" if v in set(hier) else "extra"}">{v}</span>'
                        for v in inc['valores'])
                    html += (f'<tr><td>{inc["modulacao"]}</td><td>{inc["dims"]}</td>'
                             f'<td>{tags}</td>'
                             f'<td style="color:#c0392b">{", ".join(inc["faltam"])}</td></tr>\n')
                html += '</tbody></table></div>\n'

            html += '</div></div>\n'

    html += '</div>\n'  # /section 1

    # ════════════════════════════════════════════════════════════════════
    # SEÇÃO 2
    # ════════════════════════════════════════════════════════════════════
    html += '<div class="section"><h2 class="sec-title">2. Análise de Progressão de Preços</h2>\n'
    html += ('<p style="font-size:.84rem;color:#6b7060;margin-bottom:20px">'
             'Demais características e dimensões são fixadas; verifica-se se a sequência '
             'respeita a hierarquia, igualdades e regras de proporcionalidade.</p>\n')

    for carac in CARACTERISTICAS:
        nome_c     = carac['nome']
        hierarquia = carac['hierarquia']
        if nome_c not in caracs_presentes:
            continue

        violacoes   = violacoes_carac.get(nome_c, [])
        trans_stat  = stats_transicoes.get(nome_c, {})
        prop_stat   = stats_proporcionais.get(nome_c, {})
        hier_adj    = {(hierarquia[i], hierarquia[i + 1]) for i in range(len(hierarquia) - 1)}

        html += f'<div class="carac-block"><div class="carac-header"><h3>{nome_c}</h3>'
        html += (f'<span class="badge-err">{len(violacoes)} violação(ões)</span>'
                 if violacoes else '<span class="badge-ok">Hierarquia respeitada</span>')
        html += '</div><div class="carac-body">\n'

        if violacoes:
            html += '<div class="alert-err">\n'
            html += f'<strong>⚠ {len(violacoes)} caso(s) com inconsistência:</strong>\n'
            html += ('<table class="viol-tbl"><thead><tr>'
                     '<th style="width:38%">Configuração de referência</th>'
                     '<th class="num" style="width:10%">Preço</th>'
                     '<th style="width:38%">Configuração com inconsistência</th>'
                     '<th class="num" style="width:10%">Preço</th>'
                     '<th class="num" style="width:9%">Var.</th>'
                     '</tr></thead><tbody>\n')
            for v in sorted(violacoes, key=lambda x: (x['modulacao'], x['dims'])):
                tipo_badge = {
                    'ordem':        '<span class="badge-err">ORDEM</span>',
                    'igual':        '<span class="badge-warn">IGUAL</span>',
                    'proporcional': '<span class="badge-prop">PROP</span>',
                }.get(v['tipo'], '')
                html += (f'<tr style="background:#fdedec">'
                         f'<td><div class="viol-config">{v["config1"]}</div>'
                         f'    <div class="viol-motivo">{tipo_badge} {v["motivo"]}</div></td>'
                         f'<td class="num viol-preco">R$\u00a0{v["preco1"]:,.2f}</td>'
                         f'<td><div class="viol-config">{v["config2"]}</div></td>'
                         f'<td class="num viol-preco">R$\u00a0{v["preco2"]:,.2f}</td>'
                         f'<td class="num pct-red">{v["pct"]:+.1f}%</td></tr>\n')
            html += '</tbody></table></div>\n'
        else:
            html += '<div class="alert-ok"><strong>✓ Todos os preços seguem a hierarquia, igualdades e proporções esperadas.</strong></div>\n'

        # Tabela de estatísticas por transição (hierarquia normal)
        trans_adj = {pair: pcts for pair, pcts in trans_stat.items() if pair in hier_adj}
        if trans_adj:
            html += ('<h4 class="sub-title" style="margin-top:15px;font-size:.88rem">'
                     'Acréscimos por transição de hierarquia:</h4>\n')
            html += ('<table><thead><tr>'
                     '<th>Transição</th><th class="num">Média</th>'
                     '<th class="num">Mín</th><th class="num">Máx</th>'
                     '<th class="num">n</th></tr></thead><tbody>\n')
            for i in range(len(hierarquia) - 1):
                pair = (hierarquia[i], hierarquia[i + 1])
                pcts = trans_adj.get(pair)
                if not pcts:
                    continue
                med  = statistics.mean(pcts)
                cls  = 'pct-ok' if med >= 0 else 'pct-neg'
                html += (f'<tr><td>{pair[0]} → {pair[1]}</td>'
                         f'<td class="num {cls}">{med:+.1f}%</td>'
                         f'<td class="num">{min(pcts):+.1f}%</td>'
                         f'<td class="num">{max(pcts):+.1f}%</td>'
                         f'<td class="num">{len(pcts)}</td></tr>\n')
            html += '</tbody></table>\n'

        # Tabela de estatísticas para regras de proporcionalidade
        if prop_stat:
            html += ('<h4 class="sub-title" style="margin-top:15px;font-size:.88rem">'
                     'Verificação das regras de proporcionalidade:</h4>\n')
            html += ('<table><thead><tr>'
                     '<th>Regra</th><th class="num">Esperado</th>'
                     '<th class="num">Média real</th>'
                     '<th class="num">Mín</th><th class="num">Máx</th>'
                     '<th class="num">n</th><th class="num">Violações</th>'
                     '</tr></thead><tbody>\n')
            for carac_data in CARACTERISTICAS:
                if carac_data['nome'] != nome_c:
                    continue
                for prop in carac_data.get('proporcionais', []):
                    key  = (prop['valor'], prop['referencia'])
                    pcts = prop_stat.get(key, [])
                    if not pcts:
                        continue
                    esperado_pct = (prop['fator'] - 1) * 100
                    med          = statistics.mean(pcts)
                    n_viol_prop  = sum(
                        1 for v in violacoes
                        if v['tipo'] == 'proporcional'
                        and v['val1'] == prop['referencia']
                        and v['val2'] == prop['valor'])
                    cor = 'pct-ok' if n_viol_prop == 0 else 'pct-red'
                    html += (f'<tr>'
                             f'<td>{prop["valor"]} = {prop["fator"]}× {prop["referencia"]}</td>'
                             f'<td class="num">{esperado_pct:+.1f}%</td>'
                             f'<td class="num {cor}">{med:+.1f}%</td>'
                             f'<td class="num">{min(pcts):+.1f}%</td>'
                             f'<td class="num">{max(pcts):+.1f}%</td>'
                             f'<td class="num">{len(pcts)}</td>'
                             f'<td class="num {cor}">{n_viol_prop}</td>'
                             f'</tr>\n')
            html += '</tbody></table>\n'

        html += '</div></div>\n'

    # Dimensões
    dim_labels = {'comp': 'Comprimento (COMP)', 'prof': 'Profundidade (PROF)', 'alt': 'Altura (ALT)'}
    for dim_var, dim_label in dim_labels.items():
        viol_d = violacoes_dim.get(dim_var, [])
        pcts_d = stats_dim_pcts.get(dim_var, [])
        if not pcts_d and not viol_d:
            continue

        html += f'<div class="carac-block"><div class="carac-header"><h3>Progressão por {dim_label}</h3>'
        html += (f'<span class="badge-err">{len(viol_d)} violação(ões)</span>'
                 if viol_d else '<span class="badge-ok">Progressão correta</span>')
        html += '</div><div class="carac-body">\n'

        if viol_d:
            html += '<div class="alert-err" style="margin-top:9px">\n'
            html += f'<strong>⚠ {len(viol_d)} violação(ões):</strong>\n'
            html += ('<table class="viol-tbl"><thead><tr>'
                     '<th style="width:38%">Dim. menor</th>'
                     '<th class="num" style="width:11%">Preço</th>'
                     '<th style="width:38%">Dim. maior</th>'
                     '<th class="num" style="width:11%">Preço</th>'
                     '<th class="num" style="width:7%">Var.</th>'
                     '</tr></thead><tbody>\n')
            for v in viol_d:
                html += (f'<tr style="background:#fdedec">'
                         f'<td><div class="viol-config">{v["config1"]}</div>'
                         f'    <div class="viol-motivo">{v["motivo"]}</div></td>'
                         f'<td class="num viol-preco">R$\u00a0{v["preco1"]:,.2f}</td>'
                         f'<td><div class="viol-config">{v["config2"]}</div></td>'
                         f'<td class="num viol-preco">R$\u00a0{v["preco2"]:,.2f}</td>'
                         f'<td class="num pct-red">{v["pct"]:+.1f}%</td></tr>\n')
            html += '</tbody></table></div>\n'
        else:
            html += '<div class="alert-ok"><strong>✓ Preços crescem corretamente com o aumento da dimensão.</strong></div>\n'

        if pcts_d:
            try:
                med  = statistics.mean(pcts_d)
                std  = statistics.stdev(pcts_d) if len(pcts_d) > 1 else 0
                html += (f'<p style="margin-top:9px;font-size:.81rem">'
                         f'Acréscimo médio por degrau: '
                         f'<strong style="color:#27ae60">{med:+.1f}%</strong>'
                         f'&nbsp;(σ={std:.1f}%, n={len(pcts_d)})</p>\n')
            except statistics.StatisticsError:
                pass

        html += '</div></div>\n'

    html += '</div>\n'  # /section 2

    # ════════════════════════════════════════════════════════════════════
    # SEÇÃO 3 — carrossel
    # ════════════════════════════════════════════════════════════════════
    html += '<div class="section"><h2 class="sec-title">3. Configurações com Progressão de Preços</h2>\n'
    html += ('<p style="font-size:.82rem;color:#6b7060;margin-bottom:12px">'
             'Ordenado por características (na ordem declarada) e depois por dimensões. '
             'Progressão sequencial só dentro do mesmo grupo de dimensões (╌ = quebra de tamanho). '
             'A coluna <em>Δ dim.</em> mostra a variação vs a mesma configuração com dimensão imediatamente anterior '
             '(passe o mouse para ver a referência).<br>'
             f'<span style="background:#fdedec;padding:2px 7px;border-radius:4px">'
             f'<strong style="color:#c0392b">■ Vermelho ({n_red})</strong>: violação de hierarquia</span>'
             f'&nbsp;<span style="background:#fffbe6;padding:2px 7px;border-radius:4px">'
             f'<strong style="color:#e67e22">■ Amarelo ({n_yellow})</strong>: outlier (&gt;{OUTLIER_LIMIAR:.0f}σ)</span>'
             '</p>\n')

    mods_js = ', '.join(f'"{m}"' for m, *_ in slides)
    html += '<div>\n<div class="carousel-nav">\n'
    html += '  <button class="btn-nav" id="c-prev" onclick="moveSlide(-1)" disabled>◀ Anterior</button>\n'
    html += '  <div class="carousel-dots" id="c-dots">\n'
    for i, (mod, *_) in enumerate(slides):
        html += f'    <div class="dot{"  active" if i==0 else ""}" onclick="goSlide({i})" title="{mod}"></div>\n'
    html += '  </div>\n'
    html += f'  <button class="btn-nav" id="c-next" onclick="moveSlide(1)"{" disabled" if len(slides)<=1 else ""}>Próximo ▶</button>\n'
    html += '  <span class="slide-counter" id="c-label"></span>\n</div>\n'

    for idx, (mod, grp, progs, dim_progs, cores_slide) in enumerate(slides):
        tem_dim_prog = any(dp[0] is not None for dp in dim_progs)

        html += f'<div class="slide{"  active" if idx==0 else ""}" id="slide_{idx}">\n'
        html += f'  <div class="slide-head">📦 {mod} &nbsp;·&nbsp; {len(grp)} configurações</div>\n'
        html += '  <div class="slide-body">\n'
        html += '    <table class="tbl-prog"><thead><tr>'
        html += '<th style="width:30px">#</th>'
        html += '<th>Configuração</th>'
        html += '<th class="num" style="width:125px">Preço (R$)</th>'
        html += '<th class="num" style="width:92px">Progressão</th>'
        if tem_dim_prog:
            html += '<th class="num" style="width:92px"><span class="th-dim">Δ dim.</span></th>'
        html += '</tr></thead><tbody>\n'

        prev_dims = None
        for i, (r, pct, dp, cor) in enumerate(zip(grp, progs, dim_progs, cores_slide)):
            curr_dims   = r['dims_str']
            row_classes = []
            if cor:
                row_classes.append(f'viol-{cor}')
            if prev_dims is not None and curr_dims != prev_dims:
                row_classes.append('dim-break')
            row_cls = f' class="{" ".join(row_classes)}"' if row_classes else ''

            # Progressão sequencial
            if pct is not None:
                pct_cls = ('pct-red'    if cor == 'red'    else
                           'pct-yellow' if cor == 'yellow' else
                           'pct-ok'     if pct >= 0        else 'pct-neg')
                pct_str = f'<span class="{pct_cls}">{pct:+.1f}%</span>'
            elif i == 0:
                pct_str = '<span class="pct-dash">—</span>'
            else:
                pct_str = '<span class="pct-dash" title="Quebra de grupo dimensional">╌</span>'

            # Progressão dimensional cruzada
            if tem_dim_prog:
                dp_pct, dp_cfg, dp_dim = dp
                if dp_pct is not None:
                    dp_cls   = 'pct-dim-ok' if dp_pct >= 0 else 'pct-dim-neg'
                    dim_lbl  = {'comp': 'COMP', 'prof': 'PROF', 'alt': 'ALT'}.get(dp_dim, '')
                    dp_safe  = (dp_cfg or '').replace('"', '&quot;')
                    dp_str   = (f'<abbr class="dim-ref {dp_cls}" title="vs {dp_safe}">'
                                f'{dp_pct:+.1f}%</abbr>'
                                f'<span class="dim-label">({dim_lbl}↓)</span>')
                else:
                    dp_str = '<span class="pct-dash">—</span>'

            html += f'    <tr{row_cls}>'
            html += f'<td style="color:#aaa;font-size:.71rem">{i+1}</td>'
            html += f'<td class="config-cell">{r["configuracao"]}</td>'
            html += f'<td class="preco-cell">R$\u00a0{r["preco"]:,.2f}</td>'
            html += f'<td class="num">{pct_str}</td>'
            if tem_dim_prog:
                html += f'<td class="num">{dp_str}</td>'
            html += '</tr>\n'

            prev_dims = curr_dims

        html += '    </tbody></table>\n'
        html += '  </div></div>\n'

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
    prev.disabled = cur===0;
    next.disabled = cur===slides.length-1;
    lbl.textContent = (cur+1)+' / '+slides.length+'  —  '+mods[cur];
  }}
  window.moveSlide = function(d){{ cur=Math.max(0,Math.min(slides.length-1,cur+d)); upd(); }};
  window.goSlide   = function(i){{ cur=i; upd(); }};
  upd();
}})();
</script>
</div>
"""

    html += '</div>\n'  # /section 3

    html += f"""
  </div><!-- content -->
  <div class="footer">
    Relatório de Análise de Preços · {produto_nome} ·
    Gerado em {datetime.now().strftime('%d/%m/%Y %H:%M')}
  </div>
</div><!-- wrap -->
</body></html>
"""

    nome_saida = os.path.splitext(arquivo_excel)[0] + '_analise.html'
    with open(nome_saida, 'w', encoding='utf-8') as f:
        f.write(html)

    print(f'\n{"="*68}')
    print('RELATORIO GERADO')
    print(f'{"="*68}')
    print(f'Arquivo: {nome_saida}')
    print(f'Status : {"SEM VIOLACOES" if status_ok else f"{total_viol} VIOLACAO(OES)"}')
    print(f'  Carac: {total_viol_carac} | Dim: {total_viol_dim}')

    import webbrowser
    webbrowser.open(f'file:///{os.path.abspath(nome_saida)}')


# ===========================================================================
# ENTRY POINT
# ===========================================================================
if __name__ == '__main__':
    if len(sys.argv) >= 2:
        arquivo = sys.argv[1]
    else:
        candidatos = [f for f in os.listdir('.') if f.lower().endswith('.xlsx')]
        if len(candidatos) == 1:
            arquivo = candidatos[0]
            print(f'Usando: {arquivo}')
        else:
            print('Uso: python analisar_precos_madeira.py <arquivo.xlsx>')
            if candidatos:
                print(f'Disponiveis: {", ".join(candidatos)}')
            sys.exit(1)

    analisar_e_gerar_html(arquivo)