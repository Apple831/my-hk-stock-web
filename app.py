import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import os
import time

st.set_page_config(page_title="港股狙擊手 V8.7", layout="wide")

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

# --- 2. 數據抓取 ---
def get_stock_data(ticker, period="6mo"):
    try:
        # 針對指數代碼進行備援處理
        if ticker == "^HSTECH":
            dat = yf.Ticker("^HSTECH")
            df = dat.history(period=period)
            if df.empty or len(df) < 2:
                df = yf.Ticker("3032.HK").history(period=period)
        else:
            df = yf.Ticker(ticker).history(period=period)
            
        if df.empty: return pd.DataFrame()
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        df.index = pd.to_datetime(df.index).tz_localize(None)
        return df.dropna(subset=['Close'])
    except:
        return pd.DataFrame()

def calculate_macd(df, fast=12, slow=26, signal=9):
    exp1 = df['Close'].ewm(span=fast, adjust=False).mean()
    exp2 = df['Close'].ewm(span=slow, adjust=False).mean()
    macd = exp1 - exp2
    sig = macd.ewm(span=signal, adjust=False).mean()
    hist = macd - sig
    return macd, sig, hist

# --- 3. 繪圖函數 (顏色回歸：綠漲紅跌) ---
def show_chart(ticker, df):
    fig = make_subplots(rows=3, cols=1, shared_xaxes=True, vertical_spacing=0.05, row_heights=[0.5, 0.2, 0.3])
    
    # K線：綠漲紅跌
    fig.add_trace(go.Candlestick(
        x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], 
        increasing_line_color='#26a69a', decreasing_line_color='#ef5350', name='K線'
    ), row=1, col=1)
    
    # 均線
    fig.add_trace(go.Scatter(x=df.index, y=df['Close'].rolling(5).mean(), name='5MA', line=dict(color='gray', width=1)), row=1, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df['Close'].rolling(20).mean(), name='20MA', line=dict(color='purple', width=1)), row=1, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df['Close'].rolling(60).mean(), name='60MA', line=dict(color='orange', width=2)), row=1, col=1)
    
    # 成交量
    vol_colors = ['#26a69a' if df['Close'].iloc[i] >= df['Open'].iloc[i] else '#ef5350' for i in range(len(df))]
    fig.add_trace(go.Bar(x=df.index, y=df['Volume'], name='成交量', marker_color=vol_colors), row=2, col=1)
    
    # MACD
    macd, sig, hist = calculate_macd(df)
    hist_colors = ['#26a69a' if val >= 0 else '#ef5350' for val in hist]
    fig.add_trace(go.Bar(x=df.index, y=hist, name='MACD Hist', marker_color=hist_colors), row=3, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=macd, name='DIF', line=dict(color='#1f77b4')), row=3, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=sig, name='DEA', line=dict(color='#ff7f0e')), row=3, col=1)
    
    fig.update_layout(height=600, showlegend=False, xaxis_rangeslider_visible=False, margin=dict(t=30, b=10))
    st.plotly_chart(fig, use_container_width=True)

# --- 4. 主程式 ---
st.title("🏹 港股狙擊手 V8.7")
t1, t2, t3, t4 = st.tabs(["🌍 大市導航", "🏆 跑贏大市", "🎯 策略掃描", "🔍 個股分析"])

with t1:
    st.subheader("📊 市場核心指數")
    col1, col2, col3 = st.columns(3)
    with st.spinner("連線中..."):
        hsi, hstech, vix = get_stock_data("^HSI"), get_stock_data("^HSTECH"), get_stock_data("^VIX")
        for df, col, title in [(hsi, col1, "🇭🇰 恆指"), (hstech, col2, "🚀 恆科"), (vix, col3, "🇺🇸 VIX")]:
            with col:
                if not df.empty:
                    curr, prev = df['Close'].iloc[-1], df['Close'].iloc[-2]
                    change = ((curr-prev)/prev)*100
                    st.metric(title, f"{curr:.2f}", f"{change:.2f}%", delta_color="normal") # 這裡 delta_color 會自動套用綠漲紅跌
                    fig = go.Figure(go.Scatter(x=df.index, y=df['Close'], line=dict(color='#1f77b4')))
                    fig.update_layout(height=180, margin=dict(l=0,r=0,t=0,b=0))
                    st.plotly_chart(fig, use_container_width=True)
                else:
                    st.error(f"⚠️ {title} 連線失敗")

