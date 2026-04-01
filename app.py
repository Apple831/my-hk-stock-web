import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go

st.set_page_config(page_title="港股短線選股器", layout="wide")

# 固定掃描名單（恆生科技指數 + 核心藍籌，共約 40 隻最活躍股票）
TARGET_STOCKS = [
    "0700.HK", "3690.HK", "9988.HK", "1810.HK", "1024.HK", "9888.HK", "9618.HK", "9999.HK", # 科技龍頭
    "1211.HK", "175.HK", "2333.HK", "2015.HK", # 汽車
    "2318.HK", "3988.HK", "1398.HK", "0939.HK", "0388.HK", # 金融
    "0883.HK", "0857.HK", "0386.HK", # 能源
    "2269.HK", "1093.HK", "0241.HK", # 醫藥
    "1109.HK", "0688.HK", "0960.HK"  # 地產
]

# 固定策略參數
FIXED_VOL_RATIO = 1.2  # 成交量放大 1.2 倍即視為異動

def show_chart(ticker, df, curr_p, ma20):
    fig = go.Figure(data=[go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name='K線')])
    fig.add_trace(go.Scatter(x=df.index, y=df['Close'].rolling(20).mean(), name='20MA', line=dict(color='orange', width=2)))
    
    # 標註最新價格
    fig.add_annotation(x=df.index[-1], y=curr_p, text=f"現價:{curr_p}", showarrow=True, arrowhead=1, bgcolor="red", font=dict(color="white"))
    
    fig.update_layout(xaxis_rangeslider_visible=False, height=400, margin=dict(l=10, r=10, t=30, b=10))
    st.plotly_chart(fig, use_container_width=True)

st.title("港股短線選股器")
st.info(f"當前邏輯：股價 > 20MA and 成交量比平均放大 {FIXED_VOL_RATIO} 倍")

if st.button('🎯 立即掃描全市場強勢股', use_container_width=True):
    found_any = False
    progress_bar = st.progress(0)
    
    # 使用 columns 來排版，讓畫面更緊湊
    display_area = st.container()
    
    for i, s in enumerate(TARGET_STOCKS):
        progress_bar.progress((i + 1) / len(TARGET_STOCKS))
        
        try:
            # 抓取數據
            df = yf.download(s, period="4mo", interval="1d", multi_level_index=False, progress=False)
            if df.empty or len(df) < 20: continue
            
            # 計算數據
            df['MA20'] = df['Close'].rolling(20).mean()
            curr_p = float(df['Close'].iloc[-1])
            ma20 = float(df['MA20'].iloc[-1])
            vol_ratio = float(df['Volume'].iloc[-1]) / float(df['Volume'].tail(5).mean())
            
            # 判斷邏輯
            if curr_p > ma20 and vol_ratio >= FIXED_VOL_RATIO:
                found_any = True
                with display_area:
                    st.success(f"💎 發現目標：{s} | 量比：{vol_ratio:.2f}")
                    show_chart(s, df, curr_p, ma20)
                    st.write("---")
        except:
            continue

    if not found_any:
        st.warning("目前市場較冷淡，沒有符合「價增量漲」的強勢股。")
    else:
        st.balloons()
