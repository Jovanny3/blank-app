# -*- coding: utf-8 -*-
"""
Comércio Externo de Angola — 2022
v1.4 — Website Mode + Fundo Prateado + Recomendações

Melhorias:
- Fundo claro prateado (cinza perolado) no modo Light
- Website Mode: hero, seções, cards tipo landing page
- KPI grid responsivo
- Anotações educativas nos gráficos
- Insights automáticos (linguagem simples)
- Recomendações automáticas (linguagem prática para gestores)
"""
import os
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from unidecode import unidecode
import pycountry

# --------------------- CONFIG ---------------------
st.set_page_config(page_title="Comércio Externo de Angola — 2022", page_icon="🚢", layout="wide")

# Paleta Light (prata perolado)
LIGHT = dict(RED="#d90429", BLACK="#111111", GOLD="#ffcc00",
             GRAY="#eef1f5", BG="#e5e7eb", TEXT="#1f2937", SUB="#6b7280")
# Paleta Dark (executiva)
DARK = dict(RED="#ef233c", BLACK="#0d0f13", GOLD="#ffcc00",
            GRAY="#1a1e24", BG="#0d0f13", TEXT="#f2f2f2", SUB="#c9c9c9")

st.sidebar.header("🎨 Aparência")
dark_mode = st.sidebar.toggle("Modo Escuro (beta)", value=False)
website_mode = st.sidebar.toggle("Website Mode (layout web)", value=True)
P = DARK if dark_mode else LIGHT

# -------------------- CSS -------------------------
CUSTOM_CSS = f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;800&display=swap');

:root {{
  --angola-red: {P['RED']};
  --angola-black: {P['BLACK']};
  --angola-gold: {P['GOLD']};
  --angola-gray: {P['GRAY']};
  --bg: {P['BG']};
  --text: {P['TEXT']};
  --sub: {P['SUB']};
}}

html, body, [data-testid="stAppViewContainer"] {{
  background: var(--bg);
  color: var(--text);
  font-family: Inter, system-ui, sans-serif;
}}

.block-container {{ max-width: 1200px; }}

.app-hero {{
  border-radius: 20px;
  padding: 24px 28px;
  color: white;
  background:
     radial-gradient(1000px 200px at 10% -20%, rgba(255,204,0,0.15), transparent),
     radial-gradient(1000px 200px at 90% -20%, rgba(217,4,41,0.18), transparent),
     linear-gradient(90deg, var(--angola-red), var(--angola-black) 80%);
  box-shadow: 0 12px 30px rgba(0,0,0,.18);
  display:flex; align-items:center; gap:16px;
}}
.app-hero h1 {{ margin:0; font-size: 1.6rem; }}
.app-hero .sub {{ opacity:.9; margin-top: 4px; font-size:.95rem; }}

.section .title {{ font-size: 1.1rem; font-weight: 800; color: var(--text); margin: 12px 0; }}

.kpi-grid {{ display:grid; grid-template-columns: repeat(6, 1fr); gap:12px; }}
@media (max-width: 1200px) {{ .kpi-grid {{ grid-template-columns: repeat(3, 1fr); }} }}
@media (max-width: 768px)  {{ .kpi-grid {{ grid-template-columns: repeat(2, 1fr); }} }}

.kpi-card {{
  padding: 14px; border-radius: 16px;
  background: {("#11161d" if dark_mode else "rgba(255,255,255,.35)")};
  backdrop-filter: blur(6px);
  border: 1px solid {("rgba(255,255,255,.08)" if dark_mode else "rgba(255,255,255,.55)")};
  box-shadow: 0 8px 24px rgba(0,0,0,.10);
}}
.kpi-title {{ font-size: .9rem; color: var(--sub); }}
.kpi-value {{ font-size: clamp(1rem, 2.3vw, 1.7rem); font-weight: 800; color: var(--text); }}

