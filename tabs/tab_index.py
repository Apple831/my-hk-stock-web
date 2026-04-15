# tabs/tab_index.py
import streamlit as st
from data import get_stock_data
from indicators import calculate_indicators
from charts import show_chart


def render():
    st.subheader("🌍 主要指數走勢")

    indices = {
        "恆生指數 (^HSI)":    "^HSI",
        "恆生科技 (^HSTECH)": "^HSTECH",
        "恐慌指數 (^VIX)":    "^VIX",
    }

    col1, col2 = st.columns([1, 3])
    with col1:
        selected_index = st.selectbox("選擇指數", list(indices.keys()))
        period         = st.selectbox("時間週期", ["3mo", "6mo", "1y", "2y"], index=2)

    with col2:
        ticker_code = indices[selected_index]

        with st.spinner(f"載入 {selected_index} 數據中..."):
            df_idx = get_stock_data(ticker_code, period=period)

        if df_idx.empty:
            st.error(f"❌ 無法載入 {selected_index} 數據，請稍後再試。")
            return

        df_idx = calculate_indicators(df_idx)
        show_chart(ticker_code, df_idx)
