import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import os
import time

st.set_page_config(page_title="港股狙擊手 V8.9.1", layout="wide")

# --- 1. 核心數據抓取 ---
def get_stock_data(ticker, period="1y"): 
    try:
        # 指數代碼備援邏輯
        if ticker == "^HSTECH":
            df = yf.download("^HSTECH", period=period, progress=False)
            if df.empty: df = yf.download("3032.HK", period=period, progress=False)
        elif ticker == "^HSI":
            df = yf.download("^HSI", period=period, progress=False)
            if df.empty: df = yf.download("2800.HK", period=period, progress=False)
        else:
            df = yf.download(ticker, period=period, progress=False)
            
        if df.empty: return pd.DataFrame()
        
        # 統一處理 MultiIndex 問題 (新版 yfinance 常見)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
            
        df.index = pd.to_datetime(df.index).tz_localize(None)
        return df.dropna(subset=['Close'])
    except:
        return pd.DataFrame()

# --- 2. 指標計算函數 ---
def calculate_indicators(df):
    # 均線
    df['MA5'] = df['Close'].rolling(5).mean()
    df['MA10'] = df['Close'].rolling(10).mean()
    df['MA20'] = df['Close'].rolling(20).mean()
    df['MA60'] = df['Close'].rolling(60).mean()
    
    # MACD
    exp1 = df['Close'].ewm(span=12, adjust=False).mean()
    exp2 = df['Close'].ewm(span=26, adjust=False).mean()
    df['DIF'] = exp1 - exp2
    df['DEA'] = df['DIF'].ewm(span=9, adjust=False).mean()
    df['MACD_Hist'] = df['DIF'] - df['DEA']
    
    # KDJ
    low_list = df['Low'].rolling(9).min()
    high_list = df['High'].rolling(9).max()
    rsv = (df['Close'] - low_list) / (high_list - low_list) * 100
    df['K'] = rsv.ewm(com=2, adjust=False).mean()
    df['D'] = df['K'].ewm(com=2, adjust=False).mean()
    df['J'] = 3 * df['K'] - 2 * df['D']
    
    return df

# --- 3. 繪圖 (綠漲紅跌) ---
def show_chart(ticker, df):
    fig = make_subplots(rows=4, cols=1, shared_xaxes=True, vertical_spacing=0.03, row_heights=[0.4, 0.15, 0.2, 0.2])
    
    fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], 
        increasing_line_color='#26a69a', decreasing_line_color='#ef5350', name='K線'), row=1, col=1)
    
    for ma, col in zip(['MA5', 'MA20', 'MA60'], ['gray', 'purple', 'orange']):
        fig.add_trace(go.Scatter(x=df.index, y=df[ma], name=ma, line=dict(width=1)), row=1, col=1)
    
    # 成交量
    colors = ['#26a69a' if c >= o else '#ef5350' for c, o in zip(df['Close'], df['Open'])]
    fig.add_trace(go.Bar(x=df.index, y=df['Volume'], marker_color=colors, name='成交量'), row=2, col=1)
    
    # MACD & KDJ (略，保持 V8.9 邏輯)
    h_colors = ['#26a69a' if v >= 0 else '#ef5350' for v in df['MACD_Hist']]
    fig.add_trace(go.Bar(x=df.index, y=df['MACD_Hist'], marker_color=h_colors), row=3, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df['J'], line=dict(color='#ab47bc'), name='J'), row=4, col=1)
    
    fig.update_layout(height=700, showlegend=False, xaxis_rangeslider_visible=False, margin=dict(t=10, b=10))
    st.plotly_chart(fig, use_container_width=True)

# --- 4. 主程式 UI ---
st.title("🏹 港股狙擊手 V8.9.1")

def load_stocks():
    if not os.path.exists('stocks.txt'): return ["0700.HK", "9988.HK", "3690.HK"]
    with open('stocks.txt', 'r') as f:
        return [line.split('#')[0].strip() for line in f if ".HK" in line]

STOCKS = load_stocks()
tabs = st.tabs(["🌍 指數", "🏆 跑贏大市", "🟢 買入掃描", "🔴 賣出掃描", "🔍 分析"])

