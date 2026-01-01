import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go

st.set_page_config("Demand & Supply Scanner", layout="wide")

# ---------------- LOAD NIFTY 500 ---------------- #
@st.cache_data
def load_nifty500():
    df = pd.read_csv("nifty500.csv")

    # Clean column names
    df.columns = df.columns.str.strip()

    # Take the first (and only) column as company names
    companies = df.iloc[:, 0].astype(str).str.strip()

    return companies.tolist()



STOCKS = load_nifty500()[:50]

TIMEFRAMES = {
    "15m": "15m", "30m": "30m", "60m": "60m", "75m": "75m",
    "120m": "120m", "125m": "125m", "240m": "240m",
    "Daily": "1d", "Weekly": "1wk", "Monthly": "1mo"
}

# ---------------- CORE FUNCTIONS ---------------- #
def fetch_data(symbol, interval):
    return yf.download(symbol, period="1y", interval=interval, progress=False)

def is_explosive(c, avg):
    return (c["High"] - c["Low"]) >= 2 * avg

def is_one_touch(df, zh, zl, idx):
    touches = 0
    for _, r in df.iloc[idx+1:].iterrows():
        if r["High"] >= zl and r["Low"] <= zh:
            touches += 1
        if touches > 1:
            return False
    return True

def within_1_percent(price, zh, zl):
    if price > zh:
        d = (price - zh) / price * 100
    elif price < zl:
        d = (zl - price) / price * 100
    else:
        d = 0
    return d <= 1

def rr_ok(entry, sl, target):
    risk = abs(entry - sl)
    reward = abs(target - entry)
    return risk > 0 and reward / risk >= 3

# ---------------- ZONE DETECTION ---------------- #
def detect_zones(df, tf):
    results = []
    avg_range = (df["High"] - df["Low"]).rolling(20).mean()
    max_base = 3 if tf in ["15m","30m","60m","75m","120m","125m","240m"] else 6
    price = df.iloc[-1]["Close"]

    for i in range(len(df) - max_base - 2):
        leg_in = df.iloc[i]
        base = df.iloc[i+1:i+1+max_base]
        leg_out = df.iloc[i+1+max_base]

        if base.empty:
            continue

        zh, zl = base["High"].max(), base["Low"].min()

        # -------- SUPPLY -------- #
avg = avg_range.iloc[i]
if pd.isna(avg):
    continue
if (
    leg_in["Close"].item() > leg_in["Open"].item()
    and leg_out["Close"].item() < leg_out["Open"].item()
    and is_explosive(leg_in, avg)
    and is_explosive(leg_out, avg)
):
    entry = zh
    sl = zh * 1.002
    target = entry - (entry - sl) * 3
    if (
        is_one_touch(df, zh, zl, i)
        and within_1_percent(price, zh, zl)
        and rr_ok(entry, sl, target)
    ):
        results.append(
            ("Supply", entry, sl, target, zh, zl)
        )


        # -------- DEMAND -------- #
        if (
            leg_in["Close"] < leg_in["Open"]
            and leg_out["Close"] > leg_out["Open"]
            and is_explosive(leg_in, avg_range.iloc[i])
            and is_explosive(leg_out, avg_range.iloc[i])
        ):
            entry = zl
            sl = zl * 0.998
            target = entry + (entry - sl) * 3

            if (
                is_one_touch(df, zh, zl, i)
                and within_1_percent(price, zh, zl)
                and rr_ok(entry, sl, target)
            ):
                results.append(
                    ("Demand", entry, sl, target, zh, zl)
                )

    return results

# ---------------- PLOT ---------------- #
def plot_chart(df, zones, symbol, tf):
    fig = go.Figure()
    fig.add_candlestick(
        x=df.index, open=df["Open"], high=df["High"],
        low=df["Low"], close=df["Close"]
    )

    for z in zones:
        ztype, entry, sl, tgt, zh, zl = z
        color = "red" if ztype == "Supply" else "green"

        fig.add_shape(type="rect", x0=df.index[0], x1=df.index[-1],
                      y0=zl, y1=zh, fillcolor=color, opacity=0.25, line_width=0)

        fig.add_hline(y=entry, line_dash="dot", line_color="blue")
        fig.add_hline(y=sl, line_dash="dash", line_color="red")
        fig.add_hline(y=tgt, line_dash="dash", line_color="green")

    fig.update_layout(title=f"{symbol} | {tf}", xaxis_rangeslider_visible=False)
    return fig

# ---------------- UI ---------------- #
st.title("📊 Demand & Supply Scanner (Exact Entry | SL | Target)")

selected_tf = st.multiselect(
    "Select Timeframes",
    TIMEFRAMES.keys(),
    default=["15m","30m","60m","240m","Daily"]
)

st.success("""
✔ NIFTY 500 (50 stocks)  
✔ Fresh zones (one-touch)  
✔ Price within 1%  
✔ Risk : Reward ≥ 1 : 3  
✔ Exact Entry, SL & Target  
""")

results_table = []

if st.button("🔍 Scan Now"):
    progress = st.progress(0)

    for i, stock in enumerate(STOCKS):
        progress.progress((i+1)/len(STOCKS))

        for tf in selected_tf:
            df = fetch_data(stock, TIMEFRAMES[tf])
            if df.empty or len(df) < 60:
                continue

            zones = detect_zones(df, tf)

            if zones:
                for z in zones:
                    ztype, entry, sl, tgt, zh, zl = z
                    results_table.append({
                        "Stock": stock.replace(".NS",""),
                        "TF": tf,
                        "Type": ztype,
                        "Entry": round(entry,2),
                        "SL": round(sl,2),
                        "Target": round(tgt,2),
                        "RR": round(abs(tgt-entry)/abs(entry-sl),2)
                    })

                st.subheader(f"{stock} | {tf}")
                st.plotly_chart(
                    plot_chart(df.tail(200), zones, stock, tf),
                    use_container_width=True
                )

# ---------------- RESULT TABLE ---------------- #
if results_table:
    st.subheader("📋 Trade Setups")
    st.dataframe(pd.DataFrame(results_table))
