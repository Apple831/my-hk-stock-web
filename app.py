import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import os

st.set_page_config(page_title="港股狙擊手 V7", layout="wide")

# --- 1. 名單讀取 ---
def load_stocks():
    file_path = 'stocks.txt'
    default = ["0700.HK", "3690.HK", "9988.HK"]
    if not os.path.exists(file_path): return default
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            stocks = [line.split('#')[0].strip().replace('"', '').replace("'", "") for line in f if line.strip()]
        res = [s for s in stocks if s.endswith('.HK')]
        return res if res else default
    except:
        return default

TARGET_STOCKS = load_stocks()

# --- 2. 數據抓取 (鋼鐵防護版) ---
def get_stock_data(ticker, period="6mo"):
    try:
        dat = yf.Ticker(ticker)
        df = dat.history(period=period)
        if df.empty: return pd.DataFrame()
        
        # 強制壓平多層標籤 (yfinance 新版修復)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
            
        # 確保格式正確
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
    # K線
    fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name='K線'), row=1, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df['Close'].rolling(20).mean(), name='20MA', line=dict(color='orange')), row=1, col=1)
    # 成交量
    fig.add_trace(go.Bar(x=df.index, y=df['Volume'], name='成交量', marker_color='#26a69a'), row=2, col=1)
    # RSI
    df['RSI'] = calculate_rsi(df['Close'])
    fig.add_trace(go.Scatter(x=df.index, y=df['RSI'], name='RSI', line=dict(color='#ab47bc')), row=3, col=1)
    fig.add_hline(y=70, line_dash="dot", line_color="red", row=3, col=1)
    fig.add_hline(y=30, line_dash="dot", line_color="green", row=3, col=1)

    fig.update_layout(height=600, showlegend=False, xaxis_rangeslider_visible=False, margin=dict(t=30, b=10))
    st.plotly_chart(fig, use_container_width=True)

# --- 4. 主程式佈局 ---
st.title("🏹 港股狙擊手 V7")
t1, t2, t3, t4 = st.tabs(["🌍 大市導航", "🏆 跑贏大市", "🎯 策略掃描", "🔍 個股分析"])

# --- Tab 1: 大市導航 (修正圖表缺失) ---
with t1:
    st.subheader("📊 市場即時情緒")
    col1, col2 = st.columns(2)
    
    with st.spinner("抓取數據中..."):
        hsi = get_stock_data("^HSI", period="6mo")
        vix = get_stock_data("^VIX", period="6mo")
        
        with col1:
            if not hsi.empty:
                curr = float(hsi['Close'].iloc[-1])
                prev = float(hsi['Close'].iloc[-2])
                st.metric("🇭🇰 恆生指數 (^HSI)", f"{curr:.2f}", f"{((curr-prev)/prev)*100:.2f}%")
                
                # 🌟 新增：恆指趨勢圖
                fig_hsi = go.Figure(data=[go.Scatter(x=hsi.index, y=hsi['Close'], name='恆指', line=dict(color='#1f77b4', width=2))])
                fig_hsi.update_layout(height=350, margin=dict(l=0,r=0,t=20,b=0), title="恆指半年走勢", xaxis_rangeslider_visible=False)
                st.plotly_chart(fig_hsi, use_container_width=True)
            else:
                st.warning("無法載入恆指數據")

        with col2:
            if not vix.empty:
                curr_vix = float(vix['Close'].iloc[-1])
                prev_vix = float(vix['Close'].iloc[-2])
                st.metric("🇺🇸 VIX 恐慌指數", f"{curr_vix:.2f}", f"{curr_vix - prev_vix:.2f}", delta_color="inverse")
                
                # 🌟 新增：VIX 趨勢圖
                fig_vix = go.Figure(data=[go.Scatter(x=vix.index, y=vix['Close'], name='VIX', line=dict(color='#d62728', width=2))])
                fig_vix.update_layout(height=350, margin=dict(l=0,r=0,t=20,b=0), title="VIX 走勢 (越高越恐慌)", xaxis_rangeslider_visible=False)
                st.plotly_chart(fig_vix, use_container_width=True)
            else:
                st.warning("無法載入 VIX 數據")

# --- Tab 2: 跑贏大市 ---
with t2:
    tf = st.selectbox("比較範圍", ["1mo", "3mo", "6mo"], index=1)
    if st.button("🚀 開始計算相對強度"):
        hsi_df = get_stock_data("^HSI", period=tf)
        if not hsi_df.empty:
            hsi_p = (hsi_df['Close'].iloc[-1] / hsi_df['Close'].iloc[0] - 1) * 100
            st.info(f"期間內恆生指數報酬率: {hsi_p:.2f}%")
            results = []
            pbar = st.progress(0)
            for i, s in enumerate(TARGET_STOCKS):
                pbar.progress((i+1)/len(TARGET_STOCKS))
                df = get_stock_data(s, period=tf)
                if not df.empty and len(df) > 2:
                    p = (df['Close'].iloc[-1] / df['Close'].iloc[0] - 1) * 100
                    results.append({"代碼": s, "報酬率(%)": round(p, 2), "Alpha(領先)": round(p - hsi_p, 2)})
            
            if results:
                res_df = pd.DataFrame(results).sort_values("Alpha(領先)", ascending=False)
                style_func = res_df.style.map if hasattr(res_df.style, 'map') else res_df.style.applymap
                st.dataframe(style_func(lambda x: 'color:red' if x > 0 else 'color:green', subset=['Alpha(領先)']), use_container_width=True, hide_index=True)
                
                fig_alpha = go.Figure(go.Bar(x=res_df["代碼"], y=res_df["Alpha(領先)"], marker_color=['#ef5350' if x > 0 else '#66bb6a' for x in res_df["Alpha(領先)"]]))
                fig_alpha.update_layout(title="個股 Alpha 分佈 (相對於大盤的超額收益)", height=400)
                st.plotly_chart(fig_alpha, use_container_width=True)

# --- Tab 3: 策略掃描 ---
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
            
            # 狙擊條件
            if c['Close'] > c['MA10'] and c['Close'] > c['MA20'] and vol_r > 1.5 and 50 < c['RSI'] < 72:
                hits.append({"代碼": s, "現價": round(c['Close'], 2), "量比": round(vol_r, 2), "RSI": round(c['RSI'], 1)})
                st.success(f"🎯 發現標的: {s}")
                show_chart(s, df)
        if not hits: st.warning("目前市場較弱，無符合「多頭爆發」條件的標的")

# --- Tab 4: 個股分析 ---
with t4:
    s_input = st.text_input("輸入股票代碼 (例: 0700.HK)", "0700.HK").upper()
    if st.button("查看深度分析"):
        df_s = get_stock_data(s_input)
        if not df_s.empty:
            show_chart(s_input, df_s)
        else:
            st.error("找不到該股票，請檢查代碼是否正確 (需包含 .HK)")
