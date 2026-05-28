# === Dashboard v3: Premium GovTech, dados direto do MongoDB Atlas ===
# Lê tudo de db (Mongo Atlas) já conectado pela Célula B.
# Dependências: plotly, networkx, pymongo (já instalados na Célula 1)

import json
import math
import random
import re
from pathlib import Path

import networkx as nx
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots


# ─── 1. CARREGA TUDO DO MONGO (não usa CSV nenhum) ───────────────────
print("📡 Carregando dados do Atlas...")

regioes_docs = list(db.regioes.find({}))
estab_docs = list(db.estabelecimentos.find({}))

# DataFrame de regiões direto do Mongo
df_indic = pd.DataFrame([{
    "regiao":         d["regiao"],
    "populacao":      d["populacao"],
    "UBS":            d["unidades"]["ubs"],
    "Hospital":       d["unidades"]["hospital"],
    "UPA":            d["unidades"]["upa"],
    "total_unidades": d["unidades"]["total"],
    "lat":            d["centroide"]["coordinates"][1],
    "lon":            d["centroide"]["coordinates"][0],
    "hab_por_ubs":    d["indicadores"]["hab_por_ubs"],
    "cobertura":      d["indicadores"]["cobertura"],
} for d in regioes_docs]).sort_values("hab_por_ubs", ascending=False).reset_index(drop=True)

df_estab = pd.DataFrame([{
    "codigo_cnes":   d["_id"],
    "nome":          d["nome"],
    "categoria":     d["tipo"]["categoria"],
    "tipo_desc":     d["tipo"]["descricao"],
    "bairro":        d["endereco"]["bairro"],
    "regiao":        d["endereco"]["regiao"],
    "latitude":      d["localizacao"]["coordinates"][1],
    "longitude":     d["localizacao"]["coordinates"][0],
    "is_sus":        d["vinculo_sus"],
    "natureza":      d["natureza"],
} for d in estab_docs])

df_sus = df_estab[df_estab["is_sus"]].copy()
print(f"✓ {len(df_indic)} distritos · {len(df_estab)} estabelecimentos "
      f"({len(df_sus)} SUS)")


# ─── 2. RISK SCORE 0-100 por distrito ────────────────────────────────
# Calcula um score composto baseado em 4 fatores:
#   - Pressão UBS  (hab_por_ubs alto = ruim)
#   - Cobertura SUS (poucas UBS por pop = ruim)
#   - Falta hospitalar (poucos hospitais = ruim)
#   - Falta UPA (poucas UPAs = ruim)
def risk_score(row, df_all):
    # Normaliza cada métrica 0-1 (1 = pior)
    max_hab_ubs = df_all["hab_por_ubs"].max() or 1
    pressao_ubs = row["hab_por_ubs"] / max_hab_ubs

    pop_per_hosp = row["populacao"] / max(row["Hospital"], 1)
    max_pop_hosp = (df_all["populacao"] / df_all["Hospital"].replace(0, 1)).max() or 1
    falta_hosp = pop_per_hosp / max_pop_hosp

    pop_per_upa = row["populacao"] / max(row["UPA"], 1)
    max_pop_upa = (df_all["populacao"] / df_all["UPA"].replace(0, 1)).max() or 1
    falta_upa = pop_per_upa / max_pop_upa

    densidade_inv = 1 - (row["total_unidades"] /
                        (df_all["total_unidades"].max() or 1))

    # Pesos: pressão UBS é o mais importante
    score = (pressao_ubs * 0.40 + falta_hosp * 0.25 +
             falta_upa * 0.20 + densidade_inv * 0.15) * 100
    return round(score, 1)

df_indic["risk_score"] = df_indic.apply(
    lambda r: risk_score(r, df_indic), axis=1)


def classificar_risco(s):
    if s >= 75: return "Crítico"
    if s >= 50: return "Alto"
    if s >= 25: return "Moderado"
    return "Baixo"

df_indic["risco_nivel"] = df_indic["risk_score"].apply(classificar_risco)


# ─── 3. PALETA DARK GOVTECH ──────────────────────────────────────────
PALETA = {
    "bg":          "#0A0E1A",
    "bg_card":     "#131929",
    "bg_elevated": "#1A2238",
    "border":      "#1E2A45",
    "text":        "#E5EEFF",
    "text_dim":    "#8B95B7",
    "text_muted":  "#5B6584",
    "primary":     "#5B8DEF",
    "accent":      "#00D4AA",
    "warn":        "#FFB547",
    "crit":        "#FF5C7C",
    "ok":          "#00D4AA",
    "ubs":         "#5B8DEF",
    "hospital":    "#FF5C7C",
    "upa":         "#FFB547",
}

CORES_RISCO = {
    "Crítico": PALETA["crit"],
    "Alto": "#FF8A6E",
    "Moderado": PALETA["warn"],
    "Baixo": PALETA["ok"],
}

LAYOUT_DARK = dict(
    template="plotly_dark",
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font=dict(family="Inter, -apple-system, sans-serif",
              size=12, color=PALETA["text_dim"]),
    margin=dict(l=20, r=20, t=50, b=20),
    xaxis=dict(gridcolor=PALETA["border"], zerolinecolor=PALETA["border"]),
    yaxis=dict(gridcolor=PALETA["border"], zerolinecolor=PALETA["border"]),
)


# ─── 4. GRÁFICOS ─────────────────────────────────────────────────────

# G1: Risk Score por distrito (barras horizontais)
df_risk = df_indic.sort_values("risk_score", ascending=True)
g1 = go.Figure(go.Bar(
    x=df_risk["risk_score"], y=df_risk["regiao"], orientation="h",
    marker=dict(
        color=[CORES_RISCO[r] for r in df_risk["risco_nivel"]],
        line=dict(width=0),
    ),
    text=df_risk["risk_score"].apply(lambda v: f"{v:.0f}"),
    textposition="outside",
    textfont=dict(color=PALETA["text"], size=13, family="Inter"),
    customdata=df_risk[["risco_nivel", "populacao", "UBS"]].values,
    hovertemplate=("<b>%{y}</b><br>"
                   "Risk Score: <b>%{x:.1f}/100</b><br>"
                   "Nível: %{customdata[0]}<br>"
                   "População: %{customdata[1]:,}<br>"
                   "UBS: %{customdata[2]}<extra></extra>"),
))
g1.update_layout(
    title=dict(text="<b>Risk Score por distrito</b>",
               font=dict(color=PALETA["text"], size=14)),
    height=380,
    template="plotly_dark",
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font=dict(family="Inter, -apple-system, sans-serif",
              size=12, color=PALETA["text_dim"]),
    margin=dict(l=20, r=20, t=50, b=20),
    xaxis=dict(range=[0, 110], gridcolor=PALETA["border"],
               zerolinecolor=PALETA["border"]),
    yaxis=dict(gridcolor=PALETA["border"], zerolinecolor=PALETA["border"]),
)

