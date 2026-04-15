# tabs/tab_walkforward.py
import streamlit as st
from data import get_stock_data
from indicators import calculate_indicators
from walk_forward import run_walk_forward, run_portfolio_walk_forward, show_walk_forward_results
from ui_components import preset_selector, get_preset_sigs


def render(stocks: list):
    st.subheader("🔬 Walk-Forward 驗證")
    st.markdown("""
    > **原理**：把歷史數據切成多個時間窗口，每個窗口分為 In-Sample（IS）和 Out-of-Sample（OOS）。

    | 退化率 | 意義 |
    |--------|------|
    | < 40%  | 🟢 策略穩健 |
    | 40-65% | 🟡 輕度過擬合 |
    | > 65%  | 🔴 嚴重過擬合 |
    | OOS < 0 | 🔴 危險 |
    | N/A    | IS≈0，退化率公式失效 |
    """)
    st.divider()

    wf_mode = st.radio("驗證模式", ["🔍 單股模式", "📊 投資組合模式"],
                       horizontal=True, key="wf_mode")
    st.divider()

    _preset, _custom = preset_selector("wf")
    if _custom:
        st.markdown("#### 🟢 買入策略（自定義）")
        c1, c2 = st.columns(2)
        b1  = c1.checkbox("① 突破放量",    key="wf_bb1")
        b2  = c1.checkbox("② MA5金叉",     key="wf_bb2")
        b3  = c1.checkbox("③ 底背離",      key="wf_bb3")
        b4  = c1.checkbox("④ 底部突破",    key="wf_bb4")
        b5  = c1.checkbox("⑤ 布林下軌",    key="wf_bb5")
        b6  = c2.checkbox("⑥ RSI超賣",     key="wf_bb6")
        b7  = c2.checkbox("⑦ MACD金叉",    key="wf_bb7")
        b8  = c2.checkbox("⑧ 趨勢確認",    key="wf_bb8")
        b9  = c2.checkbox("⑨ 52週新高",    key="wf_bb9")
        b10 = c2.checkbox("⑩ 縮量回調",    key="wf_bb10")
        buy_custom = (b1,b2,b3,b4,b5,b6,b7,b8,b9,b10)
        st.markdown("#### 🔴 賣出策略（自定義）")
        d1, d2 = st.columns(2)
        s1 = d1.checkbox("⑪ 頭部破MA20",  key="wf_bs1")
        s2 = d1.checkbox("⑫ 布林上軌",    key="wf_bs2")
        s3 = d1.checkbox("⑬ 上漲縮量",    key="wf_bs3")
        s4 = d1.checkbox("⑭ 放量急跌",    key="wf_bs4")
        s5 = d2.checkbox("⑮ RSI超買",     key="wf_bs5")
        s6 = d2.checkbox("⑯ MACD死叉",    key="wf_bs6")
        s7 = d2.checkbox("⑰ 三日陰線",    key="wf_bs7")
        sell_custom = (s1,s2,s3,s4,s5,s6,s7)
    else:
        buy_custom = sell_custom = None

    buy_sigs, sell_sigs = get_preset_sigs(_preset, buy_custom or (False,)*10, sell_custom or (False,)*7)
    st.divider()

    # ── 單股模式 ──────────────────────────────────────────────────
    if wf_mode == "🔍 單股模式":
        with st.expander("⚙️ 參數", expanded=True):
            c1, c2 = st.columns(2)
            with c1:
                ticker    = st.text_input("股票代碼", value="0700.HK", key="wf_ticker").upper()
                period    = st.selectbox("總數據週期", ["3y","5y","10y"], index=1, key="wf_period")
                is_m      = st.slider("IS 窗口（月）", 6, 24, 12, 3, key="wf_is")
                oos_m     = st.slider("OOS 窗口（月）", 1, 12, 3, 1, key="wf_oos")
            with c2:
                capital   = st.number_input("每筆交易金額", value=100_000, step=10_000, key="wf_cap")
                slip      = st.slider("滑點 (%)", 0.0, 1.0, 0.20, 0.05, key="wf_slip") / 100
                sl        = st.number_input("止損 %（0=不啟用）", value=0.0, step=1.0, key="wf_sl")
                tp        = st.number_input("止盈 %（0=不啟用）", value=0.0, step=5.0, key="wf_tp")
                maxd      = st.number_input("最長持倉天數（0=不限）", value=0, step=5, key="wf_maxd")
                min_oos   = st.number_input("最低有效 OOS 交易數", value=3, min_value=1, key="wf_min")
            total_m = {"3y":36,"5y":60,"10y":120}[period]
            est     = max(0, (total_m - is_m) // oos_m)
            st.info(f"預計約 **{est} 個 Fold**")

        if st.button("🔬 開始 Walk-Forward", type="primary", key="run_wf"):
            if not any(buy_sigs): st.warning("⚠️ 請勾選至少一個買入策略"); return
            if est < 2: st.warning("⚠️ Fold 數不足 2"); return
            with st.spinner(f"下載 {ticker}..."):
                df = get_stock_data(ticker, period=period)
            if df.empty: st.error(f"❌ 無法取得 {ticker}"); return
            df = calculate_indicators(df)
            with st.spinner("執行中..."):
                results = run_walk_forward(df, buy_sigs, sell_sigs,
                    is_months=is_m, oos_months=oos_m,
                    trade_size=float(capital), slippage=slip,
                    stop_loss_pct=sl if sl>0 else None,
                    take_profit_pct=tp if tp>0 else None,
                    max_hold_days=int(maxd) if maxd>0 else None,
                    min_oos_trades=int(min_oos))
            if results:
                st.success(f"✅ 完成！{len(results)} 個 Fold")
                show_walk_forward_results(results, float(capital), is_portfolio=False)
            else:
                st.warning("⚠️ 未能生成任何 Fold")

    # ── 投資組合模式 ──────────────────────────────────────────────
    else:
        col_a, col_b = st.columns([3,1])
        with col_a:
            use_all = st.checkbox("使用完整股票清單", value=True, key="wf_all")
            if not use_all:
                port_stocks = st.multiselect("選擇股票", stocks, default=stocks[:15], key="wf_stocks")
            else:
                port_stocks = stocks
        with col_b:
            n = len(port_stocks) if not use_all else len(stocks)
            st.metric("選中股票數", n)

        with st.expander("⚙️ 參數", expanded=True):
            c1, c2 = st.columns(2)
            with c1:
                period_p  = st.selectbox("總數據週期", ["3y","5y","10y"], index=1, key="wf_pp")
                is_mp     = st.slider("IS 窗口（月）", 6, 24, 12, 3, key="wf_isp")
                oos_mp    = st.slider("OOS 窗口（月）", 3, 12, 6, 1, key="wf_oosp")
                min_oos_p = st.number_input("最低有效 OOS 交易數", value=5, min_value=1, key="wf_minp")
            with c2:
                capital_p = st.number_input("每筆交易金額", value=100_000, step=10_000, key="wf_capp")
                slip_p    = st.slider("滑點 (%)", 0.0, 1.0, 0.20, 0.05, key="wf_slipp") / 100
                sl_p      = st.number_input("止損 %（0=不啟用）", value=0.0, step=1.0, key="wf_slp")
                tp_p      = st.number_input("止盈 %（0=不啟用）", value=0.0, step=5.0, key="wf_tpp")
                maxd_p    = st.number_input("最長持倉天數（0=不限）", value=0, step=5, key="wf_maxdp")
            total_mp = {"3y":36,"5y":60,"10y":120}[period_p]
            est_p    = max(0, (total_mp - is_mp) // oos_mp)
            n_sel    = n
            st.info(f"預計約 **{est_p} 個 Fold** × {n_sel} 隻股票")

        final_stocks = port_stocks if not use_all else stocks
        if st.button(f"📊 開始投資組合 WF（{len(final_stocks)} 隻）", type="primary", key="run_wfp"):
            if not any(buy_sigs): st.warning("⚠️ 請勾選至少一個買入策略"); return
            if est_p < 2: st.warning("⚠️ Fold 數不足 2"); return

            stock_data = {}
            with st.spinner(f"下載 {len(final_stocks)} 隻股票..."):
                pb = st.progress(0)
                for i, t in enumerate(final_stocks):
                    pb.progress((i+1)/len(final_stocks), text=f"下載 {t}...")
                    df_t = get_stock_data(t, period=period_p)
                    if not df_t.empty and len(df_t) >= 62:
                        stock_data[t] = calculate_indicators(df_t)
                pb.empty()

            if not stock_data: st.error("❌ 無法取得數據"); return
            st.info(f"成功下載 {len(stock_data)}/{len(final_stocks)} 隻")

            results = run_portfolio_walk_forward(stock_data, buy_sigs, sell_sigs,
                is_months=is_mp, oos_months=oos_mp,
                trade_size=float(capital_p), slippage=slip_p,
                stop_loss_pct=sl_p if sl_p>0 else None,
                take_profit_pct=tp_p if tp_p>0 else None,
                max_hold_days=int(maxd_p) if maxd_p>0 else None,
                min_oos_trades=int(min_oos_p))

            if results:
                st.success(f"✅ 完成！{len(results)} 個 Fold，{len(stock_data)} 隻股票")
                show_walk_forward_results(results, float(capital_p), is_portfolio=True)
            else:
                st.warning("⚠️ 未能生成任何 Fold")
