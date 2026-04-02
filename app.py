import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import os
import time
import requests
from datetime import datetime, timedelta

st.set_page_config(page_title="港股狙擊手 V9.0", layout="wide")

# --- 1. 核心數據抓取 (強化版) ---
def get_stock_data(ticker, period="1y"): # 增加到1年確保MA60穩定
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36'
    }
    try:
        # 使用 Session 保持連線
        with requests.Session() as s:
            s.headers.update(headers)
            stock = yf.Ticker(ticker, session=s)
            df = stock.history(period=period, interval="1d")
            
        if df.empty:
            # 如果是指數，嘗試 ETF 備援
            if ticker == "^HSTECH": return get_stock_data("3032.HK", period)
            if ticker == "^HSI": return get_stock_data("2800.HK", period)
            return pd.DataFrame()
            
        # 處理 MultiIndex 欄位
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
            
        df.index = pd.to_datetime(df.index).tz_localize(None)
        return df.dropna(subset=['Close'])
    except Exception as e:
        return pd.DataFrame()

# --- 2. 指標計算 ---
def calculate_macd(df):
    exp1 = df['Close'].ewm(span=12, adjust=False).mean()
    exp2 = df['Close'].ewm(span=26, adjust=False).mean()
    macd = exp1 - exp2
    sig = macd.ewm(span=9, adjust=False).mean()
    hist = macd - sig
    return macd, sig, hist

def calculate_kdj(df):
    low_list = df['Low'].rolling(9).min()
    high_list = df['High'].rolling(9).max()
    rsv = (df['Close'] - low_list) / (high_list - low_list) * 100
    k = rsv.ewm(com=2, adjust=False).mean()
    d = k.ewm(com=2, adjust=False).mean()
    j = 3 * k - 2 * d
    return k, d, j

# --- 3. 繪圖函數 (顏色：綠漲紅跌) ---
def show_chart(ticker, df):
    fig = make_subplots(rows=4, cols=1, shared_xaxes=True, vertical_spacing=0.03, row_heights=[0.4, 0.15, 0.2, 0.2])
    
    # K線
    fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], 
        increasing_line_color='#26a69a', decreasing_line_color='#ef5350', name='K線'), row=1, col=1)
    
    # 均線
    for ma, color in zip([5, 20, 60], ['gray', 'purple', 'orange']):
        fig.add_trace(go.Scatter(x=df.index, y=df['Close'].rolling(ma).mean(), name=f'{ma}MA', line=dict(width=1.5, color=color)), row=1, col=1)
    
    # 成交量
    colors = ['#26a69a' if c >= o else '#ef5350' for c, o in zip(df['Close'], df['Open'])]
    fig.add_trace(go.Bar(x=df.index, y=df['Volume'], marker_color=colors, name='成交量'), row=2, col=1)
    
    # MACD
    macd, sig, hist = calculate_macd(df)
    h_colors = ['#26a69a' if v >= 0 else '#ef5350' for v in hist]
    fig.add_trace(go.Bar(x=df.index, y=hist, marker_color=h_colors, name='MACD Hist'), row=3, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=macd, line=dict(color='#1f77b4'), name='DIF'), row=3, col=1)
    
    # KDJ
    k, d, j = calculate_kdj(df)
    fig.add_trace(go.Scatter(x=df.index, y=j, line=dict(color='#ab47bc'), name='J'), row=4, col=1)
    fig.add_hline(y=80, line_dash="dot", line_color="red", row=4, col=1)
    fig.add_hline(y=20, line_dash="dot", line_color="green", row=4, col=1)

    fig.update_layout(height=800, showlegend=False, xaxis_rangeslider_visible=False, margin=dict(t=10, b=10))
    st.plotly_chart(fig, use_container_width=True)

# --- 4. 主介面 ---
st.title("🏹 港股狙擊手 V9.0")

# 讀取股票清單
def load_stocks():
    if not os.path.exists('stocks.txt'): return ["0700.HK", "9988.HK"]
    with open('stocks.txt', 'r') as f:
        return [line.split('#')[0].strip() for line in f if ".HK" in line]

STOCKS = load_stocks()

tabs = st.tabs(["🌍 指數", "🟢 買入掃描", "🔴 賣出掃描", "🔍 分析"])

with tabs[0]:
    cols = st.columns(3)
    indices = [("^HSI", "恆生指數"), ("^HSTECH", "恆生科技"), ("^VIX", "美股波動")]
    for col, (sym, name) in zip(cols, indices):
        df = get_stock_data(sym, "6mo")
        if not df.empty:
            curr, prev = df['Close'].iloc[-1], df['Close'].iloc[-2]
            col.metric(name, f"{curr:.2f}", f"{((curr-prev)/prev)*100:.2f}%")
        else:
            col.error(f"{name} 獲取失敗")

