import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import os

st.set_page_config(page_title="港股狙擊手 V8.3", layout="wide")

# --- 1. 名單讀取 ---
def load_stocks():
    file_path = 'stocks.txt'
    default = ["0700.HK", "3690.HK", "9988.HK", "1810.HK", "9888.HK"]
    if not os.path.exists(file_path): return default
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            stocks = [line.split('#')[0].strip().replace('"', '').replace("'", "") for line in f if line.strip()]
        res = [s for s in stocks if s.endswith('.HK')]
        return res if res else default
    except:
        return default

TARGET_STOCKS = load_stocks()

# --- 2. 數據抓取 (新增備援邏輯) ---
def get_stock_data(ticker, period="6mo"):
    try:
        # 如果是科指，啟動雙源備援
        if ticker == "^HSTECH":
            df = yf.Ticker("^HSTECH").history(period=period)
            if df.empty or len(df) < 2:
                # 🌟 備援方案：如果真科指掛了，立刻改抓 ETF
                df = yf.Ticker("3032.HK").history(period=period)
        else:
            df = yf.Ticker(ticker).history(period=period)
            
        if df.empty: return pd.DataFrame()
        
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
            
        for col in ['Open', 'High', 'Low', 'Close', 'Volume']:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')
        
        df.index = pd.to_datetime(df.index).tz_localize(None)
        return df.dropna(subset=['Close'])
    except:
        return pd.DataFrame()

def calculate_rsi(series, period=14):
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

# --- 3. 繪圖函數 ---
def show_chart(ticker, df):
    fig = make_subplots(rows=3, cols=1, shared_xaxes=True, vertical_spacing=0.03, row_heights=[0.6, 0.2, 0.2])
    fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name='K線'), row=1, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df['Close'].rolling(20).mean(), name='20MA', line=dict(color='orange')), row=1, col=1)
    fig.add_trace(go.Bar(x=df.index, y=df['Volume'], name='成交量', marker_color='#26a69a'), row=2, col=1)
    df['RSI'] = calculate_rsi(df['Close'])
    fig.add_trace(go.Scatter(x=df.index, y=df['RSI'], name='RSI', line=dict(color='#ab47bc')), row=3, col=1)
    fig.update_layout(height=600, showlegend=False, xaxis_rangeslider_visible=False, margin=dict(t=30, b=10))
    st.plotly_chart(fig, use_container_width=True)

# --- 4. 主程式 ---
st.title("🏹 港股狙擊手 V8.3 - 終極穩壓版")
t1, t2, t3, t4 = st.tabs(["🌍 大市導航", "🏆 跑贏大市", "🎯 策略掃描", "🔍 個股分析"])

# --- Tab 1: 大市導航 ---
with t1:
    st.subheader("📊 市場核心指數")
    col1, col2, col3 = st.columns(3)
    
    with st.spinner("抓取數據中..."):
        hsi = get_stock_data("^HSI")
        hstech = get_stock_data("^HSTECH")
        vix = get_stock_data("^VIX")
        
        with col1:
            if not hsi.empty:
                curr = hsi['Close'].iloc[-1]
                prev = hsi['Close'].iloc[-2]
                st.metric("🇭🇰 恆生指數 (^HSI)", f"{curr:.2f}", f"{((curr-prev)/prev)*100:.2f}%")
                fig = go.Figure(go.Scatter(x=hsi.index, y=hsi['Close'], line=dict(color='#1f77b4')))
                fig.update_layout(height=250, margin=dict(l=0,r=0,t=0,b=0))
                st.plotly_chart(fig, use_container_width=True)

        with col2:
            if not hstech.empty:
                curr = hstech['Close'].iloc[-1]
                prev = hstech['Close'].iloc[-2]
                # 🌟 自動判斷顯示名稱
                label = "🚀 恆生科技指數" if curr > 1000 else "🚀 恆科 ETF (3032.HK)"
                st.metric(label, f"{curr:.2f}", f"{((curr-prev)/prev)*100:.2f}%")
                fig = go.Figure(go.Scatter(x=hstech.index, y=hstech['Close'], line=dict(color='#ff7f0e')))
                fig.update_layout(height=250, margin=dict(l=0,r=0,t=0,b=0))
                st.plotly_chart(fig, use_container_width=True)

        with col3:
            if not vix.empty:
                curr_vix = vix['Close'].iloc[-1]
                st.metric("🇺🇸 VIX 恐慌指數", f"{curr_vix:.2f}", f"{curr_vix - vix['Close'].iloc[-2]:.2f}", delta_color="inverse")
                fig = go.Figure(go.Scatter(x=vix.index, y=vix['Close'], line=dict(color='#d62728')))
                fig.update_layout(height=250, margin=dict(l=0,r=0,t=0,b=0))
                st.plotly_chart(fig, use_container_width=True)

