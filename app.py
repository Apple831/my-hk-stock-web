import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import os

st.set_page_config(page_title="港股狙擊手 V5 - 相對強度版", layout="wide")

# --- 1. 名單讀取 ---
def load_stocks():
    file_path = 'stocks.txt'
    default_stocks = ["0700.HK", "3690.HK", "9988.HK", "1810.HK", "1211.HK"]
    if os.path.exists(file_path):
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                stocks = [line.split('#')[0].strip().replace('"', '').replace("'", "") for line in f if line.strip()]
            valid_stocks = [s for s in stocks if s.endswith('.HK')]
            return valid_stocks if valid_stocks else default_stocks
        except:
            return default_stocks
    return default_stocks

TARGET_STOCKS = load_stocks()

# --- 2. 工具函數 ---
def get_stock_data(ticker, period="6mo"):
    try:
        df = yf.Ticker(ticker).history(period=period)
        if df.empty: return pd.DataFrame()
        if df.index.tz is not None:
            df.index = df.index.tz_localize(None)
        return df
    except:
        return pd.DataFrame()

def calculate_rsi(series, period=14):
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def show_chart(ticker, df, height=500):
    fig = make_subplots(rows=3, cols=1, shared_xaxes=True, 
                        vertical_spacing=0.03, row_heights=[0.6, 0.2, 0.2])
    fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name='K線'), row=1, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df['Close'].rolling(20).mean(), name='20MA', line=dict(color='orange', width=2)), row=1, col=1)
    colors = ['red' if r['Close'] >= r['Open'] else 'green' for _, r in df.iterrows()]
    fig.add_trace(go.Bar(x=df.index, y=df['Volume'], marker_color=colors), row=2, col=1)
    df['RSI'] = calculate_rsi(df['Close'])
    fig.add_trace(go.Scatter(x=df.index, y=df['RSI'], line=dict(color='purple')), row=3, col=1)
    fig.update_layout(height=height, showlegend=False, xaxis_rangeslider_visible=False, margin=dict(t=30, b=10))
    st.plotly_chart(fig, use_container_width=True)

# --- 3. 網頁佈局 ---
st.title("🏹 港股狙擊手 V5 - 專業交易站")
tab1, tab2, tab3, tab4 = st.tabs(["🌍 大市導航", "🏆 跑贏大市", "🎯 策略掃描", "🔍 個股分析"])

# ================= 頁籤 1：大市導航 =================
with tab1:
    st.subheader("📊 全球市場情緒")
    col1, col2 = st.columns(2)
    with st.spinner("獲取數據中..."):
        hsi = get_stock_data("^HSI", period="6mo")
        vix = get_stock_data("^VIX", period="6mo")
        if not hsi.empty and not vix.empty:
            hsi_curr = float(hsi['Close'].iloc[-1])
            hsi_prev = float(hsi['Close'].iloc[-2])
            hsi_change = ((hsi_curr - hsi_prev) / hsi_prev) * 100
            with col1:
                st.metric("🇭🇰 恆生指數 (^HSI)", f"{hsi_curr:.2f}", f"{hsi_change:.2f}%")
                fig_hsi = go.Figure(go.Scatter(x=hsi.index, y=hsi['Close'], line=dict(color='blue')))
                fig_hsi.update_layout(height=300, margin=dict(l=0,r=0,t=0,b=0))
                st.plotly_chart(fig_hsi, use_container_width=True)
            with col2:
                vix_curr = float(vix['Close'].iloc[-1])
                st.metric("🇺🇸 恐慌指數 (^VIX)", f"{vix_curr:.2f}", f"{vix_curr-float(vix['Close'].iloc[-2]):.2f}", delta_color="inverse")
                fig_vix = go.Figure(go.Scatter(x=vix.index, y=vix['Close'], line=dict(color='red')))
                fig_vix.update_layout(height=300, margin=dict(l=0,r=0,t=0,b=0))
                st.plotly_chart(fig_vix, use_container_width=True)

