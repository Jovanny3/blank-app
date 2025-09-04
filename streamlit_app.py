# -*- coding: utf-8 -*-
"""
app.py — Comércio Externo de Angola — 2022
----------------------------------------------------------------------
App Streamlit para explorar os dados mensais de comércio externo
(INE Angola, 2022). Público-alvo: investidores, gestores públicos e
acadêmicos. Inclui:
  • KPIs, filtros e conversão AOA→USD (taxa mensal ou média)
  • Séries temporais, Top parceiros/produtos, mapa-múndi (ISO3),
    participação (%), segmentação por regiões/blocos (SADC, UE, Ásia)
  • Tabelas com busca/ordenação e download
  • Exportação de gráficos em PNG (Plotly + Kaleido)
  • Modo Demo com dados sintéticos (~10–20k linhas)
----------------------------------------------------------------------
Estrutura mínima do CSV principal:
  year (int), month (1–12), flow ("Exportações"|"Importações"),
  partner_country (str, nome em PT), product_desc (str),
  value_aoa (float). Opcionais: hs_code, hs_section, weight_kg.

CSV opcional de taxas (2022):
  month (1–12), rate  # AOA por USD

Notas de qualidade e robustez:
  • Valida year=2022; trata ausentes; remove acentos; uniformiza meses
  • Mensagens claras quando faltar coluna essencial
  • Cache via st.cache_data
  • Pré-computa agregações para performance
----------------------------------------------------------------------
Ajustes rápidos (mapeamento de colunas, exceções de países, tema e logos)
estão claramente indicados no código.
"""
import os
from io import BytesIO
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from unidecode import unidecode

import pycountry

# -------------------------- CONFIGURAÇÃO GERAL --------------------------
st.set_page_config(
    page_title="Comércio Externo de Angola — 2022",
    page_icon="🚢",
    layout="wide"
)

# Estilos simples (tema executivo, leve e colorido)
CUSTOM_CSS = """
    <style>
    .kpi-card {
        padding: 0.85rem 1rem;
        border-radius: 14px;
        background: #ffffff;
        box-shadow: 0 1px 5px rgba(0,0,0,0.08);
        border: 1px solid rgba(0,0,0,0.06);
    }
    .kpi-title {
        font-size: 0.9rem;
        color: #555;
        margin-bottom: 0.2rem;
    }
    .kpi-value {
        font-size: 1.25rem;
        font-weight: 700;
    }
    .subtitle {
        color: #666;
        font-size: 0.95rem;
    }
    .muted { color: #888; }
    .header-wrap {
        display: flex; align-items: center; gap: 16px; margin-bottom: 6px;
    }
    .brand-badge { height: 40px; }
    </style>
"""
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

# -------------------- MAPEAMENTO DE COLUNAS (EDITÁVEL) ------------------
# Se o seu CSV tiver nomes de colunas diferentes, ajuste aqui.
MAPEAMENTO_COLUNAS = {
    "year": "year",
    "month": "month",
    "flow": "flow",
    "partner_country": "partner_country",
    "product_desc": "product_desc",
    "value_aoa": "value_aoa",
    # opcionais (se existirem no CSV, serão mantidos; senão, ignorados)
    "hs_code": "hs_code",
    "hs_section": "hs_section",
    "weight_kg": "weight_kg",
}

