import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import os
import time

st.set_page_config(page_title="港股狙擊手 V8.4", layout="wide")

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
        # 科指備援邏輯
        if ticker == "^HSTECH":
            df = yf.Ticker("^HSTECH").history(period=period)
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

def calculate_rsi(series, period=14):
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

# --- 3. 繪圖函數 ---
def show_chart(ticker, df):
    fig = make_subplots(rows=3, cols=1, shared_xaxes=True, vertical_spacing=0.05, row_heights=[0.6, 0.2, 0.2])
    fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name='K線'), row=1, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df['Close'].rolling(20).mean(), name='20MA', line=dict(color='orange')), row=1, col=1)
    fig.add_trace(go.Bar(x=df.index, y=df['Volume'], name='成交量', marker_color='#26a69a'), row=2, col=1)
    df['RSI_plot'] = calculate_rsi(df['Close'])
    fig.add_trace(go.Scatter(x=df.index, y=df['RSI_plot'], name='RSI', line=dict(color='#ab47bc')), row=3, col=1)
    fig.update_layout(height=500, showlegend=False, xaxis_rangeslider_visible=False, margin=dict(t=30, b=10))
    st.plotly_chart(fig, use_container_width=True)

# --- 4. 主程式 ---
st.title("🏹 港股狙擊手 V8.4")
t1, t2, t3, t4 = st.tabs(["🌍 大市導航", "🏆 跑贏大市", "🎯 策略掃描", "🔍 個股分析"])

with t1:
    st.subheader("📊 市場核心指數")
    col1, col2, col3 = st.columns(3)
    with st.spinner("獲取大市數據..."):
        hsi = get_stock_data("^HSI")
        hstech = get_stock_data("^HSTECH")
        vix = get_stock_data("^VIX")
        
        for df, col, title in [(hsi, col1, "🇭🇰 恆指"), (hstech, col2, "🚀 恆科"), (vix, col3, "🇺🇸 VIX")]:
            with col:
                if not df.empty:
                    curr, prev = df['Close'].iloc[-1], df['Close'].iloc[-2]
                    label = f"{title} (ETF 3032)" if title == "🚀 恆科" and curr < 1000 else title
                    st.metric(label, f"{curr:.2f}", f"{((curr-prev)/prev)*100:.2f}%")
                    fig = go.Figure(go.Scatter(x=df.index, y=df['Close'], line=dict(width=2)))
                    fig.update_layout(height=200, margin=dict(l=0,r=0,t=0,b=0))
                    st.plotly_chart(fig, use_container_width=True)

with t2:
    st.subheader("🥇 強度競賽")
    tf_label = st.selectbox("範圍", ["1週 (5d)", "1個月 (1mo)", "3個月 (3mo)"], index=1)
    tf = {"1週 (5d)":"5d", "1個月 (1mo)":"1mo", "3個月 (3mo)":"3mo"}[tf_label]
    if st.button("🚀 開始計算"):
        hsi_df, hst_df = get_stock_data("^HSI", tf), get_stock_data("^HSTECH", tf)
        if not hsi_df.empty and not hst_df.empty:
            hsi_p = (hsi_df['Close'].iloc[-1]/hsi_df['Close'].iloc[0]-1)*100
            hst_p = (hst_df['Close'].iloc[-1]/hst_df['Close'].iloc[0]-1)*100
            results = []
            pbar = st.progress(0)
            for i, s in enumerate(TARGET_STOCKS):
                pbar.progress((i+1)/len(TARGET_STOCKS))
                df = get_stock_data(s, tf)
                if not df.empty and len(df) >= 2:
                    p = (df['Close'].iloc[-1]/df['Close'].iloc[0]-1)*100
                    results.append({"代碼": s, "報酬率(%)": round(p,2), "領先恆指": round(p-hsi_p,2), "領先科指": round(p-hst_p,2)})
            if results:
                st.dataframe(pd.DataFrame(results).sort_values("領先科指", ascending=False), use_container_width=True)

# --- 🚀 關鍵修復：策略掃描 ---
with t3:
    st.subheader("🎯 策略掃描 (多頭排列 + 爆量)")
    st.info(f"掃描清單：共 {len(TARGET_STOCKS)} 隻個股")
    
    if st.button("🔥 執行全市場狙擊"):
        hits = []
        status_text = st.empty() # 用於顯示目前進度
        pbar = st.progress(0)
        
        for i, s in enumerate(TARGET_STOCKS):
            status_text.text(f"🔍 正在掃描: {s} ({i+1}/{len(TARGET_STOCKS)})")
            pbar.progress((i+1)/len(TARGET_STOCKS))
            
            try:
                # 這裡調用 6 個月數據來計算 MA
                df = get_stock_data(s, period="6mo")
                
                if df.empty or len(df) < 30:
                    continue
                
                # 計算指標
                df['MA10'] = df['Close'].rolling(10).mean()
                df['MA20'] = df['Close'].rolling(20).mean()
                df['RSI'] = calculate_rsi(df['Close'])
                
                curr = df.iloc[-1]
                vol_avg = df['Volume'].tail(20).mean() # 取20日均量
                vol_ratio = curr['Volume'] / vol_avg if vol_avg > 0 else 0
                
                # 策略條件：
                # 1. 股價在 10MA & 20MA 之上 (多頭排列)
                # 2. RSI 在 50-75 之間 (強勢但不超買)
                # 3. 今日成交量 > 20日平均的 1.3 倍 (爆量)
                is_bull = curr['Close'] > curr['MA10'] and curr['MA10'] > curr['MA20']
                is_strong = 50 < curr['RSI'] < 75
                is_volume_up = vol_ratio > 1.3
                
                if is_bull and is_strong and is_volume_up:
                    hits.append({"代碼": s, "現價": round(curr['Close'], 2), "量比": round(vol_ratio, 2), "RSI": round(curr['RSI'], 1)})
                    st.success(f"🎯 發現信號: {s}")
                    show_chart(s, df)
                
                # 稍微緩衝，避免被 Yahoo 封鎖
                if i % 10 == 0: time.sleep(0.5)
                
            except Exception as e:
                st.warning(f"跳過 {s}: 數據獲取異常")
                continue
        
        status_text.text("✅ 掃描完成！")
        if not hits:
            st.warning("當前盤勢下，未發現符合『多頭爆量』條件的個股。")
        else:
            st.balloons()
            st.write(f"📊 總計發現 {len(hits)} 隻符合條件標的")

with t4:
    st.subheader("🔍 個股詳細分析")
    s_input = st.text_input("輸入代碼 (例如: 0700.HK)", "0700.HK").upper()
    if st.button("查看圖表"):
        with st.spinner("載入中..."):
            df = get_stock_data(s_input)
            if not df.empty:
                st.write(f"### {s_input} 歷史走勢")
                show_chart(s_input, df)
            else:
                st.error("找不到該股票數據，請確認代碼格式 (例如 0700.HK)")
