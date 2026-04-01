import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import os

st.set_page_config(page_title="港股狙擊手 V2", layout="wide")

# --- 1. 名單讀取邏輯 (修正版) ---
def load_stocks():
    file_path = 'stocks.txt'
    default_stocks = ["0700.HK", "3690.HK", "9988.HK", "1810.HK", "1211.HK"]
    if os.path.exists(file_path):
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                # 排除備註、空格、空行，並移除可能誤打的字元
                stocks = [line.split('#')[0].strip().replace('"', '').replace("'", "") for line in f if line.strip()]
            return [s for s in stocks if s.endswith('.HK')] # 確保格式正確
        except:
            return default_stocks
    return default_stocks

TARGET_STOCKS = load_stocks()

# --- 2. 指標計算 ---
def calculate_rsi(series, period=14):
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

# --- 3. 繪圖 (三層結構) ---
def show_chart(ticker, df):
    fig = make_subplots(rows=3, cols=1, shared_xaxes=True, 
                        vertical_spacing=0.03, row_heights=[0.6, 0.2, 0.2])
    
    # K線、10MA(綠)、20MA(橘)
    fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name='K線'), row=1, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df['MA10'], name='10MA', line=dict(color='lightgreen', width=1)), row=1, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df['MA20'], name='20MA', line=dict(color='orange', width=2)), row=1, col=1)
    
    # 自動壓力支撐
    res, sup = df.tail(60)['High'].max(), df.tail(60)['Low'].min()
    fig.add_hline(y=res, line_dash="dash", line_color="red", row=1, col=1, annotation_text="壓")
    fig.add_hline(y=sup, line_dash="dash", line_color="green", row=1, col=1, annotation_text="支")

    # 成交量
    colors = ['red' if r['Close'] >= r['Open'] else 'green' for _, r in df.iterrows()]
    fig.add_trace(go.Bar(x=df.index, y=df['Volume'], marker_color=colors), row=2, col=1)

    # RSI
    fig.add_trace(go.Scatter(x=df.index, y=df['RSI'], line=dict(color='purple')), row=3, col=1)
    fig.add_hline(y=70, line_dash="dot", line_color="red", row=3, col=1)
    fig.add_hline(y=30, line_dash="dot", line_color="green", row=3, col=1)

    fig.update_layout(height=750, showlegend=False, xaxis_rangeslider_visible=False)
    st.plotly_chart(fig, use_container_width=True)

# --- 4. 網頁 UI ---
st.title("🏹 港股狙擊手 - 專業策略版")
tab1, tab2 = st.tabs(["🎯 策略掃描", "🔍 個股分析"])

with tab1:
    st.write(f"🔍 監控中股票：{len(TARGET_STOCKS)} 隻")
    if st.button('🔥 開始狙擊強勢股', use_container_width=True):
        progress = st.progress(0)
        hits = []
        
        for i, s in enumerate(TARGET_STOCKS):
            progress.progress((i + 1) / len(TARGET_STOCKS))
            try:
                df = yf.download(s, period="5mo", interval="1d", multi_level_index=False, progress=False)
                if df.empty or len(df) < 60: continue
                
                # 計算指標
                df['MA10'] = df['Close'].rolling(10).mean()
                df['MA20'] = df['Close'].rolling(20).mean()
                df['RSI'] = calculate_rsi(df['Close'])
                
                curr = df.iloc[-1]
                prev = df.iloc[-2]
                avg_vol = df['Volume'].tail(5).mean()
                vol_ratio = curr['Volume'] / avg_vol
                
                # --- 港股狙擊策略條件 ---
                c1 = curr['Close'] > curr['MA10'] and curr['Close'] > curr['MA20'] # 雙均線之上
                c2 = vol_ratio >= 1.5 # 帶量爆發
                c3 = 50 <= curr['RSI'] <= 72 # 動能強但不超買
                c4 = curr['Close'] >= (curr['High'] * 0.98) # 收盤接近最高點 (強勢)

                if c1 and c2 and c3 and c4:
                    hits.append({
                        "代碼": s,
                        "現價": round(curr['Close'], 2),
                        "漲跌": f"{round(((curr['Close']-prev['Close'])/prev['Close'])*100, 2)}%",
                        "量比": round(vol_ratio, 2),
                        "RSI": round(curr['RSI'], 1)
                    })
                    st.success(f"🎯 發現目標：{s}")
                    show_chart(s, df)
            except:
                continue
        
        if hits:
            st.subheader("📋 今日狙擊清單")
            st.table(pd.DataFrame(hits))
        else:
            st.warning("市場目前較冷淡，沒有符合「狙擊策略」的標的。")

with tab2:
    search = st.text_input("輸入代碼 (例如 9988.HK)", "0700.HK").upper()
    if st.button("查看數據"):
        df_s = yf.download(search, period="5mo", interval="1d", multi_level_index=False, progress=False)
        if not df_s.empty:
            df_s['MA10'] = df_s['Close'].rolling(10).mean()
            df_s['MA20'] = df_s['Close'].rolling(20).mean()
            df_s['RSI'] = calculate_rsi(df_s['Close'])
            show_chart(search, df_s)