# G2: Hab por UBS — visão crítica
df_hab = df_indic.sort_values("hab_por_ubs", ascending=True)
g2 = go.Figure(go.Bar(
    x=df_hab["hab_por_ubs"], y=df_hab["regiao"], orientation="h",
    marker=dict(color=[CORES_RISCO[r] for r in df_hab["risco_nivel"]],
                line=dict(width=0)),
    text=df_hab["hab_por_ubs"].apply(lambda v: f"{v:,.0f}".replace(",", ".")),
    textposition="outside",
    textfont=dict(color=PALETA["text"], size=12),
    hovertemplate="<b>%{y}</b><br>%{x:,.0f} hab/UBS<extra></extra>",
))
# Linhas de referência MS
for x_val, label, cor in [(5000, "Recomendado", PALETA["ok"]),
                          (20000, "Limite crítico", PALETA["crit"])]:
    g2.add_vline(x=x_val, line_dash="dash", line_color=cor, line_width=1,
                 opacity=0.4)
g2.update_layout(
    title=dict(text="<b>Pressão sobre atenção básica (hab/UBS)</b>",
               font=dict(color=PALETA["text"], size=14)),
    height=380, **LAYOUT_DARK,
)

# G3: Composição SUS × Privado (stacked + percent)
contagem = pd.crosstab(df_estab["categoria"], df_estab["is_sus"])
contagem.columns = ["Privado", "SUS"]
g3 = go.Figure()
g3.add_bar(name="SUS", x=contagem.index, y=contagem["SUS"],
           marker_color=PALETA["accent"],
           text=contagem["SUS"], textposition="inside",
           textfont=dict(color="#0A0E1A", size=12))
g3.add_bar(name="Privado", x=contagem.index, y=contagem["Privado"],
           marker_color=PALETA["text_muted"],
           text=contagem["Privado"], textposition="inside",
           textfont=dict(color=PALETA["text"], size=12))
g3.update_layout(
    title=dict(text="<b>SUS × Privado por categoria</b>",
               font=dict(color=PALETA["text"], size=14)),
    barmode="stack", height=320, **LAYOUT_DARK,
    legend=dict(orientation="h", y=-0.18, x=0.5, xanchor="center",
                bgcolor="rgba(0,0,0,0)"),
)

# G4: Donut — categorias
cont_cat = df_estab["categoria"].value_counts()
g4 = go.Figure(go.Pie(
    labels=cont_cat.index, values=cont_cat.values, hole=0.65,
    marker=dict(colors=[PALETA["ubs"], PALETA["hospital"], PALETA["upa"]],
                line=dict(color=PALETA["bg"], width=3)),
    textinfo="label+percent",
    textfont=dict(color=PALETA["text"], size=12),
    hovertemplate="<b>%{label}</b><br>%{value} unidades<br>%{percent}<extra></extra>",
))
g4.update_layout(
    title=dict(text=f"<b>Distribuição da rede ({len(df_estab)} unidades)</b>",
               font=dict(color=PALETA["text"], size=14)),
    height=320, **LAYOUT_DARK,
    showlegend=False,
    annotations=[dict(text=f"<b style='color:{PALETA['text']};font-size:24px;'>"
                          f"{len(df_estab)}</b><br>"
                          f"<span style='color:{PALETA['text_dim']};font-size:11px;'>"
                          f"Total</span>",
                      x=0.5, y=0.5, font_size=14, showarrow=False)],
)

# G5: RADAR multidimensional (WOW factor)
def normalize(s, invert=False):
    mn, mx = s.min(), s.max()
    if mx == mn: return [50] * len(s)
    norm = (s - mn) / (mx - mn) * 100
    return (100 - norm) if invert else norm

# Para o radar: quanto MAIOR melhor (inverte risk e hab_por_ubs)
df_radar = df_indic.copy()
df_radar["pop_norm"] = normalize(df_radar["populacao"])
df_radar["ubs_norm"] = normalize(df_radar["UBS"])
df_radar["hosp_norm"] = normalize(df_radar["Hospital"])
df_radar["upa_norm"] = normalize(df_radar["UPA"])
df_radar["cob_norm"] = normalize(df_radar["hab_por_ubs"], invert=True)

categorias_radar = ["População", "UBS", "Hospitais", "UPAs", "Cobertura"]
g5 = go.Figure()
cores_radar = [PALETA["primary"], PALETA["accent"], PALETA["warn"],
               PALETA["crit"], "#A78BFA"]
for i, (_, r) in enumerate(df_radar.iterrows()):
    valores = [r["pop_norm"], r["ubs_norm"], r["hosp_norm"],
               r["upa_norm"], r["cob_norm"]]
    g5.add_trace(go.Scatterpolar(
        r=valores + [valores[0]],
        theta=categorias_radar + [categorias_radar[0]],
        name=r["regiao"],
        line=dict(color=cores_radar[i % len(cores_radar)], width=2),
        fill="toself", fillcolor=cores_radar[i % len(cores_radar)],
        opacity=0.25,
        hovertemplate=f"<b>{r['regiao']}</b><br>%{{theta}}: %{{r:.0f}}<extra></extra>",
    ))
g5.update_layout(
    title=dict(text="<b>Perfil multidimensional por distrito</b>",
               font=dict(color=PALETA["text"], size=14)),
    polar=dict(
        bgcolor=PALETA["bg_elevated"],
        radialaxis=dict(visible=True, range=[0, 100],
                        gridcolor=PALETA["border"],
                        tickfont=dict(color=PALETA["text_muted"], size=10)),
        angularaxis=dict(gridcolor=PALETA["border"],
                         tickfont=dict(color=PALETA["text_dim"], size=11)),
    ),
    height=480,
    template="plotly_dark",
    paper_bgcolor="rgba(0,0,0,0)",
    font=dict(family="Inter, sans-serif", color=PALETA["text_dim"]),
    margin=dict(l=20, r=20, t=50, b=20),
    legend=dict(orientation="h", y=-0.08, x=0.5, xanchor="center",
                bgcolor="rgba(0,0,0,0)",
                font=dict(color=PALETA["text_dim"], size=11)),
)

