# tabs/tab_walkforward.py
import streamlit as st
from data import get_stock_data
from indicators import calculate_indicators
from walk_forward import run_walk_forward, show_walk_forward_results
from ui_components import preset_selector, get_preset_sigs


def render():
    st.subheader("🔬 Walk-Forward 驗證")

    st.markdown("""
    > **原理**：把歷史數據切成多個時間窗口，每個窗口分為 In-Sample（IS）和 Out-of-Sample（OOS）。
    > 如果 OOS 表現接近 IS，代表策略有真實 alpha。

    | 退化率 | 意義 |
    |--------|------|
    | < 40%  | 🟢 策略穩健 |
    | 40-65% | 🟡 輕度過擬合 |
    | > 65%  | 🔴 嚴重過擬合 |
    | OOS < 0 | 🔴 危險 |
    """)
    st.divider()

    _preset, _custom = preset_selector("wf")

    if _custom:
        st.markdown("#### 🟢 買入策略（自定義）")
        c1, c2 = st.columns(2)
        b1  = c1.checkbox("① 突破放量",       key="wf_bb1")
        b2  = c1.checkbox("② MA5金叉",         key="wf_bb2")
        b3  = c1.checkbox("③ 底背離",          key="wf_bb3")
        b4  = c1.checkbox("④ 底部突破MA20",    key="wf_bb4")
        b5  = c1.checkbox("⑤ 布林下軌",        key="wf_bb5")
        b6  = c2.checkbox("⑥ RSI超賣",         key="wf_bb6")
        b7  = c2.checkbox("⑦ MACD金叉",        key="wf_bb7")
        b8  = c2.checkbox("⑧ 趨勢確認",        key="wf_bb8")
        b9  = c2.checkbox("⑨ 52週新高",        key="wf_bb9")
        b10 = c2.checkbox("⑩ 縮量回調",        key="wf_bb10")
        buy_custom = (b1,b2,b3,b4,b5,b6,b7,b8,b9,b10)

        st.markdown("#### 🔴 賣出策略（自定義）")
        d1, d2 = st.columns(2)
        s1 = d1.checkbox("⑪ 頭部跌破MA20", key="wf_bs1")
        s2 = d1.checkbox("⑫ 布林上軌",     key="wf_bs2")
        s3 = d1.checkbox("⑬ 上漲縮量",     key="wf_bs3")
        s4 = d1.checkbox("⑭ 放量急跌",     key="wf_bs4")
        s5 = d2.checkbox("⑮ RSI超買",      key="wf_bs5")
        s6 = d2.checkbox("⑯ MACD死叉",     key="wf_bs6")
        s7 = d2.checkbox("⑰ 三日陰線",     key="wf_bs7")
        sell_custom = (s1,s2,s3,s4,s5,s6,s7)
    else:
        buy_custom  = (False,)*10
        sell_custom = (False,)*7

    buy_sigs, sell_sigs = get_preset_sigs(_preset, buy_custom, sell_custom)
    st.divider()

    with st.expander("⚙️ Walk-Forward 參數", expanded=True):
        c1, c2 = st.columns(2)
        with c1:
            wf_ticker     = st.text_input("股票代碼", value="0700.HK", key="wf_ticker").upper()
            wf_period     = st.selectbox("總數據週期", ["3y","5y","10y"], index=1, key="wf_period")
            wf_is_months  = st.slider("In-Sample 窗口（月）", 6, 24, 12, 3, key="wf_is_months")
            wf_oos_months = st.slider("Out-of-Sample 窗口（月）", 1, 12, 3, 1, key="wf_oos_months")
        with c2:
            wf_capital  = st.number_input("每筆交易金額 (HKD)", value=100_000, step=10_000, min_value=10_000, key="wf_capital")
            wf_slippage = st.slider("滑點 (%)", 0.0, 1.0, 0.20, 0.05, key="wf_slippage") / 100
            wf_sl       = st.number_input("止損 %（0=不啟用）", value=0.0, step=1.0, min_value=0.0, max_value=50.0, key="wf_sl")
            wf_tp       = st.number_input("止盈 %（0=不啟用）", value=0.0, step=5.0, min_value=0.0, max_value=200.0, key="wf_tp")
            wf_maxdays  = st.number_input("最長持倉天數（0=不限）", value=0, step=5, min_value=0, key="wf_maxdays")

        total_m   = {"3y":36,"5y":60,"10y":120}[wf_period]
        est_folds = max(0, (total_m - wf_is_months) // wf_oos_months)
        st.info(f"📋 預計約 **{est_folds} 個 Fold**")

    sl_v = wf_sl     if wf_sl     > 0 else None
    tp_v = wf_tp     if wf_tp     > 0 else None
    md_v = int(wf_maxdays) if wf_maxdays > 0 else None

    if st.button("🔬 開始 Walk-Forward 驗證", type="primary", key="run_wf"):
        if not any(buy_sigs):
            st.warning("⚠️ 請至少勾選一個買入策略"); return
        if not any(sell_sigs) and not wf_sl and not wf_tp and not wf_maxdays:
            st.warning("⚠️ 請設定至少一種出場條件"); return
        if est_folds < 2:
            st.warning("⚠️ 預計 Fold 數不足 2"); return

        with st.spinner(f"正在下載 {wf_ticker}（{wf_period}）..."):
            df_wf = get_stock_data(wf_ticker, period=wf_period)
        if df_wf.empty:
            st.error(f"❌ 無法取得 {wf_ticker} 數據"); return

        df_wf = calculate_indicators(df_wf)
        st.info(f"📊 數據長度：{len(df_wf)} 個交易日")

        with st.spinner("執行 Walk-Forward 中..."):
            results = run_walk_forward(
                df_wf, buy_sigs, sell_sigs,
                is_months=wf_is_months, oos_months=wf_oos_months,
                trade_size=float(wf_capital), slippage=wf_slippage,
                stop_loss_pct=sl_v, take_profit_pct=tp_v, max_hold_days=md_v,
            )

        if not results:
            st.warning("⚠️ Walk-Forward 未能生成任何 Fold")
        else:
            st.success(f"✅ 完成！共 {len(results)} 個 Fold")
            show_walk_forward_results(results, float(wf_capital))

    with st.expander("📖 如何解讀結果？"):
        st.markdown("""
        **退化率公式**：`(IS均回報 − OOS均回報) / |IS均回報| × 100%`

        **OOS 拼接資金曲線**是最重要的圖表。

        **Fold 數建議**：至少 4 個，推薦 5y + IS=12月 + OOS=3月 → 約 16 個 Fold。
        """)
