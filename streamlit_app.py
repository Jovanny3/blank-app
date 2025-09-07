# app.py — Comércio Externo de Angola — 2022
# v1.8.0 (INE/AGT + BNA + HS6 + mapa linear/log + metas persistentes + relatório HTML)
# Requisitos: streamlit>=1.31, pandas, altair, plotly, openpyxl

import streamlit as st
import pandas as pd
import numpy as np
import altair as alt
import plotly.express as px
import plotly.io as pio
from io import BytesIO
from zipfile import ZipFile, ZIP_DEFLATED
from datetime import datetime
import sqlite3
from pathlib import Path
import re
import json

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
MES_MAP = {
    "1":"Jan","01":"Jan","jan":"Jan","janeiro":"Jan","Janeiro":"Jan","Jan":"Jan",
    "2":"Fev","02":"Fev","fev":"Fev","fevereiro":"Fev","Fevereiro":"Fev","Fev":"Fev",
    "3":"Mar","03":"Mar","mar":"Mar","março":"Mar","Março":"Mar","Mar":"Mar",
    "4":"Abr","04":"Abr","abr":"Abr","abril":"Abr","Abril":"Abr","Abr":"Abr",
    "5":"Mai","05":"Mai","mai":"Mai","maio":"Mai","Maio":"Mai","Mai":"Mai",
    "6":"Jun","06":"Jun","jun":"Jun","junho":"Jun","Junho":"Jun","Jun":"Jun",
    "7":"Jul","07":"Jul","jul":"Jul","julho":"Jul","Julho":"Jul","Jul":"Jul",
    "8":"Ago","08":"Ago","ago":"Ago","agosto":"Ago","Agosto":"Ago","Ago":"Ago",
    "9":"Set","09":"Set","set":"Set","setembro":"Set","Setembro":"Set","Set":"Set",
    "10":"Out","out":"Out","outubro":"Out","Outubro":"Out","Out":"Out",
    "11":"Nov","nov":"Nov","novembro":"Nov","Novembro":"Nov","Nov":"Nov",
    "12":"Dez","dez":"Dez","dezembro":"Dez","Dezembro":"Dez","Dez":"Dez",
}

# -----------------------------------------------------------------------------
# Utils
# -----------------------------------------------------------------------------
def dedup_cols(df: pd.DataFrame) -> pd.DataFrame:
    return df.loc[:, ~df.columns.duplicated()]

def to_xlsx_or_zip(df_dict: dict[str, pd.DataFrame]) -> tuple[bytes, str, str]:
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

def to_pretty_number(v):
    try:
        return f"{v:,.0f}".replace(",", " ")
    except Exception:
        return str(v)

# --------- Persistência SQLite (metas por perfil/ano) ----------
DB_PATH = "state.db"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS metas (
            perfil TEXT NOT NULL,
            ano INTEGER NOT NULL,
            meta_cob REAL NOT NULL,
            updated_at TEXT NOT NULL,
            PRIMARY KEY (perfil, ano)
        )
    """)
    conn.commit()
    conn.close()

def get_meta(perfil: str, ano: int, default_val: float = 120.0) -> float:
    try:
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute("SELECT meta_cob FROM metas WHERE perfil=? AND ano=?", (perfil, ano))
        row = cur.fetchone()
        conn.close()
        if row is None:
            return default_val
        return float(row[0])
    except Exception:
        # fallback: session_state
        key = f"meta_{perfil}_{ano}"
        return st.session_state.get(key, default_val)

def set_meta(perfil: str, ano: int, val: float):
    try:
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO metas (perfil, ano, meta_cob, updated_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(perfil, ano) DO UPDATE SET meta_cob=excluded.meta_cob, updated_at=excluded.updated_at
        """, (perfil, ano, float(val), datetime.utcnow().isoformat()))
        conn.commit()
        conn.close()
    except Exception:
        key = f"meta_{perfil}_{ano}"
        st.session_state[key] = float(val)

