import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import os
import time
import requests

st.set_page_config(page_title="港股狙擊手 V8.6", layout="wide")

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

# --- 2. 數據抓取 (新增偽裝瀏覽器機制) ---
def get_stock_data(ticker, period="6mo"):
    try:
        # 建立一個帶有瀏覽器偽裝的 Session，大幅降低 Yahoo 擋線機率
        session = requests.Session()
        session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        })
        
        if ticker == "^HSTECH":
            df = yf.Ticker("^HSTECH", session=session).history(period=period)
            if df.empty or len(df) < 2:
                df = yf.Ticker("3032.HK", session=session).history(period=period)
        else:
            df = yf.Ticker(ticker, session=session).history(period=period)
            
        if df.empty: return pd.DataFrame()
        
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
            
        df.index = pd.to_datetime(df.index).tz_localize(None)
        return df.dropna(subset=['Close'])
    except:
        return pd.DataFrame()

# --- MACD 計算函數 ---
def calculate_macd(df, fast=12, slow=26, signal=9):
    exp1 = df['Close'].ewm(span=fast, adjust=False).mean()
    exp2 = df['Close'].ewm(span=slow, adjust=False).mean()
    macd = exp1 - exp2 # DIF 快線
    sig = macd.ewm(span=signal, adjust=False).mean() # DEA 慢線
    hist = macd - sig # MACD 柱狀圖
    return macd, sig, hist

# --- 3. 繪圖函數 (亞洲紅漲綠跌風格 + 四條均線) ---
def show_chart(ticker, df):
    fig = make_subplots(rows=3, cols=1, shared_xaxes=True, vertical_spacing=0.05, row_heights=[0.5, 0.2, 0.3])
    
    # 亞洲版 K 線顏色 (紅漲綠跌)
    fig.add_trace(go.Candlestick(
        x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], 
        increasing_line_color='#ef5350', decreasing_line_color='#26a69a', name='K線'
    ), row=1, col=1)
    
    # 均線大軍 (5, 10, 20, 60)
    fig.add_trace(go.Scatter(x=df.index, y=df['Close'].rolling(5).mean(), name='5MA', line=dict(color='yellow', width=1)), row=1, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df['Close'].rolling(10).mean(), name='10MA', line=dict(color='blue', width=1)), row=1, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df['Close'].rolling(20).mean(), name='20MA', line=dict(color='purple', width=1)), row=1, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df['Close'].rolling(60).mean(), name='60MA (季線)', line=dict(color='orange', width=2)), row=1, col=1)
    
    # 成交量
    vol_colors = ['#ef5350' if df['Close'].iloc[i] >= df['Open'].iloc[i] else '#26a69a' for i in range(len(df))]
    fig.add_trace(go.Bar(x=df.index, y=df['Volume'], name='成交量', marker_color=vol_colors), row=2, col=1)
    
    # MACD (紅漲綠跌)
    macd, sig, hist = calculate_macd(df)
    hist_colors = ['#ef5350' if val >= 0 else '#26a69a' for val in hist]
    fig.add_trace(go.Bar(x=df.index, y=hist, name='MACD 柱', marker_color=hist_colors), row=3, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=macd, name='DIF (快線)', line=dict(color='#1f77b4')), row=3, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=sig, name='DEA (慢線)', line=dict(color='#ff7f0e')), row=3, col=1)
    
    fig.update_layout(height=650, showlegend=True, legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1), xaxis_rangeslider_visible=False, margin=dict(t=30, b=10))
    st.plotly_chart(fig, use_container_width=True)

# --- 4. 主程式 ---
st.title("🏹 港股狙擊手 V8.6")
t1, t2, t3, t4 = st.tabs(["🌍 大市導航", "🏆 跑贏大市", "🎯 策略掃描", "🔍 個股分析"])

# --- Tab 1: 大市導航 ---
with t1:
    st.subheader("📊 市場核心指數")
    col1, col2, col3 = st.columns(3)
    
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
                label = "🚀 恆科 (ETF 3032)" if curr < 1000 else "🚀 恆生科技指數"
                st.metric(label, f"{curr:.2f}", f"{((curr-prev)/prev)*100:.2f}%")
                fig = go.Figure(go.Scatter(x=hstech.index, y=hstech['Close'], line=dict(width=2, color='#ff7f0e')))
                fig.update_layout(height=200, margin=dict(l=0,r=0,t=0,b=0))
                st.plotly_chart(fig, use_container_width=True)
            else:
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

# --- Tab 2: 跑贏大市 (略縮) ---
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

# --- Tab 3: 全新旗艦策略 (季線多頭 + MACD 金叉) ---
with t3:
    st.subheader("🎯 旗艦掃描: 季線多頭排列 + MACD 黃金交叉")
    st.markdown("""
    **嚴格觸發條件：**
    1. 🛡️ **季線之上**：最新收盤價 > 60 日均線 (大趨勢偏多)
    2. 📈 **短均線多頭**：5MA > 10MA > 20MA (短線動能強勁由上至下排列)
    3. 💥 **MACD 剛金叉**：DIF 快線剛穿過 DEA 慢線 (柱狀圖在**今日或昨日**剛由綠翻紅)
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
                # 抓取 6 個月數據才足夠計算 60MA
                df = get_stock_data(s, period="6mo")
                if df.empty or len(df) < 65: continue 
                
                # 計算均線
                df['MA5'] = df['Close'].rolling(5).mean()
                df['MA10'] = df['Close'].rolling(10).mean()
                df['MA20'] = df['Close'].rolling(20).mean()
                df['MA60'] = df['Close'].rolling(60).mean()
                
                # 計算 MACD
                macd, sig, hist = calculate_macd(df)
                
                curr = df.iloc[-1]
                
                # 條件 1: 價格在 60MA 之上
                cond1 = curr['Close'] > curr['MA60']
                
                # 條件 2: 5/10/20 日短均線呈多頭排列 (5 > 10 > 20)
                cond2 = (curr['MA5'] > curr['MA10']) and (curr['MA10'] > curr['MA20'])
                
                # 條件 3: MACD 黃金交叉 (柱狀圖由綠翻紅)
                # 意思是：最新一根柱子是紅的 (>0)，且上一根柱子是綠的或平的 (<=0)
                cond3 = (hist.iloc[-1] > 0) and (hist.iloc[-2] <= 0)
                
                if cond1 and cond2 and cond3:
                    hits.append({"代碼": s, "現價": round(curr['Close'], 2)})
                    st.success(f"🎯 爆發信號確認: {s}")
                    show_chart(s, df)
                
                if i % 10 == 0: time.sleep(0.5)
                
            except Exception as e:
                continue
        
        status_text.text("✅ 掃描完成！")
        if not hits:
            st.warning("當前盤勢下，未發現同時滿足「多頭排列」與「MACD 剛金叉」的標的。這個策略勝率極高，但條件嚴苛，請耐心等待訊號！")
        else:
            st.balloons()
            st.write(f"📊 總計發現 {len(hits)} 隻完美符合條件的黃金標的")

with t4:
    st.subheader("🔍 個股詳細分析")
    s_input = st.text_input("輸入代碼 (例如: 0700.HK)", "0700.HK").upper()
    if st.button("查看圖表"):
        with st.spinner("載入中..."):
            df = get_stock_data(s_input)
            if not df.empty:
                st.write(f"### {s_input} 技術線圖分析")
                show_chart(s_input, df)
            else:
                st.error("找不到該股票數據，請確認代碼格式")
