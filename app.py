import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px

st.set_page_config(page_title="DCF Valuation Engine", page_icon="💰", layout="wide")

st.title("💰 Interactive DCF Valuation & WACC Sensitivity Engine")
st.markdown("5-Year Discounted Cash Flow (DCF) model with Enterprise-to-Equity bridge and live WACC vs. Terminal Growth sensitivity heatmap.")

# Sidebar: Presets & Assumptions
st.sidebar.header("🏢 Company Preset")
preset = st.sidebar.selectbox(
    "Select Template (in ₹ Crores)",
    ["Indian IT Services Co.", "Specialty Chemicals Co.", "FMCG Leader", "Custom"]
)

presets = {
    "Indian IT Services Co.": (15000.0, 12.0, 24.0, 25.0, 4.0, 2.0, 11.5, 5.0, -2500.0, 50.0, 1100.0),
    "Specialty Chemicals Co.": (8000.0, 15.0, 20.0, 25.0, 8.0, 4.0, 12.0, 5.0, 1200.0, 25.0, 850.0),
    "FMCG Leader": (25000.0, 10.0, 22.0, 25.0, 5.0, 1.0, 10.5, 5.5, -1500.0, 100.0, 920.0),
    "Custom": (10000.0, 12.0, 20.0, 25.0, 5.0, 2.0, 11.0, 5.0, 500.0, 40.0, 750.0),
}

p_rev, p_gr, p_ebitda, p_tax, p_capex, p_nwc, p_wacc, p_tgr, p_ndebt, p_shares, p_cmp = presets[preset]

st.sidebar.header("📊 Operating Assumptions")
base_rev = st.sidebar.number_input("Base Year Revenue (₹ Cr)", value=p_rev, step=500.0)
rev_growth = st.sidebar.slider("Annual Revenue Growth (%)", 0.0, 30.0, p_gr, 0.5)
ebitda_margin = st.sidebar.slider("EBITDA Margin (%)", 5.0, 45.0, p_ebitda, 0.5)
tax_rate = st.sidebar.slider("Effective Tax Rate (%)", 15.0, 35.0, p_tax, 1.0)
capex_pct = st.sidebar.slider("CapEx (% of Revenue)", 1.0, 20.0, p_capex, 0.5)
nwc_pct = st.sidebar.slider("Change in NWC (% of Rev Growth)", 0.0, 15.0, p_nwc, 0.5)

st.sidebar.header("⚖️ Valuation & Capital Structure")
wacc = st.sidebar.slider("WACC / Discount Rate (%)", 7.0, 18.0, p_wacc, 0.25)
tgr = st.sidebar.slider("Terminal Growth Rate (%)", 2.0, 8.0, p_tgr, 0.25)
net_debt = st.sidebar.number_input("Net Debt (₹ Cr) [Negative = Net Cash]", value=p_ndebt, step=100.0)
shares = st.sidebar.number_input("Diluted Shares (Crores)", value=p_shares, min_value=1.0, step=1.0)
cmp = st.sidebar.number_input("Current Market Price (₹)", value=p_cmp, min_value=1.0, step=10.0)

if wacc <= tgr:
    st.error("WACC must be greater than Terminal Growth Rate for a valid DCF valuation.")
    st.stop()

# 5-Year DCF Calculation
years = [f"Year {i}" for i in range(1, 6)]
revs, ebitdas, taxes, capexs, nwcs, fcfs, pv_fcfs = [], [], [], [], [], [], []

prev_rev = base_rev
for i in range(1, 6):
    r = prev_rev * (1 + rev_growth / 100)
    ebitda = r * (ebitda_margin / 100)
    # Assuming D&A approx equals 70% of CapEx for EBIT calculation
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

# Terminal Value & Enterprise-to-Equity Bridge
terminal_value = (fcfs[-1] * (1 + tgr / 100)) / ((wacc - tgr) / 100)
pv_tv = terminal_value / ((1 + wacc / 100) ** 5)
enterprise_value = sum(pv_fcfs) + pv_tv
equity_value = enterprise_value - net_debt
implied_price = equity_value / shares
upside = ((implied_price - cmp) / cmp) * 100

# Top KPI Cards
c1, c2, c3, c4 = st.columns(4)
c1.metric("Enterprise Value (₹ Cr)", f"₹{enterprise_value:,.0f} Cr")
c2.metric("Equity Value (₹ Cr)", f"₹{equity_value:,.0f} Cr")
c3.metric("Implied Share Price", f"₹{implied_price:,.1f}", f"{upside:+.1f}% vs CMP (₹{cmp:,.0f})")
verdict = "UNDERVALUED (BUY)" if upside > 10 else ("OVERVALUED (SELL)" if upside < -10 else "FAIRLY VALUED (HOLD)")
c4.metric("Valuation Signal", verdict)

st.markdown("---")

# Charts Row
col1, col2 = st.columns(2)

with col1:
    st.subheader("5-Year Projected Free Cash Flow (₹ Cr)")
    fig_fcf = go.Figure()
    fig_fcf.add_trace(go.Bar(x=years, y=fcfs, name="Unlevered FCF", marker_color="#3498db", text=[f"₹{x:,.0f}" for x in fcfs], textposition="outside"))
    fig_fcf.add_trace(go.Bar(x=years, y=pv_fcfs, name="PV of FCF", marker_color="#2ecc71", text=[f"₹{x:,.0f}" for x in pv_fcfs], textposition="outside"))
    fig_fcf.update_layout(barmode="group", height=380, margin=dict(t=20, b=20), yaxis_title="₹ Crores")
    st.plotly_chart(fig_fcf, use_container_width=True)

with col2:
    st.subheader("Sensitivity Heatmap: Implied Share Price (₹)")
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
        labels=dict(x="Terminal Growth Rate (%)", y="WACC (%)", color="Implied Price (₹)"),
        x=[f"{g}%" for g in tgr_range],
        y=[f"{w}%" for w in wacc_range],
        text_auto=True,
        color_continuous_scale="RdYlGn"
    )
    fig_hm.update_layout(height=380, margin=dict(t=20, b=20))
    st.plotly_chart(fig_hm, use_container_width=True)

# Projection Table
st.subheader("5-Year Unlevered Free Cash Flow (UFCF) Schedule (₹ Cr)")
df_proj = pd.DataFrame({
    "Metric (₹ Cr)": ["Revenue", "EBITDA", "Less: Taxes", "Less: CapEx", "Less: Change in NWC", "Unlevered FCF", "PV of FCF"],
    "Year 1": [revs[0], ebitdas[0], taxes[0], capexs[0], nwcs[0], fcfs[0], pv_fcfs[0]],
    "Year 2": [revs[1], ebitdas[1], taxes[1], capexs[1], nwcs[1], fcfs[1], pv_fcfs[1]],
    "Year 3": [revs[2], ebitdas[2], taxes[2], capexs[2], nwcs[2], fcfs[2], pv_fcfs[2]],
    "Year 4": [revs[3], ebitdas[3], taxes[3], capexs[3], nwcs[3], fcfs[3], pv_fcfs[3]],
    "Year 5": [revs[4], ebitdas[4], taxes[4], capexs[4], nwcs[4], fcfs[4], pv_fcfs[4]],
})
st.dataframe(df_proj.style.format({y: "{:,.1f}" for y in years}), use_container_width=True)
