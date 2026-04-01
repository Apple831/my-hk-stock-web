import streamlit as st
import yfinance as yf
import pandas as pd

st.title("港股🚀")

# 你可以隨時在這裡增加更多港股代碼
stocks = ["0700.HK", "3690.HK", "9988.HK", "1211.HK", "2318.HK", "0388.HK", "1810.HK"]

def check_strategy(ticker):
    # 關鍵修正：加入 multi_level_index=False 確保資料格式正確
    df = yf.download(ticker, period="1mo", interval="1d", multi_level_index=False)
    
    # 檢查是否有抓到資料
    if df.empty or len(df) < 20: 
        return False
    
    # 計算 20 日均線
    df['MA20'] = df['Close'].rolling(window=20).mean()
    
    # 取得最新的數值，並強制轉為數字 (float) 避免報錯
    current_price = float(df['Close'].iloc[-1])
    last_volume = float(df['Volume'].iloc[-1])
    avg_volume = float(df['Volume'].iloc[-2: -6: -1].mean()) # 取前 5 天平均成交量
    ma20_val = float(df['MA20'].iloc[-1])

    # 策略邏輯：價格在均線上 + 成交量是平均的 1.5 倍
    if current_price > ma20_val and last_volume > (avg_volume * 1.5):
        return True
    return False

if st.button('開始掃描股票'):
    with st.spinner('正在分析港股數據...'):
        for s in stocks:
            try:
                if check_strategy(s):
                    st.success(f"✅ {s} 符合爆發條件！")
                else:
                    st.info(f"⚪ {s} 尚未觸發")
            except Exception as e:
                st.error(f"❌ {s} 數據抓取失敗: {e}")
