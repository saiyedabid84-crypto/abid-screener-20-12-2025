import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go

st.set_page_config("Demand & Supply Scanner", layout="wide")

# ---------------- LOAD NIFTY 500 ---------------- #
@st.cache_data
def load_nifty500():
    try:
        df = pd.read_csv("nifty500.csv")
        
        # Clean column names
        df.columns = df.columns.str.strip()
        
        # Take the first (and only) column as company names
        companies = df.iloc[:, 0].astype(str).str.strip()
        
        # Add .NS suffix if not present
        companies_list = []
        for comp in companies.tolist():
            if not comp.endswith('.NS'):
                companies_list.append(f"{comp}.NS")
            else:
                companies_list.append(comp)
        
        return companies_list
    except Exception as e:
        st.error(f"Error loading CSV: {e}")
        return []


STOCKS = load_nifty500()[:50]

TIMEFRAMES = {
    "15m": "15m", "30m": "30m", "60m": "60m", "75m": "75m",
    "120m": "120m", "125m": "125m", "240m": "240m",
    "Daily": "1d", "Weekly": "1wk", "Monthly": "1mo"
}

# ---------------- CORE FUNCTIONS ---------------- #
def fetch_data(symbol, interval):
    try:
        df = yf.download(symbol, period="1y", interval=interval, progress=False)
        
        # Flatten yfinance MultiIndex columns (CRITICAL)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        
        return df
    except Exception as e:
        return pd.DataFrame()


def is_explosive(c, avg):
    if pd.isna(avg) or avg == 0:
        return False
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
    
    # Safety cleanup
    df = df.dropna()
    
    if len(df) < 60:
        return results
    
    avg_range = (df["High"] - df["Low"]).rolling(20).mean()
    max_base = 3 if tf in ["15m","30m","60m","75m","120m","125m","240m"] else 6
    price = float(df.iloc[-1]["Close"])
    
    for i in range(len(df) - max_base - 2):
        leg_in = df.iloc[i]
        base = df.iloc[i + 1 : i + 1 + max_base]
        leg_out = df.iloc[i + 1 + max_base]
        
        if base.empty:
            continue
        
        zh = float(base["High"].max())
        zl = float(base["Low"].min())
        avg = avg_range.iloc[i]
        
        if pd.isna(avg):
            continue
        
        # Force scalar OHLC values
        ci = float(leg_in["Close"])
        oi = float(leg_in["Open"])
        co = float(leg_out["Close"])
        oo = float(leg_out["Open"])
        
        # -------- SUPPLY -------- #
        if (
            ci > oi
            and co < oo
            and is_explosive(leg_in, avg)
            and is_explosive(leg_out, avg)
        ):
            entry = zh
            sl = zh * 1.002
            target = entry - abs(sl - entry) * 3  # Fixed: use abs() for correct direction
            
            if (
                is_one_touch(df, zh, zl, i)
                and within_1_percent(price, zh, zl)
                and rr_ok(entry, sl, target)
            ):
                results.append(("Supply", entry, sl, target, zh, zl))
        
        # -------- DEMAND -------- #
        if (
            ci < oi
            and co > oo
            and is_explosive(leg_in, avg)
            and is_explosive(leg_out, avg)
        ):
            entry = zl
            sl = zl * 0.998
            target = entry + abs(entry - sl) * 3
            
            if (
                is_one_touch(df, zh, zl, i)
                and within_1_percent(price, zh, zl)
                and rr_ok(entry, sl, target)
            ):
                results.append(("Demand", entry, sl, target, zh, zl))
    
    return results


# ---------------- PLOT ---------------- #
def plot_chart(df, zones, symbol, tf):
    fig = go.Figure()
    fig.add_candlestick(
        x=df.index, 
        open=df["Open"], 
        high=df["High"],
        low=df["Low"], 
        close=df["Close"]
    )
    
    for z in zones:
        ztype, entry, sl, tgt, zh, zl = z
        color = "red" if ztype == "Supply" else "green"
        
        fig.add_shape(
            type="rect", 
            x0=df.index[0], 
            x1=df.index[-1],
            y0=zl, 
            y1=zh, 
            fillcolor=color, 
            opacity=0.25, 
            line_width=0
        )
        
        fig.add_hline(y=entry, line_dash="dot", line_color="blue", 
                      annotation_text="Entry", annotation_position="right")
        fig.add_hline(y=sl, line_dash="dash", line_color="red",
                      annotation_text="SL", annotation_position="right")
        fig.add_hline(y=tgt, line_dash="dash", line_color="green",
                      annotation_text="Target", annotation_position="right")
    
    fig.update_layout(
        title=f"{symbol} | {tf}", 
        xaxis_rangeslider_visible=False,
        height=600
    )
    
    return fig


# ---------------- UI ---------------- #
st.title("📊 Demand & Supply Scanner (Exact Entry | SL | Target)")

if not STOCKS:
    st.error("⚠️ Could not load stocks. Please check nifty500.csv exists.")
    st.stop()

selected_tf = st.multiselect(
    "Select Timeframes",
    list(TIMEFRAMES.keys()),
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
    if not selected_tf:
        st.warning("⚠️ Please select at least one timeframe")
    else:
        progress = st.progress(0)
        status_text = st.empty()
        
        for i, stock in enumerate(STOCKS):
            status_text.text(f"Scanning {stock} ({i+1}/{len(STOCKS)})...")
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
        
        status_text.text("✅ Scan complete!")

# ---------------- RESULT TABLE ---------------- #
if results_table:
    st.subheader("📋 Trade Setups")
    st.dataframe(pd.DataFrame(results_table), use_container_width=True)
elif st.session_state.get('scan_complete'):
    st.info("ℹ️ No trade setups found matching the criteria.")

# Track scan completion
if st.button("🔍 Scan Now"):
    st.session_state['scan_complete'] = True
