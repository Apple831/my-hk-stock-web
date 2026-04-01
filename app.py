import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go

st.set_page_config(page_title="港股獵人 - 排行榜版", layout="wide")

# 固定掃描名單
TARGET_STOCKS = [
    "0700.HK", "3690.HK", "9988.HK", "1810.HK", "1024.HK", "9888.HK", "9618.HK", "9999.HK",
    "1211.HK", "175.HK", "2333.HK", "2015.HK", "0175.HK",
    "2318.HK", "3988.HK", "1398.HK", "0939.HK", "0388.HK",
    "0883.HK", "0857.HK", "0386.HK",
    "2269.HK", "1093.HK", "0241.HK",
    "1109.HK", "0688.HK", "0960.HK", "1030.HK"
]

FIXED_VOL_RATIO = 1.2

def show_chart(ticker, df, curr_p):
    fig = go.Figure(data=[go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name='K線')])
    fig.add_trace(go.Scatter(x=df.index, y=df['Close'].rolling(20).mean(), name='20MA', line=dict(color='orange', width=2)))
    fig.update_layout(xaxis_rangeslider_visible=False, height=400, margin=dict(l=10, r=10, t=30, b=10))
    st.plotly_chart(fig, use_container_width=True)

st.title("🏹 港股短線獵人 (強勢排行榜)")

if st.button('🎯 立即掃描全市場強勢股', use_container_width=True):
    progress_bar = st.progress(0)
    hit_list = [] # 用來存儲符合條件的股票數據
    all_data = {} # 用來存儲繪圖用的數據

    # 第一階段：掃描與數據收集
    for i, s in enumerate(TARGET_STOCKS):
        progress_bar.progress((i + 1) / len(TARGET_STOCKS))
        try:
            df = yf.download(s, period="4mo", interval="1d", multi_level_index=False, progress=False)
            if df.empty or len(df) < 20: continue
            
            curr_p = float(df['Close'].iloc[-1])
            ma20 = float(df['Close'].rolling(20).mean().iloc[-1])
            vol_ratio = float(df['Volume'].iloc[-1]) / float(df['Volume'].tail(5).mean())
            change_pct = ((curr_p - float(df['Close'].iloc[-2])) / float(df['Close'].iloc[-2])) * 100
            
            if curr_p > ma20 and vol_ratio >= FIXED_VOL_RATIO:
                hit_list.append({
                    "股票代碼": s,
                    "現價": round(curr_p, 2),
                    "今日漲幅(%)": round(change_pct, 2),
                    "成交量比(量比)": round(vol_ratio, 2)
                })
                all_data[s] = {"df": df, "curr_p": curr_p}
        except:
            continue

    # 第二階段：顯示結果
    if hit_list:
        st.balloons()
        st.header("📊 今日強勢股摘要")
        
        # 將結果轉為表格並按量比排序
        report_df = pd.DataFrame(hit_list).sort_values(by="成交量比(量比)", ascending=False)
        
        # 顯示美化表格
        st.dataframe(report_df, use_container_width=True, hide_index=True)
        
        st.write("---")
        st.header("📈 詳細走勢圖")
        
        # 依照排行榜順序畫圖
        for s in report_df["股票代碼"]:
            st.subheader(f"🔥 {s}")
            show_chart(s, all_data[s]["df"], all_data[s]["curr_p"])
            st.write("---")
    else:
        st.warning("目前市場沒有符合條件的強勢股。")
