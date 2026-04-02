import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import os
import time

st.set_page_config(page_title="港股狙擊手 V8.8", layout="wide")

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

# --- 2. 數據抓取 (恆科指優先邏輯) ---
def get_stock_data(ticker, period="6mo"):
    try:
        if ticker == "^HSTECH":
            # 優先嘗試原版指數
            df = yf.Ticker("^HSTECH").history(period=period)
            if df.empty or len(df) < 2:
                # 真的不行才換 ETF
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

# --- 3. 技術指標計算 ---
def calculate_macd(df, fast=12, slow=26, signal=9):
    exp1 = df['Close'].ewm(span=fast, adjust=False).mean()
    exp2 = df['Close'].ewm(span=slow, adjust=False).mean()
    macd = exp1 - exp2
    sig = macd.ewm(span=signal, adjust=False).mean()
    hist = macd - sig
    return macd, sig, hist

def calculate_kdj(df, n=9, m1=3, m2=3):
    low_list = df['Low'].rolling(n, min_periods=1).min()
    high_list = df['High'].rolling(n, min_periods=1).max()
    rsv = (df['Close'] - low_list) / (high_list - low_list) * 100
    k = rsv.ewm(com=m1-1, adjust=False).mean()
    d = k.ewm(com=m2-1, adjust=False).mean()
    j = 3 * k - 2 * d
    return k, d, j

# --- 4. 繪圖函數 (新增 KDJ，4 窗格，綠漲紅跌) ---
def show_chart(ticker, df):
    fig = make_subplots(rows=4, cols=1, shared_xaxes=True, vertical_spacing=0.03, row_heights=[0.45, 0.15, 0.2, 0.2])
    
    # 1. K線與均線 (綠賺紅虧)
    fig.add_trace(go.Candlestick(
        x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], 
        increasing_line_color='#26a69a', decreasing_line_color='#ef5350', name='K線'
    ), row=1, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df['Close'].rolling(5).mean(), name='5MA', line=dict(color='gray', width=1)), row=1, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df['Close'].rolling(20).mean(), name='20MA', line=dict(color='purple', width=1)), row=1, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df['Close'].rolling(60).mean(), name='60MA', line=dict(color='orange', width=2)), row=1, col=1)
    
    # 2. 成交量
    vol_colors = ['#26a69a' if df['Close'].iloc[i] >= df['Open'].iloc[i] else '#ef5350' for i in range(len(df))]
    fig.add_trace(go.Bar(x=df.index, y=df['Volume'], name='成交量', marker_color=vol_colors), row=2, col=1)
    
    # 3. MACD
    macd, sig, hist = calculate_macd(df)
    hist_colors = ['#26a69a' if val >= 0 else '#ef5350' for val in hist]
    fig.add_trace(go.Bar(x=df.index, y=hist, name='MACD Hist', marker_color=hist_colors), row=3, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=macd, name='DIF', line=dict(color='#1f77b4')), row=3, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=sig, name='DEA', line=dict(color='#ff7f0e')), row=3, col=1)
    
    # 4. KDJ
    k, d, j = calculate_kdj(df)
    fig.add_trace(go.Scatter(x=df.index, y=k, name='K', line=dict(color='black', width=1)), row=4, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=d, name='D', line=dict(color='#ff7f0e', width=1)), row=4, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=j, name='J', line=dict(color='#ab47bc', width=1.5)), row=4, col=1)
    
    # 超買超賣輔助線 (20, 80)
    fig.add_hline(y=80, line_dash="dot", line_color="red", row=4, col=1)
    fig.add_hline(y=20, line_dash="dot", line_color="green", row=4, col=1)
    
    fig.update_layout(height=800, showlegend=False, xaxis_rangeslider_visible=False, margin=dict(t=30, b=10))
    st.plotly_chart(fig, use_container_width=True)

# --- 主程式 ---
st.title("🏹 港股狙擊手 V8.8 - 專業量化版")
t1, t2, t3, t4 = st.tabs(["🌍 大市導航", "🏆 跑贏大市", "🎯 策略掃描", "🔍 個股分析"])

# --- Tab 1: 大市導航 ---
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
                    
                    # 判斷科指是否啟用了 ETF 備援
                    display_title = title
                    if title == "🚀 恆科" and curr < 1000:
                        display_title = "🚀 恆科 (3032備援)"
                        
                    st.metric(display_title, f"{curr:.2f}", f"{change:.2f}%", delta_color="normal")
                    fig = go.Figure(go.Scatter(x=df.index, y=df['Close'], line=dict(color='#1f77b4')))
                    fig.update_layout(height=180, margin=dict(l=0,r=0,t=0,b=0))
                    st.plotly_chart(fig, use_container_width=True)
                else:
                    st.error(f"⚠️ {title} 連線失敗")

# --- Tab 2: 跑贏大市 (略) ---
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
                st.dataframe(res_df.style.map(lambda x: 'color: #26a69a' if x > 0 else 'color: #ef5350', subset=['贏恆指', '贏科指']), use_container_width=True)