# G6: TREEMAP hierárquico (corrigido + premium)
# Usa branchvalues='remainder' pra evitar bug de soma de filhos > pai
labels = []
parents = []
values = []
colors = []
texts = []
total_sus = len(df_sus)

# Calcula por distrito pra ordenar do maior pro menor
distritos_ordenados = (df_sus.groupby("regiao").size()
                       .sort_values(ascending=False).index.tolist())

for distrito in distritos_ordenados:
    sub_d = df_sus[df_sus["regiao"] == distrito]
    n_dist = len(sub_d)
    pct_dist = n_dist / total_sus * 100
    labels.append(distrito)
    parents.append("")
    values.append(n_dist)
    colors.append(PALETA["bg_elevated"])
    texts.append(f"<b>{distrito}</b><br>"
                 f"<span style='font-size:11px;opacity:0.7'>{n_dist} un · "
                 f"{pct_dist:.1f}%</span>")
    for cat in ["UBS", "Hospital", "UPA"]:
        sub_c = sub_d[sub_d["categoria"] == cat]
        if len(sub_c) == 0:
            continue
        n_cat = len(sub_c)
        pct_in_dist = n_cat / n_dist * 100
        cat_label = f"{cat} · {distrito}"
        labels.append(cat_label)
        parents.append(distrito)
        values.append(n_cat)
        cor_cat = {"UBS": PALETA["ubs"],
                   "Hospital": PALETA["hospital"],
                   "UPA": PALETA["upa"]}[cat]
        colors.append(cor_cat)
        texts.append(f"<b>{cat}</b><br>"
                     f"<span style='font-size:11px;opacity:0.85'>{n_cat} un · "
                     f"{pct_in_dist:.0f}% do distrito</span>")

g6 = go.Figure(go.Treemap(
    labels=labels,
    parents=parents,
    values=values,
    text=texts,
    textinfo="text",
    marker=dict(
        colors=colors,
        line=dict(color=PALETA["bg"], width=3),
        pad=dict(t=4, l=4, r=4, b=4),
        cornerradius=8,
    ),
    textfont=dict(family="Inter", size=12, color="white"),
    hovertemplate=("<b>%{label}</b><br>"
                   "Unidades: %{value}<br>"
                   "%{percentRoot} do total SUS<extra></extra>"),
    pathbar=dict(visible=True,
                 thickness=22,
                 textfont=dict(family="Inter", size=12, color=PALETA["text"])),
    tiling=dict(packing="squarify", pad=2),
    branchvalues="remainder",  # ← correção do bug
))
g6.update_layout(
    title=dict(text=f"<b>Composição hierárquica da rede SUS</b>  "
                    f"<span style='color:{PALETA['text_muted']};font-size:11px;'>"
                    f"({total_sus} unidades · clique para drill-down)</span>",
               font=dict(color=PALETA["text"], size=14)),
    height=440,
    template="plotly_dark",
    paper_bgcolor="rgba(0,0,0,0)",
    margin=dict(l=20, r=20, t=60, b=20),
    font=dict(family="Inter, sans-serif"),
)

# G7: SANKEY hierárquico — Distrito → UBS/UPA → Hospital
# Substitui o grafo network anterior por um fluxo horizontal limpo

# Construir nós em 3 camadas:
# Camada 0: distritos (5 nós)
# Camada 1: UBS/UPA agrupados por distrito (X nós)
# Camada 2: hospitais agrupados por distrito (Y nós)

distritos_sus = sorted(df_sus["regiao"].unique())

# IDs únicos dos nós e suas posições
sankey_nodes = []
node_ids = {}  # nome → idx

def add_node(label, color, x, y):
    idx = len(sankey_nodes)
    sankey_nodes.append({"label": label, "color": color, "x": x, "y": y})
    return idx

# CAMADA 0: distritos (espaçados verticalmente)
n_dist = len(distritos_sus)
for i, d in enumerate(distritos_sus):
    pop = int(df_indic[df_indic["regiao"] == d]["populacao"].values[0])
    label = f"{d} ({pop//1000}k hab)"
    y = (i + 0.5) / n_dist
    node_ids[("dist", d)] = add_node(label, PALETA["primary"], 0.01, y)

# CAMADA 1: hubs de atenção básica (UBS+UPA) por distrito
n_hubs = 0
hubs_per_dist = {}  # distrito → [idx_ubs_hub, idx_upa_hub]
for i, d in enumerate(distritos_sus):
    sub = df_sus[df_sus["regiao"] == d]
    n_ubs = (sub["categoria"] == "UBS").sum()
    n_upa = (sub["categoria"] == "UPA").sum()
    hubs_per_dist[d] = {"UBS": None, "UPA": None}
    if n_ubs > 0:
        y = (i * 2 + 0.5) / (n_dist * 2)
        idx = add_node(f"UBS · {d} ({n_ubs})", PALETA["ubs"], 0.50, y)
        node_ids[("ubs", d)] = idx
        hubs_per_dist[d]["UBS"] = idx
        n_hubs += 1
    if n_upa > 0:
        y = (i * 2 + 1.5) / (n_dist * 2)
        idx = add_node(f"UPA · {d} ({n_upa})", PALETA["upa"], 0.50, y)
        node_ids[("upa", d)] = idx
        hubs_per_dist[d]["UPA"] = idx
        n_hubs += 1

# CAMADA 2: hospitais consolidados por distrito (1 nó por distrito que tem hospital)
hosp_per_dist = {}
n_dists_com_hosp = sum(1 for d in distritos_sus
                        if (df_sus[df_sus["regiao"] == d]["categoria"] == "Hospital").sum() > 0)
hosp_y_step = 0
for d in distritos_sus:
    n_h = (df_sus[(df_sus["regiao"] == d) & (df_sus["categoria"] == "Hospital")]).shape[0]
    if n_h == 0:
        hosp_per_dist[d] = None
        continue
    y = (hosp_y_step + 0.5) / n_dists_com_hosp if n_dists_com_hosp > 0 else 0.5
    idx = add_node(f"Hospitais · {d} ({n_h})", PALETA["hospital"], 0.99, y)
    hosp_per_dist[d] = idx
    hosp_y_step += 1