# ------------------- EXCEÇÕES DE NOMES DE PAÍSES → ISO3 -----------------
# Aplique lower() + remoção de acentos ANTES de checar este dicionário.
EXCECOES_ISO3: Dict[str, str] = {
    # Exemplos fornecidos + alguns comuns para Angola
    "republica democratica do congo": "COD", "rd congo": "COD", "congo (rdc)": "COD",
    "congo-brazzaville": "COG", "republica do congo": "COG", "congo": "COG",
    "sao tome e principe": "STP", "sao tome": "STP",
    "cabo verde": "CPV",
    "costa do marfim": "CIV", "cote d’ivoire": "CIV", "cote d'ivoire": "CIV",
    "reino unido": "GBR", "uk": "GBR", "gra-bretanha": "GBR", "gra-bretanha (uk)": "GBR",
    "estados unidos": "USA", "eua": "USA", "u.s.a.": "USA", "united states": "USA",
    "coreia do sul": "KOR", "republica da coreia": "KOR",
    "russia": "RUS", "federacao russa": "RUS",
    "hong kong": "HKG", "macau": "MAC",
    "timor-leste": "TLS", "timor leste": "TLS",
    "vietname": "VNM", "vietna": "VNM",
    "emirados arabes unidos": "ARE", "eau": "ARE",
    "republica checa": "CZE", "tchequia": "CZE",
    "eslovaquia": "SVK", "eslovenia": "SVN", "eslovenia (svn)": "SVN",
    "bosnia e herzegovina": "BIH",
    "turquia": "TUR", "turkiye": "TUR",
    "essuatini": "SWZ", "eswatini": "SWZ",
    "guine-bissau": "GNB",
    # Parceiros recorrentes de Angola
    "china": "CHN",
    "india": "IND",
    "japao": "JPN",
    "singapura": "SGP",
    "malasia": "MYS",
    "tailandia": "THA",
    "indonesia": "IDN",
    "emirados": "ARE",
    "arabia saudita": "SAU",
    "qatar": "QAT",
    "oman": "OMN",
    "kuwait": "KWT",
    "portugal": "PRT",
    "espanha": "ESP",
    "franca": "FRA",
    "italia": "ITA",
    "alemanha": "DEU",
    "holanda": "NLD",
    "belgica": "BEL",
    "luxemburgo": "LUX",
    "polonia": "POL",
    "grecia": "GRC",
    "irlanda": "IRL",
    "hungria": "HUN",
    "romenia": "ROU",
    "bulgaria": "BGR",
    "austria": "AUT",
    "suecia": "SWE",
    "finlandia": "FIN",
    "dinamarca": "DNK",
    "estonia": "EST",
    "letonia": "LVA",
    "lituania": "LTU",
    "croacia": "HRV",
    "eslovaquia": "SVK",
    "eslovenia": "SVN",
    "republica da africa do sul": "ZAF", "africa do sul": "ZAF", "rsa": "ZAF",
    "namibia": "NAM",
    "zambia": "ZMB",
    "zimbabue": "ZWE",
    "botsuana": "BWA",
    "mocambique": "MOZ",
    "lesoto": "LSO",
    "malaui": "MWI",
    "tanzania": "TZA",
    "rep.dem. do congo": "COD",
    "congo (brazzaville)": "COG",
    "camaroes": "CMR",
    "gabon": "GAB",
    "egito": "EGY",
    "brasil": "BRA",
    "argelia": "DZA",
    "marrocos": "MAR",
    "tunisia": "TUN",
    "nigeria": "NGA",
    "ghana": "GHA",
    "turquia": "TUR",
    "estados unidos da america": "USA",
    "reino unido (uk)": "GBR",
}

# ---------------------- REGIÕES/BLOCOS (EMBUTIDOS) ----------------------
SADC = {
    "AGO","ZAF","BWA","COD","COG","LBR","LSO","MDG","MWI","MUS","MOZ","NAM","SYC","SWZ","TZA","ZMB","ZWE","COM","STP"
}
UE27 = {
    "AUT","BEL","BGR","HRV","CYP","CZE","DNK","EST","FIN","FRA","DEU","GRC","HUN","IRL","ITA",
    "LVA","LTU","LUX","MLT","NLD","POL","PRT","ROU","SVK","SVN","ESP","SWE"
}
ASIA = {
    "AFG","ARM","AZE","BHR","BGD","BRN","BTN","KHM","CHN","CYP","GEO","HKG","IND","IDN","IRN","IRQ","ISR","JPN",
    "JOR","KAZ","KWT","KGZ","LAO","LBN","MAC","MYS","MDV","MNG","MMR","NPL","PRK","OMN","PAK","PSE","PHL","QAT",
    "SAU","SGP","KOR","LKA","SYR","TWN","TJK","THA","TUR","TKM","ARE","UZB","VNM","YEM"
}

