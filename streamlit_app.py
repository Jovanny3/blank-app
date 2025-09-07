# app.py — Comércio Externo de Angola — 2022
# v1.7.1 (gradiente sólido de fundo + funcionalidades anteriores)
# Requisitos: streamlit>=1.31, pandas, altair, plotly, openpyxl

import streamlit as st
import pandas as pd
import numpy as np
import altair as alt
import plotly.express as px
from io import BytesIO
from zipfile import ZipFile, ZIP_DEFLATED
from datetime import datetime

# -----------------------------------------------------------------------------
# Config
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="Comércio Externo de Angola — 2022",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

MESES = ["Jan","Fev","Mar","Abr","Mai","Jun","Jul","Ago","Set","Out","Nov","Dez"]

# -----------------------------------------------------------------------------
# Utils
# -----------------------------------------------------------------------------
def dedup_cols(df: pd.DataFrame) -> pd.DataFrame:
    """Remove colunas duplicadas preservando a primeira ocorrência."""
    return df.loc[:, ~df.columns.duplicated()]

def to_xlsx_or_zip(df_dict: dict[str, pd.DataFrame]) -> tuple[bytes, str, str]:
    """
    Tenta gerar XLSX (openpyxl). Se não houver engine, gera ZIP com CSVs.
    Retorna: (bytes, filename, mime)
    """
    bio = BytesIO()
    try:
        with pd.ExcelWriter(bio, engine="openpyxl") as writer:
            for name, df in df_dict.items():
                dedup_cols(df).to_excel(writer, sheet_name=name[:31], index=False)
        return bio.getvalue(), "comercio_externo.xlsx", \
               "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    except Exception:
        bio = BytesIO()
        with ZipFile(bio, "w", ZIP_DEFLATED) as zf:
            for name, df in df_dict.items():
                csv_bytes = dedup_cols(df).to_csv(index=False).encode("utf-8")
                zf.writestr(f"{name}.csv", csv_bytes)
        return bio.getvalue(), "comercio_externo_csvs.zip", "application/zip"

@st.cache_data(show_spinner=False)
def load_sample_data(anos: list[int]):
    flows, partners, products = [], [], []
    np.random.seed(11)
    for ano in anos:
        base_exp = 11000 + (ano-2020)*900
        base_imp =  7000 + (ano-2020)*500
        exp = (np.array([base_exp, base_exp-400, base_exp+1500, base_exp+1800, base_exp+2100, base_exp+1900,
                         base_exp+2300, base_exp+2600, base_exp+2400, base_exp+2800, base_exp+3000, base_exp+3300])
               * (1 + np.random.normal(0, 0.02, 12))).astype(int)
        imp = (np.array([base_imp, base_imp+200, base_imp-100, base_imp+400, base_imp+600, base_imp+500,
                         base_imp+800, base_imp+1100, base_imp+900, base_imp+1200, base_imp+1400, base_imp+1600])
               * (1 + np.random.normal(0, 0.02, 12))).astype(int)

        flows.append(pd.DataFrame({"Ano": ano, "Mês": MESES,
                                   "Exportações": exp, "Importações": imp}))

        partners.append(pd.DataFrame({
            "Ano": ano,
            "Parceiro": ["China","European Union","United States","India","United Arab Emirates","South Africa"],
            "ISO3": ["CHN","EUU","USA","IND","ARE","ZAF"],
            "Exportações": [42000, 28000, 16000, 14000,  9000, 7000],
            "Importações": [18000, 22000,  9000,  7000,  6000, 5000],
        }))

        products.append(pd.DataFrame({
            "Ano": ano,
            "Capítulo HS": ["27 Combustíveis","27 Combustíveis","71 Pedras/Metais preciosos","03 Peixes","09 Café"],
            "Posição HS": ["2709 Petróleo bruto","2711 Gás natural","7102 Diamantes","0303 Peixes congelados","0901 Café"],
            "Valor Exportado": [120000, 18000, 9000, 2500, 1200],
        }))

    return (pd.concat(flows, ignore_index=True),
            pd.concat(partners, ignore_index=True),
            pd.concat(products, ignore_index=True))