# LIGAÇÕES (links) com espessura proporcional ao fluxo:
# - distrito → UBS-hub (espessura = nº de UBS)
# - distrito → UPA-hub (espessura = nº de UPA)
# - UBS-hub  → hospital-hub (toda UBS referencia hospital do próprio distrito)
# - UPA-hub  → hospital-hub
# - distrito → hospital-hub direto (caso especial: pacientes acessam hospital diretamente)

links_src, links_tgt, links_val, links_color = [], [], [], []

def hex_with_alpha(hex_color, alpha):
    """Converte #RRGGBB pra rgba(r,g,b,alpha)."""
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return f"rgba({r},{g},{b},{alpha})"

for d in distritos_sus:
    n_ubs = int((df_sus[(df_sus["regiao"] == d) & (df_sus["categoria"] == "UBS")]).shape[0])
    n_upa = int((df_sus[(df_sus["regiao"] == d) & (df_sus["categoria"] == "UPA")]).shape[0])
    n_hosp = int((df_sus[(df_sus["regiao"] == d) & (df_sus["categoria"] == "Hospital")]).shape[0])

    src_dist = node_ids[("dist", d)]

    # Distrito → UBS hub
    if n_ubs > 0:
        links_src.append(src_dist)
        links_tgt.append(node_ids[("ubs", d)])
        links_val.append(n_ubs)
        links_color.append(hex_with_alpha(PALETA["ubs"], 0.35))

    # Distrito → UPA hub
    if n_upa > 0:
        links_src.append(src_dist)
        links_tgt.append(node_ids[("upa", d)])
        links_val.append(n_upa)
        links_color.append(hex_with_alpha(PALETA["upa"], 0.35))

    # UBS hub → Hospital hub
    if n_ubs > 0 and hosp_per_dist[d] is not None:
        links_src.append(node_ids[("ubs", d)])
        links_tgt.append(hosp_per_dist[d])
        links_val.append(n_ubs)
        links_color.append(hex_with_alpha(PALETA["hospital"], 0.25))

    # UPA hub → Hospital hub
    if n_upa > 0 and hosp_per_dist[d] is not None:
        links_src.append(node_ids[("upa", d)])
        links_tgt.append(hosp_per_dist[d])
        links_val.append(n_upa)
        links_color.append(hex_with_alpha(PALETA["hospital"], 0.25))

    # Caso o distrito tenha hospital mas nem UBS nem UPA → link direto distrito→hospital
    if n_ubs == 0 and n_upa == 0 and hosp_per_dist[d] is not None:
        links_src.append(src_dist)
        links_tgt.append(hosp_per_dist[d])
        links_val.append(n_hosp)
        links_color.append(hex_with_alpha(PALETA["hospital"], 0.35))

g7 = go.Figure(go.Sankey(
    arrangement="snap",  # respeita posições x/y manuais
    node=dict(
        label=[n["label"] for n in sankey_nodes],
        color=[n["color"] for n in sankey_nodes],
        x=[n["x"] for n in sankey_nodes],
        y=[n["y"] for n in sankey_nodes],
        pad=20,
        thickness=22,
        line=dict(color=PALETA["bg"], width=2),
    ),
    link=dict(
        source=links_src,
        target=links_tgt,
        value=links_val,
        color=links_color,
        hovertemplate=("<b>%{source.label}</b> → <b>%{target.label}</b><br>"
                       "%{value} unidades<extra></extra>"),
    ),
    textfont=dict(family="Inter", size=11, color=PALETA["text"]),
))
g7.update_layout(
    title=dict(text=("<b>Rede de Referência Hospitalar</b>  "
                     f"<span style='color:{PALETA['text_muted']};font-size:11px;'>"
                     "Distrito → Atenção Básica → Hospitais</span>"),
               font=dict(color=PALETA["text"], size=14)),
    height=600,
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    margin=dict(l=20, r=20, t=60, b=20),
    font=dict(family="Inter, sans-serif"),
)


# ─── 5. INSIGHTS AUTOMÁTICOS ─────────────────────────────────────────
top_risco = df_indic.nlargest(1, "risk_score").iloc[0]
top_pop = df_indic.nlargest(1, "populacao").iloc[0]
pior_cob = df_indic.nlargest(1, "hab_por_ubs").iloc[0]
melhor_cob = df_indic[df_indic["UBS"] > 0].nsmallest(1, "hab_por_ubs").iloc[0]
n_critica = (df_indic["risco_nivel"] == "Crítico").sum() + \
            (df_indic["risco_nivel"] == "Alto").sum()
pop_critica_total = int(df_indic[
    df_indic["risco_nivel"].isin(["Crítico", "Alto"])
]["populacao"].sum())
n_sus = len(df_sus)
n_priv = len(df_estab) - n_sus
pct_priv = n_priv / len(df_estab) * 100

# ─── 6. PREPARA MARKERS PRO MAPA LEAFLET ─────────────────────────────
markers_data = []
for _, e in df_sus.iterrows():
    markers_data.append({
        "lat": float(e["latitude"]),
        "lng": float(e["longitude"]),
        "nome": str(e["nome"])[:60].replace("'", "&#39;"),
        "categoria": e["categoria"],
        "regiao": e["regiao"],
    })

# Adiciona ranking visual de risco (badge HTML)
def badge_risco(nivel):
    cor = CORES_RISCO[nivel]
    return (f'<span class="badge" style="background:{cor}1A;color:{cor};'
            f'border-color:{cor}66;">{nivel}</span>')

ranking_rows = ""
for _, r in df_indic.sort_values("risk_score", ascending=False).iterrows():
    # Mini barra de risco visual
    bar_pct = r["risk_score"]
    cor = CORES_RISCO[r["risco_nivel"]]
    ranking_rows += f"""
    <tr>
      <td><b>{r['regiao']}</b></td>
      <td>{r['populacao']:,}</td>
      <td>{int(r['UBS'])}</td>
      <td>{int(r['Hospital'])}</td>
      <td>{int(r['UPA'])}</td>
      <td>{r['hab_por_ubs']:,.0f}</td>
      <td>
        <div class="score-bar-wrap">
          <div class="score-bar" style="width:{bar_pct}%;background:{cor};"></div>
          <span class="score-val">{r['risk_score']:.0f}</span>
        </div>
      </td>
      <td>{badge_risco(r['risco_nivel'])}</td>
    </tr>"""