# --------- Normalizadores / Validadores ----------
def _normalize_mes(x) -> str:
    s = str(x).strip()
    return MES_MAP.get(s, MES_MAP.get(s.lower(), s))

def _ensure_columns(df: pd.DataFrame, cols: list[str], name: str):
    missing = [c for c in cols if c not in df.columns]
    if missing:
        st.error(f"{name}: faltam colunas {missing}")
        st.stop()

def _assert_no_duplicates(df: pd.DataFrame, keys: list[str], name: str):
    dups = df.duplicated(subset=keys, keep=False)
    if dups.any():
        st.error(f"{name}: ficheiro contém linhas duplicadas por {keys}. Remova duplicados e reenvie.")
        st.stop()

# -----------------------------------------------------------------------------
# Leitores oficiais (INE/AGT, BNA, HS)
# -----------------------------------------------------------------------------
@st.cache_data(show_spinner=False)
def read_official_flows(uploaded_file) -> pd.DataFrame:
    """
    Espera colunas (case-insensitive) com semântica: Ano, Mes/Mês, Exportações, Importações
    Aceita CSV ou XLSX.
    """
    if uploaded_file is None:
        return pd.DataFrame()
    try:
        if uploaded_file.name.lower().endswith(".csv"):
            df = pd.read_csv(uploaded_file)
        else:
            df = pd.read_excel(uploaded_file)
    except Exception as e:
        st.error(f"Falha a ler ficheiro INE/AGT: {e}")
        st.stop()

    # normalizar nomes
    rename_map = {}
    cols_low = {c.lower(): c for c in df.columns}
    # mapeamento flexível
    for target, candidates in {
        "Ano": ["ano", "year"],
        "Mês": ["mês","mes","month"],
        "Exportações": ["exportações","exportacoes","exports","exp"],
        "Importações": ["importações","importacoes","imports","imp"],
    }.items():
        found = None
        for c in candidates:
            if c in cols_low:
                found = cols_low[c]
                break
        if found:
            rename_map[found] = target
    df = df.rename(columns=rename_map)
    _ensure_columns(df, ["Ano","Mês","Exportações","Importações"], "INE/AGT")

    # limpeza de tipos
    df["Ano"] = pd.to_numeric(df["Ano"], errors="coerce").astype("Int64")
    df["Mês"] = df["Mês"].apply(_normalize_mes)
    df["Exportações"] = pd.to_numeric(df["Exportações"], errors="coerce").fillna(0.0)
    df["Importações"] = pd.to_numeric(df["Importações"], errors="coerce").fillna(0.0)

    # validar duplicados por (Ano, Mês)
    _assert_no_duplicates(df, ["Ano","Mês"], "INE/AGT")

    # ordenar meses pela ordem definida
    df["M_idx"] = pd.Categorical(df["Mês"], categories=MESES, ordered=True)
    df = df.sort_values(["Ano","M_idx"]).drop(columns=["M_idx"]).reset_index(drop=True)
    return df

@st.cache_data(show_spinner=False)
def read_bna_rates(uploaded_file) -> pd.DataFrame:
    """
    Espera colunas: Ano, Mês, USD, EUR
    Recusa duplicados por (Ano,Mês).
    """
    if uploaded_file is None:
        return pd.DataFrame()
    try:
        if uploaded_file.name.lower().endswith(".csv"):
            df = pd.read_csv(uploaded_file)
        else:
            df = pd.read_excel(uploaded_file)
    except Exception as e:
        st.error(f"Falha a ler ficheiro BNA: {e}")
        st.stop()

    rename = {}
    cols_low = {c.lower(): c for c in df.columns}
    for target, candidates in {
        "Ano": ["ano","year"],
        "Mês": ["mês","mes","month"],
        "USD": ["usd","taxa_usd","aoa_usd","cambio_usd"],
        "EUR": ["eur","taxa_eur","aoa_eur","cambio_eur"],
    }.items():
        for c in candidates:
            if c in cols_low:
                rename[cols_low[c]] = target
                break
    df = df.rename(columns=rename)
    _ensure_columns(df, ["Ano","Mês","USD","EUR"], "BNA")

    df["Ano"] = pd.to_numeric(df["Ano"], errors="coerce").astype("Int64")
    df["Mês"] = df["Mês"].apply(_normalize_mes)
    df["USD"] = pd.to_numeric(df["USD"], errors="coerce")
    df["EUR"] = pd.to_numeric(df["EUR"], errors="coerce")

    _assert_no_duplicates(df, ["Ano","Mês"], "BNA")

    df["M_idx"] = pd.Categorical(df["Mês"], categories=MESES, ordered=True)
    df = df.sort_values(["Ano","M_idx"]).drop(columns=["M_idx"]).reset_index(drop=True)
    return df

