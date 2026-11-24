import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
import yfinance as yf

st.set_page_config(page_title="Live DCF Valuation Engine", page_icon="💰", layout="wide")

st.title("💰 Live DCF Valuation & WACC Sensitivity Engine")
st.markdown("Enter any **NSE/BSE** (e.g., `TCS.NS`, `TATACHEM.NS`, `INFY.NS`) or **US** ticker (e.g., `AAPL`, `MSFT`) to pull live financials and run a 5-Year DCF.")

# Sidebar: Live Ticker Fetch
st.sidebar.header("🔍 Live Company Search")
ticker_input = st.sidebar.text_input("Stock Ticker (add .NS for NSE)", value="TCS.NS").upper().strip()

@st.cache_data(ttl=3600)
def fetch_company_data(ticker_symbol):
    stock = yf.Ticker(ticker_symbol)
    info = stock.info
    is_inr = ticker_symbol.endswith(".NS") or ticker_symbol.endswith(".BO")
    divisor = 1e7 if is_inr else 1e6  # ₹ Crores for India, $ Millions for Global
    curr = "₹" if is_inr else "$"
    unit = "Cr" if is_inr else "M"
    
    name = info.get("longName", ticker_symbol)
    rev = (info.get("totalRevenue") or 10000 * divisor) / divisor
    ebitda_raw = info.get("ebitda")
    ebitda_margin = ((ebitda_raw / info.get("totalRevenue")) * 100) if (ebitda_raw and info.get("totalRevenue")) else 20.0
    total_debt = (info.get("totalDebt") or 0) / divisor
    total_cash = (info.get("totalCash") or 0) / divisor
    net_debt = total_debt - total_cash
    shares = (info.get("sharesOutstanding") or 50 * divisor) / divisor
    cmp = info.get("currentPrice") or info.get("regularMarketPrice") or 1000.0
    
    return {
        "name": name, "curr": curr, "unit": unit,
        "rev": round(float(rev), 1),
        "ebitda_margin": round(max(5.0, min(60.0, float(ebitda_margin))), 1),
        "net_debt": round(float(net_debt), 1),
        "shares": round(max(0.1, float(shares)), 2),
        "cmp": round(float(cmp), 2)
    }

try:
    c_data = fetch_company_data(ticker_input)
    st.success(f"Loaded Live Data: **{c_data['name']}** ({ticker_input})")
except Exception:
    st.warning("Could not fetch live data for this ticker. Using default values.")
    c_data = {"name": ticker_input, "curr": "₹", "unit": "Cr", "rev": 10000.0, "ebitda_margin": 20.0, "net_debt": 500.0, "shares": 40.0, "cmp": 750.0}

curr, unit = c_data["curr"], c_data["unit"]

st.sidebar.header("📊 Operating Assumptions")
base_rev = st.sidebar.number_input(f"Base Year Revenue ({curr} {unit})", value=c_data["rev"], step=500.0)
rev_growth = st.sidebar.slider("Annual Revenue Growth (%)", 0.0, 30.0, 12.0, 0.5)
ebitda_margin = st.sidebar.slider("EBITDA Margin (%)", 5.0, 60.0, c_data["ebitda_margin"], 0.5)
tax_rate = st.sidebar.slider("Effective Tax Rate (%)", 15.0, 35.0, 25.0, 1.0)
capex_pct = st.sidebar.slider("CapEx (% of Revenue)", 1.0, 20.0, 5.0, 0.5)
nwc_pct = st.sidebar.slider("Change in NWC (% of Rev Growth)", 0.0, 15.0, 2.0, 0.5)

st.sidebar.header("⚖️ Valuation & Capital Structure")
wacc = st.sidebar.slider("WACC / Discount Rate (%)", 7.0, 18.0, 11.5, 0.25)
tgr = st.sidebar.slider("Terminal Growth Rate (%)", 2.0, 8.0, 5.0, 0.25)
net_debt = st.sidebar.number_input(f"Net Debt ({curr} {unit}) [-ve = Net Cash]", value=c_data["net_debt"], step=100.0)
shares = st.sidebar.number_input(f"Diluted Shares ({unit})", value=c_data["shares"], min_value=0.1, step=1.0)
cmp = st.sidebar.number_input(f"Current Market Price ({curr})", value=c_data["cmp"], min_value=1.0, step=10.0)

if wacc <= tgr:
    st.error("WACC must be greater than Terminal Growth Rate.")
    st.stop()

# 5-Year DCF Calculation
years = [f"Year {i}" for i in range(1, 6)]
revs, ebitdas, taxes, capexs, nwcs, fcfs, pv_fcfs = [], [], [], [], [], [], []

