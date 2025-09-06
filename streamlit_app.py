# app.py — Comércio Externo de Angola — 2022
# v1.6.1 (Template CSS corrigido, navbar/header, footer, KPIs espaçados, recomendações)
# Requisitos: streamlit>=1.31, pandas, altair

import streamlit as st
import pandas as pd
import altair as alt
from datetime import datetime

# -----------------------------------------------------------------------------
# Configuração da página
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="Comércio Externo de Angola — 2022",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# -----------------------------------------------------------------------------
# 🔧 Utilidades
# -----------------------------------------------------------------------------
def aoa(n):
    try:
        return f"AOA {n:,.0f}".replace(",", " ")
    except Exception:
        return "–"

@st.cache_data(show_spinner=False)
def load_sample_data():
    # Dados de exemplo para gráficos (substitua pelos seus dados INE/AGT)
    meses = ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun", "Jul", "Ago", "Set", "Out", "Nov", "Dez"]
    df_flow = pd.DataFrame({
        "Mês": meses,
        "Exportações": [11000, 10500, 12000, 12500, 13000, 12800, 13500, 14000, 13800, 14200, 14500, 15000],
        "Importações": [7000, 7200, 6800, 7500, 7700, 7600, 7900, 8200, 8100, 8300, 8500, 8700],
    })
    df_partners = pd.DataFrame({
        "Parceiro": ["China", "UE", "EUA", "Índia", "Rússia"],
        "Exportações": [42000, 28000, 16000, 14000, 6000],
        "Importações": [18000, 22000, 9000, 7000, 5000],
    })
    df_products = pd.DataFrame({
        "Produto": ["Petróleo bruto", "Gás", "Diamantes", "Peixes", "Café"],
        "Valor Exportado": [120000, 18000, 9000, 2500, 1200],
    })
    return df_flow, df_partners, df_products

# -----------------------------------------------------------------------------
# 🎨 Template CSS (ATENÇÃO: string simples, SEM f-string)
# -----------------------------------------------------------------------------
TEMPLATE_CSS = """
<style>
:root{
  --primary:#0ea5e9; /* sky-500 */
  --bg:#0b1220;      /* fundo escuro */
  --card:#101826;
  --muted:#8aa1c1;
  --accent:#22c55e;  /* green-500 */
  --warn:#f59e0b;    /* amber-500 */
  --danger:#ef4444;  /* red-500 */
}
html, body, [data-testid="stAppViewContainer"]{
  background: linear-gradient(180deg, #0b1220 0%, #0b1220 60%, #0d1424 100%);
  color: #e6edf6;
}

/* Navbar / Header */
.navbar{
  position: sticky;
  top: 0;
  z-index: 999;
  backdrop-filter: blur(6px);
  background: rgba(16, 24, 38, 0.72);
  border-bottom: 1px solid #172236;
  padding: 12px 18px;
  border-radius: 0 0 14px 14px;
  margin-bottom: 22px;
}
.navbar .brand{
  display: flex; align-items: center; gap: 12px;
  font-weight: 700; letter-spacing: .3px;
}
.navbar .tag{
  font-size: 12px; padding: 3px 8px; border-radius: 999px;
  background: rgba(14,165,233,.12); color: var(--primary);
  border: 1px solid rgba(14,165,233,.35);
}
.navbar .links{
  display: flex; gap: 14px; flex-wrap: wrap;
}
.navbar a{
  color: #cfe3ff; text-decoration: none; font-size: 14px; opacity: .9;
}
.navbar a:hover{ opacity: 1; text-decoration: underline; }

/* KPI cards */
.kpis{
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
  gap: 16px;
  margin: 6px 0 18px 0;
}
.kpi-card{
  background: var(--card);
  border: 1px solid #192336;
  border-radius: 14px;
  padding: 16px;
  box-shadow: 0 4px 18px rgba(2,6,23,0.36);
}
.kpi-title{
  font-size: 12px; color: var(--muted); margin-bottom: 6px; text-transform: uppercase; letter-spacing: .6px;
}
.kpi-value{
  font-size: 26px; font-weight: 800; line-height: 1.2; margin-bottom: 6px;
}
.kpi-delta{
  font-size: 13px; font-weight: 600;
}
.kpi-delta.up{ color: var(--accent); }
.kpi-delta.down{ color: var(--danger); }

/* Seções com cartão */
.block{
  background: var(--card);
  border: 1px solid #182335;
  border-radius: 14px;
  padding: 16px 16px 8px 16px;
  margin-bottom: 16px;
}

/* Footer */
.footer{
  margin-top: 26px;
  padding: 16px;
  border-top: 1px solid #172236;
  color: #9db4d8;
  font-size: 13px;
  text-align: center;
}
.badge{
  display:inline-block; padding: 2px 8px; border-radius: 999px; font-size: 12px;
  border: 1px solid #2a3b57; color: #b9d1ff; background: rgba(59,130,246,.08);
}
</style>
"""