@st.cache_data(show_spinner=False)
def read_hs_table(uploaded_file) -> pd.DataFrame:
    """
    Espera colunas: HS6 (ou CodigoHS), Capitulo (ou Capítulo), Posicao (ou Posição), Descricao
    Aceita variações; HS6 deve ser 6 dígitos (string).
    """
    if uploaded_file is None:
        return pd.DataFrame()
    try:
        if uploaded_file.name.lower().endswith(".csv"):
            df = pd.read_csv(uploaded_file, dtype=str)
        else:
            df = pd.read_excel(uploaded_file, dtype=str)
    except Exception as e:
        st.error(f"Falha a ler tabela HS: {e}")
        st.stop()

    rename = {}
    cols_low = {c.lower(): c for c in df.columns}
    mapping = {
        "HS6": ["hs6","codigo_hs","codigohs","hs_6","hs"],
        "Capítulo HS": ["capitulo","capítulo","capitulo hs","capítulo hs","capitulo_hs","capítulo_hs","chapter"],
        "Posição HS": ["posicao","posição","posicao hs","posição hs","posicao_hs","posição_hs","position"],
        "Descrição": ["descricao","descrição","description","desc"]
    }
    for target, candidates in mapping.items():
        for c in candidates:
            if c in cols_low:
                rename[cols_low[c]] = target
                break
    df = df.rename(columns=rename)
    # se não tiver Capítulo/Posição, pelo menos HS6 e Descrição
    _ensure_columns(df, ["HS6"], "Tabela HS")
    if "Descrição" not in df.columns:
        df["Descrição"] = ""

    # normalizar HS6: manter 6 dígitos
    df["HS6"] = df["HS6"].astype(str).str.extract(r"(\d{6})", expand=False)
    df = df.dropna(subset=["HS6"]).drop_duplicates(subset=["HS6"]).reset_index(drop=True)
    return df

# -----------------------------------------------------------------------------
# Conversão cambial
# -----------------------------------------------------------------------------
def converter_moeda(df: pd.DataFrame, moeda: str, taxas: pd.DataFrame) -> pd.DataFrame:
    if moeda == "AOA" or taxas.empty:
        return df.copy()
    out = df.copy()
    cols_convert = [c for c in ["Exportações","Importações","Valor","Valor Exportado"] if c in out.columns]
    tx = taxas[["Ano","Mês",moeda]].copy()
    out = out.merge(tx, on=["Ano","Mês"], how="left")
    rate = out[moeda].replace({0: np.nan})
    for c in cols_convert:
        out[c] = (out[c] / rate).round(2)
    out.drop(columns=[moeda], inplace=True)
    return dedup_cols(out)