prev_rev = base_rev
for i in range(1, 6):
    r = prev_rev * (1 + rev_growth / 100)
    ebitda = r * (ebitda_margin / 100)
    da = r * (capex_pct / 100) * 0.7
    ebit = ebitda - da
    tax = max(0.0, ebit * (tax_rate / 100))
    capex = r * (capex_pct / 100)
    nwc_change = (r - prev_rev) * (nwc_pct / 100)
    fcf = ebitda - tax - capex - nwc_change
    pv = fcf / ((1 + wacc / 100) ** i)
    
    revs.append(r); ebitdas.append(ebitda); taxes.append(tax)
    capexs.append(capex); nwcs.append(nwc_change); fcfs.append(fcf); pv_fcfs.append(pv)
    prev_rev = r

terminal_value = (fcfs[-1] * (1 + tgr / 100)) / ((wacc - tgr) / 100)
pv_tv = terminal_value / ((1 + wacc / 100) ** 5)
enterprise_value = sum(pv_fcfs) + pv_tv
equity_value = enterprise_value - net_debt
implied_price = equity_value / shares
upside = ((implied_price - cmp) / cmp) * 100

# Top KPI Cards (Fixed truncation)
c1, c2, c3, c4 = st.columns(4)
c1.metric(f"Enterprise Value ({curr} {unit})", f"{curr}{enterprise_value:,.0f} {unit}")
c2.metric(f"Equity Value ({curr} {unit})", f"{curr}{equity_value:,.0f} {unit}")
c3.metric("Implied Share Price", f"{curr}{implied_price:,.1f}", f"{upside:+.1f}% vs CMP ({curr}{cmp:,.1f})")
verdict = "BUY" if upside > 10 else ("SELL" if upside < -10 else "HOLD")
c4.metric("Valuation Signal", verdict)

st.markdown("---")

# Charts Row
col1, col2 = st.columns(2)

with col1:
    st.subheader(f"5-Year Projected Free Cash Flow ({curr} {unit})")
    fig_fcf = go.Figure()
    fig_fcf.add_trace(go.Bar(x=years, y=fcfs, name="Unlevered FCF", marker_color="#3498db", text=[f"{curr}{x:,.0f}" for x in fcfs], textposition="outside"))
    fig_fcf.add_trace(go.Bar(x=years, y=pv_fcfs, name="PV of FCF", marker_color="#2ecc71", text=[f"{curr}{x:,.0f}" for x in pv_fcfs], textposition="outside"))
    fig_fcf.update_layout(barmode="group", height=380, margin=dict(t=20, b=20), yaxis_title=f"{curr} {unit}")
    st.plotly_chart(fig_fcf, use_container_width=True)

with col2:
    st.subheader(f"Sensitivity Heatmap: Implied Price ({curr})")
    wacc_range = [round(wacc + d, 2) for d in [-1.5, -0.75, 0, 0.75, 1.5]]
    tgr_range = [round(tgr + d, 2) for d in [-1.0, -0.5, 0, 0.5, 1.0]]
    
    matrix = []
    for w in wacc_range:
        row = []
        for g in tgr_range:
            if w <= g:
                row.append(np.nan)
            else:
                pv_sum = sum([fcfs[idx] / ((1 + w / 100) ** (idx + 1)) for idx in range(5)])
                tv = (fcfs[-1] * (1 + g / 100)) / ((w - g) / 100)
                ev = pv_sum + (tv / ((1 + w / 100) ** 5))
                row.append(round((ev - net_debt) / shares, 1))
        matrix.append(row)
    
    fig_hm = px.imshow(
        matrix,
        labels=dict(x="Terminal Growth Rate (%)", y="WACC (%)", color=f"Price ({curr})"),
        x=[f"{g}%" for g in tgr_range],
        y=[f"{w}%" for w in wacc_range],
        text_auto=True,
        color_continuous_scale="RdYlGn"
    )
    fig_hm.update_layout(height=380, margin=dict(t=20, b=20))
    st.plotly_chart(fig_hm, use_container_width=True)

# Projection Table
st.subheader(f"5-Year Unlevered Free Cash Flow (UFCF) Schedule ({curr} {unit})")
df_proj = pd.DataFrame({
    f"Metric ({curr} {unit})": ["Revenue", "EBITDA", "Less: Taxes", "Less: CapEx", "Less: Change in NWC", "Unlevered FCF", "PV of FCF"],
    "Year 1": [revs[0], ebitdas[0], taxes[0], capexs[0], nwcs[0], fcfs[0], pv_fcfs[0]],
    "Year 2": [revs[1], ebitdas[1], taxes[1], capexs[1], nwcs[1], fcfs[1], pv_fcfs[1]],
    "Year 3": [revs[2], ebitdas[2], taxes[2], capexs[2], nwcs[2], fcfs[2], pv_fcfs[2]],
    "Year 4": [revs[3], ebitdas[3], taxes[3], capexs[3], nwcs[3], fcfs[3], pv_fcfs[3]],
    "Year 5": [revs[4], ebitdas[4], taxes[4], capexs[4], nwcs[4], fcfs[4], pv_fcfs[4]],
})
st.dataframe(df_proj.style.format({y: "{:,.1f}" for y in years}), use_container_width=True)