with t2:
    st.subheader("🥇 強度競賽")
    tf = st.selectbox("範圍", ["5d", "1mo", "3mo"], index=1)
    if st.button("🚀 開始計算"):
        hsi_df, hst_df = get_stock_data("^HSI", tf), get_stock_data("^HSTECH", tf)
        if not hsi_df.empty and not hst_df.empty:
            hsi_p = (hsi_df['Close'].iloc[-1]/hsi_df['Close'].iloc[0]-1)*100
            hst_p = (hst_df['Close'].iloc[-1]/hst_df['Close'].iloc[0]-1)*100
            results = []
            for s in TARGET_STOCKS:
                df = get_stock_data(s, tf)
                if not df.empty and len(df) >= 2:
                    p = (df['Close'].iloc[-1]/df['Close'].iloc[0]-1)*100
                    results.append({"代碼": s, "報酬率": round(p,2), "贏恆指": round(p-hsi_p,2), "贏科指": round(p-hst_p,2)})
            if results:
                res_df = pd.DataFrame(results).sort_values("贏科指", ascending=False)
                # 顏色回歸：大於 0 顯示綠色 (profit)
                st.dataframe(res_df.style.map(lambda x: 'color: #26a69a' if x > 0 else 'color: #ef5350', subset=['贏恆指', '贏科指']), use_container_width=True)

# --- 🚀 關鍵更新：自定義策略開關 ---
with t3:
    st.subheader("🎯 策略自選掃描器")
    
    col_a, col_b, col_c = st.columns(3)
    use_ma60 = col_a.checkbox("條件 1：價格在季線 (60MA) 之上", value=True)
    use_align = col_b.checkbox("條件 2：短均線多頭 (5 > 10 > 20)", value=True)
    use_macd = col_c.checkbox("條件 3：MACD 剛翻紅 (金叉)", value=True)
    
    if st.button("🔥 執行全市場狙擊"):
        hits = []
        pbar = st.progress(0)
        status = st.empty()
        
        for i, s in enumerate(TARGET_STOCKS):
            pbar.progress((i+1)/len(TARGET_STOCKS))
            status.text(f"掃描中: {s}")
            try:
                df = get_stock_data(s, period="6mo")
                if df.empty or len(df) < 60: continue
                
                #指標計算
                df['MA5'] = df['Close'].rolling(5).mean()
                df['MA10'] = df['Close'].rolling(10).mean()
                df['MA20'] = df['Close'].rolling(20).mean()
                df['MA60'] = df['Close'].rolling(60).mean()
                macd, sig, hist = calculate_macd(df)
                
                curr = df.iloc[-1]
                
                # 邏輯判斷 (根據 checkbox)
                check1 = (curr['Close'] > curr['MA60']) if use_ma60 else True
                check2 = (curr['MA5'] > curr['MA10'] > curr['MA20']) if use_align else True
                check3 = (hist.iloc[-1] > 0 and hist.iloc[-2] <= 0) if use_macd else True
                
                if check1 and check2 and check3:
                    hits.append(s)
                    st.success(f"🎯 發現標的: {s}")
                    show_chart(s, df)
                
            except: continue
            
        status.text("✅ 掃描結束")
        if not hits: st.warning("未發現符合所選條件的股票")

with t4:
    s_input = st.text_input("輸入代碼", "0700.HK").upper()
    if st.button("查看"):
        df = get_stock_data(s_input)
        if not df.empty: show_chart(s_input, df)