# -----------------------------------------------------------------------------
# 🧭 Navbar / Header
# -----------------------------------------------------------------------------
def render_navbar():
    st.markdown(
        TEMPLATE_CSS +
        """
        <div class="navbar">
          <div style="display:flex;justify-content:space-between;align-items:center;gap:16px;flex-wrap:wrap;">
            <div class="brand">
              <span>📊 Comércio Externo de Angola</span>
              <span class="badge">Ano-base: 2022</span>
              <span class="tag">v1.6.1</span>
            </div>
            <div class="links">
              <a href="#kpis">KPIs</a>
              <a href="#fluxos-mensais">Fluxos mensais</a>
              <a href="#parceiros">Parceiros</a>
              <a href="#produtos">Produtos</a>
              <a href="#recomendacoes">Recomendações</a>
            </div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

# -----------------------------------------------------------------------------
# 🦴 Layout principal
# -----------------------------------------------------------------------------
def main():
    render_navbar()

    st.sidebar.header("🔎 Filtros")
    ano = st.sidebar.selectbox("Ano", ["2022"], index=0)
    moeda = st.sidebar.selectbox("Moeda", ["AOA"], index=0)
    st.sidebar.caption("Substitua por filtros reais (mês, parceiro, produto, etc.) quando ligar a base oficial.")

    df_flow, df_partners, df_products = load_sample_data()

    # ===================== KPIs =====================
    st.markdown('<div id="kpis"></div>', unsafe_allow_html=True)
    st.subheader("Indicadores-Chave (2022)")
    # Números de exemplo (substitua pelos oficiais)
    exp_total = int(df_flow["Exportações"].sum())
    imp_total = int(df_flow["Importações"].sum())
    balanca = exp_total - imp_total
    taxa_cobertura = (exp_total / imp_total) * 100 if imp_total else 0

    # Grid de KPIs com espaçamento
    kpi_cols = st.columns(4, gap="medium")
    with kpi_cols[0]:
        st.markdown('<div class="kpi-card"><div class="kpi-title">Exportações (ano)</div>'
                    f'<div class="kpi-value">{aoa(exp_total)}</div>'
                    '<div class="kpi-delta up">▲ tendência anual</div></div>', unsafe_allow_html=True)
    with kpi_cols[1]:
        st.markdown('<div class="kpi-card"><div class="kpi-title">Importações (ano)</div>'
                    f'<div class="kpi-value">{aoa(imp_total)}</div>'
                    '<div class="kpi-delta down">▼ pressão importadora</div></div>', unsafe_allow_html=True)
    with kpi_cols[2]:
        trend_class = "up" if balanca >= 0 else "down"
        arrow = "▲" if balanca >= 0 else "▼"
        st.markdown('<div class="kpi-card"><div class="kpi-title">Balança Comercial</div>'
                    f'<div class="kpi-value">{aoa(balanca)}</div>'
                    f'<div class="kpi-delta {trend_class}">{arrow} saldo</div></div>', unsafe_allow_html=True)
    with kpi_cols[3]:
        st.markdown('<div class="kpi-card"><div class="kpi-title">Taxa de Cobertura</div>'
                    f'<div class="kpi-value">{taxa_cobertura:,.1f}%</div>'
                    '<div class="kpi-delta up">▲ exp/imp</div></div>', unsafe_allow_html=True)

    # ===================== Fluxos mensais =====================
    st.markdown('<div id="fluxos-mensais"></div>', unsafe_allow_html=True)
    with st.container():
        st.markdown('<div class="block">', unsafe_allow_html=True)
        st.markdown("### Fluxos mensais — Exportações vs Importações (AOA)")
        dfm = df_flow.melt("Mês", var_name="Tipo", value_name="Valor")
        chart = (
            alt.Chart(dfm)
            .mark_line(point=True)
            .encode(
                x=alt.X("Mês:N", sort=list(df_flow["Mês"])),
                y=alt.Y("Valor:Q", title="Valor (AOA mil)"),
                color="Tipo:N",
                tooltip=["Mês", "Tipo", "Valor"]
            )
            .properties(height=360)
        )
        st.altair_chart(chart, use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)

    # ===================== Parceiros =====================
    st.markdown('<div id="parceiros"></div>', unsafe_allow_html=True)
    with st.container():
        st.markown = st.markdown  # atalho
        st.markown('<div class="block">', unsafe_allow_html=True)
        st.markown("### Principais parceiros comerciais (AOA)")
        c1, c2 = st.columns([1, 1], gap="medium")

        with c1:
            chart_exp = (
                alt.Chart(df_partners.sort_values("Exportações", ascending=False))
                .mark_bar()
                .encode(
                    x=alt.X("Exportações:Q", title="Exportações"),
                    y=alt.Y("Parceiro:N", sort="-x"),
                    tooltip=["Parceiro", "Exportações"]
                )
                .properties(height=260)
            )
            st.altair_chart(chart_exp, use_container_width=True)

        with c2:
            chart_imp = (
                alt.Chart(df_partners.sort_values("Importações", ascending=False))
                .mark_bar()
                .encode(
                    x=alt.X("Importações:Q", title="Importações"),
                    y=alt.Y("Parceiro:N", sort="-x"),
                    tooltip=["Parceiro", "Importações"]
                )
                .properties(height=260)
            )
            st.altair_chart(chart_imp, use_container_width=True)
        st.markown('</div>', unsafe_allow_html=True)

    # ===================== Produtos =====================
    st.markdown('<div id="produtos"></div>', unsafe_allow_html=True)
    with st.container():
        st.markdown('<div class="block">', unsafe_allow_html=True)
        st.markdown("### Principais produtos exportados (AOA)")
        chart_prod = (
            alt.Chart(df_products.sort_values("Valor Exportado", ascending=False))
            .mark_bar()
            .encode(
                x=alt.X("Valor Exportado:Q", title="Valor Exportado"),
                y=alt.Y("Produto:N", sort="-x"),
                tooltip=["Produto", "Valor Exportado"]
            )
            .properties(height=280)
        )
        st.altair_chart(chart_prod, use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)

    # ===================== Recomendações =====================
    st.markdown('<div id="recomendacoes"></div>', unsafe_allow_html=True)
    with st.container():
        st.markdown('<div class="block">', unsafe_allow_html=True)
        st.markdown("### Recomendações (para versões futuras)")
        st.markdown(
            """
- **Conexão a dados oficiais (INE/AGT)**: importar séries mensais 2020-2024 para comparação temporal.
- **Conversão cambial**: alternar AOA/USD/EUR com taxa média mensal (fonte: BNA).
- **Drill-down por HS-Code**: detalhar produtos de exportação/importação por capítulo e posição.
- **Mapa choropleth**: fluxo por país/parceiro com escala logarítmica.
- **Alertas e metas**: definir metas anuais e alertas (ex.: cobertura < 120%).
- **Exportação**: botões para CSV/XLSX/PDF dos relatórios e gráficos.
- **Perfis de utilizador**: ver “Investidor”, “Gestor Público”, “Académico” com painéis ajustados.
            """
        )
        st.markdown('</div>', unsafe_allow_html=True)

    # ===================== Footer =====================
    st.markdown(
        f"""
        <div class="footer">
          <div>© {datetime.now().year} • Dashboard de Comércio Externo de Angola — <span class="badge">v1.6.1</span></div>
          <div>Construído com Streamlit • Tema escuro otimizado • Layout responsivo</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

# -----------------------------------------------------------------------------
# Execução
# -----------------------------------------------------------------------------
if __name__ == "__main__":
    main()
