# 🎈 Blank app template

A simple Streamlit app template for you to modify!

[![Open in Streamlit]

### How to run it on your own machine

# Comércio Externo de Angola — 2022 (Streamlit)

Dashboard interativo para explorar os dados mensais de comércio externo de Angola (INE, 2022), pensado para **investidores**, **gestores públicos** e **acadêmicos**.  
Inclui KPIs, filtros avançados, conversão AOA→USD com **taxas mensais** (ou média), **séries temporais**, **top parceiros/produtos**, **mapa mundial (ISO3)**, **participação (%)**, segmentação por **SADC/UE/Ásia**, tabela com **download CSV** e **exportação de gráficos PNG** (Plotly + Kaleido).

---

## 🚀 Deploy no Streamlit Community Cloud

1. **Crie um repositório público** no GitHub com os seguintes arquivos na raiz:
   ```text
   app.py
   requirements.txt
   README.md
   insignia_angola.png           # opcional (insígnia exibida se presente)
   data/                         # (opcional) coloque aqui seus CSVs reais, se quiser
   ```
2. Acesse (https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://blank-app-template.streamlit.app/), conecte sua conta GitHub e selecione o repositório.
3. Como **Main file path**, indique `app.py`.
4. Clique em **Deploy**.

> **Dicas**  
> - A exportação de PNG usa **kaleido** (já incluso em `requirements.txt`).  
> - Se algum gráfico não baixar, confira os *logs* de dependências na aba “Logs” do Streamlit Cloud.  
> - Para desempenho, o app usa `st.cache_data` e pré-agrupa dados com `groupby`.  

---

## 📥 Estrutura dos dados

**CSV principal (obrigatório)** — colunas mínimas:
- `year` (int) – deve ser 2022  
- `month` (1–12)  
- `flow` – `"Exportações"` ou `"Importações"`  
- `partner_country` – nome do país em PT (p. ex., “Congo (RDC)”, “África do Sul”)  
- `product_desc` – descrição do produto  
- `value_aoa` (float) – valor em **AOA**

**Colunas opcionais**: `hs_code`, `hs_section`, `weight_kg`

**CSV de taxas AOA→USD (opcional)** — colunas:
- `month` (1–12)  
- `rate` (AOA por USD)

Se o CSV de taxas não for enviado, o app solicitará as 12 taxas (jan–dez) manualmente na sidebar; meses sem valor usam a **média** dos meses preenchidos.

---

## 🛠️ Mapeamento de colunas (personalizável)

Se seus CSVs usam nomes diferentes, edite o bloco `MAPEAMENTO_COLUNAS` no início do `app.py` para mapear para os nomes internos:
```python
MAPEAMENTO_COLUNAS = {
    "year": "year",
    "month": "month",
    "flow": "flow",
    "partner_country": "partner_country",
    "product_desc": "product_desc",
    "value_aoa": "value_aoa",
    "hs_code": "hs_code",
    "hs_section": "hs_section",
    "weight_kg": "weight_kg",
}
```

---

## 🧪 Modo Demo

Marque **“Modo Demo (dados sintéticos)”** na sidebar para carregar um dataset coerente (~10–20k linhas) que simula os fluxos de 2022, permitindo testar o dashboard sem dados do INE.

---

## 🗺️ Normalização de países (ISO3)

O app converte `partner_country` → `iso3` usando:
1. Um dicionário de **exceções PT↔EN** (editável em `EXCECOES_ISO3`).
2. *Fallback* via `pycountry` (métodos `lookup`/`search_fuzzy`).

Países não mapeados permanecem sem **ISO3** e, portanto, não aparecem coloridos no mapa.

---

## 🧭 Regiões/Blocos

O agrupamento por **SADC**, **UE**, **Ásia** é feito por dicionários embutidos no código. Ajuste livremente conforme a sua necessidade.

---

## 🧾 Execução local

```bash
# 1) Crie e ative um ambiente virtual (opcional)
python -m venv .venv
source .venv/bin/activate   # (Windows: .venv\\Scripts\\activate)

# 2) Instale dependências
pip install -r requirements.txt

# 3) Rode o app
streamlit run app.py
```

Abra o endereço local que o Streamlit indicar (geralmente http://localhost:8501).

---

## ✅ Critérios de aceitação cobertos

- Roda com `streamlit run app.py` ✅  
- KPIs, filtros, gráficos, mapa, tabelas e exportação funcionando tanto em modo demo quanto com CSV real ✅  
- Conversão AOA↔USD aplica **taxas mensais** quando fornecidas ou **média** quando faltantes ✅  
- Países mapeados corretamente a ISO3; exceções documentadas no código (`EXCECOES_ISO3`) ✅  
- Layout executivo, responsivo e legível; ícones nos KPIs; insígnia exibida quando `insignia_angola.png` está presente ✅  
- Rodapé: “Fonte: INE (Angola), 2022.” ✅

---

## 📎 Observações

- Para datasets muito grandes, considere filtrar previamente por 2022 e por HS se necessário.
- Caso o CSV possua colunas adicionais, elas serão preservadas na tabela final (se renomeadas via mapeamento).
- Para internacionalização adicional (ex.: nomes de países menos comuns em PT), amplie `EXCECOES_ISO3`.