# ─── 7. MONTAGEM DO HTML ─────────────────────────────────────────────
def to_div(fig, did):
    return fig.to_html(include_plotlyjs=False, full_html=False, div_id=did,
                       config={"displayModeBar": False, "responsive": True})


markers_json = json.dumps(markers_data, ensure_ascii=False)

CSS = """
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  :root {
    --bg: #0A0E1A;
    --bg-card: #131929;
    --bg-elev: #1A2238;
    --border: #1E2A45;
    --border-strong: #2A3656;
    --text: #E5EEFF;
    --text-dim: #8B95B7;
    --text-muted: #5B6584;
    --primary: #5B8DEF;
    --accent: #00D4AA;
    --warn: #FFB547;
    --crit: #FF5C7C;
    --ok: #00D4AA;
    --shadow-sm: 0 1px 2px rgba(0,0,0,0.4);
    --shadow-md: 0 4px 16px rgba(0,0,0,0.3), 0 1px 2px rgba(0,0,0,0.4);
    --shadow-lg: 0 20px 50px rgba(0,0,0,0.5);
    --shadow-glow: 0 0 0 1px rgba(91,141,239,0.2), 0 12px 32px rgba(91,141,239,0.15);
  }
  body {
    font-family: 'Inter', -apple-system, system-ui, sans-serif;
    background: var(--bg);
    color: var(--text);
    line-height: 1.55;
    -webkit-font-smoothing: antialiased;
    min-height: 100vh;
    overflow-x: hidden;
  }
  body::before {
    content: '';
    position: fixed; inset: 0; z-index: 0; pointer-events: none;
    background:
      radial-gradient(circle at 15% 0%, rgba(91,141,239,0.08), transparent 50%),
      radial-gradient(circle at 85% 100%, rgba(0,212,170,0.06), transparent 50%);
  }
  .container { max-width: 1500px; margin: 0 auto; padding: 32px 24px; position: relative; z-index: 1; }

  /* HERO */
  header.hero {
    background: linear-gradient(135deg, #0F1530 0%, #0A0E1A 100%);
    border-bottom: 1px solid var(--border);
    padding: 32px 24px 40px;
    position: relative;
    overflow: hidden;
  }
  header.hero::after {
    content: '';
    position: absolute; top: 0; right: 0; width: 60%; height: 100%;
    background: radial-gradient(ellipse at top right, rgba(91,141,239,0.15), transparent 60%);
    pointer-events: none;
  }
  .hero-content {
    max-width: 1500px; margin: 0 auto; position: relative; z-index: 1;
    display: grid; grid-template-columns: 1fr auto; gap: 32px; align-items: start;
  }
  .pill {
    display: inline-flex; align-items: center; gap: 6px;
    background: rgba(91,141,239,0.1); color: var(--primary);
    padding: 4px 12px; border-radius: 100px; font-size: 11px;
    letter-spacing: 1.5px; text-transform: uppercase; font-weight: 600;
    border: 1px solid rgba(91,141,239,0.25); margin-bottom: 16px;
  }
  .pill::before {
    content: ''; width: 6px; height: 6px; border-radius: 50%;
    background: var(--accent); box-shadow: 0 0 8px var(--accent);
    animation: pulse 2s infinite;
  }
  @keyframes pulse {
    0%, 100% { opacity: 1; transform: scale(1); }
    50% { opacity: 0.6; transform: scale(0.85); }
  }
  header.hero h1 {
    font-size: 36px; font-weight: 800; letter-spacing: -0.8px;
    line-height: 1.15; margin-bottom: 12px;
    background: linear-gradient(135deg, #E5EEFF 0%, #8B95B7 100%);
    -webkit-background-clip: text; -webkit-text-fill-color: transparent;
    background-clip: text;
  }
  header.hero .subtitle {
    font-size: 16px; color: var(--text-dim); max-width: 720px; margin-bottom: 20px;
  }
  .meta { display: flex; gap: 24px; flex-wrap: wrap; font-size: 12px; color: var(--text-muted); }
  .meta span { display: flex; align-items: center; gap: 6px; }
  .meta .dot { width: 4px; height: 4px; border-radius: 50%; background: var(--text-muted); }

  /* DIAGNÓSTICO EXECUTIVO */
  .diag-card {
    background: linear-gradient(135deg, rgba(255,92,124,0.08), rgba(91,141,239,0.04));
    border: 1px solid rgba(255,92,124,0.25);
    border-radius: 16px;
    padding: 24px 28px;
    min-width: 360px;
    backdrop-filter: blur(20px);
    -webkit-backdrop-filter: blur(20px);
    box-shadow: 0 8px 32px rgba(255,92,124,0.08);
  }
  .diag-label {
    font-size: 11px; color: var(--crit); font-weight: 700;
    letter-spacing: 1.5px; text-transform: uppercase; margin-bottom: 8px;
    display: flex; align-items: center; gap: 8px;
  }
  .diag-label::before {
    content: '⚠'; font-size: 14px;
  }
  .diag-title { font-size: 22px; font-weight: 700; color: var(--text); margin-bottom: 12px; line-height: 1.3; }
  .diag-stats { display: flex; gap: 24px; margin-top: 16px; padding-top: 16px; border-top: 1px solid var(--border); }
  .diag-stat { flex: 1; }
  .diag-stat-val { font-size: 24px; font-weight: 800; color: var(--text); letter-spacing: -0.5px; }
  .diag-stat-lbl { font-size: 11px; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.8px; margin-top: 4px; }

  /* KPI cards */
  .kpis {
    display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
    gap: 12px; margin: 32px 0;
  }
  .kpi {
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 18px 20px;
    transition: all 0.3s cubic-bezier(.4,0,.2,1);
    position: relative; overflow: hidden;
  }
  .kpi::before {
    content: ''; position: absolute; left: 0; top: 0; bottom: 0;
    width: 2px; background: var(--primary); opacity: 0.6;
  }
  .kpi.crit::before { background: var(--crit); }
  .kpi.ok::before { background: var(--ok); }
  .kpi.warn::before { background: var(--warn); }
  .kpi:hover {
    transform: translateY(-2px);
    border-color: var(--border-strong);
    box-shadow: var(--shadow-md);
  }
  .kpi-icon {
    font-size: 16px; opacity: 0.5; margin-bottom: 6px;
  }
  .kpi-val {
    font-size: 24px; font-weight: 800; color: var(--text);
    letter-spacing: -0.5px; line-height: 1;
    font-variant-numeric: tabular-nums;
  }
  .kpi.crit .kpi-val { color: var(--crit); }
  .kpi.ok .kpi-val { color: var(--ok); }
  .kpi.warn .kpi-val { color: var(--warn); }
  .kpi-lbl {
    font-size: 10px; color: var(--text-muted); margin-top: 6px;
    text-transform: uppercase; letter-spacing: 0.8px; font-weight: 600;
  }
  .kpi-trend { font-size: 11px; margin-top: 4px; color: var(--text-dim); }

  /* SECTIONS */
  section { margin-top: 48px; }
  .section-head {
    display: flex; align-items: baseline; justify-content: space-between;
    margin-bottom: 20px;
  }
  .section-head h2 {
    font-size: 20px; font-weight: 700; color: var(--text);
    letter-spacing: -0.3px;
  }
  .section-head .num {
    color: var(--primary); margin-right: 8px; font-weight: 800;
  }
  .section-head .desc { font-size: 13px; color: var(--text-muted); }

  /* INSIGHT */
  .insight {
    background: linear-gradient(135deg, rgba(91,141,239,0.06), rgba(0,212,170,0.04));
    border: 1px solid var(--border);
    border-left: 3px solid var(--primary);
    padding: 14px 18px; border-radius: 10px; margin-bottom: 20px;
    font-size: 13px; line-height: 1.6; color: var(--text-dim);
  }
  .insight b { color: var(--text); }
  .insight.crit { border-left-color: var(--crit); background: linear-gradient(135deg, rgba(255,92,124,0.08), transparent); }
  .insight.warn { border-left-color: var(--warn); }

  /* GRID */
  .grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 16px; }
  @media (max-width: 1100px) { .grid { grid-template-columns: 1fr; } }
  .card {
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: 14px;
    padding: 12px;
    transition: all 0.3s ease;
  }
  .card:hover { border-color: var(--border-strong); box-shadow: var(--shadow-md); }
  .card.full { grid-column: 1 / -1; }

  /* RANKING */
  .ranking {
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: 14px;
    padding: 20px; overflow-x: auto;
  }
  .ranking table { width: 100%; border-collapse: collapse; font-size: 13px; }
  .ranking th {
    text-align: left; padding: 10px 14px; font-weight: 600;
    color: var(--text-muted); text-transform: uppercase;
    font-size: 10px; letter-spacing: 1px;
    border-bottom: 1px solid var(--border);
  }
  .ranking td { padding: 14px; border-bottom: 1px solid var(--border); color: var(--text-dim); font-variant-numeric: tabular-nums; }
  .ranking tr:last-child td { border-bottom: none; }
  .ranking tr:hover { background: rgba(91,141,239,0.04); }
  .ranking td b { color: var(--text); }

  /* SCORE BAR */
  .score-bar-wrap {
    display: flex; align-items: center; gap: 10px;
    background: var(--bg-elev); border-radius: 100px;
    padding: 3px 4px; min-width: 140px;
  }
  .score-bar {
    height: 10px; border-radius: 100px; transition: width 0.5s ease;
    min-width: 10px;
  }
  .score-val { font-weight: 700; color: var(--text); font-size: 12px; padding-right: 8px; }

  /* BADGE */
  .badge {
    display: inline-block; padding: 3px 10px; border-radius: 100px;
    font-size: 10px; font-weight: 700; letter-spacing: 0.5px;
    border: 1px solid; text-transform: uppercase;
  }

  /* MAPA */
  #mapa-leaflet {
    height: 540px; border-radius: 14px; overflow: hidden;
    border: 1px solid var(--border); box-shadow: var(--shadow-md);
  }
  .leaflet-popup-content-wrapper {
    background: var(--bg-card) !important; color: var(--text) !important;
    border-radius: 10px !important; padding: 4px !important;
    border: 1px solid var(--border) !important;
  }
  .leaflet-popup-tip { background: var(--bg-card) !important; }
  .leaflet-popup-content { margin: 12px 16px !important; font-family: Inter, sans-serif; font-size: 13px; }
  .leaflet-popup-content b { color: var(--primary); }
  .leaflet-popup-content .cat-tag {
    display: inline-block; padding: 2px 8px; border-radius: 100px;
    font-size: 10px; font-weight: 700; margin-top: 6px;
  }
  .leaflet-control-attribution {
    background: rgba(10,14,26,0.8) !important; color: var(--text-muted) !important;
    font-size: 10px !important;
  }
  .leaflet-control-attribution a { color: var(--primary) !important; }

  /* CONCLUSÕES */
  .conclusao {
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-left: 3px solid var(--accent);
    border-radius: 10px;
    padding: 16px 20px; margin-bottom: 10px;
    font-size: 13px; line-height: 1.6; color: var(--text-dim);
  }
  .conclusao b { color: var(--text); }

  /* FOOTER */
  footer {
    margin-top: 64px; padding: 32px 24px;
    border-top: 1px solid var(--border);
    text-align: center; font-size: 12px; color: var(--text-muted);
  }
  footer p { margin-bottom: 6px; }
  footer strong { color: var(--text-dim); }

  /* MAP LEGEND */
  .map-legend {
    position: absolute; bottom: 16px; left: 16px; z-index: 1000;
    background: rgba(19,25,41,0.92); border: 1px solid var(--border);
    backdrop-filter: blur(20px); -webkit-backdrop-filter: blur(20px);
    border-radius: 10px; padding: 12px 14px; font-size: 12px;
  }
  .map-legend-item { display: flex; align-items: center; gap: 8px; margin: 4px 0; color: var(--text-dim); }
  .map-legend-dot { width: 10px; height: 10px; border-radius: 50%; box-shadow: 0 0 0 2px rgba(10,14,26,0.6); }
</style>
"""