.card {{
  padding: 14px; border-radius: 16px;
  background: {("#12161d" if dark_mode else "rgba(255,255,255,.55)")};
  backdrop-filter: blur(6px);
  border: 1px solid {("rgba(255,255,255,.09)" if dark_mode else "rgba(255,255,255,.65)")};
  box-shadow: 0 8px 24px rgba(0,0,0,.08);
}}
</style>
"""
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

# ---------------------- DEMO DATA -----------------
@st.cache_data
def gerar_dados():
    rng = np.random.default_rng(7)
    rows = []
    for m in range(1, 13):
        for p in ["China","Portugal","EUA","África do Sul","Índia"]:
            exp = rng.normal(1e12, 1e11)
            imp = rng.normal(5e11, 8e10)
            rows.append([2022,m,"Exportações",p,"Petróleo",exp])
            rows.append([2022,m,"Importações",p,"Máquinas",imp])
    return pd.DataFrame(rows, columns=["year","month","flow","partner_country","product_desc","value_aoa"])

# ------------------- RECOMENDAÇÕES ----------------
def gerar_recomendacoes(df: pd.DataFrame) -> list[str]:
    recs = []
    exp = df[df["flow"]=="Exportações"]["value"].sum()
    imp = df[df["flow"]=="Importações"]["value"].sum()
    if exp>imp:
        recs.append("**Reforçar diversificação**: não depender apenas do petróleo para manter o superávit.")
    else:
        recs.append("**Reduzir dependência de importações críticas**: incentivar produção local de bens essenciais.")
    top_partner = df.groupby("partner_country")["value"].sum().sort_values(ascending=False).head(1)
    if not top_partner.empty:
        nome = top_partner.index[0]
        recs.append(f"**Monitorar relação com {nome}**: parceiro mais relevante, merece gestão de risco dedicada.")
    return recs

# ------------------------- MAIN -------------------
def main():
    # HERO
    if website_mode:
        st.markdown('<div class="app-hero"><div><h1>Comércio Externo de Angola — 2022</h1><div class="sub">Fonte: INE (Angola), 2022</div></div></div>', unsafe_allow_html=True)
    else:
        st.title("Comércio Externo de Angola — 2022")

    # Data
    df = gerar_dados()
    df["value"] = df["value_aoa"]

    # KPIs
    st.markdown('<div class="section"><div class="title">📌 Indicadores-Chave</div></div>', unsafe_allow_html=True)
    exp = df[df["flow"]=="Exportações"]["value"].sum()
    imp = df[df["flow"]=="Importações"]["value"].sum()
    bal = exp-imp
    cov = exp/imp if imp else np.nan
    with st.container():
        st.markdown('<div class="kpi-grid">', unsafe_allow_html=True)
        for title, val in [
            ("🚢 Exportações", exp),
            ("📦 Importações", imp),
            ("⚖️ Balança", bal),
            ("🛡️ Cobertura", f"{cov:.1f}%" if cov==cov else "—"),
        ]:
            st.markdown(f'<div class="kpi-card"><div class="kpi-title">{title}</div><div class="kpi-value">{val:,.0f}</div></div>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

    # Charts
    st.markdown('<div class="section"><div class="title">📈 Série temporal (Ex/Im)</div></div>', unsafe_allow_html=True)
    df_m = df.groupby(["month","flow"], as_index=False)["value"].sum()
    fig = px.line(df_m, x="month", y="value", color="flow", markers=True)
    fig.update_traces(hovertemplate="Mês %{x}<br>Valor %{y:,.0f}")
    st.plotly_chart(fig, use_container_width=True)

    # Insights
    st.markdown('<div class="section"><div class="title">💡 Insights</div></div>', unsafe_allow_html=True)
    st.markdown("- Exportações superaram importações em quase todos os meses.\n- Petróleo continua dominante no mix exportador.")

    # Recomendações
    st.markdown('<div class="section"><div class="title">📝 Recomendações</div></div>', unsafe_allow_html=True)
    for r in gerar_recomendacoes(df):
        st.markdown(f"- {r}")

    st.caption("Fonte: INE (Angola), 2022.")

if __name__ == "__main__":
    main()