# ----------------------- FUNÇÕES AUXILIARES/NUCLEARES -------------------
@st.cache_data(show_spinner=False)
def gerar_dados_sinteticos(seed: int = 7) -> pd.DataFrame:
    """Gera dataset sintético coerente com ~10–20k linhas (ano 2022)."""
    rng = np.random.default_rng(seed)
    meses = np.arange(1, 13, dtype=int)

    parceiros = [
        "China","Índia","Portugal","África do Sul","Espanha","França","Holanda",
        "Itália","Alemanha","Emirados Árabes Unidos","Singapura","Japão",
        "Brasil","Namíbia","Zâmbia","Congo (RDC)","Congo-Brazzaville","EUA","Reino Unido"
    ]
    produtos = [
        "Petróleo bruto","Gás natural","Diamantes","Derivados de petróleo",
        "Bebidas","Cimentos","Madeira serrada","Peixes congelados","Café","Açúcar"
    ]

    rows = []
    for month in meses:
        for partner in parceiros:
            for prod in produtos:
                base_exp = 1.8e12 if prod in {"Petróleo bruto", "Gás natural", "Diamantes"} else 1.2e10
                base_imp = 8e11 if prod in {"Derivados de petróleo", "Cimentos", "Máquinas"} else 1e10

                v_exp = max(0, rng.normal(loc=base_exp, scale=0.2*base_exp))
                v_imp = max(0, rng.normal(loc=base_imp, scale=0.25*base_imp))

                saz = (1 + 0.1*np.sin(2*np.pi*(month/12.0)))
                v_exp *= saz
                v_imp *= (2 - saz)

                rows.append([2022, month, "Exportações", partner, prod, float(v_exp)])
                rows.append([2022, month, "Importações", partner, prod, float(v_imp)])

    df = pd.DataFrame(rows, columns=[
        "year","month","flow","partner_country","product_desc","value_aoa"
    ])
    return df

def _slug(text: str) -> str:
    return unidecode(str(text).strip().lower())

def _to_month_name(m: int) -> str:
    nomes = ["Jan","Fev","Mar","Abr","Mai","Jun","Jul","Ago","Set","Out","Nov","Dez"]
    if 1 <= int(m) <= 12:
        return nomes[int(m)-1]
    return str(m)

def _fmt_val(v: float, moeda: str) -> str:
    if pd.isna(v):
        return "—"
    if moeda == "USD":
        return f"$ {v:,.0f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"kz {v:,.0f}".replace(",", "X").replace(".", ",").replace("X", ".")

def _download_png_button(fig: go.Figure, filename: str, key: str):
    try:
        png_bytes = fig.to_image(format="png", engine="kaleido", scale=2)
        st.download_button("⬇️ Baixar PNG", data=png_bytes, file_name=filename, mime="image/png", key=key)
    except Exception as e:
        st.info("Para baixar PNG, verifique se **kaleido** está corretamente instalado nas dependências.")

@st.cache_data(show_spinner=False)
def carregar_dados(uploaded_file, demo: bool) -> pd.DataFrame:
    """Carrega CSV principal (ou dados demo). Aplica mapeamento de colunas e limpeza."""
    if demo or uploaded_file is None:
        df = gerar_dados_sinteticos()
    else:
        df = pd.read_csv(uploaded_file)

    rename_map = {v: k for k, v in MAPEAMENTO_COLUNAS.items() if v in df.columns}
    df = df.rename(columns=rename_map)

    colunas_essenciais = ["year","month","flow","partner_country","product_desc","value_aoa"]
    faltantes = [c for c in colunas_essenciais if c not in df.columns]
    if faltantes:
        st.error(f"CSV inválido: faltam colunas essenciais: {', '.join(faltantes)}")
        st.stop()

    df = df.copy()
    df["year"] = pd.to_numeric(df["year"], errors="coerce").astype("Int64")
    df["month"] = pd.to_numeric(df["month"], errors="coerce").astype("Int64")
    df["flow"] = df["flow"].astype(str)
    df["partner_country"] = df["partner_country"].astype(str)
    df["product_desc"] = df["product_desc"].fillna("Desconhecido").astype(str)
    df["value_aoa"] = pd.to_numeric(df["value_aoa"], errors="coerce").fillna(0.0)

    if not (df["year"] == 2022).any():
        st.error("O dataset não contém linhas do ano **2022**.")
        st.stop()

    if (df["year"] != 2022).any():
        st.warning("Foram encontradas linhas fora de 2022; apenas 2022 será considerado.")
        df = df[df["year"] == 2022]

    df = df[(df["month"] >= 1) & (df["month"] <= 12)].copy()
    df["month_name"] = df["month"].apply(_to_month_name)

    return df