# Top distrito crítico
top_critico = df_indic.nlargest(1, "risk_score").iloc[0]

html = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Saúde Pública Campinas · Plataforma Analítica</title>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css">
<script src="https://cdn.plot.ly/plotly-2.35.2.min.js"></script>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
{CSS}
</head>
<body>

<header class="hero">
  <div class="hero-content">
    <div>
      <div class="pill">Healthcare Analytics · Campinas/SP</div>
      <h1>Mapa de Acesso à<br>Saúde Pública</h1>
      <p class="subtitle">
        Plataforma analítica para diagnóstico territorial da rede SUS em Campinas,
        integrando dados oficiais do CNES/DataSUS e Censo IBGE 2022 com indicadores
        compostos de pressão sobre a atenção básica.
      </p>
      <div class="meta">
        <span>📍 Município de Campinas/SP</span>
        <span class="dot"></span>
        <span>👥 1.139.047 habitantes</span>
        <span class="dot"></span>
        <span>🎯 ODS 3</span>
        <span class="dot"></span>
        <span>🏛️ PUC-Campinas · PI 2026</span>
      </div>
    </div>

    <div class="diag-card">
      <div class="diag-label">Diagnóstico Executivo</div>
      <div class="diag-title">{top_critico['regiao']} apresenta o maior risco da cidade</div>
      <p style="color:var(--text-dim);font-size:13px;line-height:1.5;">
        Risk score de <b style="color:var(--crit)">{top_critico['risk_score']:.0f}/100</b>
        com {top_critico['hab_por_ubs']:,.0f} habitantes por UBS — {top_critico['hab_por_ubs']/4000:.1f}× acima
        do recomendado pelo Ministério da Saúde.
      </p>
      <div class="diag-stats">
        <div class="diag-stat">
          <div class="diag-stat-val">{n_critica}/5</div>
          <div class="diag-stat-lbl">Distritos críticos</div>
        </div>
        <div class="diag-stat">
          <div class="diag-stat-val">{pop_critica_total:,}</div>
          <div class="diag-stat-lbl">Pop. afetada</div>
        </div>
        <div class="diag-stat">
          <div class="diag-stat-val">{pct_priv:.0f}%</div>
          <div class="diag-stat-lbl">Rede privada</div>
        </div>
      </div>
    </div>
  </div>