@st.cache_data(show_spinner=False)
def taxas_stub():
    data = []
    for ano in range(2020, 2025):
        for i, mes in enumerate(MESES, start=1):
            usd = 650 + (ano-2020)*120 + i*2
            eur = usd * 1.07
            data.append({"Ano": ano, "Mês": mes, "USD": usd, "EUR": eur})
    return pd.DataFrame(data)

def converter_moeda(df: pd.DataFrame, moeda: str, taxas: pd.DataFrame) -> pd.DataFrame:
    if moeda == "AOA":
        return df.copy()

    out = df.copy()
    cols_convert = [c for c in ["Exportações","Importações","Valor","Valor Exportado"] if c in out.columns]

    tx = taxas[["Ano","Mês",moeda]].copy()
    out = out.merge(tx, on=["Ano","Mês"], how="left")

    rate = out[moeda].replace({0: np.nan})
    for c in cols_convert:
        out[c] = (out[c] / rate).round(2)

    out.drop(columns=[moeda], inplace=True)
    out = dedup_cols(out)
    return out

# -----------------------------------------------------------------------------
# Background com gradiente sólido
# -----------------------------------------------------------------------------
def build_gradient_css(color_a: str, color_b: str, angle_deg: int, blur_px: int) -> str:
    css = f"""
    <style>
    [data-testid="stAppViewContainer"] {{
      background: transparent !important;
    }}
    [data-testid="stHeader"] {{
      background: transparent !important;
    }}
    [data-testid="stSidebar"] {{
      background: rgba(10,16,28,0.70) !important;
      backdrop-filter: blur(8px);
      -webkit-backdrop-filter: blur(8px);
    }}
    .stApp::before {{
      content: "";
      position: fixed;
      inset: 0;
      z-index: -1;
      pointer-events: none;
      background: linear-gradient({angle_deg}deg, {color_a}, {color_b});
      filter: blur({blur_px}px);
      transform: scale(1.02);
    }}
    .block, .kpi-card, .navbar {{
      background: rgba(16,24,38,0.78);
      backdrop-filter: blur(10px);
      -webkit-backdrop-filter: blur(10px);
      border: 1px solid rgba(255,255,255,0.06);
    }}
    html, body, [data-testid="stAppViewContainer"] {{
      color: #e7eefb;
    }}
    </style>
    """
    return css

# -----------------------------------------------------------------------------
# CSS base e Navbar
# -----------------------------------------------------------------------------
TEMPLATE_CSS = """
<style>
:root{ --primary:#0ea5e9; --card:#101826; --muted:#8aa1c1;
       --accent:#22c55e; --warn:#f59e0b; --danger:#ef4444; }
.navbar{ position: sticky; top: 0; z-index: 999; backdrop-filter: blur(6px);
  background: rgba(16, 24, 38, 0.72); border-bottom: 1px solid #172236;
  padding: 12px 18px; border-radius: 0 0 14px 14px; margin-bottom: 22px; }
.navbar .brand{ display:flex; align-items:center; gap:12px; font-weight:700; letter-spacing:.3px; }
.navbar .tag{ font-size:12px; padding:3px 8px; border-radius:999px; background:rgba(14,165,233,.12); color:var(--primary); border:1px solid rgba(14,165,233,.35); }
.navbar .links{ display:flex; gap:14px; flex-wrap:wrap; }
.navbar a{ color:#cfe3ff; text-decoration:none; font-size:14px; opacity:.9; }
.navbar a:hover{ opacity:1; text-decoration:underline; }
.kpis{ display:grid; grid-template-columns:repeat(auto-fit, minmax(240px, 1fr)); gap:16px; margin:6px 0 18px 0; }
.kpi-card{ background:var(--card); border:1px solid #192336; border-radius:14px; padding:16px; box-shadow:0 4px 18px rgba(2,6,23,0.36); }
.kpi-title{ font-size:12px; color:var(--muted); margin-bottom:6px; text-transform:uppercase; letter-spacing:.6px; }
.kpi-value{ font-size:26px; font-weight:800; line-height:1.2; margin-bottom:6px; }
.kpi-delta{ font-size:13px; font-weight:600; }
.kpi-delta.up{ color:var(--accent); } .kpi-delta.down{ color:var(--danger); }
.block{ background:var(--card); border:1px solid #182335; border-radius:14px; padding:16px 16px 8px 16px; margin-bottom:16px; }
.footer{ margin-top:26px; padding:16px; border-top:1px solid #172236; color:#9db4d8; font-size:13px; text-align:center; }
.badge{ display:inline-block; padding:2px 8px; border-radius:999px; font-size:12px; border:1px solid #2a3b57; color:#b9d1ff; background:rgba(59,130,246,.08); }
</style>
"""

