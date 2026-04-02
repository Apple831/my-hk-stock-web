import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import os
import time

st.set_page_config(page_title="港股狙擊手 V8.5", layout="wide")

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

# --- 新增: MACD 計算函數 ---
def calculate_macd(df, fast=12, slow=26, signal=9):
    exp1 = df['Close'].ewm(span=fast, adjust=False).mean()
    exp2 = df['Close'].ewm(span=slow, adjust=False).mean()
    macd = exp1 - exp2
    sig = macd.ewm(span=signal, adjust=False).mean()
    hist = macd - sig
    return macd, sig, hist

# --- 3. 繪圖函數 (更新為 MACD 圖表) ---
def show_chart(ticker, df):
    fig = make_subplots(rows=3, cols=1, shared_xaxes=True, vertical_spacing=0.05, row_heights=[0.5, 0.2, 0.3])
    
    # Row 1: K線與均線
    fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name='K線'), row=1, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df['Close'].rolling(10).mean(), name='10MA', line=dict(color='blue', width=1)), row=1, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df['Close'].rolling(20).mean(), name='20MA', line=dict(color='orange', width=1.5)), row=1, col=1)
    
    # Row 2: 成交量
    fig.add_trace(go.Bar(x=df.index, y=df['Volume'], name='成交量', marker_color='#26a69a'), row=2, col=1)
    
    # Row 3: MACD
    macd, sig, hist = calculate_macd(df)
    colors = ['#26a69a' if val >= 0 else '#ef5350' for val in hist] # 柱狀圖紅綠色
    fig.add_trace(go.Bar(x=df.index, y=hist, name='MACD Hist', marker_color=colors), row=3, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=macd, name='MACD Line', line=dict(color='#1f77b4')), row=3, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=sig, name='Signal', line=dict(color='#ff7f0e')), row=3, col=1)
    
    fig.update_layout(height=650, showlegend=False, xaxis_rangeslider_visible=False, margin=dict(t=30, b=10))
    st.plotly_chart(fig, use_container_width=True)

# --- 4. 主程式 ---
st.title("🏹 港股狙擊手 V8.5")
t1, t2, t3, t4 = st.tabs(["🌍 大市導航", "🏆 跑贏大市", "🎯 策略掃描", "🔍 個股分析"])

# --- Tab 1: 大市導航 (修復排版消失問題) ---
with t1:
    st.subheader("📊 市場核心指數")
    col1, col2, col3 = st.columns(3) # 固定三個欄位
    
    with st.spinner("獲取大市數據..."):
        hsi = get_stock_data("^HSI")
        hstech = get_stock_data("^HSTECH")
        vix = get_stock_data("^VIX")
        
        with col1:
            if not hsi.empty:
                curr, prev = hsi['Close'].iloc[-1], hsi['Close'].iloc[-2]
                st.metric("🇭🇰 恆指", f"{curr:.2f}", f"{((curr-prev)/prev)*100:.2f}%")
                fig = go.Figure(go.Scatter(x=hsi.index, y=hsi['Close'], line=dict(width=2, color='#1f77b4')))
                fig.update_layout(height=200, margin=dict(l=0,r=0,t=0,b=0))
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.warning("⚠️ 恆指數據暫時缺失")

        with col2:
            if not hstech.empty:
                curr, prev = hstech['Close'].iloc[-1], hstech['Close'].iloc[-2]
                label = "🚀 恆科 (ETF 3032)" if curr < 1000 else "🚀 恆科指"
                st.metric(label, f"{curr:.2f}", f"{((curr-prev)/prev)*100:.2f}%")
                fig = go.Figure(go.Scatter(x=hstech.index, y=hstech['Close'], line=dict(width=2, color='#ff7f0e')))
                fig.update_layout(height=200, margin=dict(l=0,r=0,t=0,b=0))
                st.plotly_chart(fig, use_container_width=True)
            else:
                # 就算空值，也會顯示這個警告框把位置卡住，排版不會崩
                st.error("⚠️ 科指數據暫時無法連線")

        with col3:
            if not vix.empty:
                curr, prev = vix['Close'].iloc[-1], vix['Close'].iloc[-2]
                st.metric("🇺🇸 VIX", f"{curr:.2f}", f"{curr-prev:.2f}", delta_color="inverse")
                fig = go.Figure(go.Scatter(x=vix.index, y=vix['Close'], line=dict(width=2, color='#d62728')))
                fig.update_layout(height=200, margin=dict(l=0,r=0,t=0,b=0))
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.warning("⚠️ VIX數據暫時缺失")

# --- Tab 2: 跑贏大市 ---
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

# --- Tab 3: 全新 MACD + 均線策略 ---
with t3:
    st.subheader("🎯 策略掃描: 多頭排列 (MA) + 動能向上 (MACD)")
    st.markdown("""
    **觸發條件：**
    1. 📈 股價站在 20 日均線之上 (中期趨勢偏多)
    2. 📊 MACD 柱狀圖大於 0 (MACD 快線 > 慢線，短線動能強勢)
    """)
    st.info(f"掃描清單：共 {len(TARGET_STOCKS)} 隻個股")
    
    if st.button("🔥 執行全市場狙擊"):
        hits = []
        status_text = st.empty() 
        pbar = st.progress(0)
        
        for i, s in enumerate(TARGET_STOCKS):
            status_text.text(f"🔍 正在掃描: {s} ({i+1}/{len(TARGET_STOCKS)})")
            pbar.progress((i+1)/len(TARGET_STOCKS))
            
            try:
                df = get_stock_data(s, period="6mo")
                if df.empty or len(df) < 30: continue
                
                # 計算 MA
                df['MA20'] = df['Close'].rolling(20).mean()
                
                # 計算 MACD
                macd, sig, hist = calculate_macd(df)
                
                curr_close = df['Close'].iloc[-1]
                curr_ma20 = df['MA20'].iloc[-1]
                curr_hist = hist.iloc[-1]
                
                # 判斷邏輯：股價 > 20MA 且 MACD 柱狀體大於 0
                if curr_close > curr_ma20 and curr_hist > 0:
                    hits.append({"代碼": s, "現價": round(curr_close, 2)})
                    st.success(f"🎯 發現信號: {s}")
                    show_chart(s, df)
                
                if i % 10 == 0: time.sleep(0.5) # 防止被 Yahoo 封鎖
                
            except Exception as e:
                continue
        
        status_text.text("✅ 掃描完成！")
        if not hits:
            st.warning("當前盤勢下，未發現符合 MA + MACD 條件的個股。")
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
                st.write(f"### {s_input} 歷史走勢 (包含 MACD)")
                show_chart(s_input, df)
            else:
                st.error("找不到該股票數據，請確認代碼格式")
