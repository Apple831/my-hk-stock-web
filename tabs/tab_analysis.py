# tabs/tab_analysis.py
import streamlit as st
from data import get_stock_data
from indicators import calculate_indicators
from signals import evaluate_signals
from charts import show_chart


def render():
    st.subheader("🔍 個股深度分析")

    col_left, col_right = st.columns([1, 3])
    with col_left:
        custom_ticker   = st.text_input("輸入股票代碼", value="0700.HK").upper()
        analysis_period = st.selectbox("週期", ["3mo", "6mo", "1y", "2y"], index=2, key="analysis_period")
        analyze_btn     = st.button("🔍 開始分析", type="primary")

    with col_right:
        if analyze_btn:
            with st.spinner(f"正在分析 {custom_ticker}..."):
                df_a = get_stock_data(custom_ticker, period=analysis_period)

            if df_a.empty:
                st.error(f"❌ 無法取得 {custom_ticker} 數據，請確認代碼正確。")
                return

            df_a = calculate_indicators(df_a)
            c    = df_a.iloc[-1]
            p    = df_a.iloc[-2]

            pct_1d = (c["Close"] - p["Close"]) / p["Close"] * 100
            m1, m2, m3, m4, m5, m6 = st.columns(6)
            m1.metric("現價 (HKD)",  f"{c['Close']:.2f}",  f"{pct_1d:+.2f}%")
            m2.metric("MA20",        f"{c['MA20']:.2f}",   f"{((c['Close']-c['MA20'])/c['MA20']*100):+.1f}%")
            m3.metric("MA60",        f"{c['MA60']:.2f}",   f"{((c['Close']-c['MA60'])/c['MA60']*100):+.1f}%")
            m4.metric("RSI (14)",    f"{c['RSI']:.1f}",    "超賣" if c["RSI"] < 30 else ("超買" if c["RSI"] > 70 else "中性"))
            m5.metric("J 值",        f"{c['J']:.1f}",      "超賣" if c["J"] < 10 else ("超買" if c["J"] > 90 else "中性"))
            m6.metric("MACD 柱",     f"{c['MACD_Hist']:.4f}", "多頭" if c["MACD_Hist"] > 0 else "空頭")

            st.divider()

            signals   = evaluate_signals(df_a)
            buy_hits  = [s for s in signals["buy"]  if s[2]]
            sell_hits = [s for s in signals["sell"] if s[2]]
            buy_miss  = [s for s in signals["buy"]  if not s[2]]
            sell_miss = [s for s in signals["sell"] if not s[2]]

            buy_score  = len(buy_hits)
            sell_score = len(sell_hits)

            if buy_score > sell_score and buy_score >= 2:
                verdict_color, verdict = "#26a69a", f"🟢 偏多訊號（{buy_score} 買 / {sell_score} 賣）"
            elif sell_score > buy_score and sell_score >= 2:
                verdict_color, verdict = "#ef5350", f"🔴 偏空訊號（{buy_score} 買 / {sell_score} 賣）"
            else:
                verdict_color, verdict = "#f9a825", f"🟡 中性觀望（{buy_score} 買 / {sell_score} 賣）"

            st.markdown(
                f"<div style='background:rgba(255,255,255,0.05);border-left:4px solid {verdict_color};"
                f"padding:10px 16px;border-radius:6px;font-size:18px;font-weight:bold'>{verdict}</div>",
                unsafe_allow_html=True,
            )
            st.caption("策略訊號以最新一根 K 線數據為準（與掃描 Tab 邏輯完全一致）")
            st.divider()

            col_buy, col_sell = st.columns(2)
            with col_buy:
                st.markdown("### 🟢 買入策略")
                if buy_hits:
                    for name, detail, _ in buy_hits:
                        with st.container():
                            st.success(f"✅ **{name}**")
                            st.caption(detail)
                else:
                    st.info("目前沒有觸發任何買入策略")
                if buy_miss:
                    with st.expander(f"未觸發的買入策略（{len(buy_miss)} 個）"):
                        for name, detail, _ in buy_miss:
                            st.markdown(f"⬜ **{name}**")
                            st.caption(detail)

            with col_sell:
                st.markdown("### 🔴 賣出策略")
                if sell_hits:
                    for name, detail, _ in sell_hits:
                        with st.container():
                            st.error(f"🚨 **{name}**")
                            st.caption(detail)
                else:
                    st.info("目前沒有觸發任何賣出策略")
                if sell_miss:
                    with st.expander(f"未觸發的賣出策略（{len(sell_miss)} 個）"):
                        for name, detail, _ in sell_miss:
                            st.markdown(f"⬜ **{name}**")
                            st.caption(detail)

            st.divider()
            st.markdown(f"### 📈 {custom_ticker} 技術圖表")
            show_chart(custom_ticker, df_a)