</header>

<div class="container">

  <div class="kpis">
    <div class="kpi"><div class="kpi-icon">👥</div>
      <div class="kpi-val">1.139.047</div>
      <div class="kpi-lbl">Habitantes</div></div>
    <div class="kpi"><div class="kpi-icon">🏥</div>
      <div class="kpi-val">{len(df_estab)}</div>
      <div class="kpi-lbl">Unidades totais</div></div>
    <div class="kpi ok"><div class="kpi-icon">✓</div>
      <div class="kpi-val">{n_sus}</div>
      <div class="kpi-lbl">Unidades SUS</div></div>
    <div class="kpi"><div class="kpi-icon">⚕️</div>
      <div class="kpi-val">{int(df_indic['UBS'].sum())}</div>
      <div class="kpi-lbl">UBS</div></div>
    <div class="kpi"><div class="kpi-icon">🏨</div>
      <div class="kpi-val">{int(df_indic['Hospital'].sum())}</div>
      <div class="kpi-lbl">Hospitais</div></div>
    <div class="kpi warn"><div class="kpi-icon">🚨</div>
      <div class="kpi-val">{int(df_indic['UPA'].sum())}</div>
      <div class="kpi-lbl">UPAs</div></div>
    <div class="kpi crit"><div class="kpi-icon">📊</div>
      <div class="kpi-val">{df_indic[df_indic['UBS']>0]['hab_por_ubs'].median():,.0f}</div>
      <div class="kpi-lbl">Hab/UBS (mediana)</div></div>
    <div class="kpi crit"><div class="kpi-icon">⚠</div>
      <div class="kpi-val">{n_critica}/5</div>
      <div class="kpi-lbl">Distritos críticos</div></div>
  </div>

  <section>
    <div class="section-head">
      <h2><span class="num">01</span>Risk Score por distrito</h2>
      <span class="desc">Indicador composto: pressão UBS + densidade hospitalar + UPAs</span>
    </div>
    <div class="insight crit">
      <b>{top_risco['regiao']}</b> lidera o ranking de risco com score
      <b>{top_risco['risk_score']:.0f}/100</b>. {n_critica} dos 5 distritos
      estão classificados como crítico ou alto risco, afetando
      <b>{pop_critica_total:,}</b> habitantes.
    </div>
    <div class="grid">
      <div class="card">{to_div(g1, "g1")}</div>
      <div class="card">{to_div(g2, "g2")}</div>
    </div>
  </section>

  <section>
    <div class="section-head">
      <h2><span class="num">02</span>Ranking de cobertura</h2>
      <span class="desc">Visão tabular com barras de risco</span>
    </div>
    <div class="ranking">
      <table>
        <thead>
          <tr>
            <th>Distrito</th><th>População</th><th>UBS</th><th>Hosp</th>
            <th>UPA</th><th>Hab/UBS</th><th>Risk Score</th><th>Nível</th>
          </tr>
        </thead>
        <tbody>{ranking_rows}</tbody>
      </table>
    </div>
  </section>

  <section>
    <div class="section-head">
      <h2><span class="num">03</span>Composição da rede</h2>
      <span class="desc">SUS × Privado · Distribuição por categoria</span>
    </div>
    <div class="insight">
      Do total de <b>{len(df_estab)}</b> unidades, apenas <b>{n_sus}
      ({100-pct_priv:.0f}%)</b> atendem pelo SUS. Para a parcela da população
      dependente do sistema público, a oferta efetiva é significativamente
      menor que os números absolutos sugerem.
    </div>
    <div class="grid">
      <div class="card">{to_div(g3, "g3")}</div>
      <div class="card">{to_div(g4, "g4")}</div>
    </div>
  </section>

  <section>
    <div class="section-head">
      <h2><span class="num">04</span>Perfil multidimensional</h2>
      <span class="desc">Comparação radar entre os 5 distritos · 5 eixos</span>
    </div>
    <div class="insight">
      Cada distrito tem assinatura própria. <b>{top_pop['regiao']}</b> domina
      em volume populacional mas é dominado por <b>{melhor_cob['regiao']}</b>
      no eixo de cobertura SUS.
    </div>
    <div class="card full">{to_div(g5, "g5")}</div>
  </section>

  <section>
    <div class="section-head">
      <h2><span class="num">05</span>Hierarquia da rede SUS</h2>
      <span class="desc">Treemap · Distrito → Categoria</span>
    </div>
    <div class="card full">{to_div(g6, "g6")}</div>
  </section>

  <section>
    <div class="section-head">
      <h2><span class="num">06</span>Rede de referência hospitalar</h2>
      <span class="desc">Fluxo distrito → atenção básica → hospital</span>
    </div>
    <div class="card full">{to_div(g7, "g7")}</div>
  </section>

  <section>
    <div class="section-head">
      <h2><span class="num">07</span>Geografia da saúde</h2>
      <span class="desc">Mapa interativo · {n_sus} unidades SUS</span>
    </div>
    <div style="position:relative;">
      <div id="mapa-leaflet"></div>
      <div class="map-legend">
        <div style="font-weight:700;color:var(--text);margin-bottom:8px;font-size:11px;letter-spacing:1px;text-transform:uppercase;">Legenda</div>
        <div class="map-legend-item"><span class="map-legend-dot" style="background:#5B8DEF"></span>UBS</div>
        <div class="map-legend-item"><span class="map-legend-dot" style="background:#FF5C7C"></span>Hospital</div>
        <div class="map-legend-item"><span class="map-legend-dot" style="background:#FFB547"></span>UPA</div>
      </div>
    </div>
  </section>

  <section>
    <div class="section-head">
      <h2><span class="num">08</span>Conclusões estratégicas</h2>
      <span class="desc">Síntese automatizada dos achados</span>
    </div>
    <div class="conclusao">
      <b>Pressão estrutural generalizada:</b> a mediana de {df_indic[df_indic['UBS']>0]['hab_por_ubs'].median():,.0f}
      hab/UBS está {df_indic[df_indic['UBS']>0]['hab_por_ubs'].median()/4000:.1f}×
      acima do limite recomendado pelo MS (3-5 mil). Déficit estrutural visível em toda a cidade.
    </div>
    <div class="conclusao">
      <b>Desigualdade interna:</b> {pior_cob['regiao']} carrega {pior_cob['hab_por_ubs']/melhor_cob['hab_por_ubs']:.1f}×
      mais habitantes por UBS que {melhor_cob['regiao']}. O problema não é só de
      quantidade — é de distribuição territorial.
    </div>
    <div class="conclusao">
      <b>Centralização hospitalar:</b> hospitais SUS concentram-se nas regiões
      centrais, gerando padrão clássico de centro-periferia no acesso à atenção
      especializada.
    </div>
    <div class="conclusao">
      <b>Peso do setor privado:</b> {pct_priv:.0f}% das unidades são privadas.
      Como ~70% da população brasileira depende do SUS, a oferta efetiva fica
      muito aquém do volume absoluto de estabelecimentos.
    </div>
    <div class="conclusao">
      <b>Recomendação:</b> expansão prioritária da atenção básica em
      {top_risco['regiao']} (risk score {top_risco['risk_score']:.0f}/100),
      alinhada à Meta 3.8 do ODS 3 — cobertura universal de saúde.
    </div>
  </section>

  <section>
    <div class="section-head">
      <h2><span class="num">09</span>Metodologia</h2>
      <span class="desc">Fontes e transparência</span>
    </div>
    <div class="insight">
      <b>Fontes oficiais:</b> CNES/DataSUS via API DEMAS (estabelecimentos com
      lat/long, tipo, vínculo SUS) · IBGE Censo 2022 via SIDRA tabela 4709
      (população total: 1.139.047). Dados armazenados em MongoDB Atlas com
      3 coleções (regioes, estabelecimentos, relacoes) e 11 índices (incluindo
      2dsphere geoespacial).
    </div>
    <div class="insight warn">
      <b>Limitação metodológica:</b> população por distrito de saúde é
      estimativa proporcional. O IBGE não publica dados nesta divisão
      específica da SMS Campinas — apenas em distritos administrativos
      (Barão Geraldo, Sousas, etc.). Total municipal preservado conforme Censo.
    </div>
  </section>

