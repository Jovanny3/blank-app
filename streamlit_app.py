# -*- coding: utf-8 -*-
"""
Comércio Externo de Angola — 2022
v1.5 — Tabs + Website Mode + Prata + Recomendações + Correções de robustez

• Modo claro prateado (cinza perolado) e Modo escuro executivo
• Website Mode: hero, cards, grid de KPIs
• Tabs de navegação: Visão Geral | Parceiros | Produtos | Regiões | Dados
• Treemap para Top Produtos (toggle), PNG export (kaleido)
• Anotações educativas em gráficos (pico/vale, 80/20, superávit/déficit)
• Insights automáticos e Recomendações para leigos/gestores
• Conversão AOA⇄USD (taxas por mês 2022; CSV opcional ou entrada manual)
• Países → ISO3 (pycountry + exceções PT↔EN)
• Cache seguro e widgets fora de funções cacheadas
"""

import os
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from unidecode import unidecode
import pycountry

# --------------------- CONFIGURAÇÃO BÁSICA ---------------------
st.set_page_config(page_title="Comércio Externo de Angola — 2022", page_icon="🚢", layout="wide")

# Paleta Light (prateado) e Dark (executiva)
LIGHT = dict(RED="#d90429", BLACK="#111111", GOLD="#ffcc00",
             GRAY="#eef1f5", BG="#e5e7eb", TEXT="#1f2937", SUB="#6b7280")
DARK  = dict(RED="#ef233c", BLACK="#0d0f13", GOLD="#ffcc00",
             GRAY="#1a1e24", BG="#0d0f13", TEXT="#f2f2f2", SUB="#c9c9c9")

# --------------------- APARÊNCIA / WEBSITE MODE ----------------
st.sidebar.header("🎨 Aparência")
dark_mode = st.sidebar.toggle("Modo Escuro (beta)", value=False, help="Tema executivo escuro.")
website_mode = st.sidebar.toggle("Website Mode (layout web)", value=True,
                                 help="Seções com ‘hero’, cartões glass e grid de KPIs.")
P = DARK if dark_mode else LIGHT

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
  font-family: Inter, system-ui, -apple-system, Segoe UI, Roboto, "Helvetica Neue", Arial, "Apple Color Emoji", "Segoe UI Emoji", "Segoe UI Symbol";
}}

.block-container {{ max-width: 1200px; padding-top: .6rem; }}

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
.app-hero h1 {{ margin:0; font-size: 1.6rem; letter-spacing:.2px; }}
.app-hero .sub {{ opacity:.9; margin-top: 4px; font-size:.95rem; }}

.section .title {{ font-size: 1.08rem; font-weight: 800; color: var(--text); margin: 12px 0 8px; }}

.kpi-grid {{ display:grid; grid-template-columns: repeat(6, 1fr); gap:12px; }}
@media (max-width: 1200px) {{ .kpi-grid {{ grid-template-columns: repeat(3, 1fr); }} }}
@media (max-width: 768px)  {{ .kpi-grid {{ grid-template-columns: repeat(2, 1fr); }} }}

.kpi-card {{
  padding: 14px 16px; border-radius: 16px;
  background: {("#11161d" if dark_mode else "rgba(255,255,255,.35)")};
  backdrop-filter: blur(6px);
  border: 1px solid {("rgba(255,255,255,.08)" if dark_mode else "rgba(255,255,255,.55)")};
  box-shadow: 0 8px 24px rgba(0,0,0,.10);
}}
.kpi-title {{ font-size: .9rem; color: var(--sub); margin-bottom: .25rem; }}
.kpi-value {{ font-size: clamp(1rem, 2.3vw, 1.7rem); font-weight: 800; color: var(--text); line-height:1.1; }}

.card {{
  padding: 14px; border-radius: 16px;
  background: {("#12161d" if dark_mode else "rgba(255,255,255,.55)")};
  backdrop-filter: blur(6px);
  border: 1px solid {("rgba(255,255,255,.09)" if dark_mode else "rgba(255,255,255,.65)")};
  box-shadow: 0 8px 24px rgba(0,0,0,.08);
}}

