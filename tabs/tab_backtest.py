# tabs/tab_backtest.py

# 

# V18 修復（2026-04-27）— 來自 V17.0 策略複審報告：

# 🔴-3：自定義模式 buy_custom 擴到 11 元素（補 b11）、sell_custom 擴到 8 元素（補 s8）

# 🟡-1：滑桿預設從 0.20% 改為 0.10%，與 tab_walkforward 一致；

# backtest.py 自動疊加 0.13% commission，總成本單邊 0.23% / 雙邊 0.46%

import streamlit as st
import pandas as pd
import plotly.graph_objects as go

from data import get_stock_data, get_cached, batch_download
from indicators import calculate_indicators, precompute_signals
from backtest import run_backtest, calc_bt_metrics, run_grid_search
from charts import show_backtest_chart
from ui_components import (
preset_selector, get_preset_sigs, cache_banner,
render_single_bt_result,
)

def render(stocks: list):
st.subheader(“📊 策略回測系統 V18”)

```
bt_mode = st.radio(
    "回測模式",
    ["🔍 單股回測", "🚀 全倉掃描回測（所有股票）"],
    horizontal=True, key="bt_mode",
)
st.divider()

st.markdown("#### 🟢 買入策略")
_preset, _custom = preset_selector("tab5")

if _custom:
    st.markdown("#### 🟢 買入策略（自定義）")
    bc1, bc2 = st.columns(2)
    bb1  = bc1.checkbox("① 突破阻力位 + 放量",       key="bb1")
    bb2  = bc1.checkbox("② MA5 金叉 MA20",            key="bb2")
    bb3  = bc1.checkbox("③ 底背離（MACD未新低）",     key="bb3")
    bb4  = bc1.checkbox("④ 底部形態突破 MA20",        key="bb4")
    bb5  = bc1.checkbox("⑤ 布林帶下軌（牛市過濾）",  key="bb5")
    bb6  = bc2.checkbox("⑥ RSI 超賣（< 30，牛市）",  key="bb6")
    bb7  = bc2.checkbox("⑦ MACD 金叉",                key="bb7")
    bb8  = bc2.checkbox("⑧ 個股趨勢確認 MA20>MA60",  key="bb8")
    bb9  = bc2.checkbox("⑨ 52週新高突破",             key="bb9")
    bb10 = bc2.checkbox("⑩ 縮量回調至 MA20",         key="bb10")
    # 🔴-3 V18：補 b11
    bb11 = bc2.checkbox("⑪ KDJ 超賣金叉（K<20, D<20, K上穿D）", key="bb11")
    buy_custom = (bb1, bb2, bb3, bb4, bb5, bb6, bb7, bb8, bb9, bb10, bb11)

    st.markdown("#### 🔴 賣出策略（自定義）")
    st.caption("⚠️ 若不勾選任何賣出策略，只靠止損 / 止盈 / 最長持倉天數出場")
    sc1, sc2 = st.columns(2)
    bs1 = sc1.checkbox("⑫ 頭部跌破 MA20（放量）",  key="bs1")
    bs2 = sc1.checkbox("⑬ 布林帶上軌賣出",          key="bs2")
    bs3 = sc1.checkbox("⑭ 上漲縮量警惕頂部",        key="bs3")
    bs4 = sc1.checkbox("⑮ 放量急跌",                key="bs4")
    bs5 = sc2.checkbox("⑯ RSI 超買（> 70）",        key="bs5")
    bs6 = sc2.checkbox("⑰ MACD 死叉",               key="bs6")
    bs7 = sc2.checkbox("⑱ 三日陰線 + 跌破MA20",     key="bs7")
    # 🔴-3 V18：補 s8
    bs8 = sc2.checkbox("⑲ KDJ 高位死叉（K>80, D>80, K下穿D）", key="bs8")
    sell_custom = (bs1, bs2, bs3, bs4, bs5, bs6, bs7, bs8)
else:
    # 🔴-3 V18：(False,)*10/7 → (False,)*11/8
    buy_custom  = (False,) * 11
    sell_custom = (False,) * 8

buy_sigs, sell_sigs = get_preset_sigs(_preset, buy_custom, sell_custom)
st.divider()

# ── 回測參數 ──────────────────────────────────────────────────
with st.expander("⚙️ 回測參數", expanded=True):
    p1, p2 = st.columns(2)
    with p1:
        bt_period   = st.selectbox("回測週期", ["1y","2y","5y"], index=1, key="bt_period")
        bt_capital  = st.number_input("每筆交易金額 (HKD)", value=100_000, step=10_000, min_value=10_000, key="bt_capital")
        # 🟡-1 V18：滑桿預設 0.20 → 0.10，明確化文案
        bt_slippage = st.slider(
            "純滑點 % (不含手續費)", 0.0, 1.0, 0.10, 0.05, key="bt_slippage",
            help="這只是純價格滑點，0.13% 手續費（印花稅+佣金+交易費）會由 backtest 自動疊加。"
                 "預設 0.10% + 0.13% = 單邊 0.23% / 雙邊 0.46%（貼合港股實盤）",
        ) / 100
    with p2:
        bt_sl      = st.number_input("止損 %（0=不啟用）", value=0.0, step=1.0, min_value=0.0, max_value=50.0, key="bt_sl")
        bt_tp      = st.number_input("止盈 %（0=不啟用）", value=0.0, step=5.0, min_value=0.0, max_value=200.0, key="bt_tp")
        bt_maxdays = st.number_input("最長持倉天數（0=不限）", value=0, step=5, min_value=0, key="bt_maxdays")

    if bt_mode == "🔍 單股回測":
        bt_ticker = st.text_input("股票代碼", value="0700.HK", key="bt_ticker").upper()
    else:
        bt_min_trades = st.number_input("最少交易次數篩選", value=2, min_value=1, step=1, key="bt_min_trades")
        bt_sort_col   = st.selectbox("排行榜排序依據", ["平均每筆%","勝率%","Profit F","交易次數","最大回撤%"], key="bt_sort_col")
        bt_top_charts = st.number_input("自動展示前 N 名 K 線圖（0=不展示）", value=3, min_value=0, max_value=10, key="bt_top_charts")

sl_val = bt_sl     if bt_sl     > 0 else None
tp_val = bt_tp     if bt_tp     > 0 else None
md_val = int(bt_maxdays) if bt_maxdays > 0 else None

# ══════════════════════════════════════════════════════════════
# 單股回測
# ══════════════════════════════════════════════════════════════
if bt_mode == "🔍 單股回測":
    col_run, col_gs = st.columns(2)
    run_btn = col_run.button("🚀 開始單股回測", type="primary", key="run_bt_single")
    gs_btn  = col_gs.button("🔁 網格搜索最佳參數", key="run_gs")

    if run_btn:
        if not any(buy_sigs):
            st.warning("⚠️ 請至少勾選一個買入策略"); return
        if not any(sell_sigs) and not bt_sl and not bt_tp and not bt_maxdays:
            st.warning("⚠️ 請設定至少一種出場條件"); return

        with st.spinner(f"正在下載 {bt_ticker} 並執行回測..."):
            df_bt     = get_stock_data(bt_ticker, period=bt_period)
            df_hsi_bt = get_stock_data("^HSI",    period=bt_period)

        if df_bt.empty:
            st.error(f"❌ 無法取得 {bt_ticker} 數據"); return

        df_bt = calculate_indicators(df_bt)
        trades, equity_df, _ = run_backtest(
            df_bt, buy_sigs, sell_sigs,
            trade_size=float(bt_capital), slippage=bt_slippage,
            stop_loss_pct=sl_val, take_profit_pct=tp_val, max_hold_days=md_val,
        )
        metrics = calc_bt_metrics(trades, equity_df, float(bt_capital))
        if not metrics:
            st.warning("⚠️ 回測期間內沒有觸發任何交易"); return
        render_single_bt_result(bt_ticker, metrics, equity_df, df_bt, trades, float(bt_capital), df_hsi_bt)

    if gs_btn:
        if not any(buy_sigs):
            st.warning("⚠️ 請至少勾選一個買入策略"); return
        with st.spinner(f"正在下載 {bt_ticker}..."):
            df_gs = get_stock_data(bt_ticker, period=bt_period)
        if df_gs.empty:
            st.error(f"❌ 無法取得 {bt_ticker} 數據"); return
        df_gs = calculate_indicators(df_gs)
        st.divider(); st.markdown("### 🔁 網格搜索結果")
        gs_sort = st.selectbox("排序指標", ["平均每筆%","勝率%","Profit F","交易次數","最大回撤%"], key="gs_sort")
        df_gs_r = run_grid_search(df_gs, buy_sigs, sell_sigs, trade_size=float(bt_capital), slippage=bt_slippage, sort_metric=gs_sort)
        if df_gs_r.empty:
            st.warning("⚠️ 所有組合均無交易"); return
        def _gs_c(val):
            try:
                v = float(val)
                if v > 0: return "color:#26a69a;font-weight:bold"
                if v < 0: return "color:#ef5350"
            except Exception: pass
            return ""
        st.dataframe(df_gs_r.head(20).style.map(_gs_c, subset=["平均每筆%"]).format({"平均每筆%":"{:+.2f}%","勝率%":"{:.1f}%","最大回撤%":"{:.2f}%","Profit F":"{:.2f}"}), use_container_width=True, hide_index=True)
        best = df_gs_r.iloc[0]
        st.success(f"🏆 最佳組合（按{gs_sort}）：止損 {best['止損%']} ｜ 止盈 {best['止盈%']} ｜ 最長持倉 {best['最長持倉']} ｜ 平均每筆 {best['平均每筆%']:+.2f}% ｜ 勝率 {best['勝率%']:.1f}%")

# ══════════════════════════════════════════════════════════════
# 全倉掃描回測
# ══════════════════════════════════════════════════════════════
else:
    cache_banner()
    n_stocks = len(stocks)
    st.info(f"📋 將對 **{n_stocks} 隻**股票套用相同策略進行回測。")
    run_batch = st.button(f"🚀 開始全倉掃描回測（{n_stocks} 隻）", type="primary", key="run_bt_batch")

    if run_batch:
        if not any(buy_sigs):
            st.warning("⚠️ 請至少勾選一個買入策略"); return
        if not any(sell_sigs) and not bt_sl and not bt_tp and not bt_maxdays:
            st.warning("⚠️ 請設定至少一種出場條件"); return

        cache = st.session_state.get("stock_cache", {})
        need_dl = [s for s in stocks if s not in cache]
        if need_dl:
            with st.spinner(f"批量下載 {len(need_dl)} 隻未緩存股票..."):
                extra = batch_download(need_dl, period=bt_period)
                cache.update(extra)
                st.session_state["stock_cache"] = cache

        df_hsi_bt = get_stock_data("^HSI", period=bt_period)
        batch_results, batch_dfs, batch_trades, batch_equities = [], {}, {}, {}
        pbar   = st.progress(0, text="準備中...")
        status = st.empty()

        for idx, ticker in enumerate(stocks):
            pbar.progress((idx+1)/n_stocks, text=f"回測 {ticker} ({idx+1}/{n_stocks})")
            status.text(f"⏳ {ticker}")
            df_s = cache.get(ticker)
            if df_s is None or df_s.empty or len(df_s) < 62:
                continue
            try:
                pre_s = precompute_signals(df_s)
                t_s, eq_s, _ = run_backtest(
                    df_s, buy_sigs, sell_sigs,
                    trade_size=float(bt_capital), slippage=bt_slippage,
                    stop_loss_pct=sl_val, take_profit_pct=tp_val, max_hold_days=md_val,
                    _precomputed=pre_s,
                )
                m = calc_bt_metrics(t_s, eq_s, float(bt_capital))
                if not m or m["交易次數"] < bt_min_trades:
                    continue
                batch_results.append({
                    "代碼": ticker, "平均每筆%": m["平均每筆回報%"],
                    "勝率%": m["勝率%"], "交易次數": m["交易次數"],
                    "Profit F": m["Profit Factor"], "最大回撤%": m["最大回撤%"],
                    "最大連輸": m["最大連輸"], "平均持倉天": m["平均持倉天數"],
                })
                batch_dfs[ticker]      = df_s
                batch_trades[ticker]   = t_s
                batch_equities[ticker] = eq_s
            except Exception:
                continue

        pbar.empty(); status.empty()

        if not batch_results:
            st.warning("⚠️ 沒有任何股票符合條件"); return

        df_rank = pd.DataFrame(batch_results)
        sort_asc = (bt_sort_col == "最大回撤%")
        df_rank  = df_rank.sort_values(bt_sort_col, ascending=sort_asc).reset_index(drop=True)
        df_rank.index += 1

        n_pos = int((df_rank["平均每筆%"] > 0).sum())
        n_neg = int((df_rank["平均每筆%"] <= 0).sum())
        avg_r = float(df_rank["平均每筆%"].mean())

        st.divider()
        st.markdown("### 🏆 全倉掃描回測結果")
        st.markdown(
            f"<div style='background:rgba(255,255,255,0.05);border-left:4px solid #f9a825;"
            f"padding:10px 16px;border-radius:6px;font-size:16px;font-weight:bold'>"
            f"📊 共回測 <b>{len(batch_results)}</b> 隻 ｜ 🟢 正回報 <b>{n_pos}</b> ｜ 🔴 負回報 <b>{n_neg}</b> ｜ 平均每筆 <b>{avg_r:+.2f}%</b></div>",
            unsafe_allow_html=True,
        )
        st.write("")

        def _cv(val):
            try:
                v = float(val)
                if v > 0: return "color:#26a69a;font-weight:bold"
                if v < 0: return "color:#ef5350;font-weight:bold"
            except Exception: pass
            return ""

        st.dataframe(
            df_rank.style
                .map(_cv, subset=["平均每筆%","勝率%"])
                .map(lambda v: "color:#ef5350;font-weight:bold" if isinstance(v,(int,float)) and v<-15 else "", subset=["最大回撤%"])
                .format({"平均每筆%":"{:+.2f}%","勝率%":"{:.1f}%","Profit F":"{:.2f}","最大回撤%":"{:.2f}%","平均持倉天":"{:.0f}"}),
            use_container_width=True, height=min(600, 35*len(df_rank)+40),
        )

        # 分布圖
        st.divider(); st.markdown("### 📊 平均每筆回報分布")
        colors_bar = ["#26a69a" if v > 0 else "#ef5350" for v in df_rank["平均每筆%"]]
        fig_bar = go.Figure(go.Bar(
            x=df_rank["代碼"], y=df_rank["平均每筆%"],
            marker_color=colors_bar,
            text=[f"{v:+.1f}%" for v in df_rank["平均每筆%"]],
            textposition="outside",
        ))
        fig_bar.update_layout(height=350, margin=dict(t=10,b=10), paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", yaxis_ticksuffix="%", xaxis_tickangle=-45, yaxis_title="平均每筆回報%")
        st.plotly_chart(fig_bar, use_container_width=True)

        if bt_top_charts > 0:
            st.divider()
            st.markdown(f"### 🎯 前 {bt_top_charts} 名 K 線標記圖")
            for tk in df_rank["代碼"].head(int(bt_top_charts)).tolist():
                m_r = next(r for r in batch_results if r["代碼"] == tk)
                ret = m_r["平均每筆%"]
                icon = "🟢" if ret > 0 else "🔴"
                st.markdown(f"**{icon} {tk}**　平均每筆 {ret:+.2f}%　勝率 {m_r['勝率%']:.1f}%　交易 {m_r['交易次數']} 次　PF {m_r['Profit F']:.2f}")
                show_backtest_chart(batch_dfs[tk], batch_trades[tk])
                st.write("")

        st.session_state["bt_batch_results"]  = batch_results
        st.session_state["bt_batch_dfs"]      = batch_dfs
        st.session_state["bt_batch_trades"]   = batch_trades
        st.session_state["bt_batch_equities"] = batch_equities

        # 深挖
        st.divider(); st.markdown("### 🔬 單股深挖")
        drill_opts = df_rank["代碼"].tolist()
        drill_tk   = st.selectbox("選擇股票查看詳細回測結果", drill_opts, key="bt_drill")
        if st.button("📋 查看詳細結果", key="bt_drill_btn"):
            d_m = calc_bt_metrics(batch_trades[drill_tk], batch_equities[drill_tk], float(bt_capital))
            render_single_bt_result(drill_tk, d_m, batch_equities[drill_tk], batch_dfs[drill_tk], batch_trades[drill_tk], float(bt_capital), df_hsi_bt)
```