# -----------------------------------------------------------------------------
# Background (gradiente sólido) + Navbar
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
      <span class="tag">v1.8.0</span>
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
    # === Visual ===
    st.sidebar.header("🎨 Fundo (gradiente sólido)")
    color_a = st.sidebar.color_picker("Cor A", "#0b1220")
    color_b = st.sidebar.color_picker("Cor B", "#0d1424")
    angle   = st.sidebar.slider("Ângulo (°)", 0, 360, 135, 5)
    blur    = st.sidebar.slider("Blur do fundo (px)", 0, 20, 6, 1)
    st.markdown(build_gradient_css(color_a, color_b, angle, blur), unsafe_allow_html=True)
    render_navbar()

    # === Uploads oficiais ===
    st.sidebar.header("📥 Dados oficiais")
    up_ine = st.sidebar.file_uploader("INE/AGT (CSV/XLSX) — Fluxos", type=["csv","xlsx"])
    up_bna = st.sidebar.file_uploader("BNA (CSV/XLSX) — Taxas USD/EUR", type=["csv","xlsx"])
    up_hs  = st.sidebar.file_uploader("Tabela HS (CSV/XLSX) — HS6/Descrição", type=["csv","xlsx"])

    # === Perfis, anos, moeda ===
    st.sidebar.header("🔎 Filtros")
    perfil = st.sidebar.selectbox("Perfil", ["Investidor","Gestor Público","Académico"], index=1)
    anos_default = [2022]
    anos = st.sidebar.multiselect("Anos", [2020,2021,2022,2023,2024], default=anos_default)
    if not anos:
        st.stop()
    moeda = st.sidebar.selectbox("Moeda", ["AOA","USD","EUR"], index=0)
    escala_mapa = st.sidebar.radio("Escala do mapa", ["Linear","Log"], index=1, horizontal=True)

    # === Ler bases ===
    df_flow = read_official_flows(up_ine) if up_ine is not None else pd.DataFrame()
    if df_flow.empty:
        # fallback de exemplo (apenas para demo)
        @st.cache_data(show_spinner=False)
        def _demo():
            flows = []
            np.random.seed(11)
            for ano in [2020,2021,2022,2023,2024]:
                base_exp = 11000 + (ano-2020)*900
                base_imp =  7000 + (ano-2020)*500
                exp = (np.array([base_exp, base_exp-400, base_exp+1500, base_exp+1800, base_exp+2100, base_exp+1900,
                                 base_exp+2300, base_exp+2600, base_exp+2400, base_exp+2800, base_exp+3000, base_exp+3300])
                       * (1 + np.random.normal(0, 0.02, 12))).astype(int)
                imp = (np.array([base_imp, base_imp+200, base_imp-100, base_imp+400, base_imp+600, base_imp+500,
                                 base_imp+800, base_imp+1100, base_imp+900, base_imp+1200, base_imp+1400, base_imp+1600])
                       * (1 + np.random.normal(0, 0.02, 12))).astype(int)
                flows.append(pd.DataFrame({"Ano": ano, "Mês": MESES, "Exportações": exp, "Importações": imp}))
            return pd.concat(flows, ignore_index=True)
        df_flow = _demo()

    df_bna = read_bna_rates(up_bna) if up_bna is not None else pd.DataFrame()
    df_hs  = read_hs_table(up_hs)   if up_hs  is not None else pd.DataFrame()

    # filtrar anos
    df_flow = df_flow[df_flow["Ano"].isin(anos)].copy()

    # Conversão cambial
    df_flow_conv = df_flow.copy()
    df_bna_use = df_bna[df_bna["Ano"].isin(anos)].copy() if not df_bna.empty else df_bna
    df_flow_conv = converter_moeda(df_flow_conv.assign(Valor=df_flow["Exportações"]), moeda, df_bna_use) \
        .rename(columns={"Valor":"Exportações"})
    tmp_imp = converter_moeda(df_flow.assign(Valor=df_flow["Importações"]), moeda, df_bna_use) \
        .rename(columns={"Valor":"Importações"})
    df_flow_conv["Importações"] = tmp_imp["Importações"].values
    df_flow_conv = dedup_cols(df_flow_conv)

    # ===================== KPIs =====================
    st.markdown('<div id="kpis"></div>', unsafe_allow_html=True)
    st.subheader("Indicadores-Chave")

    totals = (df_flow_conv.groupby("Ano")[["Exportações","Importações"]]
              .sum().reset_index())
    totals["Balança"] = totals["Exportações"] - totals["Importações"]
    totals["Cobertura_%"] = (totals["Exportações"] / totals["Importações"] * 100).round(1)

    c1,c2,c3,c4 = st.columns(4, gap="medium")
    ano_focus = anos[0] if len(anos)==1 else max(anos)
    row = totals.loc[totals["Ano"]==ano_focus].iloc[0]

    with c1:
        st.markdown(f'<div class="kpi-card"><div class="kpi-title">Exportações ({ano_focus})</div>'
                    f'<div class="kpi-value">{to_pretty_number(row["Exportações"])} {moeda}</div>'
                    '<div class="kpi-delta up">▲</div></div>', unsafe_allow_html=True)
    with c2:
        st.markdown(f'<div class="kpi-card"><div class="kpi-title">Importações ({ano_focus})</div>'
                    f'<div class="kpi-value">{to_pretty_number(row["Importações"])} {moeda}</div>'
                    '<div class="kpi-delta down">▼</div></div>', unsafe_allow_html=True)
    with c3:
        arrow = "▲" if row["Balança"]>=0 else "▼"
        cls = "up" if row["Balança"]>=0 else "down"
        st.markdown(f'<div class="kpi-card"><div class="kpi-title">Balança Comercial</div>'
                    f'<div class="kpi-value">{to_pretty_number(row["Balança"])} {moeda}</div>'
                    f'<div class="kpi-delta {cls}">{arrow}</div></div>', unsafe_allow_html=True)
    with c4:
        st.markdown(f'<div class="kpi-card"><div class="kpi-title">Taxa de Cobertura</div>'
                    f'<div class="kpi-value">{row["Cobertura_%"]:,.1f}%</div>'
                    '<div class="kpi-delta up">▲ exp/imp</div></div>', unsafe_allow_html=True)

    # ===================== Metas (persistência) =====================
    init_db()
    st.markdown('<div class="block">', unsafe_allow_html=True)
    default_meta = 120.0 if perfil=="Gestor Público" else 110.0
    meta_cob_loaded = get_meta(perfil, ano_focus, default_meta)
    meta_cob = st.slider("Meta de Taxa de Cobertura (%)", 80, 200, int(meta_cob_loaded), step=5)
    if st.button("💾 Guardar meta para este perfil/ano"):
        set_meta(perfil, ano_focus, float(meta_cob))
        st.success("Meta guardada.")
    if row["Cobertura_%"] >= meta_cob:
        st.success(f"Cobertura {row['Cobertura_%']:.1f}% ≥ meta {meta_cob}%.")
    else:
        st.warning(f"Cobertura {row['Cobertura_%']:.1f}% < meta {meta_cob}% — atenção.")
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

    # ===================== Parceiros + Mapa =====================
    st.markdown('<div id="parceiros"></div>', unsafe_allow_html=True)
    st.markdown('<div class="block">', unsafe_allow_html=True)
    st.markdown("### Parceiros comerciais (exemplo)")
    # Obs.: Se tiveres uma base oficial por país, podes fazer upload e substituir esta secção.
    partners_demo = pd.DataFrame({
        "Ano": [ano_focus]*6,
        "Parceiro": ["China","European Union","United States","India","United Arab Emirates","South Africa"],
        "ISO3": ["CHN","EUU","USA","IND","ARE","ZAF"],
        "Exportações": [42000, 28000, 16000, 14000,  9000, 7000],
        "Importações": [18000, 22000,  9000,  7000,  6000, 5000],
    })
    dfp = partners_demo.copy()

    if not df_bna_use.empty and moeda != "AOA":
        tx_ano = df_bna_use.loc[df_bna_use["Ano"]==ano_focus, ["USD","EUR"]].mean()
        rate = tx_ano["USD"] if moeda=="USD" else tx_ano["EUR"]
        dfp["Exportações"] = (dfp["Exportações"]/rate).round(2)
        dfp["Importações"] = (dfp["Importações"]/rate).round(2)

    c1, c2 = st.columns([1,1], gap="medium")
    with c1:
        st.altair_chart(
            alt.Chart(dfp.sort_values("Exportações", ascending=False))
               .mark_bar()
               .encode(x=alt.X("Exportações:Q", title=f"Exportações ({moeda})"),
                       y=alt.Y("Parceiro:N", sort="-x"),
                       tooltip=["Parceiro","Exportações"])
               .properties(height=280),
            use_container_width=True
        )
    with c2:
        st.altair_chart(
            alt.Chart(dfp.sort_values("Importações", ascending=False))
               .mark_bar()
               .encode(x=alt.X("Importações:Q", title=f"Importações ({moeda})"),
                       y=alt.Y("Parceiro:N", sort="-x"),
                       tooltip=["Parceiro","Importações"])
               .properties(height=280),
            use_container_width=True
        )

    df_map = dfp.copy()
    df_map["Fluxo"] = df_map["Exportações"] + df_map["Importações"]
    if escala_mapa == "Log":
        df_map["ValorMapa"] = np.log1p(df_map["Fluxo"])
        color_title = f"log(1+Fluxo) ({moeda})"
    else:
        df_map["ValorMapa"] = df_map["Fluxo"]
        color_title = f"Fluxo ({moeda})"

    fig_map = px.choropleth(
        df_map, locations="ISO3", color="ValorMapa",
        hover_name="Parceiro",
        hover_data={
            "ISO3": False,
            "Exportações": True,
            "Importações": True,
            "Fluxo": True,
            "ValorMapa": False
        },
        color_continuous_scale="Blues",
        title=f"Fluxo Total por Parceiro — {ano_focus}"
    )
    fig_map.update_coloraxes(colorbar_title=color_title)
    st.plotly_chart(fig_map, use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)

    # ===================== Produtos (HS) + Tabela HS6 =====================
    st.markdown('<div id="produtos"></div>', unsafe_allow_html=True)
    st.markdown('<div class="block">', unsafe_allow_html=True)
    st.markdown("### Drill-down por HS-Code (até 6 dígitos)")

    # Exemplo de produtos a partir dos fluxos (se houver base própria, substituir)
    # Para demonstrar o join HS6, vamos sintetizar uma base a partir de strings:
    sample_products = pd.DataFrame({
        "Ano": [ano_focus]*5,
        "Mês": ["Jan"]*5,
        "Posição HS": ["270900 Petróleo bruto","271121 Gás natural","710210 Diamantes",
                       "030363 Peixes congelados","090111 Café"],
        "Valor Exportado": [120000, 18000, 9000, 2500, 1200],
    })
    # extrair HS6
    def extract_hs6(s: str) -> str:
        m = re.search(r"(\d{6})", str(s))
        return m.group(1) if m else None
    sample_products["HS6"] = sample_products["Posição HS"].apply(extract_hs6)

    if not df_hs.empty:
        prods = sample_products.merge(df_hs[["HS6","Descrição"]], on="HS6", how="left")
    else:
        prods = sample_products.copy()
        prods["Descrição"] = ""

    cap_list = sorted(prods["HS6"].str[:2].unique())
    cap_sel = st.selectbox("Capítulo (2 dígitos)", cap_list)
    view = prods[prods["HS6"].str.startswith(cap_sel)].copy()
    st.dataframe(view[["HS6","Posição HS","Descrição","Valor Exportado"]],
                 use_container_width=True, hide_index=True)

    st.altair_chart(
        alt.Chart(view.sort_values("Valor Exportado", ascending=False))
           .mark_bar()
           .encode(x=alt.X("Valor Exportado:Q", title=f"Valor Exportado ({moeda})"),
                   y=alt.Y("Posição HS:N", sort="-x"),
                   tooltip=["HS6","Posição HS","Descrição","Valor Exportado"])
           .properties(height=300),
        use_container_width=True
    )
    st.markdown('</div>', unsafe_allow_html=True)

    # ===================== Exportação (CSV/XLSX + Relatório HTML) =====================
    st.markdown('<div class="block">', unsafe_allow_html=True)
    st.markdown("### Exportação de dados e relatório")

    cexp1, cexp2, cexp3 = st.columns(3)
    with cexp1:
        st.download_button(
            "⬇️ Fluxos (CSV)",
            data=dedup_cols(df_flow).to_csv(index=False).encode("utf-8"),
            file_name=f"fluxos_{'-'.join(map(str,anos))}.csv",
            mime="text/csv"
        )
    with cexp2:
        payload, fname, mime = to_xlsx_or_zip({
            "Fluxos": df_flow,
            "Fluxos_convertidos": df_flow_conv,
            "Parceiros_demo": dfp,
            "Produtos_demo": prods
        })
        st.download_button(f"⬇️ {'Tudo (XLSX)' if fname.endswith('.xlsx') else 'Tudo (ZIP/CSVs)'}",
                           data=payload, file_name=fname, mime=mime)

    with cexp3:
        # Relatório HTML simples (Plotly to_html + KPIs)
        # build KPI snippet
        kpi_html = f"""
        <h2 style="font-family:system-ui;margin:0 0 8px">Relatório — {ano_focus}</h2>
        <p style="font-family:system-ui;margin:4px 0">Exportações: <b>{to_pretty_number(row['Exportações'])} {moeda}</b> &nbsp;|&nbsp;
        Importações: <b>{to_pretty_number(row['Importações'])} {moeda}</b> &nbsp;|&nbsp;
        Balança: <b>{to_pretty_number(row['Balança'])} {moeda}</b> &nbsp;|&nbsp;
        Cobertura: <b>{row['Cobertura_%']:.1f}%</b></p>
        <hr/>
        """
        # incorporar o mapa (plotly) no HTML
        map_html = pio.to_html(fig_map, include_plotlyjs="cdn", full_html=False)
        doc = f"<!doctype html><html><head><meta charset='utf-8'><title>Relatório CE Angola</title></head><body>{kpi_html}{map_html}</body></html>"
        st.download_button("⬇️ Relatório HTML", data=doc.encode("utf-8"),
                           file_name=f"relatorio_{ano_focus}.html", mime="text/html")
    st.markdown('</div>', unsafe_allow_html=True)

    # ===================== Recomendações (texto) =====================
    st.markdown('<div id="recomendacoes"></div>', unsafe_allow_html=True)
    st.markdown('<div class="block">', unsafe_allow_html=True)
    st.markdown("### Roadmap (cumprido nesta versão)")
    st.markdown("""
- ✅ **Conexão a dados oficiais (INE/AGT)** com normalização e validações.
- ✅ **Conversão cambial (BNA)**, recusa de duplicados em `Ano,Mês`.
- ✅ **HS-Code até 6 dígitos** com _join_ à tabela HS.
- ✅ **Mapa** com opção **Linear/Log** e tooltips com **Exp/Imp**.
- ✅ **Metas** persistentes por perfil/ano via **SQLite** (fallback `st.session_state`).
- ✅ **Relatório HTML** com KPIs e mapa (Plotly embutido).
    """)
    st.markdown('</div>', unsafe_allow_html=True)

    # ===================== Footer =====================
    st.markdown(f"""
    <div class="footer">
      <div>© {datetime.now().year} • Dashboard de Comércio Externo de Angola — <span class="badge">v1.8.0</span></div>
      <div>Streamlit • Altair • Plotly</div>
    </div>
    """, unsafe_allow_html=True)

# -----------------------------------------------------------------------------
if __name__ == "__main__":
    main()
