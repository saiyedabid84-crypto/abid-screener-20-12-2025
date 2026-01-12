import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime, timedelta
import numpy as np

st.set_page_config(page_title="125 Min RBR Detector", layout="wide")

st.title("📊 125 Minute RBR (Rally-Base-Rally) Pattern Detector")
st.markdown("Upload your OHLC data or use demo data to detect RBR patterns")

# Sidebar for parameters
st.sidebar.header("RBR Parameters")
base_threshold = st.sidebar.slider("Base Consolidation Threshold (%)", 0.5, 5.0, 2.0, 0.1)
min_rally_percent = st.sidebar.slider("Minimum Rally % Required", 1.0, 10.0, 3.0, 0.5)
lookback_candles = st.sidebar.slider("Lookback Period (candles)", 20, 100, 50, 5)

# File upload
uploaded_file = st.file_uploader("Upload CSV file (columns: Date, Open, High, Low, Close)", type=['csv'])

def generate_demo_data():
    """Generate demo candlestick data with RBR pattern"""
    np.random.seed(42)
    dates = pd.date_range(start='2024-01-01', periods=100, freq='125min')
    
    # Create price movement with RBR pattern
    prices = []
    base_price = 100
    
    for i in range(100):
        if i < 20:  # Initial downtrend/consolidation
            base_price += np.random.uniform(-0.5, 0.3)
        elif i < 35:  # First Rally
            base_price += np.random.uniform(0.3, 1.2)
        elif i < 55:  # Base formation (consolidation)
            base_price += np.random.uniform(-0.3, 0.3)
        elif i < 70:  # Second Rally
            base_price += np.random.uniform(0.4, 1.5)
        else:  # Continuation
            base_price += np.random.uniform(-0.5, 0.8)
        
        prices.append(base_price)
    
    df = pd.DataFrame({
        'Date': dates,
        'Open': prices,
        'High': [p + np.random.uniform(0.2, 1.0) for p in prices],
        'Low': [p - np.random.uniform(0.2, 1.0) for p in prices],
        'Close': [p + np.random.uniform(-0.5, 0.5) for p in prices]
    })
    
    return df

def detect_rbr_pattern(df, base_threshold_pct, min_rally_pct, lookback):
    """
    Detect RBR (Rally-Base-Rally) pattern
    Returns list of detected patterns with base zones
    """
    patterns = []
    
    for i in range(lookback, len(df) - 10):
        # Look for potential base zone
        base_start = i - 15
        base_end = i
        
        if base_start < 0:
            continue
        
        base_candles = df.iloc[base_start:base_end]
        base_high = base_candles['High'].max()
        base_low = base_candles['Low'].min()
        base_range_pct = ((base_high - base_low) / base_low) * 100
        
        # Check if it's a valid base (consolidation)
        if base_range_pct > base_threshold_pct:
            continue
        
        # Check for rally before base
        rally1_start = max(0, base_start - 15)
        rally1_candles = df.iloc[rally1_start:base_start]
        
        if len(rally1_candles) < 5:
            continue
        
        rally1_low = rally1_candles['Low'].min()
        rally1_gain_pct = ((base_low - rally1_low) / rally1_low) * 100
        
        # Check for rally after base
        rally2_end = min(len(df), base_end + 15)
        rally2_candles = df.iloc[base_end:rally2_end]
        
        if len(rally2_candles) < 5:
            continue
        
        rally2_high = rally2_candles['High'].max()
        rally2_gain_pct = ((rally2_high - base_high) / base_high) * 100
        
        # Validate RBR pattern
        if rally1_gain_pct >= min_rally_pct and rally2_gain_pct >= min_rally_pct:
            patterns.append({
                'base_start_idx': base_start,
                'base_end_idx': base_end,
                'base_high': base_high,
                'base_low': base_low,
                'base_range_pct': base_range_pct,
                'rally1_gain': rally1_gain_pct,
                'rally2_gain': rally2_gain_pct,
                'base_start_date': df.iloc[base_start]['Date'],
                'base_end_date': df.iloc[base_end]['Date']
            })
    
    return patterns

# Load data
if uploaded_file is not None:
    df = pd.read_csv(uploaded_file)
    df['Date'] = pd.to_datetime(df['Date'])
    st.success(f"✅ Loaded {len(df)} candles from uploaded file")
else:
    df = generate_demo_data()
    st.info("📌 Using demo data. Upload your CSV file to analyze your own data.")

