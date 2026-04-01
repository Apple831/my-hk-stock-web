import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import os

# 設定網頁標題
st.set_page_config(page_title="港股獵人 - 終極完全體", layout="wide")

# --- 1. 名單讀取邏輯 (修正版) ---
def load_stocks():
    file_path = 'stocks.txt'
    # 預設保底名單，萬一檔案讀取失敗時使用
    default_stocks = ["0700.HK", "3690.HK", "9988.HK", "1810.HK", "1211.HK"]
    
    if os.path.exists(file_path):
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                # 讀取每一行，過濾掉 # 後的註解、空格，並確保不是空行
                stocks = []
                for line in f:
                    clean_line = line.split('#')[0].strip()
                    if clean_line:
                        stocks.append(clean_line)
                # 如果讀出來是空的，就回傳保底名單
                return stocks if stocks else default_stocks
        except Exception as e:
            st.error(f"讀取 stocks.txt 時發生錯誤: {e}")
            return default_stocks
    else:
        return default_stocks

# 執行讀取
TARGET_STOCKS = load_stocks()

# --- 2. 技術指標計算 ---
def calculate_rsi(series, period=14):
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

# --- 3. 繪圖邏輯 (K線 + 成交量 + RSI) ---
def show_chart(ticker, df):
    fig = make_subplots(rows=3, cols=1, shared_xaxes=True, 
                        vertical_spacing=0.03, row_heights=[0.6, 0.2, 0.2])

    # K線與 20MA
    fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name='K線'), row=1, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df['MA20'], name='20MA', line=dict(color='orange', width=2)), row=1, col=1)
    
    # 壓力與支撐 (最近60天)
    res_level = df.tail(60)['High'].max()
    sup_level = df.tail(60)['Low'].min()
    fig.add_hline(y=res_level, line_dash="dash", line_color="red", annotation_text=f"壓力:{res_level:.2f}", row=1, col=1)
    fig.add_hline(y=sup_level, line_dash="dash", line_color="green", annotation_text=f"支撐:{sup_level:.2f}", row=1, col=1)

    # 成交量
    colors = ['red' if row['Close'] >= row['Open'] else 'green' for _, row in df.iterrows()]
    fig.add_trace(go.Bar(x=df.index, y=df['Volume'], name='成交量', marker_color=colors), row=2, col=1)

    # RSI
    fig.add_trace(go.Scatter(x=df.index, y=df['RSI'], name='RSI', line=dict(color='purple')), row=3, col=1)
    fig.add_hline(y=70, line_dash="dot", line_color="red", row=3, col=1)
    fig.add_hline(y=30, line_dash="dot", line_color="green", row=3, col=1)

    fig.update_xaxes(rangeslider_visible=False)
    fig.update_layout(height=700, margin=dict(l=10, r=10, t=30, b=10), showlegend=False)
    st.plotly_chart(fig, use_container_width=True)

# --- 4. 網頁介面 ---
st.title("🏹 港股短線獵人 (終極全能版)")

tab1, tab2 = st.tabs(["🎯 強勢股自動掃描", "🔍 個股深度搜尋"])

# ================= 頁籤 1：自動掃描 =================
with tab1:
    st.info(f"目前監控清單中共 {len(TARGET_STOCKS)} 隻股票。策略：股價 > 20MA 且 量比 > 1.2。")
    if st.button('🎯 立即開始掃描', use_container_width=True):
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
                
                if curr_p > ma20 and vol_ratio >= 1.2:
                    hit_list.append({
                        "股票代碼": s,
                        "現價": round(curr_p, 2),
                        "今日漲幅(%)": round(change_pct, 2),
                        "成交量比": round(vol_ratio, 2),
                        "RSI (14)": round(curr_rsi, 2)
                    })
                    all_data[s] = df
            except:
                continue

        if hit_list:
            st.balloons()
            st.header("📊 今日強勢股排行榜")
            report_df = pd.DataFrame(hit_list).sort_values(by="成交量比", ascending=False)
            st.dataframe(report_df, use_container_width=True, hide_index=True)
            
            st.write("---")
            for s in report_df["股票代碼"]:
                st.subheader(f"🔥 {s}")
                show_chart(s, all_data[s])
        else:
            st.warning("暫時沒有符合條件的強勢股。")

# ================= 頁籤 2：個股搜尋 =================
with tab2:
    st.subheader("輸入任何港股代碼 (例如 0700.HK)")
    col_input, col_btn = st.columns([3, 1])
    with col_input:
        search_ticker = st.text_input("搜尋代碼", value="0700.HK").upper()
    with col_btn:
        st.write(" ")
        st.write(" ")
        search_btn = st.button("🔍 查詢")

    if search_btn:
        with st.spinner("數據讀取中..."):
            try:
                df_search = yf.download(search_ticker, period="4mo", interval="1d", multi_level_index=False, progress=False)
                if not df_search.empty:
                    df_search['MA20'] = df_search['Close'].rolling(20).mean()
                    df_search['RSI'] = calculate_rsi(df_search['Close'])
                    
                    p = float(df_search['Close'].iloc[-1])
                    m = float(df_search['MA20'].iloc[-1])
                    r = float(df_search['RSI'].iloc[-1])
                    
                    m1, m2, m3 = st.columns(3)
                    m1.metric("最新價", f"${p:.2f}")
                    m2.metric("20MA", f"${m:.2f}", "🟢之上" if p>m else "🔴之下")
                    m3.metric("RSI", f"{r:.2f}", "🔥超買" if r>70 else ("🧊超賣" if r<30 else "正常"))
                    
                    show_chart(search_ticker, df_search)
                else:
                    st.error("找不到該股票數據。")
            except Exception as e:
                st.error(f"錯誤: {e}")
