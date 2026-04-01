import streamlit as st
import yfinance as yf
import pandas as pd

st.title("🚀 港股短線選股器")

# 設定你想監控的港股代碼 (例如：騰訊, 美團, 阿里巴巴, 比亞迪)
stocks = ["0700.HK", "3690.HK", "9988.HK", "1211.HK", "2318.HK"]

def check_strategy(ticker):
    df = yf.download(ticker, period="1mo", interval="1d")
    if len(df) < 20: return False
    
    # 計算 20 日均線
    df['MA20'] = df['Close'].rolling(window=20).mean()
    current_price = df['Close'].iloc[-1]
    last_volume = df['Volume'].iloc[-1]
    avg_volume = df['Volume'].tail(5).mean()

    # 簡單策略：價格在均線上 + 成交量翻倍
    if current_price > df['MA20'].iloc[-1] and last_volume > (avg_volume * 1.5):
        return True
    return False

if st.button('開始掃描股票'):
    for s in stocks:
        if check_strategy(s):
            st.success(f"✅ {s} 符合爆發條件！")
        else:
            st.info(f"⚪ {s} 尚未觸發")