# Detect patterns
patterns = detect_rbr_pattern(df, base_threshold, min_rally_percent, lookback_candles)

# Display results
st.header(f"🎯 Detected {len(patterns)} RBR Pattern(s)")

if len(patterns) > 0:
    # Create candlestick chart
    fig = go.Figure()
    
    # Add candlestick
    fig.add_trace(go.Candlestick(
        x=df['Date'],
        open=df['Open'],
        high=df['High'],
        low=df['Low'],
        close=df['Close'],
        name='Price'
    ))
    
    # Add base zones for each pattern
    for idx, pattern in enumerate(patterns):
        # Add base zone rectangle
        fig.add_shape(
            type="rect",
            x0=pattern['base_start_date'],
            x1=pattern['base_end_date'],
            y0=pattern['base_low'],
            y1=pattern['base_high'],
            fillcolor="rgba(144, 238, 144, 0.3)",
            line=dict(color="green", width=2),
            name=f"Base Zone {idx+1}"
        )
        
        # Add annotation
        fig.add_annotation(
            x=pattern['base_start_date'],
            y=pattern['base_high'],
            text=f"RBR Base<br>Range: {pattern['base_range_pct']:.2f}%",
            showarrow=True,
            arrowhead=2,
            bgcolor="lightgreen",
            font=dict(size=10)
        )
    
    fig.update_layout(
        title="125 Min RBR Pattern Detection",
        xaxis_title="Date",
        yaxis_title="Price",
        height=600,
        xaxis_rangeslider_visible=False,
        hovermode='x unified'
    )
    
    st.plotly_chart(fig, use_container_width=True)
    
    # Display pattern details
    st.subheader("📋 Pattern Details")
    
    for idx, pattern in enumerate(patterns):
        with st.expander(f"RBR Pattern #{idx+1}"):
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.metric("Base Range %", f"{pattern['base_range_pct']:.2f}%")
                st.write(f"**Base Low:** {pattern['base_low']:.2f}")
                st.write(f"**Base High:** {pattern['base_high']:.2f}")
            
            with col2:
                st.metric("Rally 1 Gain %", f"{pattern['rally1_gain']:.2f}%", delta="Before Base")
                st.metric("Rally 2 Gain %", f"{pattern['rally2_gain']:.2f}%", delta="After Base")
            
            with col3:
                st.write(f"**Base Start:** {pattern['base_start_date'].strftime('%Y-%m-%d %H:%M')}")
                st.write(f"**Base End:** {pattern['base_end_date'].strftime('%Y-%m-%d %H:%M')}")
                st.write(f"**Support Zone:** {pattern['base_low']:.2f} - {pattern['base_high']:.2f}")

else:
    st.warning("⚠️ No RBR patterns detected with current parameters. Try adjusting the parameters in the sidebar.")
    
    # Still show the chart
    fig = go.Figure()
    fig.add_trace(go.Candlestick(
        x=df['Date'],
        open=df['Open'],
        high=df['High'],
        low=df['Low'],
        close=df['Close'],
        name='Price'
    ))
    
    fig.update_layout(
        title="125 Min Candlestick Chart",
        xaxis_title="Date",
        yaxis_title="Price",
        height=600,
        xaxis_rangeslider_visible=False
    )
    
    st.plotly_chart(fig, use_container_width=True)

# Instructions
with st.expander("ℹ️ How to Use"):
    st.markdown("""
    ### CSV File Format
    Your CSV file should have the following columns:
    - **Date**: Date and time (e.g., 2024-01-01 09:00:00)
    - **Open**: Opening price
    - **High**: Highest price
    - **Low**: Lowest price
    - **Close**: Closing price
    
    ### RBR Pattern Explanation
    **Rally-Base-Rally (RBR)** is a bullish continuation pattern consisting of:
    1. **First Rally**: Initial upward price movement
    2. **Base Zone**: Consolidation period with minimal price range (demand zone)
    3. **Second Rally**: Continuation of upward movement after base
    
    The base zone acts as a **support level** for future price action.
    
    ### Parameters
    - **Base Consolidation Threshold**: Maximum % range for base zone
    - **Minimum Rally %**: Minimum gain required for each rally
    - **Lookback Period**: Number of candles to analyze for pattern detection
    """)

st.markdown("---")
st.markdown("💡 **Tip**: The green zones represent demand/support areas where price consolidated before rallying.")
