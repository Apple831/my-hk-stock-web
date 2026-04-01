import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import os

st.set_page_config(page_title="港股狙擊手 V3 - 宏觀修復版", layout="wide")

# --- 1. 名單讀取 ---
def load_stocks():
    file_path = 'stocks.txt'
    default_stocks = ["0700.HK", "3690.HK", "9988.HK", "1810.HK", "1211.HK"]
    if os.path.exists(file_path):
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                stocks = [line.split('#')[0].strip().replace('"', '').replace("'", "") for line in f if line.strip()]
            return [s for s in stocks if s.endswith('.HK')]
        except:
            return default_stocks
    return default_stocks

TARGET_STOCKS = load_stocks()

# --- 2. 工具函數 ---
# 🌟 新增：專門處理 yfinance 新版雙層標籤的下載函數
def get_stock_data(ticker, period="6mo"):
    try:
        df = yf.download(ticker, period=period, interval="1d", progress=False)
        if df.empty:
            return df
        # 關鍵修復：判斷如果是雙層標籤 (MultiIndex)，就將其「壓平」提取第一層
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        return df
    except Exception as e:
        st.error(f"下載 {ticker} 數據時出錯: {e}")
        return pd.DataFrame()

def calculate_rsi(series, period=14):
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def show_chart(ticker, df, height=700):
    fig = make_subplots(rows=3, cols=1, shared_xaxes=True, 
                        vertical_spacing=0.03, row_heights=[0.6, 0.2, 0.2])
    fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name='K線'), row=1, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df['Close'].rolling(20).mean(), name='20MA', line=dict(color='orange', width=2)), row=1, col=1)
    
    colors = ['red' if r['Close'] >= r['Open'] else 'green' for _, r in df.iterrows()]
    fig.add_trace(go.Bar(x=df.index, y=df['Volume'], marker_color=colors), row=2, col=1)
    
    df['RSI'] = calculate_rsi(df['Close'])
    fig.add_trace(go.Scatter(x=df.index, y=df['RSI'], line=dict(color='purple')), row=3, col=1)
    fig.add_hline(y=70, line_dash="dot", line_color="red", row=3, col=1)
    fig.add_hline(y=30, line_dash="dot", line_color="green", row=3, col=1)

    fig.update_layout(height=height, showlegend=False, xaxis_rangeslider_visible=False, margin=dict(t=30, b=10))
    st.plotly_chart(fig, use_container_width=True)

# --- 3. 網頁佈局 ---
st.title("🏹 港股狙擊手 V3 - 專業宏觀儀表板")
tab1, tab2, tab3 = st.tabs(["🌍 大市導航", "🎯 策略掃描", "🔍 個股分析"])

# ================= 頁籤 1：大市導航 =================
with tab1:
    st.subheader("📊 全球市場情緒")
    col1, col2 = st.columns(2)
    
    with st.spinner("正在獲取大盤數據..."):
        # 👉 將 yf.download 替換為我們的 get_stock_data 函數
        hsi = get_stock_data("^HSI", period="6mo")
        vix = get_stock_data("^VIX", period="6mo")

        if not hsi.empty and not vix.empty:
            hsi_curr = float(hsi['Close'].iloc[-1])
            hsi_prev = float(hsi['Close'].iloc[-2])
            hsi_change = ((hsi_curr - hsi_prev) / hsi_prev) * 100
            hsi_ma50 = hsi['Close'].rolling(50).mean().iloc[-1]

            vix_curr = float(vix['Close'].iloc[-1])
            vix_prev = float(vix['Close'].iloc[-2])
            
            with col1:
                st.metric("🇭🇰 恆生指數 (^HSI)", f"{hsi_curr:.2f}", f"{hsi_change:.2f}%")
                status = "🟢 多頭排列" if hsi_curr > hsi_ma50 else "🔴 趨勢偏弱"
                st.write(f"大盤狀態：**{status}** (相對於 50MA)")
                
                fig_hsi = go.Figure()
                fig_hsi.add_trace(go.Scatter(x=hsi.index, y=hsi['Close'], name='恆指', line=dict(color='blue')))
                fig_hsi.update_layout(height=300, title="恆指半年走勢", margin=dict(l=0,r=0,t=30,b=0))
                st.plotly_chart(fig_hsi, use_container_width=True)

            with col2:
                vix_delta = vix_curr - vix_prev
                st.metric("🇺🇸 恐慌指數 (^VIX)", f"{vix_curr:.2f}", f"{vix_delta:.2f}", delta_color="inverse")
                vix_status = "😨 市場恐慌" if vix_curr > 25 else ("😊 市場樂觀" if vix_curr < 15 else "😐 情緒中性")
                st.write(f"恐慌程度：**{vix_status}**")
                
                fig_vix = go.Figure()
                fig_vix.add_trace(go.Scatter(x=vix.index, y=vix['Close'], name='VIX', line=dict(color='red')))
                fig_vix.update_layout(height=300, title="VIX 走勢 (越高越危險)", margin=dict(l=0,r=0,t=30,b=0))
                st.plotly_chart(fig_vix, use_container_width=True)
        else:
            st.error("無法取得恆指或 VIX 數據，請檢查網路連線。")

# ================= 頁籤 2：策略掃描 =================
with tab2:
    st.info(f"掃描策略：雙均線之上 + 量比 > 1.5 + RSI 50~72。目前監控：{len(TARGET_STOCKS)} 隻")
    if st.button('🔥 開始掃描', use_container_width=True):
        progress = st.progress(0)
        hits = []
        for i, s in enumerate(TARGET_STOCKS):
            progress.progress((i + 1) / len(TARGET_STOCKS))
            # 👉 將 yf.download 替換為我們的 get_stock_data 函數
            df = get_stock_data(s, period="4mo")
            if df.empty or len(df) < 30: continue
            
            df['MA10'] = df['Close'].rolling(10).mean()
            df['MA20'] = df['Close'].rolling(20).mean()
            df['RSI'] = calculate_rsi(df['Close'])
            
            curr = df.iloc[-1]
            vol_ratio = float(curr['Volume']) / float(df['Volume'].tail(5).mean())
            
            if curr['Close'] > curr['MA10'] and curr['Close'] > curr['MA20'] and vol_ratio >= 1.5 and 50 <= curr['RSI'] <= 72:
                hits.append({"代碼": s, "現價": round(float(curr['Close']), 2), "量比": round(float(vol_ratio), 2), "RSI": round(float(curr['RSI']), 1)})
                st.success(f"🎯 發現目標：{s}")
                show_chart(s, df, height=500)
                
        if hits:
            st.subheader("📋 今日清單")
            st.dataframe(pd.DataFrame(hits), use_container_width=True, hide_index=True)

# ================= 頁籤 3：個股分析 =================
with tab3:
    search = st.text_input("輸入代碼 (例如 9988.HK)", "0700.HK").upper()
    if st.button("查看數據", key="search_btn"):
        with st.spinner(f"正在分析 {search}..."):
            # 👉 將 yf.download 替換為我們的 get_stock_data 函數
            df_s = get_stock_data(search, period="6mo")
            if not df_s.empty:
                show_chart(search, df_s)
            else:
                st.error("找不到該股票數據。")