def _pycountry_to_iso3(name: str) -> str:
    try:
        res = pycountry.countries.lookup(name)
        return res.alpha_3
    except Exception:
        try:
            res = pycountry.countries.search_fuzzy(name)[0]
            return res.alpha_3
        except Exception:
            return ""

@st.cache_data(show_spinner=False)
def normalizar_paises(df: pd.DataFrame) -> pd.DataFrame:
    """Gera colunas partner_country_clean e iso3 a partir de partner_country."""
    df = df.copy()
    df["partner_country_clean"] = df["partner_country"].fillna("").astype(str)

    iso_codes = []
    for raw in df["partner_country_clean"]:
        key = _slug(raw)
        if key in EXCECOES_ISO3:
            iso_codes.append(EXCECOES_ISO3[key])
            continue
        iso = _pycountry_to_iso3(unidecode(raw))
        iso_codes.append(iso if iso else None)

    df["iso3"] = iso_codes
    return df

def _build_region(iso3: str) -> str:
    if not iso3 or not isinstance(iso3, str):
        return "Outros"
    if iso3 in SADC:
        return "SADC"
    if iso3 in UE27:
        return "UE"
    if iso3 in ASIA:
        return "Ásia"
    return "Outros"

@st.cache_data(show_spinner=False)
def carregar_taxas(uploaded_rates) -> Tuple[Dict[int, float], float, bool]:
    """Retorna (mapa_mes_taxa, taxa_media, completo_bool).
    Se 'uploaded_rates' for None, solicitar entradas manuais na sidebar.
    """
    taxas = {}
    if uploaded_rates is not None:
        try:
            df = pd.read_csv(uploaded_rates)
            df["month"] = pd.to_numeric(df["month"], errors="coerce").astype("Int64")
            df["rate"] = pd.to_numeric(df["rate"], errors="coerce")
            df = df[(df["month"] >= 1) & (df["month"] <= 12) & df["rate"].notna()]
            taxas = dict(zip(df["month"].astype(int), df["rate"].astype(float)))
        except Exception:
            st.warning("Não foi possível ler o CSV de taxas. Usando entradas manuais.")

    st.sidebar.markdown("### 💱 Taxas de câmbio AOA→USD (2022)")
    for m in range(1, 13):
        default = taxas.get(m, None)
        val = st.sidebar.number_input(
            f"Taxa mês {m:02d} (AOA por USD)",
            min_value=0.0, value=float(default) if default is not None else 0.0, step=0.1, format="%.4f",
            key=f"rate_{m:02d}"
        )
        if val > 0:
            taxas[m] = float(val)

    valid = [v for v in taxas.values() if v and v > 0]
    taxa_media = float(np.mean(valid)) if valid else 0.0
    completo = all(m in taxas and taxas[m] > 0 for m in range(1, 13))
    return taxas, taxa_media, completo

def converter_moeda(df: pd.DataFrame, moeda: str, taxas: Dict[int, float], taxa_media: float) -> Tuple[pd.DataFrame, str]:
    """Adiciona coluna 'value' na moeda escolhida e retorna descrição da taxa aplicada."""
    df = df.copy()
    if moeda == "AOA":
        df["value"] = df["value_aoa"]
        return df, "Moeda: AOA (valores originais)."
    def _rate_for_month(m):
        r = taxas.get(int(m), 0.0)
        return r if r and r > 0 else taxa_media
    df["applied_rate"] = df["month"].apply(_rate_for_month)
    df["value"] = df["value_aoa"] / df["applied_rate"].replace(0, np.nan)
    msg = "Moeda: USD — taxa mensal aplicada quando disponível; ausentes usam **média**."
    return df, msg

