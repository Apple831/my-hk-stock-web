import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots # 引入子圖表功能

st.set_page_config(page_title="港股獵人 - 終極版", layout="wide")

TARGET_STOCKS = [
    "0700.HK", "3690.HK", "9988.HK", "1810.HK", "1024.HK", "9888.HK", "9618.HK", "9999.HK",
    "1211.HK", "0175.HK", "2333.HK", "2015.HK",
    "2318.HK", "3988.HK", "1398.HK", "0939.HK", "0388.HK",
    "0883.HK", "0857.HK", "0386.HK",
    "2269.HK", "1093.HK", "0241.HK",
    "1109.HK", "0688.HK", "0960.HK"
]

FIXED_VOL_RATIO = 1.2

# 1. 計算 RSI 的專屬函數
def calculate_rsi(series, period=14):
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

# 2. 繪製包含 K線、均線、支撐壓力、RSI 的雙層圖表
def show_chart(ticker, df, curr_p):
    # 建立上下兩層的圖表架構 (K線佔 70%，RSI佔 30%)
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, 
                        vertical_spacing=0.05, row_heights=[0.7, 0.3])

    # --- 上半部：K 線與 20MA ---
    fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name='K線'), row=1, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df['MA20'], name='20MA', line=dict(color='orange', width=2)), row=1, col=1)
    
    # 計算並畫出「自動壓力與支撐線」 (抓取最近 60 天的最高與最低)
    recent_60_days = df.tail(60)
    res_level = recent_60_days['High'].max()
    sup_level = recent_60_days['Low'].min()
    
    # 畫壓力線 (紅虛線) 與 支撐線 (綠虛線)
    fig.add_hline(y=res_level, line_dash="dash", line_color="red", annotation_text=f"近期壓力: {res_level:.2f}", row=1, col=1)
    fig.add_hline(y=sup_level, line_dash="dash", line_color="green", annotation_text=f"近期支撐: {sup_level:.2f}", row=1, col=1)

    # --- 下半部：RSI 指標 ---
    fig.add_trace(go.Scatter(x=df.index, y=df['RSI'], name='RSI (14)', line=dict(color='purple', width=2)), row=2, col=1)
    # 畫 RSI 的超買超賣警戒線
    fig.add_hline(y=70, line_dash="dot", line_color="red", row=2, col=1)
    fig.add_hline(y=30, line_dash="dot", line_color="green", row=2, col=1)

    # 隱藏下方時間軸拉桿，調整整體高度
    fig.update_layout(xaxis_rangeslider_visible=False, xaxis2_rangeslider_visible=False, height=550, margin=dict(l=10, r=10, t=30, b=10))
    st.plotly_chart(fig, use_container_width=True)


st.title("🏹 港股短線獵人 (終極全能版)")

if st.button('🎯 立即掃描全市場強勢股', use_container_width=True):
    progress_bar = st.progress(0)
    hit_list = [] 
    all_data = {} 

    for i, s in enumerate(TARGET_STOCKS):
        progress_bar.progress((i + 1) / len(TARGET_STOCKS))
        try:
            df = yf.download(s, period="4mo", interval="1d", multi_level_index=False, progress=False)
            if df.empty or len(df) < 60: continue # 確保有足夠數據算 60天高低點
            
            # 計算所有技術指標
            df['MA20'] = df['Close'].rolling(20).mean()
            df['RSI'] = calculate_rsi(df['Close'])
            
            curr_p = float(df['Close'].iloc[-1])
            ma20 = float(df['MA20'].iloc[-1])
            curr_rsi = float(df['RSI'].iloc[-1])
            vol_ratio = float(df['Volume'].iloc[-1]) / float(df['Volume'].tail(5).mean())
            change_pct = ((curr_p - float(df['Close'].iloc[-2])) / float(df['Close'].iloc[-2])) * 100
            
            # 策略過濾：只要價漲量增就抓出來
            if curr_p > ma20 and vol_ratio >= FIXED_VOL_RATIO:
                hit_list.append({
                    "股票代碼": s,
                    "現價": round(curr_p, 2),
                    "今日漲幅(%)": round(change_pct, 2),
                    "成交量比": round(vol_ratio, 2),
                    "RSI (14)": round(curr_rsi, 2) # 將 RSI 加入排行榜
                })
                all_data[s] = {"df": df, "curr_p": curr_p}
        except:
            continue

    if hit_list:
        st.balloons()
        st.header("📊 今日強勢股排行榜")
        
        # 顯示包含 RSI 的表格
        report_df = pd.DataFrame(hit_list).sort_values(by="成交量比", ascending=False)
        st.dataframe(report_df, use_container_width=True, hide_index=True)
        
        st.write("---")
        st.header("📈 詳細技術線圖 (含壓力支撐與 RSI)")
        
        for s in report_df["股票代碼"]:
            st.subheader(f"🔥 {s}")
            show_chart(s, all_data[s]["df"], all_data[s]["curr_p"])
            st.write("---")
    else:
        st.warning("目前市場沒有符合條件的強勢股。")
