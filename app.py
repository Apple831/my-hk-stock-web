import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import os

st.set_page_config(page_title="港股狙擊手 V6", layout="wide")

# --- 1. 名單讀取 (強制回傳 List) ---
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
        # 使用 history 獲取單一 Ticker 資料
        dat = yf.Ticker(ticker)
        df = dat.history(period=period)
        if df.empty: return pd.DataFrame()
        
        # 強制壓平所有可能的雙層標籤
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
            
        # 確保必要的欄位都是數值型態且移除時區
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
    fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name='K'), row=1, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df['Close'].rolling(20).mean(), name='20MA', line=dict(color='orange')), row=1, col=1)
    fig.add_trace(go.Bar(x=df.index, y=df['Volume'], name='Vol'), row=2, col=1)
    df['RSI'] = calculate_rsi(df['Close'])
    fig.add_trace(go.Scatter(x=df.index, y=df['RSI'], name='RSI', line=dict(color='purple')), row=3, col=1)
    fig.update_layout(height=600, showlegend=False, xaxis_rangeslider_visible=False)
    st.plotly_chart(fig, use_container_width=True)

# --- 4. 主程式 ---
st.title("🏹 港股狙擊手 V6")
t1, t2, t3, t4 = st.tabs(["🌍 大市導航", "🏆 跑贏大市", "🎯 策略掃描", "🔍 個股分析"])

# --- Tab 1: 大市 ---
with t1:
    col1, col2 = st.columns(2)
    hsi = get_stock_data("^HSI")
    vix = get_stock_data("^VIX")
    if not hsi.empty:
        curr = float(hsi['Close'].iloc[-1])
        prev = float(hsi['Close'].iloc[-2])
        col1.metric("恆生指數", f"{curr:.2f}", f"{((curr-prev)/prev)*100:.2f}%")
    if not vix.empty:
        curr_vix = float(vix['Close'].iloc[-1])
        col2.metric("VIX 恐慌指數", f"{curr_vix:.2f}", f"{curr_vix - float(vix['Close'].iloc[-2]):.2f}", delta_color="inverse")

# --- Tab 2: 跑贏大市 (修正版本相容性) ---
with t2:
    tf = st.selectbox("範圍", ["1mo", "3mo", "6mo"], index=1)
    if st.button("🚀 開始比較"):
        hsi_df = get_stock_data("^HSI", period=tf)
        if not hsi_df.empty:
            hsi_p = (hsi_df['Close'].iloc[-1] / hsi_df['Close'].iloc[0] - 1) * 100
            st.write(f"大盤報酬率: {hsi_p:.2f}%")
            results = []
            pbar = st.progress(0)
            for i, s in enumerate(TARGET_STOCKS):
                pbar.progress((i+1)/len(TARGET_STOCKS))
                df = get_stock_data(s, period=tf)
                if not df.empty:
                    p = (df['Close'].iloc[-1] / df['Close'].iloc[0] - 1) * 100
                    results.append({"代碼": s, "報酬率(%)": round(p, 2), "Alpha": round(p - hsi_p, 2)})
            
            res_df = pd.DataFrame(results).sort_values("Alpha", ascending=False)
            # 🌟 修復核心：檢查 Pandas 版本使用 map 或 applymap
            style_func = res_df.style.map if hasattr(res_df.style, 'map') else res_df.style.applymap
            st.dataframe(style_func(lambda x: 'color:red' if x > 0 else 'color:green', subset=['Alpha']), use_container_width=True)

# --- Tab 3: 策略掃描 ---
with t3:
    if st.button("🔥 執行狙擊掃描"):
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
        if not hits: st.warning("目前無符合條件標的")

# --- Tab 4: 個股 ---
with t4:
    s_input = st.text_input("輸入代碼", "0700.HK")
    if st.button("查詢"):
        df = get_stock_data(s_input)
        if not df.empty: show_chart(s_input, df)