# --- 掃描邏輯引擎 ---
def run_scanner(mode="buy"):
    st.write(f"### ⚙️ 正在根據設定掃描 {len(STOCKS)} 隻股票...")
    results = []
    progress = st.progress(0)
    status_msg = st.empty()
    
    # 建立一個容器存放圖表，避免刷新時閃爍
    chart_container = st.container()
    
    for i, s in enumerate(STOCKS):
        progress.progress((i+1)/len(STOCKS))
        status_msg.text(f"正在檢查: {s}")
        
        df = get_stock_data(s)
        if df.empty or len(df) < 60:
            st.warning(f"⚠️ {s}: 數據獲取失敗或數據不足 (需60天資料)")
            continue
            
        # 計算指標
        df['MA5'] = df['Close'].rolling(5).mean()
        df['MA10'] = df['Close'].rolling(10).mean()
        df['MA20'] = df['Close'].rolling(20).mean()
        df['MA60'] = df['Close'].rolling(60).mean()
        macd, sig, hist = calculate_macd(df)
        k, d, j = calculate_kdj(df)
        
        c = df.iloc[-1]
        p = df.iloc[-2]
        vol_avg = df['Volume'].tail(20).mean()
        
        is_hit = False
        if mode == "buy":
            # 買入條件邏輯 (b1-b6 為外部 checkbox 變數)
            conds = []
            if b1: conds.append(c['Close'] > c['MA60'])
            if b2: conds.append(c['MA5'] > c['MA10'] > c['MA20'])
            if b3: conds.append(c['Close'] > df['High'].iloc[-21:-1].max() and c['Volume'] > vol_avg*1.5)
            if b4: conds.append(hist.iloc[-1] > 0 and hist.iloc[-2] <= 0)
            if b5: conds.append(j.iloc[-1] < 10)
            if b6: conds.append(c['Close'] > c['MA20'] and p['Close'] <= p['MA20'])
            if conds and all(conds): is_hit = True
        else:
            # 賣出條件邏輯
            conds = []
            if s1: conds.append(c['Close'] < c['MA60'])
            if s2: conds.append(c['MA5'] < c['MA10'] < c['MA20'])
            if s3: conds.append(c['Close'] < df['Low'].iloc[-21:-1].min() and c['Volume'] > vol_avg*1.5)
            if s4: conds.append(hist.iloc[-1] < 0 and hist.iloc[-2] >= 0)
            if s5: conds.append(j.iloc[-1] > 90)
            if s6: conds.append(c['Close'] < c['MA20'] and p['Close'] >= p['MA20'])
            if conds and all(conds): is_hit = True
            
        if is_hit:
            change = ((c['Close']-p['Close'])/p['Close'])*100
            results.append({"代碼": s, "現價": round(c['Close'],2), "漲跌%": round(change,2), "成交量": int(c['Volume'])})
            with chart_container:
                st.success(f"🎯 發現信號: {s}")
                show_chart(s, df)
        
        # 避免請求過快
        time.sleep(0.2)
        
    status_msg.success(f"✅ 掃描完成，共發現 {len(results)} 個標的")
    if results:
        st.subheader("📋 掃描結果總覽")
        st.table(pd.DataFrame(results))

with tabs[1]:
    st.subheader("🟢 買入條件")
    b1 = st.checkbox("價格 > 60MA (季線支撐)")
    b2 = st.checkbox("均線多頭 (5>10>20)")
    b3 = st.checkbox("爆量突破 20日高點")
    b4 = st.checkbox("MACD 金叉 (柱體翻紅)")
    b5 = st.checkbox("KDJ 超賣 (J < 10)")
    b6 = st.checkbox("站上 20MA (底部反轉)")
    if st.button("開始掃描買點"):
        run_scanner("buy")

with tabs[2]:
    st.subheader("🔴 賣出條件")
    s1 = st.checkbox("價格 < 60MA (季線壓力)")
    s2 = st.checkbox("均線空頭 (5<10<20)")
    s3 = st.checkbox("爆量跌破 20日低點")
    s4 = st.checkbox("MACD 死叉 (柱體翻綠)")
    s5 = st.checkbox("KDJ 超買 (J > 90)")
    s6 = st.checkbox("跌破 20MA (高檔轉弱)")
    if st.button("開始掃描賣點"):
        run_scanner("sell")