</div>

<footer>
  <p><strong>Fontes:</strong> CNES/DataSUS · IBGE Censo 2022 · SMS Campinas</p>
  <p><strong>Stack:</strong> Python · MongoDB Atlas · Plotly · NetworkX · Leaflet</p>
  <p>Arthur Costa Marques · Conrado Marques · Fábio Barbosa Gonsalez · Patrick Rovaron Franco</p>
  <p style="margin-top:12px;opacity:0.5;font-size:11px;">
    Projeto Integrador · Bancos de Dados Não Relacionais · PUC-Campinas · 2026
  </p>
</footer>

<script>
// ─── MAPA LEAFLET com dark tiles ────────────────────────────────────
const markers = {markers_json};

const map = L.map('mapa-leaflet', {{
  zoomControl: true,
  attributionControl: true,
}}).setView([-22.9056, -47.0608], 11);

L.tileLayer('https://{{s}}.basemaps.cartocdn.com/dark_all/{{z}}/{{x}}/{{y}}{{r}}.png', {{
  attribution: '© OpenStreetMap · © CARTO',
  subdomains: 'abcd',
  maxZoom: 20,
}}).addTo(map);

const CORES = {{
  'UBS':      '#5B8DEF',
  'Hospital': '#FF5C7C',
  'UPA':      '#FFB547',
}};

markers.forEach(m => {{
  const cor = CORES[m.categoria] || '#8B95B7';
  const marker = L.circleMarker([m.lat, m.lng], {{
    radius: m.categoria === 'Hospital' ? 9 : (m.categoria === 'UPA' ? 8 : 6),
    fillColor: cor,
    color: '#0A0E1A',
    weight: 1.5,
    opacity: 1,
    fillOpacity: 0.85,
  }}).addTo(map);

  marker.bindPopup(`
    <b>${{m.nome}}</b><br>
    <span style="color:#8B95B7;font-size:12px;">${{m.regiao}}</span>
    <div class="cat-tag" style="background:${{cor}}26;color:${{cor}};">
      ${{m.categoria}}
    </div>
  `);
}});

// Bounds: ajusta zoom inicial
if (markers.length > 0) {{
  const bounds = markers.map(m => [m.lat, m.lng]);
  map.fitBounds(bounds, {{padding: [40, 40], maxZoom: 12}});
}}
</script>

</body>
</html>"""


# ─── 8. Salva HTML ───────────────────────────────────────────────────
OUT = Path("/content/dashboard.html")
OUT.write_text(html, encoding="utf-8")
print(f"\n✓ Dashboard v3 salvo: {OUT}")
print(f"  Tamanho: {OUT.stat().st_size:,} bytes")
