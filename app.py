import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import os

st.set_page_config(page_title="港股獵人 - 終極完全體", layout="wide")

def load_stocks():
    file_path = 'stocks.txt'
    if os.path.exists(file_path):
        with open(file_path, 'r', encoding='utf-8') as f:
            stocks = [line.strip() for line in f if line.strip()]
        return stocks
    else:
        # error tp
        return ["0700.HK", "9988.HK"]

TARGET_STOCKS = load_stocks()


FIXED_VOL_RATIO = 1.2

def calculate_rsi(series, period=14):
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

# 升級版：包含 K線、成交量、RSI 的三層圖表
def show_chart(ticker, df, curr_p):
    # 建立 3 個子圖，高度比例為 60%、20%、20%
    fig = make_subplots(rows=3, cols=1, shared_xaxes=True, 
                        vertical_spacing=0.03, row_heights=[0.6, 0.2, 0.2])

    # 1. K線與均線 (第一層)
    fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name='K線'), row=1, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df['MA20'], name='20MA', line=dict(color='orange', width=2)), row=1, col=1)
    
    # 壓力與支撐
    recent_60_days = df.tail(60)
    res_level = recent_60_days['High'].max()
    sup_level = recent_60_days['Low'].min()
    fig.add_hline(y=res_level, line_dash="dash", line_color="red", annotation_text=f"壓力: {res_level:.2f}", row=1, col=1)
    fig.add_hline(y=sup_level, line_dash="dash", line_color="green", annotation_text=f"支撐: {sup_level:.2f}", row=1, col=1)

    # 2. 成交量柱狀圖 (第二層)
    # 亞洲股市習慣：收盤 >= 開盤 為紅 (漲)，收盤 < 開盤 為綠 (跌)
    colors = ['red' if row['Close'] >= row['Open'] else 'green' for index, row in df.iterrows()]
    fig.add_trace(go.Bar(x=df.index, y=df['Volume'], name='成交量', marker_color=colors), row=2, col=1)

    # 3. RSI 指標 (第三層)
    fig.add_trace(go.Scatter(x=df.index, y=df['RSI'], name='RSI (14)', line=dict(color='purple', width=2)), row=3, col=1)
    fig.add_hline(y=70, line_dash="dot", line_color="red", row=3, col=1)
    fig.add_hline(y=30, line_dash="dot", line_color="green", row=3, col=1)

    # 隱藏底部的時間滑桿，確保畫面乾淨，並拉高整體圖表高度以容納三個指標
    fig.update_xaxes(rangeslider_visible=False)
    fig.update_layout(height=700, margin=dict(l=10, r=10, t=30, b=10), showlegend=False)
    
    st.plotly_chart(fig, use_container_width=True)


st.title("🏹 港股短線獵人 (終極版)")

tab1, tab2 = st.tabs(["🎯 強勢股自動掃描", "🔍 個股深度搜尋"])

# ================= 頁籤 1：自動掃描 =================
with tab1:
    st.info("自動過濾出「股價站在 20MA 之上」且「成交量放大 1.2 倍」的強勢股。")
    if st.button('🎯 立即掃描全市場強勢股', use_container_width=True):
        progress_bar = st.progress(0)
        hit_list = [] 
        all_data = {} 

        for i, s in enumerate(TARGET_STOCKS):
            progress_bar.progress((i + 1) / len(TARGET_STOCKS))
            try:
                df = yf.download(s, period="4mo", interval="1d", multi_level_index=False, progress=False)
                if df.empty or len(df) < 60: continue 
                
                df['MA20'] = df['Close'].rolling(20).mean()
                df['RSI'] = calculate_rsi(df['Close'])
                
                curr_p = float(df['Close'].iloc[-1])
                ma20 = float(df['MA20'].iloc[-1])
                curr_rsi = float(df['RSI'].iloc[-1])
                vol_ratio = float(df['Volume'].iloc[-1]) / float(df['Volume'].tail(5).mean())
                change_pct = ((curr_p - float(df['Close'].iloc[-2])) / float(df['Close'].iloc[-2])) * 100
                
                if curr_p > ma20 and vol_ratio >= FIXED_VOL_RATIO:
                    hit_list.append({
                        "股票代碼": s,
                        "現價": round(curr_p, 2),
                        "今日漲幅(%)": round(change_pct, 2),
                        "成交量比": round(vol_ratio, 2),
                        "RSI (14)": round(curr_rsi, 2)
                    })
                    all_data[s] = {"df": df, "curr_p": curr_p}
            except:
                continue

        if hit_list:
            st.balloons()
            st.header("📊 今日強勢股排行榜")
            report_df = pd.DataFrame(hit_list).sort_values(by="成交量比", ascending=False)
            st.dataframe(report_df, use_container_width=True, hide_index=True)
            
            st.write("---")
            st.header("📈 詳細技術線圖 (含成交量與 RSI)")
            for s in report_df["股票代碼"]:
                st.subheader(f"🔥 {s}")
                show_chart(s, all_data[s]["df"], all_data[s]["curr_p"])
                st.write("---")
        else:
            st.warning("目前市場沒有符合條件的強勢股。")

# ================= 頁籤 2：個股搜尋 =================
with tab2:
    st.subheader("輸入任何港股代碼，立即查看技術面")
    col_input, col_btn = st.columns([3, 1])
    with col_input:
        search_ticker = st.text_input("請輸入股票代碼 (需加上 .HK，例如 0700.HK)", value="0700.HK")
    with col_btn:
        st.write("") 
        st.write("")
        search_btn = st.button("🔍 查詢走勢", use_container_width=True)

    if search_btn:
        with st.spinner(f"正在分析 {search_ticker} 的數據..."):
            try:
                df_search = yf.download(search_ticker.upper(), period="4mo", interval="1d", multi_level_index=False, progress=False)
                
                if df_search.empty or len(df_search) < 60:
                    st.error(f"❌ 找不到 {search_ticker} 的數據，請確認代碼是否正確。")
                else:
                    df_search['MA20'] = df_search['Close'].rolling(20).mean()
                    df_search['RSI'] = calculate_rsi(df_search['Close'])
                    
                    curr_p = float(df_search['Close'].iloc[-1])
                    ma20 = float(df_search['MA20'].iloc[-1])
                    curr_rsi = float(df_search['RSI'].iloc[-1])
                    
                    st.write("---")
                    metric_col1, metric_col2, metric_col3 = st.columns(3)
                    metric_col1.metric("📌 最新收盤價", f"${curr_p:.2f}")
                    ma_status = "🟢 位於均線之上" if curr_p > ma20 else "🔴 跌破均線"
                    metric_col2.metric("📈 20日均線 (MA20)", f"${ma20:.2f}", ma_status)
                    rsi_status = "🔥 超買警戒" if curr_rsi >= 70 else ("🧊 超賣區間" if curr_rsi <= 30 else "穩健區間")
                    metric_col3.metric("📊 RSI (14)", f"{curr_rsi:.2f}", rsi_status)
                    
                    st.subheader(f"📊 {search_ticker.upper()} 技術線圖")
                    show_chart(search_ticker.upper(), df_search, curr_p)
                    
            except Exception as e:
                st.error(f"❌ 發生錯誤: {e}，請稍後再試。")