# --- 🚀 Tab 3: 全新策略自選掃描器 (結果置頂) ---
with t3:
    st.subheader("🎯 策略兵器庫 (自選組合)")
    st.info("💡 提示：左側偏向『右側順勢/突破』，右側偏向『左側抄底/反轉』。請合理組合，全選可能找不到任何股票！")
    
    col_l, col_r = st.columns(2)
    with col_l:
        use_ma60 = st.checkbox("📈 1. 價格在季線 (60MA) 之上", value=False)
        use_align = st.checkbox("🔥 2. 短均線多頭 (5 > 10 > 20)", value=False)
        use_breakout = st.checkbox("🚀 3. 突破20日新高 + 成交量放大1.5倍", value=False)
    with col_r:
        use_macd = st.checkbox("💥 4. MACD 剛翻正 (金叉)", value=False)
        use_kdj = st.checkbox("📉 5. KDJ 超賣區 (J < 10 找底)", value=False)
        use_pattern = st.checkbox("🪃 6. 底部形態突破 (股價剛穿過20MA且距近期低點不遠)", value=False)
    
    if st.button("🔥 執行全市場狙擊"):
        if not any([use_ma60, use_align, use_macd, use_breakout, use_kdj, use_pattern]):
            st.warning("請至少勾選一個條件！")
        else:
            hits_data = [] # 存儲總表數據
            hits_dfs = {}  # 緩存圖表數據，避免重複抓取
            pbar = st.progress(0)
            status = st.empty()
            
            for i, s in enumerate(TARGET_STOCKS):
                pbar.progress((i+1)/len(TARGET_STOCKS))
                status.text(f"🔍 掃描中: {s}")
                try:
                    df = get_stock_data(s, period="6mo")
                    if df.empty or len(df) < 65: continue
                    
                    # 計算所有必要指標
                    df['MA5'] = df['Close'].rolling(5).mean()
                    df['MA10'] = df['Close'].rolling(10).mean()
                    df['MA20'] = df['Close'].rolling(20).mean()
                    df['MA60'] = df['Close'].rolling(60).mean()
                    macd, sig, hist = calculate_macd(df)
                    k, d, j = calculate_kdj(df)
                    
                    curr = df.iloc[-1]
                    
                    # 條件判定邏輯
                    c1 = (curr['Close'] > curr['MA60']) if use_ma60 else True
                    c2 = (curr['MA5'] > curr['MA10'] > curr['MA20']) if use_align else True
                    c3 = (hist.iloc[-1] > 0 and hist.iloc[-2] <= 0) if use_macd else True
                    
                    # 突破前高 + 爆量 (條件4)
                    recent_high = df['High'].iloc[-21:-1].max() # 過去20天最高(不含今天)
                    vol_avg = df['Volume'].iloc[-21:-1].mean()
                    c4 = (curr['Close'] > recent_high and curr['Volume'] > vol_avg * 1.5) if use_breakout else True
                    
                    # KDJ 超賣 (條件5)
                    c5 = (j.iloc[-1] < 10) if use_kdj else True
                    
                    # 底部形態突破 (條件6): 股價剛穿上20MA，且過去20天內有創下近期低點
                    recent_low = df['Low'].tail(30).min()
                    c6 = (curr['Close'] > curr['MA20'] and df['Close'].iloc[-2] <= df['MA20'].iloc[-2] and df['Low'].iloc[-20:].min() == recent_low) if use_pattern else True
                    
                    if c1 and c2 and c3 and c4 and c5 and c6:
                        hits_data.append({
                            "代碼": s, 
                            "現價": round(curr['Close'], 2), 
                            "J值": round(j.iloc[-1], 2),
                            "量比": round(curr['Volume']/vol_avg, 2) if vol_avg > 0 else 0
                        })
                        hits_dfs[s] = df # 存起來等一下畫圖
                    
                except: continue
                
            status.text("✅ 掃描結束")
            pbar.empty()
            
            # --- 結果先置頂顯示 ---
            if not hits_data: 
                st.warning("沒有股票符合你設定的嚴格條件。試著減少互斥的條件（例如不要同時勾選突破新高與KDJ超賣）。")
            else:
                st.success(f"🎉 發現 {len(hits_data)} 隻符合條件的標的！總覽如下：")
                st.dataframe(pd.DataFrame(hits_data), use_container_width=True)
                
                st.markdown("---")
                st.subheader("📈 符合標的技術線圖")
                # --- 再把圖表畫在下面 ---
                for item in hits_data:
                    code = item["代碼"]
                    st.write(f"### 🎯 {code}")
                    show_chart(code, hits_dfs[code])

with t4:
    s_input = st.text_input("輸入代碼", "0700.HK").upper()
    if st.button("查看"):
        df = get_stock_data(s_input)
        if not df.empty: show_chart(s_input, df)
