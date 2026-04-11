# tabs/tab_beat.py
import streamlit as st
import pandas as pd
from data import get_stock_data, get_cached
from ui_components import cache_banner


def render(stocks: list):
    st.subheader("🏆 跑贏大市排行（僅顯示強勢股）")
    cache_banner()

    period_options = {"1日": 2, "1週": 6, "1個月": 22, "3個月": 63, "6個月": 126}
    period_beat = st.selectbox("比較週期", list(period_options.keys()), index=2, key="beat_period")

    if st.button("📊 開始計算跑贏大市"):
        lb     = period_options[period_beat]
        df_hsi = get_stock_data("^HSI", period="6mo")
        if df_hsi.empty:
            st.error("無法取得恆指數據")
            return

        si      = -lb if len(df_hsi) >= lb else 0
        hsi_ret = (df_hsi["Close"].iloc[-1] - df_hsi["Close"].iloc[si]) / df_hsi["Close"].iloc[si] * 100

        results = []
        pbar    = st.progress(0)
        for i, s in enumerate(stocks):
            pbar.progress((i + 1) / len(stocks))
            df_s = get_cached(s)
            if df_s.empty or len(df_s) < 2:
                continue
            si_s      = -lb if len(df_s) >= lb else 0
            stock_ret = (df_s["Close"].iloc[-1] - df_s["Close"].iloc[si_s]) / df_s["Close"].iloc[si_s] * 100
            results.append({
                "代碼": s, "現價": round(float(df_s["Close"].iloc[-1]), 2),
                "股票升幅%": stock_ret, "恆指升幅%": hsi_ret,
                "超額回報%": stock_ret - hsi_ret,
            })
        pbar.empty()

        if results:
            df_res = pd.DataFrame(results)
            df_res = df_res[df_res["超額回報%"] > 0].sort_values("超額回報%", ascending=False)
            if not df_res.empty:
                st.success(f"✅ {len(df_res)} 隻跑贏大市，恆指回報：{hsi_ret:.2f}%")
                st.dataframe(df_res.style.format({
                    "現價": "${:.2f}", "股票升幅%": "{:+.2f}%",
                    "恆指升幅%": "{:+.2f}%", "超額回報%": "{:+.2f}%",
                }).map(
                    lambda x: "color:#26a69a" if x > 0 else ("color:#ef5350" if x < 0 else ""),
                    subset=["股票升幅%", "超額回報%"],
                ), use_container_width=True)
            else:
                st.warning(f"⚠️ 沒有股票跑贏大市（恆指回報：{hsi_ret:.2f}%）")
