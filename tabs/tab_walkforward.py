# tabs/tab_walkforward.py
import streamlit as st
from data import get_stock_data
from indicators import calculate_indicators
from backtest import build_hsi_filter
from walk_forward import (
    run_walk_forward, run_portfolio_walk_forward,
    show_walk_forward_results,
)
from ui_components import preset_selector, get_preset_sigs
from config import STRATEGY_PRESETS, PRESET_CUSTOM


# ── helper：從選定的 preset 讀取 min_hold_days ─────────────────────
def _get_preset_min_hold(preset_name: str):
    if preset_name == PRESET_CUSTOM:
        return None
    return STRATEGY_PRESETS.get(preset_name, {}).get("min_hold_days")


def render(stocks: list):
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
    | N/A    | IS≈0，退化率公式失效，僅看 OOS 數值 |
    """)
    st.divider()

    # ── 模式選擇 ──────────────────────────────────────────────────
    wf_mode = st.radio(
        "驗證模式",
        ["🔍 單股模式", "📊 投資組合模式"],
        horizontal=True, key="wf_mode",
    )
    st.divider()

    # ── 策略選擇（共用）─────────────────────────────────────────
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

    # ── 讀取 preset 的 min_hold_days（自定義時為 None）────────────
    preset_min_hold = _get_preset_min_hold(_preset)
    if preset_min_hold:
        st.info(
            f"🔒 此策略已啟用 **min_hold_days = {preset_min_hold} 交易日**"
            f"（進場後 {preset_min_hold} 個 bar 內凍結策略 sell，只允許止損/止盈出場）"
        )

    # ══════════════════════════════════════════════════════════════
    # 共用進階過濾器（改進二 + 三）
    # ══════════════════════════════════════════════════════════════
    st.divider()
    st.markdown("#### 🔧 進階入場過濾器（改進二 & 三）")

    adv1, adv2 = st.columns(2)
    with adv1:
        use_hsi_filter = st.checkbox(
            "🌐 改進二：啟用恒指趨勢過濾（恒指 MA20 > MA60 才允許入場）",
            value=False, key="wf_hsi_filter",
            help=(
                "只有在恒指本身處於上升趨勢（MA20 > MA60）時才觸發買入。\n"
                "目標：過濾橫盤 / 熊市環境的假訊號（如 F3 2023-04~10）。\n"
                "代價：訊號頻率會降低，部分 Fold 交易數可能不足門檻。"
            ),
        )
    with adv2:
        use_b8_filter = st.checkbox(
            "📈 改進三：加入個股趨勢確認（b8：個股 MA20 > MA60）",
            value=False, key="wf_b8_filter",
            help=(
                "在原有買入條件基礎上，額外要求個股本身 MA20 > MA60。\n"
                "目標：排除下降趨勢中的底部假突破。\n"
                "代價：訊號頻率進一步降低。"
            ),
        )

    extra_buy = (False,False,False,False,False,False,False,use_b8_filter,False,False)

    if use_hsi_filter or use_b8_filter:
        active_filters = []
        if use_hsi_filter: active_filters.append("恒指 MA20>MA60")
        if use_b8_filter:  active_filters.append("個股 MA20>MA60（b8）")
        st.info(f"🔧 已啟用：{' + '.join(active_filters)}")

    st.divider()

    # ══════════════════════════════════════════════════════════════
    # 🔍 單股模式
    # ══════════════════════════════════════════════════════════════
    if wf_mode == "🔍 單股模式":
        with st.expander("⚙️ 單股 Walk-Forward 參數", expanded=True):
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
                wf_min_oos  = st.number_input("每 Fold 最低有效 OOS 交易數", value=3, min_value=1, max_value=20, step=1, key="wf_min_oos")

            total_m   = {"3y":36,"5y":60,"10y":120}[wf_period]
            est_folds = max(0, (total_m - wf_is_months) // wf_oos_months)
            st.info(f"📋 預計約 **{est_folds} 個 Fold**")

        sl_v = wf_sl    if wf_sl    > 0 else None
        tp_v = wf_tp    if wf_tp    > 0 else None
        md_v = int(wf_maxdays) if wf_maxdays > 0 else None

        if st.button("🔬 開始 Walk-Forward 驗證", type="primary", key="run_wf"):
            if not any(buy_sigs):
                st.warning("⚠️ 請至少勾選一個買入策略"); return
            if not any(sell_sigs) and not wf_sl and not wf_tp and not wf_maxdays:
                st.warning("⚠️ 請設定至少一種出場條件"); return
            if est_folds < 2:
                st.warning("⚠️ 預計 Fold 數不足 2"); return

            hsi_filter_series = None
            if use_hsi_filter:
                with st.spinner("下載恒指數據以建立市場過濾器..."):
                    df_hsi = get_stock_data("^HSI", period=wf_period)
                if df_hsi.empty:
                    st.warning("⚠️ 無法取得恒指數據，市場過濾器將停用。")
                else:
                    df_hsi = calculate_indicators(df_hsi)
                    hsi_filter_series = build_hsi_filter(df_hsi)
                    bull_pct = hsi_filter_series.mean() * 100
                    st.info(f"🌐 恒指過濾器已建立：過去 {wf_period} 中 {bull_pct:.0f}% 的交易日允許入場")

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
                    min_hold_days=preset_min_hold,
                    min_oos_trades=int(wf_min_oos),
                    hsi_filter=hsi_filter_series,
                    extra_buy_sigs=extra_buy if use_b8_filter else None,
                )

            if not results:
                st.warning("⚠️ Walk-Forward 未能生成任何 Fold")
            else:
                st.success(f"✅ 完成！共 {len(results)} 個 Fold")
                show_walk_forward_results(results, float(wf_capital), is_portfolio=False)

    # ══════════════════════════════════════════════════════════════
    # 📊 投資組合模式
    # ══════════════════════════════════════════════════════════════
    else:
        st.markdown("""
        > **投資組合模式**：每個 Fold 同時對所有選定股票跑回測，把所有交易聚合計算指標。
        > 解決單股 OOS 交易次數不足的問題。OOS 預設 **6 個月**。
        """)

        col_a, col_b = st.columns([3, 1])
        with col_a:
            use_all = st.checkbox("使用完整股票清單", value=True, key="wf_port_all")
            if not use_all:
                port_stocks = st.multiselect(
                    "手動選擇股票（建議 10 隻以上）",
                    stocks, default=stocks[:15], key="wf_port_stocks",
                )
            else:
                port_stocks = stocks
        with col_b:
            n_sel = len(port_stocks) if not use_all else len(stocks)
            st.metric("選中股票數", n_sel)
            if n_sel < 10:
                st.caption("⚠️ 建議至少 10 隻")

        with st.expander("⚙️ 投資組合 Walk-Forward 參數", expanded=True):
            c1, c2 = st.columns(2)
            with c1:
                wf_port_period = st.selectbox("總數據週期", ["3y","5y","10y"], index=1, key="wf_port_period")
                wf_port_is     = st.slider("In-Sample 窗口（月）", 6, 24, 12, 3, key="wf_port_is")
                wf_port_oos    = st.slider("Out-of-Sample 窗口（月）", 3, 12, 6, 1, key="wf_port_oos",
                                           help="投資組合模式建議 6 個月。")
                wf_port_min    = st.number_input("每 Fold 最低有效 OOS 交易數", value=5, min_value=1, max_value=50, step=1, key="wf_port_min")
            with c2:
                wf_port_capital = st.number_input("每筆交易金額 (HKD)", value=100_000, step=10_000, min_value=10_000, key="wf_port_capital")
                wf_port_slip    = st.slider("滑點 (%)", 0.0, 1.0, 0.20, 0.05, key="wf_port_slip") / 100
                wf_port_sl      = st.number_input("止損 %（0=不啟用）", value=0.0, step=1.0, min_value=0.0, max_value=50.0, key="wf_port_sl")
                wf_port_tp      = st.number_input("止盈 %（0=不啟用）", value=0.0, step=5.0, min_value=0.0, max_value=200.0, key="wf_port_tp")
                wf_port_maxdays = st.number_input("最長持倉天數（0=不限）", value=0, step=5, min_value=0, key="wf_port_maxdays")

            total_m_p   = {"3y":36,"5y":60,"10y":120}[wf_port_period]
            est_folds_p = max(0, (total_m_p - wf_port_is) // wf_port_oos)
            st.info(
                f"📋 預計約 **{est_folds_p} 個 Fold** × {n_sel} 隻股票　｜　"
                f"預計每 Fold OOS：{n_sel} 隻 × 約 2 筆 ≈ **{n_sel * 2} 筆**（視策略而定）"
            )

        sl_pv = wf_port_sl     if wf_port_sl     > 0 else None
        tp_pv = wf_port_tp     if wf_port_tp     > 0 else None
        md_pv = int(wf_port_maxdays) if wf_port_maxdays > 0 else None
        final_stocks = port_stocks if not use_all else stocks

        if st.button(f"📊 開始投資組合 Walk-Forward（{len(final_stocks)} 隻）", type="primary", key="run_wf_port"):
            if not any(buy_sigs):
                st.warning("⚠️ 請至少勾選一個買入策略"); return
            if not any(sell_sigs) and not wf_port_sl and not wf_port_tp and not wf_port_maxdays:
                st.warning("⚠️ 請設定至少一種出場條件"); return
            if est_folds_p < 2:
                st.warning("⚠️ 預計 Fold 數不足 2"); return

            hsi_filter_series = None
            if use_hsi_filter:
                with st.spinner("下載恒指數據以建立市場過濾器..."):
                    df_hsi = get_stock_data("^HSI", period=wf_port_period)
                if df_hsi.empty:
                    st.warning("⚠️ 無法取得恒指數據，市場過濾器將停用。")
                else:
                    df_hsi = calculate_indicators(df_hsi)
                    hsi_filter_series = build_hsi_filter(df_hsi)
                    bull_pct = hsi_filter_series.mean() * 100
                    st.info(f"🌐 恒指過濾器已建立：{bull_pct:.0f}% 交易日允許入場")

            stock_data = {}
            with st.spinner(f"下載 {len(final_stocks)} 隻股票（{wf_port_period}）數據..."):
                dl_pbar = st.progress(0)
                for i, ticker in enumerate(final_stocks):
                    dl_pbar.progress((i + 1) / len(final_stocks), text=f"下載 {ticker}...")
                    df_t = get_stock_data(ticker, period=wf_port_period)
                    if not df_t.empty and len(df_t) >= 62:
                        stock_data[ticker] = calculate_indicators(df_t)
                dl_pbar.empty()

            if not stock_data:
                st.error("❌ 無法取得任何股票數據"); return

            st.info(f"📊 成功下載 **{len(stock_data)}/{len(final_stocks)}** 隻股票")

            results = run_portfolio_walk_forward(
                stock_data,
                buy_sigs, sell_sigs,
                is_months=wf_port_is, oos_months=wf_port_oos,
                trade_size=float(wf_port_capital), slippage=wf_port_slip,
                stop_loss_pct=sl_pv, take_profit_pct=tp_pv, max_hold_days=md_pv,
                min_hold_days=preset_min_hold,
                min_oos_trades=int(wf_port_min),
                hsi_filter=hsi_filter_series,
                extra_buy_sigs=extra_buy if use_b8_filter else None,
            )

            if not results:
                st.warning("⚠️ Walk-Forward 未能生成任何 Fold。")
            else:
                st.success(f"✅ 完成！共 {len(results)} 個 Fold，聚合 {len(stock_data)} 隻股票")
                show_walk_forward_results(results, float(wf_port_capital), is_portfolio=True)

    with st.expander("📖 如何解讀結果？"):
        st.markdown("""
        **退化率公式**：`(IS均回報 − OOS均回報) / |IS均回報| × 100%`

        **N/A**：IS 均回報 < 0.5% 時，退化率公式因分母趨近零而失效，顯示 N/A。此時只看 OOS 數值本身。

        **改進二（恒指過濾）的作用**：只在恒指 MA20 > MA60 的日子允許入場，過濾橫盤/熊市假訊號。
        預期效果：F3（2023年橫盤）虧損收窄或消失；代價是部分有效 Fold 的交易數會減少。

        **改進三（b8 個股趨勢確認）的作用**：額外要求個股本身在上升趨勢才入場。

        **min_hold_days（MIN30 等策略）的作用**：進場後若干個交易日內凍結策略 sell 訊號，
        只允許止損/止盈出場。用來過濾快死叉的假突破，例如 b1+b8/s6 原版 WF -0.70%
        但延伸追蹤 +5.72%，差異主要來自 14 天內 MACD 假死叉。
        """)