.badge {{
  display:inline-block; padding: 4px 8px; border-radius: 999px;
  background: rgba(0,0,0,.08); color: var(--text); font-size:.78rem; margin-left:6px;
}}
</style>
"""
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

# --------------------- MAPEAMENTO / EXCEÇÕES -------------------
MAPEAMENTO_COLUNAS = {
    "year":"year","month":"month","flow":"flow","partner_country":"partner_country",
    "product_desc":"product_desc","value_aoa":"value_aoa",
    "hs_code":"hs_code","hs_section":"hs_section","weight_kg":"weight_kg",
}

EXCECOES_ISO3: Dict[str, str] = {
    "republica democratica do congo":"COD","rd congo":"COD","congo (rdc)":"COD","rep.dem. do congo":"COD","rdc":"COD",
    "congo-brazzaville":"COG","republica do congo":"COG","congo (brazzaville)":"COG","congo":"COG",
    "sao tome e principe":"STP","sao tome":"STP",
    "cabo verde":"CPV","guine-bissau":"GNB","mocambique":"MOZ",
    "republica da africa do sul":"ZAF","africa do sul":"ZAF","rsa":"ZAF",
    "essuatini":"SWZ","eswatini":"SWZ","zimbabue":"ZWE","zambia":"ZMB","namibia":"NAM","botsuana":"BWA","lesoto":"LSO",
    "tanzania":"TZA","malaui":"MWI","angola":"AGO",
    "reino unido":"GBR","uk":"GBR","gra-bretanha":"GBR","gra-bretanha (uk)":"GBR",
    "republica checa":"CZE","tchequia":"CZE","eslovaquia":"SVK","eslovenia":"SVN",
    "alemanha":"DEU","franca":"FRA","italia":"ITA","espanha":"ESP","portugal":"PRT",
    "holanda":"NLD","paises baixos":"NLD","grecia":"GRC","polonia":"POL","hungria":"HUN","romenia":"ROU","bulgaria":"BGR",
    "suecia":"SWE","finlandia":"FIN","dinamarca":"DNK","irlanda":"IRL","austria":"AUT",
    "estonia":"EST","letonia":"LVA","lituania":"LTU","croacia":"HRV","luxemburgo":"LUX","belgica":"BEL",
    "estados unidos":"USA","eua":"USA","u.s.a.":"USA","united states":"USA",
    "brasil":"BRA","coreia do sul":"KOR","republica da coreia":"KOR","russia":"RUS","federacao russa":"RUS",
    "hong kong":"HKG","macau":"MAC","timor-leste":"TLS","timor leste":"TLS",
    "vietname":"VNM","vietna":"VNM","emirados arabes unidos":"ARE","eau":"ARE","emirados":"ARE",
    "arabia saudita":"SAU","qatar":"QAT","oman":"OMN","kuwait":"KWT",
    "japao":"JPN","china":"CHN","india":"IND","singapura":"SGP","malasia":"MYS","tailandia":"THA","indonesia":"IDN",
    "turquia":"TUR","turkiye":"TUR","argelia":"DZA","marrocos":"MAR","tunisia":"TUN","egito":"EGY",
    "nigeria":"NGA","ghana":"GHA","costa do marfim":"CIV","cote d’ivoire":"CIV","cote d'ivoire":"CIV",
    "reino unido (uk)":"GBR",
}

SADC = {"AGO","ZAF","BWA","COD","COG","LBR","LSO","MDG","MWI","MUS","MOZ","NAM","SYC","SWZ","TZA","ZMB","ZWE","COM","STP"}
UE27 = {"AUT","BEL","BGR","HRV","CYP","CZE","DNK","EST","FIN","FRA","DEU","GRC","HUN","IRL","ITA","LVA","LTU","LUX","MLT","NLD","POL","PRT","ROU","SVK","SVN","ESP","SWE"}
ASIA = {"AFG","ARM","AZE","BHR","BGD","BRN","BTN","KHM","CHN","CYP","GEO","HKG","IND","IDN","IRN","IRQ","ISR","JPN","JOR","KAZ","KWT","KGZ","LAO","LBN","MAC","MYS","MDV","MNG","MMR","NPL","PRK","OMN","PAK","PSE","PHL","QAT","SAU","SGP","KOR","LKA","SYR","TWN","TJK","THA","TUR","TKM","ARE","UZB","VNM","YEM"}

# --------------------- HELPERS ---------------------
def _slug(text: str) -> str:
    return unidecode(str(text).strip().lower())

def _to_month_name(m: int) -> str:
    nomes = ["Jan","Fev","Mar","Abr","Mai","Jun","Jul","Ago","Set","Out","Nov","Dez"]
    return nomes[int(m)-1] if 1 <= int(m) <= 12 else str(m)

def _fmt_compact(v: float) -> str:
    try: n = float(v)
    except Exception: return "—"
    for div, suf in [(1e12,"T"), (1e9,"B"), (1e6,"M"), (1e3,"K")]:
        if abs(n) >= div:
            return f"{n/div:.2f}{suf}"
    return f"{n:,.0f}"

def _y_prefix(moeda: str) -> str:
    return "$ " if moeda == "USD" else "kz "

def _download_png_button(fig: go.Figure, filename: str, key: str):
    try:
        png_bytes = fig.to_image(format="png", engine="kaleido", scale=2)
        st.download_button("⬇️ Baixar PNG", data=png_bytes, file_name=filename, mime="image/png", key=key)
    except Exception:
        st.info("Para baixar PNG, verifique se **kaleido** está instalado.")

# --------------------- DADOS (DEMO / CSV) ---------------------
@st.cache_data(show_spinner=False)
def gerar_dados_sinteticos(seed: int = 7) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    meses = np.arange(1, 13, dtype=int)
    parceiros = ["China","Índia","Portugal","África do Sul","Espanha","França","Holanda","Itália","Alemanha","Emirados Árabes Unidos","Singapura","Japão","Brasil","Namíbia","Zâmbia","Congo (RDC)","Congo-Brazzaville","EUA","Reino Unido"]
    produtos = ["Petróleo bruto","Gás natural","Diamantes","Derivados de petróleo","Bebidas","Cimentos","Madeira serrada","Peixes congelados","Café","Açúcar"]
    rows = []
    for month in meses:
        saz = (1 + 0.1*np.sin(2*np.pi*(month/12.0)))
        for partner in parceiros:
            for prod in produtos:
                base_exp = 1.8e12 if prod in {"Petróleo bruto", "Gás natural", "Diamantes"} else 1.2e10
                base_imp = 8e11 if prod in {"Derivados de petróleo", "Cimentos", "Máquinas"} else 1e10
                v_exp = max(0, rng.normal(loc=base_exp, scale=0.2*base_exp)) * saz
                v_imp = max(0, rng.normal(loc=base_imp, scale=0.25*base_imp)) * (2 - saz)
                rows.append([2022, month, "Exportações", partner, prod, float(v_exp)])
                rows.append([2022, month, "Importações", partner, prod, float(v_imp)])
    return pd.DataFrame(rows, columns=["year","month","flow","partner_country","product_desc","value_aoa"])

@st.cache_data(show_spinner=False)
def carregar_dados(uploaded_file, demo: bool) -> pd.DataFrame:
    if demo or uploaded_file is None:
        df = gerar_dados_sinteticos()
    else:
        df = pd.read_csv(uploaded_file)
    rename_map = {v: k for k, v in MAPEAMENTO_COLUNAS.items() if v in df.columns}
    df = df.rename(columns=rename_map)
    colunas_essenciais = ["year","month","flow","partner_country","product_desc","value_aoa"]
    faltantes = [c for c in colunas_essenciais if c not in df.columns]
    if faltantes:
        st.error(f"CSV inválido: faltam colunas essenciais: {', '.join(faltantes)}"); st.stop()
    df["year"] = pd.to_numeric(df["year"], errors="coerce").astype("Int64")
    df["month"] = pd.to_numeric(df["month"], errors="coerce").astype("Int64")
    df["value_aoa"] = pd.to_numeric(df["value_aoa"], errors="coerce").fillna(0.0)
    df["flow"] = df["flow"].astype(str)
    df["partner_country"] = df["partner_country"].astype(str)
    df["product_desc"] = df["product_desc"].fillna("Desconhecido").astype(str)
    if not (df["year"] == 2022).any():
        st.error("O dataset não contém linhas do ano **2022**."); st.stop()
    if (df["year"] != 2022).any():
        st.warning("Foram encontradas linhas fora de 2022; apenas 2022 será considerado.")
        df = df[df["year"] == 2022]
    df = df[(df["month"] >= 1) & (df["month"] <= 12)].copy()
    df["month_name"] = df["month"].apply(_to_month_name)
    return df

def _pycountry_to_iso3(name: str) -> str:
    try:
        return pycountry.countries.lookup(name).alpha_3
    except Exception:
        try:
            return pycountry.countries.search_fuzzy(name)[0].alpha_3
        except Exception:
            return ""

@st.cache_data(show_spinner=False)
def normalizar_paises(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["partner_country_clean"] = df["partner_country"].fillna("").astype(str)
    iso_codes = []
    for raw in df["partner_country_clean"]:
        key = _slug(raw)
        if key in EXCECOES_ISO3:
            iso_codes.append(EXCECOES_ISO3[key]); continue
        iso = _pycountry_to_iso3(unidecode(raw))
        iso_codes.append(iso if iso else None)
    df["iso3"] = iso_codes
    return df

@st.cache_data(show_spinner=False)
def ler_taxas_csv(uploaded_rates) -> Dict[int, float]:
    taxas = {}
    if uploaded_rates is not None:
        try:
            dfr = pd.read_csv(uploaded_rates)
            dfr["month"] = pd.to_numeric(dfr["month"], errors="coerce").astype("Int64")
            dfr["rate"] = pd.to_numeric(dfr["rate"], errors="coerce")
            dfr = dfr[(dfr["month"] >= 1) & (dfr["month"] <= 12) & dfr["rate"].notna()]
            taxas = dict(zip(dfr["month"].astype(int), dfr["rate"].astype(float)))
        except Exception:
            pass
    return taxas

def obter_taxas(taxas_lidas: Dict[int, float]) -> Tuple[Dict[int, float], float, bool]:
    """ Widgets de taxa fora do cache """
    taxas = dict(taxas_lidas) if taxas_lidas else {}
    st.sidebar.markdown("### 💱 Taxas de câmbio AOA→USD (2022)")
    cols = st.sidebar.columns(3)
    for m in range(1, 13):
        c = cols[(m-1) % 3]
        with c:
            default = float(taxas.get(m, 0.0))
            val = st.number_input(f"M{m:02d}", min_value=0.0, value=default, step=0.1, format="%.4f", key=f"rate_{m:02d}")
        if val > 0:
            taxas[m] = float(val)
    valid = [v for v in taxas.values() if v and v > 0]
    taxa_media = float(np.mean(valid)) if valid else 0.0
    completo = all(m in taxas and taxas[m] > 0 for m in range(1, 13))
    return taxas, taxa_media, completo

# --------------------- AGREGAÇÕES ---------------------
@st.cache_data(show_spinner=False)
def precompute_aggs(df: pd.DataFrame) -> Dict[str, pd.DataFrame]:
    monthly_flow = df.groupby(["month","flow"], as_index=False)["value"].sum().sort_values(["month","flow"])
    by_partner   = df.groupby(["partner_country_clean","iso3","flow"], as_index=False)["value"].sum()
    by_product   = df.groupby(["product_desc","flow"], as_index=False)["value"].sum()
    tmp = df.copy()
    tmp["regiao"] = tmp["iso3"].apply(lambda x: "SADC" if x in SADC else ("UE" if x in UE27 else ("Ásia" if x in ASIA else "Outros")))
    by_region    = tmp.groupby(["regiao","flow"], as_index=False)["value"].sum()
    monthly_region = tmp.groupby(["month","regiao"], as_index=False)["value"].sum()
    return {"monthly_flow": monthly_flow, "by_partner": by_partner, "by_product": by_product,
            "by_region": by_region, "monthly_region": monthly_region}

# --------------------- GRÁFICOS ---------------------
def _hover_val(moeda):
    return f"<b>%{{y:,.0f}}</b> {moeda}<br><span style='font-size:0.9em;color:#888'>Passe o rato para comparar meses.</span>"

def plot_series(monthly_flow: pd.DataFrame, moeda: str) -> go.Figure:
    pvt = monthly_flow.pivot(index="month", columns="flow", values="value").fillna(0.0).reindex(range(1,13), fill_value=0.0)
    for col in ["Exportações","Importações"]:
        if col not in pvt.columns:
            pvt[col] = 0.0
    pvt["month_name"] = [_to_month_name(m) for m in pvt.index]
    long = pvt.reset_index().melt(id_vars=["month","month_name"], value_vars=["Exportações","Importações"], var_name="Fluxo", value_name="Valor")
    fig = px.line(long, x="month_name", y="Valor", color="Fluxo", markers=True,
                  labels={"Valor": f"Valor ({moeda})", "month_name":"Mês"},
                  color_discrete_map={"Exportações": P["RED"], "Importações": P["GOLD"]})
    fig.update_traces(hovertemplate=_hover_val(moeda))
    tot = long.groupby("month_name")["Valor"].sum()
    if len(tot) > 0:
        mx, mn = tot.idxmax(), tot.idxmin()
        fig.add_annotation(x=mx, y=tot[mx], text="Pico", showarrow=True, arrowcolor=P["GOLD"])
        fig.add_annotation(x=mn, y=tot[mn], text="Vale", showarrow=True, arrowcolor=P["RED"])
    fig.update_layout(legend_title=None, margin=dict(l=10,r=10,t=10,b=10),
                      plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
    fig.update_yaxes(tickprefix=_y_prefix(moeda))
    return fig

def plot_balanca_mensal(monthly_flow: pd.DataFrame, moeda: str) -> go.Figure:
    pvt = monthly_flow.pivot(index="month", columns="flow", values="value").fillna(0.0).reindex(range(1,13), fill_value=0.0)
    exp = pvt.get("Exportações", pd.Series(0.0, index=pvt.index))
    imp = pvt.get("Importações", pd.Series(0.0, index=pvt.index))
    bal = exp - imp
    df = pd.DataFrame({"Mês":[_to_month_name(m) for m in pvt.index],
                       "Exportações":exp.values, "Importações":imp.values, "Balança":bal.values})
    fig = go.Figure()
    fig.add_bar(name="Exportações", x=df["Mês"], y=df["Exportações"], marker_color=P["RED"], opacity=0.9, hovertemplate=_hover_val(moeda))
    fig.add_bar(name="Importações", x=df["Mês"], y=df["Importações"], marker_color=P["GOLD"], opacity=0.9, hovertemplate=_hover_val(moeda))
    fig.add_trace(go.Scatter(name="Balança (linha)", x=df["Mês"], y=df["Balança"], mode="lines+markers",
                             line=dict(width=3, color=P["TEXT"]), hovertemplate=_hover_val(moeda)))
    saldo_total = df["Balança"].sum()
    txt = "Superávit no ano" if saldo_total >= 0 else "Déficit no ano"
    fig.add_annotation(x=df["Mês"].iloc[-1], y=df["Balança"].iloc[-1], text=txt, showarrow=True, arrowcolor=P["TEXT"])
    fig.update_layout(barmode="group", legend_title=None, margin=dict(l=10,r=10,t=10,b=10),
                      yaxis_title=f"Valor ({moeda})", plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
    fig.update_yaxes(tickprefix=_y_prefix(moeda))
    return fig

def plot_top_parceiros(by_partner: pd.DataFrame, top_n: int, fluxo: str, moeda: str) -> go.Figure:
    df = by_partner[by_partner["flow"] == fluxo].groupby(["partner_country_clean","iso3"], as_index=False)["value"].sum()
    df = df.sort_values("value", ascending=False).head(top_n)
    fig = px.bar(df, x="value", y="partner_country_clean", orientation="h",
                 labels={"value": f"Valor ({moeda})", "partner_country_clean":"Parceiro"},
                 hover_data={"iso3": True, "partner_country_clean": True, "value": ":,.0f"},
                 color_discrete_sequence=[P["RED"]])
    fig.update_traces(hovertemplate="<b>%{y}</b><br>Valor: %{x:,.0f} "+moeda)
    fig.update_layout(yaxis={"categoryorder":"total ascending"}, margin=dict(l=10,r=10,t=10,b=10),
                      plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
    fig.update_xaxes(tickprefix=_y_prefix(moeda))
    return fig

def plot_top_produtos_bar(by_product: pd.DataFrame, top_n: int, fluxo: str, moeda: str) -> go.Figure:
    df = by_product[by_product["flow"] == fluxo].groupby(["product_desc"], as_index=False)["value"].sum().sort_values("value", ascending=False).head(top_n)
    fig = px.bar(df, x="value", y="product_desc", orientation="h",
                 labels={"value": f"Valor ({moeda})", "product_desc":"Produto"},
                 hover_data={"product_desc": True, "value": ":,.0f"},
                 color_discrete_sequence=[P["GOLD"]])
    fig.update_traces(hovertemplate="<b>%{y}</b><br>Valor: %{x:,.0f} "+moeda)
    fig.update_layout(yaxis={"categoryorder":"total ascending"}, margin=dict(l=10,r=10,t=10,b=10),
                      plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
    fig.update_xaxes(tickprefix=_y_prefix(moeda))
    return fig

def plot_top_produtos_treemap(by_product: pd.DataFrame, top_n: int, fluxo: str, moeda: str) -> go.Figure:
    df = by_product[by_product["flow"] == fluxo].groupby(["product_desc"], as_index=False)["value"].sum().sort_values("value", ascending=False).head(top_n)
    fig = px.treemap(df, path=["product_desc"], values="value",
                     hover_data={"value":":,.0f"},
                     color="value",
                     color_continuous_scale=[[0, P["GRAY"]],[0.5, P["GOLD"]],[1, P["RED"]]])
    fig.update_traces(hovertemplate="<b>%{label}</b><br>Valor: %{value:,.0f} "+moeda)
    fig.update_layout(margin=dict(l=10,r=10,t=10,b=10), coloraxis_showscale=False,
                      plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
    return fig

def plot_mapa(by_partner: pd.DataFrame, fluxo: str, moeda: str) -> go.Figure:
    df = by_partner[by_partner["flow"] == fluxo].groupby(["iso3"], as_index=False)["value"].sum()
    df = df[df["iso3"].notna() & (df["iso3"] != "")]
    fig = px.choropleth(df, locations="iso3", color="value",
                        color_continuous_scale=[[0, P["GRAY"]],[0.5, P["GOLD"]],[1, P["RED"]]],
                        labels={"value": f"Valor ({moeda})"}, hover_data={"iso3": True, "value": ":,.0f"},
                        projection="natural earth")
    fig.update_layout(margin=dict(l=10,r=10,t=10,b=10),
                      plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
    return fig

def plot_participacao(df_base: pd.DataFrame, top_n: int, por: str, fluxo: str, moeda: str) -> go.Figure:
    if por == "partner":
        g = df_base[df_base["flow"] == fluxo].groupby("partner_country_clean", as_index=False)["value"].sum()
        label, ycol, color = "Parceiro", "partner_country_clean", P["RED"]
    else:
        g = df_base[df_base["flow"] == fluxo].groupby("product_desc", as_index=False)["value"].sum()
        label, ycol, color = "Produto", "product_desc", P["GOLD"]
    total = g["value"].sum()
    g["pct"] = 100.0 * g["value"] / total if total else 0.0
    g = g.sort_values("pct", ascending=False).head(top_n)
    fig = px.bar(g, x="pct", y=ycol, orientation="h",
                 labels={"pct":"Participação (%)", ycol:label},
                 hover_data={ycol:True, "pct":":.2f", "value":":,.0f"},
                 color_discrete_sequence=[color])
    fig.update_traces(hovertemplate="<b>%{y}</b><br>Participação: %{x:.2f}%")
    fig.update_layout(yaxis={"categoryorder":"total ascending"}, margin=dict(l=10,r=10,t=10,b=10),
                      plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
    return fig

def plot_regioes(by_region: pd.DataFrame, moeda: str) -> go.Figure:
    df = by_region.pivot(index="regiao", columns="flow", values="value").fillna(0.0).reset_index()
    for col in ["Exportações","Importações"]:
        if col not in df.columns: df[col] = 0.0
    fig = px.bar(df, x="regiao", y=["Exportações","Importações"], barmode="group",
                 labels={"value": f"Valor ({moeda})", "regiao":"Região/Bloco", "variable":"Fluxo"},
                 color_discrete_map={"Exportações": P["RED"], "Importações": P["GOLD"]})
    fig.update_layout(margin=dict(l=10,r=10,t=10,b=10), legend_title=None,
                      plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
    fig.update_yaxes(tickprefix=_y_prefix(moeda))
    return fig

def plot_area_regioes(monthly_region: pd.DataFrame, moeda: str) -> go.Figure:
    g = monthly_region.copy()
    g["Mês"] = g["month"].apply(_to_month_name)
    fig = px.area(g, x="Mês", y="value", color="regiao",
                  labels={"value": f"Valor ({moeda})", "regiao":"Região/Bloco"})
    fig.update_traces(hovertemplate="<b>%{fullData.name}</b><br>Mês: %{x}<br>Valor: %{y:,.0f} " + moeda)
    fig.update_layout(margin=dict(l=10,r=10,t=10,b=10), legend_title=None,
                      plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
    fig.update_yaxes(tickprefix=_y_prefix(moeda))
    return fig

def plot_pareto_parceiros(by_partner: pd.DataFrame, fluxo: str) -> go.Figure:
    df = by_partner[by_partner["flow"] == fluxo].groupby("partner_country_clean", as_index=False)["value"].sum().sort_values("value", ascending=False)
    fig = go.Figure()
    if df.empty:
        return fig
    df["cum_pct"] = 100 * df["value"].cumsum() / df["value"].sum()
    fig.add_bar(x=df["partner_country_clean"], y=df["value"], name="Valor", marker_color=P["RED"], hovertemplate="<b>%{x}</b><br>Valor: %{y:,.0f}")
    fig.add_trace(go.Scatter(x=df["partner_country_clean"], y=df["cum_pct"], name="Acumulado (%)", yaxis="y2",
                             mode="lines+markers", line=dict(color=P["TEXT"]), hovertemplate="Acumulado: %{y:.1f}%"))
    close80 = (df["cum_pct"] - 80).abs().idxmin()
    fig.add_annotation(x=df["partner_country_clean"].iloc[close80], y=df["cum_pct"].iloc[close80], text="≈80%", showarrow=True, arrowcolor=P["TEXT"])
    fig.update_layout(yaxis=dict(title="Valor"), yaxis2=dict(title="Acumulado (%)", overlaying="y", side="right", range=[0,100]),
                      margin=dict(l=10,r=10,t=10,b=10), legend_title=None,
                      plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
    return fig

# --------------------- KPIs / INSIGHTS / RECOMENDAÇÕES ---------------------
def gerar_kpis(df_filtered: pd.DataFrame, moeda: str, meses_sel: List[int]) -> None:
    prefix = _y_prefix(moeda)
    st.markdown('<div class="section"><div class="title">📌 Indicadores-Chave</div></div>', unsafe_allow_html=True)

    def fmt(n): return prefix + _fmt_compact(n)

    exp_total = df_filtered.loc[df_filtered["flow"]=="Exportações","value"].sum()
    imp_total = df_filtered.loc[df_filtered["flow"]=="Importações","value"].sum()
    balanca   = exp_total - imp_total
    cobertura = (exp_total/imp_total) if imp_total else float("nan")
    n_parceiros = df_filtered["partner_country_clean"].nunique()

    mes_ref = max(meses_sel) if meses_sel else int(df_filtered["month"].max()) if not df_filtered.empty else 1
    cur = df_filtered[df_filtered["month"] == mes_ref]["value"].sum() if not df_filtered.empty else float("nan")
    prev = df_filtered[df_filtered["month"] == (mes_ref-1)]["value"].sum() if mes_ref>1 else float("nan")
    var_mm = (cur/prev - 1.0)*100.0 if (prev and prev>0) else float("nan")

    st.markdown('<div class="kpi-grid">', unsafe_allow_html=True)
    st.markdown(f'<div class="kpi-card"><div class="kpi-title">🚢 Exportações</div><div class="kpi-value">{fmt(exp_total)}</div></div>', unsafe_allow_html=True)
    st.markdown(f'<div class="kpi-card"><div class="kpi-title">📦 Importações</div><div class="kpi-value">{fmt(imp_total)}</div></div>', unsafe_allow_html=True)
    st.markdown(f'<div class="kpi-card" title="Balança = Exportações − Importações."><div class="kpi-title">⚖️ Balança</div><div class="kpi-value">{fmt(balanca)}</div></div>', unsafe_allow_html=True)
    cob_text = f"{cobertura*100:.1f}%" if cobertura==cobertura else "—"
    st.markdown(f'<div class="kpi-card" title="Cobertura = Exportações / Importações."><div class="kpi-title">🛡️ Cobertura</div><div class="kpi-value">{cob_text}</div></div>', unsafe_allow_html=True)
    st.markdown(f'<div class="kpi-card"><div class="kpi-title">🌍 N.º de parceiros</div><div class="kpi-value">{int(n_parceiros)}</div></div>', unsafe_allow_html=True)
    var_text = f"{var_mm:.1f}%" if var_mm==var_mm else "—"
    st.markdown(f'<div class="kpi-card" title="Variação m/m do comércio total no último mês do filtro."><div class="kpi-title">↕️ Variação m/m</div><div class="kpi-value">{var_text}</div></div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

def gerar_insights(df: pd.DataFrame, fluxo_ref: str) -> List[str]:
    insights = []
    if df.empty: return ["Sem valores no filtro atual."]
    total = df["value"].sum()
    if total <= 0:
        return ["Sem valores no filtro atual."]
    top_partner = df.groupby("partner_country_clean")["value"].sum().sort_values(ascending=False).head(1)
    if not top_partner.empty:
        nome = top_partner.index[0]; val = top_partner.iloc[0]; pct = 100*val/total
        insights.append(f"**{nome}** é o principal parceiro no período filtrado, com **{pct:.1f}%** do total.")
    top_prod = df.groupby("product_desc")["value"].sum().sort_values(ascending=False).head(1)
    if not top_prod.empty:
        nome = top_prod.index[0]; val = top_prod.iloc[0]; pct = 100*val/total
        insights.append(f"O produto de maior peso é **{nome}**, com **{pct:.1f}%** do total.")
    by_m = df.groupby("month")["value"].sum().reindex(range(1,13)).fillna(0)
    if by_m.max() > 0:
        best_m = int(by_m.idxmax()); worst_m = int(by_m.idxmin())
        insights.append(f"O mês com **maior atividade** foi **{_to_month_name(best_m)}**, e o **menor** foi **{_to_month_name(worst_m)}**.")
    exp = df[df["flow"]=="Exportações"]["value"].sum()
    imp = df[df["flow"]=="Importações"]["value"].sum()
    bal = exp - imp
    if bal >= 0: insights.append("A **balança comercial está superavitária** no período filtrado (exportações > importações).")
    else:        insights.append("A **balança comercial está deficitária** no período filtrado (importações > exportações).")
    share = df.groupby("partner_country_clean")["value"].sum().sort_values(ascending=False).cumsum() / total * 100
    n80 = (share <= 80).sum()
    if n80 >= 1:
        insights.append(f"**{n80} parceiros** respondem por cerca de **80%** do valor total — atenção à concentração.")
    return insights

def gerar_recomendacoes(df: pd.DataFrame) -> List[str]:
    recs = []
    if df.empty: return ["Sem dados para recomendações."]
    exp = df[df["flow"]=="Exportações"]["value"].sum()
    imp = df[df["flow"]=="Importações"]["value"].sum()
    if exp > imp:
        recs.append("**Diversificar a pauta exportadora** além de petróleo/gás para reduzir risco de preço.")
    else:
        recs.append("**Substituição competitiva de importações** em bens essenciais (máquinas/derivados) com políticas de incentivo.")
    top_partner = df.groupby("partner_country_clean")["value"].sum().sort_values(ascending=False).head(1)
    if not top_partner.empty:
        nome = top_partner.index[0]
        recs.append(f"**Gestão de risco com {nome}**: negociar contratos, seguro de crédito e monitorar logística.")
    # Exemplo de leitura regional
    if (df["iso3"].isin(SADC)).any():
        recs.append("**Aprofundar integração SADC** (regras de origem, facilitação aduaneira) para reduzir custos.")
    return recs

# --------------------- APP ---------------------
def main():
    # HERO / Cabeçalho
    if website_mode:
        c1, c2 = st.columns([1,6])
        with c1:
            if os.path.exists("insignia_angola.png"):
                st.image("insignia_angola.png", use_column_width=False)
        with c2:
            st.markdown('<div class="app-hero"><div><h1>Comércio Externo de Angola — 2022</h1><div class="sub">Análise mensal do INE com conversão AOA⇄USD e visual executivo.</div></div></div>', unsafe_allow_html=True)
    else:
        st.title("Comércio Externo de Angola — 2022")
        st.caption("Fonte: INE (Angola), 2022.")

    # ---------------- Sidebar: arquivos e opções ----------------
    st.sidebar.header("⚙️ Dados e opções")
    demo_mode = st.sidebar.toggle("Modo Demo (dados sintéticos)", value=True)
    uploaded_file = st.sidebar.file_uploader("CSV principal (2022)", type=["csv"])
    uploaded_rates = st.sidebar.file_uploader("CSV de taxas AOA→USD (opcional)", type=["csv"])

    # Moeda
    moeda = st.sidebar.radio("Moeda", options=["AOA","USD"], horizontal=True)

    # Ler dados
    df_raw = carregar_dados(uploaded_file, demo=demo_mode)
    df_norm = normalizar_paises(df_raw)

    # Taxas
    taxas_lidas = ler_taxas_csv(uploaded_rates)
    taxas, taxa_media, completo_rates = obter_taxas(taxas_lidas)

    # Conversão
    df_val = df_norm.copy()
    if moeda == "AOA":
        df_val["value"] = df_val["value_aoa"]
        msg_taxa = "Moeda: AOA (valores originais)."
        badge = ""
    else:
        def _rate_for_month(m):
            r = taxas.get(int(m), 0.0)
            return r if r and r > 0 else taxa_media
        df_val["applied_rate"] = df_val["month"].apply(_rate_for_month)
        df_val["value"] = df_val["value_aoa"] / df_val["applied_rate"].replace(0, np.nan)
        msg_taxa = "Moeda: USD — usa taxa mensal quando disponível; meses sem taxa usam **média**."
        badge = "" if completo_rates else '<span class="badge">Taxa média aplicada em meses faltantes</span>'
    st.caption(msg_taxa + (" " + badge if badge else ""))

    # ---------------- Filtros ----------------
    st.sidebar.header("🔎 Filtros")
    meses = sorted(df_val["month"].dropna().astype(int).unique().tolist())
    parceiros = sorted(df_val["partner_country_clean"].unique().tolist())
    produtos = sorted(df_val["product_desc"].unique().tolist())
    fluxos = ["Exportações","Importações"]

    if "meses_sel" not in st.session_state: st.session_state["meses_sel"] = meses
    if "parceiros_sel" not in st.session_state: st.session_state["parceiros_sel"] = []
    if "produtos_sel" not in st.session_state: st.session_state["produtos_sel"] = []
    if "fluxo_sel" not in st.session_state: st.session_state["fluxo_sel"] = "Todos"
    if "topn" not in st.session_state: st.session_state["topn"] = 10
    if "tipo_prod_viz" not in st.session_state: st.session_state["tipo_prod_viz"] = "Barras"

    col_reset, col_topn = st.sidebar.columns([1,1])
    with col_reset:
        if st.button("🔄 Resetar filtros"):
            st.session_state["meses_sel"] = meses
            st.session_state["parceiros_sel"] = []
            st.session_state["produtos_sel"] = []
            st.session_state["fluxo_sel"] = "Todos"
            st.session_state["topn"] = 10
            st.session_state["tipo_prod_viz"] = "Barras"

    st.session_state["meses_sel"] = st.sidebar.multiselect("Mês", options=meses, default=st.session_state["meses_sel"], format_func=lambda m: f"{m:02d} - {_to_month_name(m)}")
    st.session_state["parceiros_sel"] = st.sidebar.multiselect("Parceiros", options=parceiros, default=st.session_state["parceiros_sel"])
    st.session_state["produtos_sel"] = st.sidebar.multiselect("Produtos", options=produtos, default=st.session_state["produtos_sel"])
    st.session_state["fluxo_sel"] = st.sidebar.selectbox("Fluxo", options=["Todos"] + fluxos, index=0)
    vmin, vmax = float(df_val["value"].min()), float(df_val["value"].max())
    faixa = st.sidebar.slider("Faixa de valor", min_value=0.0, max_value=max(1.0, vmax), value=(0.0, vmax))
    with col_topn:
        st.session_state["topn"] = st.selectbox("Top N", options=[5,10,20], index=1)

    st.sidebar.markdown("**Top Produtos**")
    st.session_state["tipo_prod_viz"] = st.sidebar.radio("Tipo", ["Barras","Treemap"], horizontal=True, key="tipo_prod_viz_radio")

    # Aplicar filtros
    df_f = df_val[df_val["month"].isin(st.session_state["meses_sel"])].copy()
    if st.session_state["parceiros_sel"]:
        df_f = df_f[df_f["partner_country_clean"].isin(st.session_state["parceiros_sel"])]
    if st.session_state["produtos_sel"]:
        df_f = df_f[df_f["product_desc"].isin(st.session_state["produtos_sel"])]
    if st.session_state["fluxo_sel"] in fluxos:
        df_f = df_f[df_f["flow"] == st.session_state["fluxo_sel"]]
    df_f = df_f[(df_f["value"] >= faixa[0]) & (df_f["value"] <= faixa[1])]
    aggs = precompute_aggs(df_f)

    # ---------------- Tabs ----------------
    tab1, tab2, tab3, tab4, tab5 = st.tabs(["📊 Visão Geral", "🤝 Parceiros", "📦 Produtos", "🧭 Regiões", "📋 Dados"])

    # ----- Visão Geral -----
    with tab1:
        # KPIs
        gerar_kpis(df_f, moeda, st.session_state["meses_sel"])

        # Série temporal
        st.markdown('<div class="section"><div class="title">📈 Série temporal (2022)</div></div>', unsafe_allow_html=True)
        st.markdown('<div class="card">', unsafe_allow_html=True)
        fig_series = plot_series(aggs["monthly_flow"], moeda)
        st.plotly_chart(fig_series, use_container_width=True)
        _download_png_button(fig_series, f"serie_temporal_{moeda}.png", key="dl_series")
        st.markdown('</div>', unsafe_allow_html=True)

        # Balança
        st.markdown('<div class="section"><div class="title">📉 Balança mensal (colunas + linha)</div></div>', unsafe_allow_html=True)
        st.markdown('<div class="card">', unsafe_allow_html=True)
        fig_bal = plot_balanca_mensal(aggs["monthly_flow"], moeda)
        st.plotly_chart(fig_bal, use_container_width=True)
        _download_png_button(fig_bal, f"balanca_mensal_{moeda}.png", key="dl_bal")
        st.markdown('</div>', unsafe_allow_html=True)

        # Insights + Recomendações
        colA, colB = st.columns(2)
        with colA:
            st.markdown('<div class="section"><div class="title">💡 Insights automáticos</div></div>', unsafe_allow_html=True)
            st.markdown('<div class="card">', unsafe_allow_html=True)
            for i in gerar_insights(df_f, st.session_state["fluxo_sel"] if st.session_state["fluxo_sel"] in {"Exportações","Importações"} else "Exportações"):
                st.markdown(f"- {i}")
            st.markdown('</div>', unsafe_allow_html=True)
        with colB:
            st.markdown('<div class="section"><div class="title">📝 Recomendações</div></div>', unsafe_allow_html=True)
            st.markdown('<div class="card">', unsafe_allow_html=True)
            for r in gerar_recomendacoes(df_f):
                st.markdown(f"- {r}")
            st.markdown('</div>', unsafe_allow_html=True)

    # ----- Parceiros -----
    with tab2:
        fluxo_ref = st.session_state["fluxo_sel"] if st.session_state["fluxo_sel"] in {"Exportações","Importações"} else "Exportações"
        col1, col2 = st.columns(2)
        with col1:
            st.markdown('<div class="section"><div class="title">🌍 Top Parceiros</div></div>', unsafe_allow_html=True)
            st.markdown('<div class="card">', unsafe_allow_html=True)
            fig_top_parc = plot_top_parceiros(aggs["by_partner"], st.session_state["topn"], fluxo_ref, moeda)
            st.plotly_chart(fig_top_parc, use_container_width=True)
            _download_png_button(fig_top_parc, f"top_parceiros_{fluxo_ref}_{moeda}.png", key="dl_parc")
            st.markdown('</div>', unsafe_allow_html=True)
        with col2:
            st.markdown('<div class="section"><div class="title">📊 Pareto de Parceiros (acumulado %)</div></div>', unsafe_allow_html=True)
            st.markdown('<div class="card">', unsafe_allow_html=True)
            fig_pareto = plot_pareto_parceiros(aggs["by_partner"], fluxo_ref)
            st.plotly_chart(fig_pareto, use_container_width=True)
            _download_png_button(fig_pareto, f"pareto_{fluxo_ref}.png", key="dl_pareto")
            st.markdown('</div>', unsafe_allow_html=True)

        st.markdown('<div class="section"><div class="title">🗺️ Mapa mundial (por parceiro)</div></div>', unsafe_allow_html=True)
        st.markdown('<div class="card">', unsafe_allow_html=True)
        fig_map = plot_mapa(aggs["by_partner"], fluxo_ref, moeda)
        st.plotly_chart(fig_map, use_container_width=True)
        _download_png_button(fig_map, f"mapa_{fluxo_ref}_{moeda}.png", key="dl_map")
        st.markdown('</div>', unsafe_allow_html=True)

    # ----- Produtos -----
    with tab3:
        col1, col2 = st.columns(2)
        with col1:
            st.markdown('<div class="section"><div class="title">🧩 Top Produtos</div></div>', unsafe_allow_html=True)
            st.markdown('<div class="card">', unsafe_allow_html=True)
            if st.session_state["tipo_prod_viz"] == "Treemap":
                fig_top_prod = plot_top_produtos_treemap(aggs["by_product"], st.session_state["topn"], fluxo_ref, moeda)
                st.plotly_chart(fig_top_prod, use_container_width=True)
                _download_png_button(fig_top_prod, f"top_produtos_treemap_{fluxo_ref}_{moeda}.png", key="dl_prod_tm")
            else:
                fig_top_prod = plot_top_produtos_bar(aggs["by_product"], st.session_state["topn"], fluxo_ref, moeda)
                st.plotly_chart(fig_top_prod, use_container_width=True)
                _download_png_button(fig_top_prod, f"top_produtos_{fluxo_ref}_{moeda}.png", key="dl_prod")
            st.markdown('</div>', unsafe_allow_html=True)
        with col2:
            st.markdown('<div class="section"><div class="title">% Participação por Produto</div></div>', unsafe_allow_html=True)
            st.markdown('<div class="card">', unsafe_allow_html=True)
            fig_pr = plot_participacao(df_f, st.session_state["topn"], "product", fluxo_ref, moeda)
            st.plotly_chart(fig_pr, use_container_width=True)
            _download_png_button(fig_pr, f"participacao_produtos_{fluxo_ref}_{moeda}.png", key="dl_pr")
            st.markdown('</div>', unsafe_allow_html=True)

    # ----- Regiões -----
    with tab4:
        col1, col2 = st.columns(2)
        with col1:
            st.markdown('<div class="section"><div class="title">🧭 Regiões/Blocos</div></div>', unsafe_allow_html=True)
            st.markdown('<div class="card">', unsafe_allow_html=True)
            fig_reg = plot_regioes(aggs["by_region"], moeda)
            st.plotly_chart(fig_reg, use_container_width=True)
            _download_png_button(fig_reg, f"regioes_{moeda}.png", key="dl_reg")
            st.markdown('</div>', unsafe_allow_html=True)
        with col2:
            st.markdown('<div class="section"><div class="title">🌐 Séries por Regiões (área empilhada)</div></div>', unsafe_allow_html=True)
            st.markdown('<div class="card">', unsafe_allow_html=True)
            fig_area = plot_area_regioes(aggs["monthly_region"], moeda)
            st.plotly_chart(fig_area, use_container_width=True)
            _download_png_button(fig_area, f"series_regioes_{moeda}.png", key="dl_area")
            st.markdown('</div>', unsafe_allow_html=True)

    # ----- Dados -----
    with tab5:
        st.markdown('<div class="section"><div class="title">📋 Dados filtrados</div></div>', unsafe_allow_html=True)
        st.markdown('<div class="card">', unsafe_allow_html=True)
        termo = st.text_input("🔍 Buscar (parceiro/produto)", "")
        df_view = df_f.copy()
        if termo:
            t = _slug(termo)
            df_view = df_view[ df_view["partner_country_clean"].apply(lambda x: t in _slug(x)) | df_view["product_desc"].apply(lambda x: t in _slug(x)) ]
        st.dataframe(df_view.sort_values(["month","flow","partner_country_clean"]), use_container_width=True, hide_index=True)
        csv_bytes = df_view.to_csv(index=False).encode("utf-8")
        st.download_button("⬇️ Baixar CSV filtrado", data=csv_bytes, file_name="dados_filtrados.csv", mime="text/csv")
        st.markdown('</div>', unsafe_allow_html=True)

    st.markdown("---")
    st.caption("Fonte: INE (Angola), 2022.")

if __name__ == "__main__":
    main()
