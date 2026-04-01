import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go

st.set_page_config(page_title="港股短線選股器", layout="wide")
st.title("This will lose you money.. YES FR")

# 股票池
stocks = ["0700.HK", "3690.HK", "9988.HK", "1211.HK", "2318.HK", "0388.HK", "1810.HK", "1024.HK", "9888.HK"]

def show_chart(ticker, df):
    fig = go.Figure(data=[go.Candlestick(x=df.index,
                open=df['Open'], high=df['High'],
                low=df['Low'], close=df['Close'], name='K線')])
    fig.add_trace(go.Scatter(x=df.index, y=df['Close'].rolling(20).mean(), name='20MA', line=dict(color='orange')))
    fig.update_layout(title=f"{ticker} 走勢圖", xaxis_rangeslider_visible=False, height=400)
    st.plotly_chart(fig, use_container_width=True)

if st.button('Start'):
    cols = st.columns(2) # 分成兩列顯示，看起來更專業
    for i, s in enumerate(stocks):
        with st.spinner(f'正在分析 {s}...'):
            df = yf.download(s, period="3mo", interval="1d", multi_level_index=False)
            if df.empty: continue
            
            # 策略判斷
            ma20 = df['Close'].rolling(20).mean().iloc[-1]
            curr_p = float(df['Close'].iloc[-1])
            vol_ratio = float(df['Volume'].iloc[-1]) / float(df['Volume'].tail(5).mean())
            
            with cols[i % 2]: # 交替放在左/右兩欄
                st.subheader(f"股票: {s}")
                if curr_p > ma20 and vol_ratio > 1.2:
                    st.success(f"🔥 訊號觸發！成交量放大 {vol_ratio:.2f} 倍")
                else:
                    st.info(f"😴 趨勢盤整中 (量比: {vol_ratio:.2f})")
                
                show_chart(s, df) # 秀出圖表
                st.write("---")