# ================= 頁籤 2：跑贏大市 =================
with tab2:
    st.subheader("🥇 個股 vs 恆指 報酬率競賽")
    timeframe = st.selectbox("選擇比較時間範圍", ["1個月", "3個月", "6個月"], index=1)
    tf_map = {"1個月": "1mo", "3個月": "3mo", "6個月": "6mo"}
    
    if st.button("🚀 開始計算相對強度"):
        progress = st.progress(0)
        comparison_list = []
        
        # 先抓恆指的報酬率
        hsi_bench = get_stock_data("^HSI", period=tf_map[timeframe])
        if not hsi_bench.empty:
            hsi_start = float(hsi_bench['Close'].iloc[0])
            hsi_end = float(hsi_bench['Close'].iloc[-1])
            hsi_perf = ((hsi_end - hsi_start) / hsi_start) * 100
            
            st.info(f"期間內恆生指數報酬率：**{hsi_perf:.2f}%**")
            
            for i, s in enumerate(TARGET_STOCKS):
                progress.progress((i + 1) / len(TARGET_STOCKS))
                df = get_stock_data(s, period=tf_map[timeframe])
                if not df.empty and len(df) > 2:
                    s_start = float(df['Close'].iloc[0])
                    s_end = float(df['Close'].iloc[-1])
                    s_perf = ((s_end - s_start) / s_start) * 100
                    comparison_list.append({
                        "股票代碼": s,
                        "個股報酬率(%)": round(s_perf, 2),
                        "相較大盤(Alpha)": round(s_perf - hsi_perf, 2)
                    })
            
            if comparison_list:
                res_df = pd.DataFrame(comparison_list).sort_values(by="相較大盤(Alpha)", ascending=False)
                
                # 顯示表格
                st.write("---")
                def highlight_alpha(val):
                    color = 'red' if val > 0 else 'green'
                    return f'color: {color}; font-weight: bold'
                st.dataframe(res_df.style.applymap(highlight_alpha, subset=['相較大盤(Alpha)']), use_container_width=True, hide_index=True)
                
                # 繪製長條圖
                fig_comp = go.Figure()
                fig_comp.add_trace(go.Bar(
                    x=res_df["股票代碼"], 
                    y=res_df["相較_大盤(Alpha)"] if "相較_大盤(Alpha)" in res_df else res_df["相較大盤(Alpha)"],
                    marker_color=['red' if x > 0 else 'green' for x in res_df["相較大盤(Alpha)"]]
                ))
                fig_comp.update_layout(title=f"跑贏大市排名 (Alpha 值)", ylabel="領先/落後 %")
                st.plotly_chart(fig_comp, use_container_width=True)

# ================= 頁籤 3：策略掃描 =================
with tab3:
    st.info("掃描策略：雙均線之上 + 量比 > 1.5 + RSI 50~72")
    if st.button('🔥 開始狙擊掃描', use_container_width=True):
        progress = st.progress(0)
        hits = []
        for i, s in enumerate(TARGET_STOCKS):
            progress.progress((i + 1) / len(TARGET_STOCKS))
            df = get_stock_data(s, period="4mo")
            if df.empty or len(df) < 30: continue
            df['MA10'] = df['Close'].rolling(10).mean()
            df['MA20'] = df['Close'].rolling(20).mean()
            df['RSI'] = calculate_rsi(df['Close'])
            curr = df.iloc[-1]
            avg_vol = df['Volume'].tail(5).mean()
            vol_ratio = float(curr['Volume']) / float(avg_vol) if avg_vol > 0 else 0
            if curr['Close'] > curr['MA10'] and curr['Close'] > curr['MA20'] and vol_ratio >= 1.5 and 50 <= curr['RSI'] <= 72:
                hits.append({"代碼": s, "現價": round(float(curr['Close']), 2), "量比": round(float(vol_ratio), 2), "RSI": round(float(curr['RSI']), 1)})
                st.success(f"🎯 發現強勢股：{s}")
                show_chart(s, df)
        if hits: st.table(pd.DataFrame(hits))

# ================= 頁籤 4：個股分析 =================
with tab4:
    search = st.text_input("輸入代碼 (例如 9988.HK)", "0700.HK").upper()
    if st.button("查看數據"):
        df_s = get_stock_data(search, period="6mo")
        if not df_s.empty: show_chart(search, df_s)