@st.cache_data(show_spinner=False)
def precompute_aggs(df: pd.DataFrame) -> Dict[str, pd.DataFrame]:
    """Pré-computa agregações usuais para reutilização."""
    monthly_flow = (
        df.groupby(["month","flow"], as_index=False)["value"].sum()
        .sort_values(["month","flow"])
    )
    by_partner = (
        df.groupby(["partner_country_clean","iso3","flow"], as_index=False)["value"].sum()
    )
    by_product = (
        df.groupby(["product_desc","flow"], as_index=False)["value"].sum()
    )
    tmp = df.copy()
    tmp["regiao"] = tmp["iso3"].apply(_build_region)
    by_region = tmp.groupby(["regiao","flow"], as_index=False)["value"].sum()

    return {
        "monthly_flow": monthly_flow,
        "by_partner": by_partner,
        "by_product": by_product,
        "by_region": by_region
    }

# ------------------------------- GRÁFICOS -------------------------------
def plot_series(monthly_flow: pd.DataFrame, moeda: str) -> go.Figure:
    """Série temporal: Exportações vs Importações (2022)."""
    pvt = monthly_flow.pivot(index="month", columns="flow", values="value").fillna(0.0)
    pvt = pvt.reindex(range(1, 13), fill_value=0.0)
    pvt["month_name"] = [ _to_month_name(m) for m in pvt.index ]
    fig = px.line(
        pvt.reset_index(),
        x="month_name",
        y=["Exportações","Importações"],
        markers=True,
        labels={"value": f"Valor ({moeda})", "month_name": "Mês", "variable": "Fluxo"},
        hover_data={"month_name": True}
    )
    fig.update_layout(legend_title=None, margin=dict(l=10,r=10,t=10,b=10))
    return fig

def plot_top_parceiros(by_partner: pd.DataFrame, top_n: int, fluxo: str, moeda: str) -> go.Figure:
    df = by_partner[by_partner["flow"] == fluxo].copy()
    df = df.groupby(["partner_country_clean","iso3"], as_index=False)["value"].sum()
    df = df.sort_values("value", ascending=False).head(top_n)
    fig = px.bar(
        df, x="value", y="partner_country_clean", orientation="h",
        labels={"value": f"Valor ({moeda})", "partner_country_clean": "Parceiro"},
        hover_data={"iso3": True, "partner_country_clean": True, "value": ":,.0f"}
    )
    fig.update_layout(yaxis={"categoryorder":"total ascending"}, margin=dict(l=10,r=10,t=10,b=10))
    return fig

def plot_top_produtos(by_product: pd.DataFrame, top_n: int, fluxo: str, moeda: str) -> go.Figure:
    df = by_product[by_product["flow"] == fluxo].copy()
    df = df.groupby(["product_desc"], as_index=False)["value"].sum()
    df = df.sort_values("value", ascending=False).head(top_n)
    fig = px.bar(
        df, x="value", y="product_desc", orientation="h",
        labels={"value": f"Valor ({moeda})", "product_desc":"Produto"},
        hover_data={"product_desc": True, "value": ":,.0f"}
    )
    fig.update_layout(yaxis={"categoryorder":"total ascending"}, margin=dict(l=10,r=10,t=10,b=10))
    return fig

def plot_mapa(by_partner: pd.DataFrame, fluxo: str, moeda: str) -> go.Figure:
    df = by_partner[by_partner["flow"] == fluxo].copy()
    df = df.groupby(["iso3"], as_index=False)["value"].sum()
    df = df[df["iso3"].notna() & (df["iso3"] != "")]
    fig = px.choropleth(
        df, locations="iso3", color="value",
        color_continuous_scale="Viridis",
        labels={"value": f"Valor ({moeda})"},
        hover_data={"iso3": True, "value": ":,.0f"},
        projection="natural earth"
    )
    fig.update_layout(margin=dict(l=10,r=10,t=10,b=10))
    return fig

def plot_participacao(df_base: pd.DataFrame, top_n: int, por: str, fluxo: str, moeda: str) -> go.Figure:
    """por: 'partner' | 'product'"""
    if por == "partner":
        g = df_base[df_base["flow"] == fluxo].groupby("partner_country_clean", as_index=False)["value"].sum()
        label = "Parceiro"
        ycol = "partner_country_clean"
    else:
        g = df_base[df_base["flow"] == fluxo].groupby("product_desc", as_index=False)["value"].sum()
        label = "Produto"
        ycol = "product_desc"
    total = g["value"].sum()
    g["pct"] = 100.0 * g["value"] / total if total else 0.0
    g = g.sort_values("pct", ascending=False).head(top_n)
    fig = px.bar(
        g, x="pct", y=ycol,
        orientation="h",
        labels={"pct":"Participação (%)", ycol:label},
        hover_data={ ycol:True, "pct":":.2f", "value":":,.0f" }
    )
    fig.update_layout(yaxis={"categoryorder":"total ascending"}, margin=dict(l=10,r=10,t=10,b=10))
    return fig