# --- Tab 2: 跑贏大市 ---
with t2:
    st.subheader("🥇 個股強度競賽")
    tf_label = st.selectbox("選擇比較範圍", ["1日 (1d)", "1週 (5d)", "1個月 (1mo)", "3個月 (3mo)", "6個月 (6mo)"], index=2)
    tf_map = {"1日 (1d)": "1d", "1週 (5d)": "5d", "1個月 (1mo)": "1mo", "3個月 (3mo)": "3mo", "6個月 (6mo)": "6mo"}
    tf = tf_map[tf_label]
    
    if st.button("🚀 開始計算相對強度"):
        hsi_df = get_stock_data("^HSI", period=tf)
        hst_df = get_stock_data("^HSTECH", period=tf)
        
        if not hsi_df.empty and not hst_df.empty:
            hsi_p = (hsi_df['Close'].iloc[-1] / hsi_df['Close'].iloc[0] - 1) * 100
            hst_p = (hst_df['Close'].iloc[-1] / hst_df['Close'].iloc[0] - 1) * 100
            
            c1, c2 = st.columns(2)
            c1.info(f"恆指報酬率: {hsi_p:.2f}%")
            c2.warning(f"科指報酬率: {hst_p:.2f}%")
            
            results = []
            pbar = st.progress(0)
            for i, s in enumerate(TARGET_STOCKS):
                pbar.progress((i+1)/len(TARGET_STOCKS))
                df = get_stock_data(s, period=tf)
                if not df.empty and len(df) >= 2:
                    p = (df['Close'].iloc[-1] / df['Close'].iloc[0] - 1) * 100
                    results.append({"代碼": s, "報酬率(%)": round(p, 2), "領先恆指(%)": round(p - hsi_p, 2), "領先科指(%)": round(p - hst_p, 2)})
            
            if results:
                res_df = pd.DataFrame(results).sort_values("領先科指(%)", ascending=False)
                style_func = res_df.style.map if hasattr(res_df.style, 'map') else res_df.style.applymap
                st.dataframe(style_func(lambda x: 'color:red' if x > 0 else 'color:green', subset=['領先恆指(%)', '領先科指(%)']), use_container_width=True)
        else:
            st.error("大數據源目前繁忙，請稍後再試。")

# --- Tab 3 & 4 (略) ---
with t3:
    if st.button("🔥 執行全市場狙擊"):
        hits = []
        pbar = st.progress(0)
        for i, s in enumerate(TARGET_STOCKS):
            pbar.progress((i+1)/len(TARGET_STOCKS))
            df = get_stock_data(s)
            if len(df) < 30: continue
            df['MA10'] = df['Close'].rolling(10).mean()
            df['MA20'] = df['Close'].rolling(20).mean()
            df['RSI'] = calculate_rsi(df['Close'])
            c = df.iloc[-1]
            vol_avg = df['Volume'].tail(5).mean()
            vol_r = c['Volume'] / vol_avg if vol_avg > 0 else 0
            if c['Close'] > c['MA10'] and c['Close'] > c['MA20'] and vol_r > 1.5 and 50 < c['RSI'] < 72:
                hits.append({"代碼": s, "現價": round(c['Close'], 2), "量比": round(vol_r, 2)})
                st.success(f"🎯 發現標的: {s}")
                show_chart(s, df)

with t4:
    s_input = st.text_input("輸入代碼", "0700.HK").upper()
    if st.button("查詢"):
        df = get_stock_data(s_input)
        if not df.empty: show_chart(s_input, df)