NAVBAR_HTML = """
<div class="navbar">
  <div style="display:flex;justify-content:space-between;align-items:center;gap:16px;flex-wrap:wrap;">
    <div class="brand">
      <span>📊 Comércio Externo de Angola</span>
      <span class="badge">Ano-base: 2022</span>
      <span class="tag">v1.7.1</span>
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
"""

def render_navbar():
    st.markdown(TEMPLATE_CSS, unsafe_allow_html=True)
    st.markdown(NAVBAR_HTML, unsafe_allow_html=True)

# -----------------------------------------------------------------------------
# App
# -----------------------------------------------------------------------------
def main():
    # === Sidebar: fundo gradiente ===
    st.sidebar.header("🎨 Fundo (gradiente sólido)")
    color_a = st.sidebar.color_picker("Cor A", "#0b1220")
    color_b = st.sidebar.color_picker("Cor B", "#0d1424")
    angle   = st.sidebar.slider("Ângulo (°)", 0, 360, 135, 5)
    blur    = st.sidebar.slider("Blur do fundo (px)", 0, 20, 6, 1)

    st.markdown(build_gradient_css(color_a, color_b, angle, blur), unsafe_allow_html=True)
    render_navbar()

    # === Sidebar: filtros ===
    st.sidebar.header("🔎 Filtros")
    perfil = st.sidebar.selectbox("Perfil de utilizador", ["Investidor","Gestor Público","Académico"], index=1)
    anos = st.sidebar.multiselect("Anos (comparação temporal)", [2020,2021,2022,2023,2024], default=[2022])
    if not anos:
        st.stop()
    moeda = st.sidebar.selectbox("Moeda", ["AOA","USD","EUR"], index=0)

    st.sidebar.markdown("#### 📥 Taxas BNA (opcional)")
    up_tx = st.sidebar.file_uploader("Carregar CSV (colunas: Ano,Mês,USD,EUR)", type=["csv"])

    taxas = taxas_stub()
    if up_tx is not None:
        try:
            taxas_user = pd.read_csv(up_tx)
            if {"Ano","Mês","USD","EUR"}.issubset(taxas_user.columns):
                taxas = taxas_user.copy()
                st.sidebar.success("Taxas BNA carregadas.")
            else:
                st.sidebar.error("CSV inválido. Colunas esperadas: Ano,Mês,USD,EUR.")
        except Exception as e:
            st.sidebar.error(f"Erro ao ler CSV: {e}")

    # === Dados ===
    df_flow, df_partners, df_products = load_sample_data(anos)

    # ===================== KPIs =====================
    st.markdown('<div id="kpis"></div>', unsafe_allow_html=True)
    st.subheader("Indicadores-Chave")

    df_flow_conv = df_flow.copy()
    df_flow_conv = converter_moeda(df_flow_conv.assign(Valor=df_flow["Exportações"]), moeda, taxas) \
        .rename(columns={"Valor":"Exportações"})
    tmp_imp = converter_moeda(df_flow.assign(Valor=df_flow["Importações"]), moeda, taxas) \
        .rename(columns={"Valor":"Importações"})
    df_flow_conv["Importações"] = tmp_imp["Importações"].values
    df_flow_conv = dedup_cols(df_flow_conv)

    totals = (df_flow_conv.groupby("Ano")[["Exportações","Importações"]]
              .sum().reset_index())
    totals["Balança"] = totals["Exportações"] - totals["Importações"]
    totals["Cobertura_%"] = (totals["Exportações"] / totals["Importações"] * 100).round(1)

    c1,c2,c3,c4 = st.columns(4, gap="medium")
    ano_focus = anos[0] if len(anos)==1 else max(anos)
    row = totals.loc[totals["Ano"]==ano_focus].iloc[0]

    with c1:
        st.markdown(f'<div class="kpi-card"><div class="kpi-title">Exportações ({ano_focus})</div>'
                    f'<div class="kpi-value">{row["Exportações"]:,.0f} {moeda}</div>'
                    '<div class="kpi-delta up">▲ tendência</div></div>', unsafe_allow_html=True)
    with c2:
        st.markdown(f'<div class="kpi-card"><div class="kpi-title">Importações ({ano_focus})</div>'
                    f'<div class="kpi-value">{row["Importações"]:,.0f} {moeda}</div>'
                    '<div class="kpi-delta down">▼ pressão</div></div>', unsafe_allow_html=True)
    with c3:
        arrow = "▲" if row["Balança"]>=0 else "▼"
        cls = "up" if row["Balança"]>=0 else "down"
        st.markdown(f'<div class="kpi-card"><div class="kpi-title">Balança Comercial</div>'
                    f'<div class="kpi-value">{row["Balança"]:,.0f} {moeda}</div>'
                    f'<div class="kpi-delta {cls}">{arrow} saldo</div></div>', unsafe_allow_html=True)
    with c4:
        st.markdown(f'<div class="kpi-card"><div class="kpi-title">Taxa de Cobertura</div>'
                    f'<div class="kpi-value">{row["Cobertura_%"]:,.1f}%</div>'
                    '<div class="kpi-delta up">▲ exp/imp</div></div>', unsafe_allow_html=True)

    # ===================== Alertas e metas =====================
    st.markdown('<div class="block">', unsafe_allow_html=True)
    meta_cob = 120 if perfil=="Gestor Público" else 110
    meta_cob = st.slider("Meta de Taxa de Cobertura (%)", 80, 200, int(meta_cob), step=5)
    if row["Cobertura_%"] >= meta_cob:
        st.success(f"Cobertura {row['Cobertura_%']:.1f}% ≥ meta {meta_cob}%.")
    else:
        st.warning(f"Cobertura {row['Cobertura_%']:.1f}% < meta {meta_cob}% — atenção à pressão importadora.")
    st.markdown('</div>', unsafe_allow_html=True)

    # ===================== Fluxos mensais =====================
    st.markdown('<div id="fluxos-mensais"></div>', unsafe_allow_html=True)
    st.markdown('<div class="block">', unsafe_allow_html=True)
    st.markdown("### Fluxos mensais — Exportações vs Importações")
    df_plot = df_flow_conv.melt(["Ano","Mês"], var_name="Tipo", value_name="Valor")
    chart = (
        alt.Chart(df_plot)
        .mark_line(point=True)
        .encode(
            x=alt.X("Mês:N", sort=MESES),
            y=alt.Y("Valor:Q", title=f"Valor ({moeda})"),
            color="Tipo:N",
            tooltip=["Ano","Mês","Tipo","Valor"]
        )
        .properties(height=360)
        .facet(column="Ano:N")
        .resolve_scale(y='independent')
    )
    st.altair_chart(chart, use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)

    # ===================== Parceiros + Choropleth =====================
    st.markdown('<div id="parceiros"></div>', unsafe_allow_html=True)
    st.markdown('<div class="block">', unsafe_allow_html=True