def plot_regioes(by_region: pd.DataFrame, moeda: str) -> go.Figure:
    df = by_region.copy()
    df = df.pivot(index="regiao", columns="flow", values="value").fillna(0.0).reset_index()
    fig = px.bar(
        df, x="regiao", y=["Exportações","Importações"],
        barmode="group", labels={"value": f"Valor ({moeda})", "regiao":"Região/Bloco", "variable":"Fluxo"}
    )
    fig.update_layout(margin=dict(l=10,r=10,t=10,b=10))
    return fig

# ------------------------------- KPIs -----------------------------------
def gerar_kpis(df_filtered: pd.DataFrame, moeda: str, meses_sel: List[int]) -> None:
    col1, col2, col3, col4, col5, col6 = st.columns(6)

    exp_total = df_filtered.loc[df_filtered["flow"]=="Exportações","value"].sum()
    imp_total = df_filtered.loc[df_filtered["flow"]=="Importações","value"].sum()
    balanca = exp_total - imp_total
    cobertura = (exp_total/imp_total) if imp_total else np.nan

    n_parceiros = df_filtered["partner_country_clean"].nunique()

    mes_ref = max(meses_sel) if meses_sel else int(df_filtered["month"].max())
    cur = df_filtered[df_filtered["month"] == mes_ref]["value"].sum()
    prev = df_filtered[df_filtered["month"] == (mes_ref-1)]["value"].sum() if mes_ref>1 else np.nan
    var_mm = (cur/prev - 1.0)*100.0 if prev and prev>0 else np.nan

    with col1:
        st.markdown(f'<div class="kpi-card" title="Soma de Exportações no período filtrado."><div class="kpi-title">🚢 Exportações</div><div class="kpi-value">{_fmt_val(exp_total, moeda)}</div></div>', unsafe_allow_html=True)
    with col2:
        st.markdown(f'<div class="kpi-card" title="Soma de Importações no período filtrado."><div class="kpi-title">📦 Importações</div><div class="kpi-value">{_fmt_val(imp_total, moeda)}</div></div>', unsafe_allow_html=True)
    with col3:
        st.markdown(f'<div class="kpi-card" title="Balança = Exportações − Importações."><div class="kpi-title">⚖️ Balança</div><div class="kpi-value">{_fmt_val(balanca, moeda)}</div></div>', unsafe_allow_html=True)
    with col4:
        cob_text = f"{(cobertura*100):.1f}%" if cobertura==cobertura else "—"
        st.markdown(f'<div class="kpi-card" title="Cobertura = Exportações / Importações."><div class="kpi-title">🛡️ Cobertura</div><div class="kpi-value">{cob_text}</div></div>', unsafe_allow_html=True)
    with col5:
        st.markdown(f'<div class="kpi-card" title="Número de parceiros (países) únicos no filtro."><div class="kpi-title">🌍 N.º de parceiros</div><div class="kpi-value">{int(n_parceiros)}</div></div>', unsafe_allow_html=True)
    with col6:
        var_text = f"{var_mm:.1f}%" if var_mm==var_mm else "—"
        st.markdown(f'<div class="kpi-card" title="Variação m/m do comércio total no último mês selecionado."><div class="kpi-title">↕️ Variação m/m</div><div class="kpi-value">{var_text}</div></div>', unsafe_allow_html=True)