with tabs[2]: # 買入掃描
    st.subheader("🟢 買入訊號庫")
    col_a, col_b = st.columns(2)
    b1 = col_a.checkbox("📈 價格 > 60MA (多頭趨勢)")
    b2 = col_a.checkbox("🔥 均線多頭 (5>10>20)")
    b3 = col_a.checkbox("🚀 20日高點突破 + 爆量")
    b4 = col_b.checkbox("💥 MACD 剛翻紅 (金叉)")
    b5 = col_b.checkbox("📉 KDJ 超賣 (J < 10)")
    b6 = col_b.checkbox("🪃 站上 20MA (轉強)")
    
    if st.button("🟢 開始掃描買點"):
        results = []
        hits_dfs = {}
        pbar = st.progress(0)
        status = st.empty()
        
        for i, s in enumerate(STOCKS):
            pbar.progress((i+1)/len(STOCKS))
            status.text(f"正在分析 {s}...")
            df = get_stock_data(s)
            if df.empty or len(df) < 60: continue
            
            df = calculate_indicators(df)
            c, p = df.iloc[-1], df.iloc[-2]
            vol_avg = df['Volume'].iloc[-21:-1].mean()
            
            # 條件過濾邏輯
            checks = []
            if b1: checks.append(c['Close'] > c['MA60'])
            if b2: checks.append(c['MA5'] > c['MA10'] > c['MA20'])
            if b3: checks.append(c['Close'] > df['High'].iloc[-21:-1].max() and c['Volume'] > vol_avg*1.5)
            if b4: checks.append(c['MACD_Hist'] > 0 and p['MACD_Hist'] <= 0)
            if b5: checks.append(c['J'] < 10)
            if b6: checks.append(c['Close'] > c['MA20'] and p['Close'] <= p['MA20'])
            
            if checks and all(checks):
                pct = ((c['Close']-p['Close'])/p['Close'])*100
                results.append({"代碼": s, "現價": round(c['Close'],2), "漲跌%": round(pct,2), "J值": round(c['J'],1)})
                hits_dfs[s] = df
        
        status.empty()
        if results:
            st.success(f"發現 {len(results)} 個標的")
            st.dataframe(pd.DataFrame(results).style.map(lambda x: 'color: #26a69a' if x > 0 else 'color: #ef5350', subset=['漲跌%']), use_container_width=True)
            for s in hits_dfs:
                st.write(f"### 🎯 {s}")
                show_chart(s, hits_dfs[s])
        else:
            st.warning("⚠️ 沒有符合條件的股票。請嘗試只勾選一個條件（例如：MACD 翻紅）來測試連線是否正常。")

with tabs[3]: # 賣出掃描
    st.subheader("🔴 賣出訊號庫")
    col_c, col_d = st.columns(2)
    s1 = col_c.checkbox("📉 價格 < 60MA (空頭趨勢)")
    s4 = col_d.checkbox("💔 MACD 剛翻綠 (死叉)")
    s5 = col_d.checkbox("📈 KDJ 超買 (J > 90)")
    
    if st.button("🔴 開始掃描賣點"):
        results = []
        hits_dfs = {}
        for s in STOCKS:
            df = get_stock_data(s)
            if df.empty or len(df) < 60: continue
            df = calculate_indicators(df)
            c, p = df.iloc[-1], df.iloc[-2]
            
            checks = []
            if s1: checks.append(c['Close'] < c['MA60'])
            if s4: checks.append(c['MACD_Hist'] < 0 and p['MACD_Hist'] >= 0)
            if s5: checks.append(c['J'] > 90)
            
            if checks and all(checks):
                pct = ((c['Close']-p['Close'])/p['Close'])*100
                results.append({"代碼": s, "現價": round(c['Close'],2), "漲跌%": round(pct,2), "J值": round(c['J'],1)})
                hits_dfs[s] = df
        
        if results:
            st.error(f"發現 {len(results)} 個標的")
            st.table(pd.DataFrame(results))
            for s in hits_dfs: show_chart(s, hits_dfs[s])
        else:
            st.warning("目前沒有符合賣出條件的股票。")
