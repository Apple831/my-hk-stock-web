import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go

st.set_page_config(page_title="港股短線選股器", layout="wide")

# --- 側邊欄設定 ---
st.sidebar.title("Dont ask why i use this function")
scan_mode = st.sidebar.selectbox("選擇掃描範圍", ["大型藍籌 (HSI)", "科技股 (HSTECH)", "自定義名單"])
min_vol_ratio = st.sidebar.slider("成交量放大倍數 (量比)", 1.0, 3.0, 1.5, 0.1)

# 準備股票名單 (這裡先列出核心權重股，你可以隨時手動增加)
hsi_stocks = ["0001.HK", "0002.HK", "0003.HK", "0005.HK", "0011.HK", "0016.HK", "0388.HK", "0700.HK", "0883.HK", "0939.HK", "0941.HK", "1211.HK", "1299.HK", "1398.HK", "2318.HK", "2388.HK", "3690.HK", "3988.HK", "9988.HK"]
hstech_stocks = ["0020.HK", "0182.HK", "0241.HK", "0268.HK", "0285.HK", "0700.HK", "0762.HK", "0772.HK", "0960.HK", "0981.HK", "0992.HK", "1024.HK", "1310.HK", "1810.HK", "2013.HK", "2382.HK", "2400.HK", "3690.HK", "6060.HK", "6618.HK", "9618.HK", "9626.HK", "9698.HK", "9866.HK", "9868.HK", "9888.HK", "9928.HK", "9961.HK", "9988.HK", "9999.HK"]

target_stocks = hstech_stocks if scan_mode == "科技股 (HSTECH)" else hsi_stocks

# --- 主畫面 ---
st.title("🏹 港股短線選股器")
st.write(f"目前掃描範圍：{scan_mode} (共 {len(target_stocks)} 隻)")

def show_chart(ticker, df):
    fig = go.Figure(data=[go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name='K線')])
    fig.add_trace(go.Scatter(x=df.index, y=df['Close'].rolling(20).mean(), name='20MA', line=dict(color='orange')))
    fig.update_layout(xaxis_rangeslider_visible=False, height=300, margin=dict(l=20, r=20, t=30, b=20))
    st.plotly_chart(fig, use_container_width=True)

if st.sidebar.button('🚀 開始一鍵掃描'):
    found_any = False
    progress_bar = st.progress(0) # 加入進度條
    
    # 建立結果顯示區
    st.subheader("🎯 掃描結果 (僅顯示符合條件的股票)")
    cols = st.columns(2)
    col_idx = 0

    for i, s in enumerate(target_stocks):
        # 更新進度條
        progress_bar.progress((i + 1) / len(target_stocks))
        
        try:
            df = yf.download(s, period="3mo", interval="1d", multi_level_index=False, progress=False)
            if df.empty or len(df) < 20: continue
            
            # 策略：價格 > 20MA 且 成交量 > 平均 * 倍數
            curr_p = float(df['Close'].iloc[-1])
            ma20 = float(df['Close'].rolling(20).mean().iloc[-1])
            vol_ratio = float(df['Volume'].iloc[-1]) / float(df['Volume'].tail(5).mean())
            
            if curr_p > ma20 and vol_ratio >= min_vol_ratio:
                found_any = True
                with cols[col_idx % 2]:
                    st.success(f"🔥 **{s}** | 價格: {curr_p:.2f} | 量比: {vol_ratio:.2f}")
                    show_chart(s, df)
                    st.write("---")
                col_idx += 1
        except:
            continue

    if not found_any:
        st.warning("暫時沒有股票符合選股條件，請試著調低量比或換個模式。")
    
    st.balloons() # 掃描完畢噴彩帶