# ------------------------------- APLICATIVO ------------------------------
def main():
    left, right = st.columns([1,5])
    with left:
        if os.path.exists("insignia_angola.png"):
            st.image("insignia_angola.png", caption=None, use_column_width=False, output_format="PNG")
    with right:
        st.markdown('<div class="header-wrap"><h1>Comércio Externo de Angola — 2022</h1></div>', unsafe_allow_html=True)
        st.caption("Fonte: INE (Angola), 2022.")

    st.markdown("---")

    st.sidebar.header("⚙️ Configurações")
    demo_mode = st.sidebar.toggle("Modo Demo (dados sintéticos)", value=True, help="Use um dataset de exemplo (~10–20k linhas). Desative para subir CSV real.")

    uploaded_file = st.sidebar.file_uploader("CSV principal (2022)", type=["csv"])
    uploaded_rates = st.sidebar.file_uploader("CSV de taxas AOA→USD (opcional)", type=["csv"])

    taxas, taxa_media, completo_rates = carregar_taxas(uploaded_rates)

    df_raw = carregar_dados(uploaded_file, demo=demo_mode)
    df_norm = normalizar_paises(df_raw)

    moeda = st.sidebar.radio("Moeda", options=["AOA","USD"], horizontal=True)
    df_val, msg_taxa = converter_moeda(df_norm, moeda, taxas, taxa_media)
    st.caption(msg_taxa)

    st.sidebar.header("🔎 Filtros")
    meses = sorted(df_val["month"].dropna().astype(int).unique().tolist())
    parceiros = sorted(df_val["partner_country_clean"].unique().tolist())
    produtos = sorted(df_val["product_desc"].unique().tolist())
    fluxos = ["Exportações","Importações"]

    if "meses_sel" not in st.session_state:
        st.session_state["meses_sel"] = meses
    if "parceiros_sel" not in st.session_state:
        st.session_state["parceiros_sel"] = []
    if "produtos_sel" not in st.session_state:
        st.session_state["produtos_sel"] = []
    if "fluxo_sel" not in st.session_state:
        st.session_state["fluxo_sel"] = "Todos"
    if "topn" not in st.session_state:
        st.session_state["topn"] = 10

    col_reset, col_topn = st.sidebar.columns([1,1])
    with col_reset:
        if st.button("🔄 Resetar filtros"):
            st.session_state["meses_sel"] = meses
            st.session_state["parceiros_sel"] = []
            st.session_state["produtos_sel"] = []
            st.session_state["fluxo_sel"] = "Todos"
            st.session_state["topn"] = 10

    st.session_state["meses_sel"] = st.sidebar.multiselect(
        "Mês", options=meses, default=st.session_state["meses_sel"],
        format_func=lambda m: f"{m:02d} - {_to_month_name(m)}"
    )

    st.session_state["parceiros_sel"] = st.sidebar.multiselect(
        "Parceiros", options=parceiros, default=st.session_state["parceiros_sel"]
    )

    st.session_state["produtos_sel"] = st.sidebar.multiselect(
        "Produtos", options=produtos, default=st.session_state["produtos_sel"]
    )

    st.session_state["fluxo_sel"] = st.sidebar.selectbox(
        "Fluxo", options=["Todos"] + fluxos, index=0
    )

    vmin, vmax = float(df_val["value"].min()), float(df_val["value"].max())
    faixa = st.sidebar.slider("Faixa de valor", min_value=0.0, max_value=max(1.0, vmax), value=(0.0, vmax))

    with col_topn:
        st.session_state["topn"] = st.selectbox("Top N", options=[5,10,20], index=1)

    df_f = df_val[ df_val["month"].isin(st.session_state["meses_sel"]) ].copy()
    if st.session_state["parceiros_sel"]:
        df_f = df_f[ df_f["partner_country_clean"].isin(st.session_state["parceiros_sel"]) ]
    if st.session_state["produtos_sel"]:
        df_f = df_f[ df_f["product_desc"].isin(st.session_state["produtos_sel"]) ]
    if st.session_state["fluxo_sel"] in fluxos:
        df_f = df_f[ df_f["flow"] == st.session_state["fluxo_sel"] ]
    df_f = df_f[(df_f["value"] >= faixa[0]) & (df_f["value"] <= faixa[1])]

    gerar_kpis(df_f, moeda, st.session_state["meses_sel"])

    aggs = precompute_aggs(df_f)

    st.markdown("### 📈 Série temporal (2022)")
    fig_series = plot_series(aggs["monthly_flow"], moeda)
    st.plotly_chart(fig_series, use_container_width=True)
    _download_png_button(fig_series, f"serie_temporal_{moeda}.png", key="dl_series")

    colA, colB = st.columns(2)
    with colA:
        st.markdown("### 🌍 Top Parceiros")
        fluxo_ref = st.session_state["fluxo_sel"] if st.session_state["fluxo_sel"] in fluxos else "Exportações"
        fig_top_parc = plot_top_parceiros(aggs["by_partner"], st.session_state["topn"], fluxo_ref, moeda)
        st.plotly_chart(fig_top_parc, use_container_width=True)
        _download_png_button(fig_top_parc, f"top_parceiros_{fluxo_ref}_{moeda}.png", key="dl_parc")
    with colB:
        st.markdown("### 🧩 Top Produtos")
        fig_top_prod = plot_top_produtos(aggs["by_product"], st.session_state["topn"], fluxo_ref, moeda)
        st.plotly_chart(fig_top_prod, use_container_width=True)
        _download_png_button(fig_top_prod, f"top_produtos_{fluxo_ref}_{moeda}.png", key="dl_prod")

    st.markdown("### 🗺️ Mapa mundial (por parceiro)")
    fig_map = plot_mapa(aggs["by_partner"], fluxo_ref, moeda)
    st.plotly_chart(fig_map, use_container_width=True)
    _download_png_button(fig_map, f"mapa_{fluxo_ref}_{moeda}.png", key="dl_map")

    colC, colD = st.columns(2)
    with colC:
        st.markdown("### % Participação por Parceiro")
        fig_pp = plot_participacao(df_f, st.session_state["topn"], "partner", fluxo_ref, moeda)
        st.plotly_chart(fig_pp, use_container_width=True)
        _download_png_button(fig_pp, f"participacao_parceiros_{fluxo_ref}_{moeda}.png", key="dl_pp")
    with colD:
        st.markdown("### % Participação por Produto")
        fig_pr = plot_participacao(df_f, st.session_state["topn"], "product", fluxo_ref, moeda)
        st.plotly_chart(fig_pr, use_container_width=True)
        _download_png_button(fig_pr, f"participacao_produtos_{fluxo_ref}_{moeda}.png", key="dl_pr")

    st.markdown("### 🧭 Segmentação por Regiões/Blocos")
    fig_reg = plot_regioes(aggs["by_region"], moeda)
    st.plotly_chart(fig_reg, use_container_width=True)
    _download_png_button(fig_reg, f"regioes_{moeda}.png", key="dl_reg")

    st.markdown("### 📋 Dados filtrados")
    termo = st.text_input("🔍 Buscar (parceiro/produto)", "")
    df_view = df_f.copy()
    if termo:
        t = _slug(termo)
        df_view = df_view[
            df_view["partner_country_clean"].apply(lambda x: t in _slug(x)) |
            df_view["product_desc"].apply(lambda x: t in _slug(x))
        ]
    st.dataframe(
        df_view.sort_values(["month","flow","partner_country_clean"]),
        use_container_width=True,
        hide_index=True
    )
    csv_bytes = df_view.to_csv(index=False).encode("utf-8")
    st.download_button("⬇️ Baixar CSV filtrado", data=csv_bytes, file_name="dados_filtrados.csv", mime="text/csv")

    with st.expander("ℹ️ Como ler este dashboard"):
        st.write("""
        - **KPIs** no topo mostram visão rápida do período filtrado.
        - A **série temporal** contrasta Exportações vs Importações mês a mês.
        - Os **Top Parceiros/Produtos** focam concentração de fluxos.
        - O **Mapa** usa códigos **ISO3**; países não reconhecidos ficam sem cor.
        - **Participação (%)** indica o peso relativo no total do fluxo selecionado.
        - **Regiões/Blocos**: SADC, UE e Ásia são dicionários embutidos; demais → "Outros".
        - Use **Moeda AOA/USD**; taxas mensais ou média (indicadas abaixo do título).
        """)
    with st.expander("📘 Definições"):
        st.write("""
        - **Balança** = **Exportações − Importações**  
        - **Cobertura** = **Exportações / Importações**  
        - **Variação m/m** = % de mudança do **comércio total** vs mês anterior no último mês filtrado  
        """)

    st.markdown("---")
    st.caption("Fonte: INE (Angola), 2022.")

if __name__ == "__main__":
    main()
