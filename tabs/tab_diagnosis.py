# tabs/tab_diagnosis.py
import streamlit as st
import pandas as pd
import plotly.graph_objects as go

from data import batch_download
from indicators import precompute_signals
from config import (
    PRESET_NAMES, PRESET_CUSTOM, B_NAMES, S_NAMES,
)
from ui_components import get_preset_sigs, cache_banner


def render(stocks: list):
    st.subheader("📡 訊號頻率診斷")

    st.markdown("""
    > **用途**：掃描全市場，找出哪些股票對指定策略最「敏感」（訊號最多）。
    > **Walk-Forward 門檻**：每月平均訊號 ≥ **0.8 次**
    """)
    st.divider()

    st.markdown("#### 選擇要診斷的策略組合")
    dc1, dc2 = st.columns([2, 1])
    with dc1:
        preset_name = st.selectbox("⚡ 選擇預設組合", PRESET_NAMES, key="diag_preset")
    with dc2:
        diag_period = st.selectbox("診斷週期", ["1y","2y","3y"], index=1, key="diag_period")

    if preset_name == PRESET_CUSTOM:
        st.caption("🟢 買入策略")
        c1, c2 = st.columns(2)
        dbb1  = c1.checkbox("① 突破放量",    key="diag_bb1")
        dbb2  = c1.checkbox("② MA5金叉",      key="diag_bb2")
        dbb3  = c1.checkbox("③ 底背離",       key="diag_bb3")
        dbb4  = c1.checkbox("④ 底部突破MA20", key="diag_bb4")
        dbb5  = c1.checkbox("⑤ 布林下軌",     key="diag_bb5")
        dbb6  = c2.checkbox("⑥ RSI超賣",      key="diag_bb6")
        dbb7  = c2.checkbox("⑦ MACD金叉",     key="diag_bb7")
        dbb8  = c2.checkbox("⑧ 趨勢確認",     key="diag_bb8")
        dbb9  = c2.checkbox("⑨ 52週新高",     key="diag_bb9")
        dbb10 = c2.checkbox("⑩ 縮量回調",     key="diag_bb10")
        buy_sigs = (dbb1,dbb2,dbb3,dbb4,dbb5,dbb6,dbb7,dbb8,dbb9,dbb10)

        st.caption("🔴 賣出策略")
        d1, d2 = st.columns(2)
        dbs1 = d1.checkbox("⑪ 頭部跌破MA20", key="diag_bs1")
        dbs2 = d1.checkbox("⑫ 布林上軌",     key="diag_bs2")
        dbs3 = d1.checkbox("⑬ 上漲縮量",     key="diag_bs3")
        dbs4 = d1.checkbox("⑭ 放量急跌",     key="diag_bs4")
        dbs5 = d2.checkbox("⑮ RSI超買",      key="diag_bs5")
        dbs6 = d2.checkbox("⑯ MACD死叉",     key="diag_bs6")
        dbs7 = d2.checkbox("⑰ 三日陰線",     key="diag_bs7")
        sell_sigs = (dbs1,dbs2,dbs3,dbs4,dbs5,dbs6,dbs7)
    else:
        buy_sigs, sell_sigs = get_preset_sigs(preset_name, (False,)*10, (False,)*7)

    with st.expander("⚙️ 篩選參數", expanded=True):
        fc1, fc2, fc3 = st.columns(3)
        min_trades_wf   = fc1.number_input("WF 最低交易次數", min_value=1, value=10, step=1, key="diag_min_wf")
        min_trades_show = fc2.number_input("表格最低交易次數", min_value=1, value=3, step=1, key="diag_min_show")
        top_n_diag      = fc3.number_input("顯示前 N 名", min_value=5, value=30, step=5, key="diag_top_n")

    cache_banner()

    if st.button("📡 開始訊號頻率診斷", type="primary", key="run_diag"):
        if not any(buy_sigs):
            st.warning("⚠️ 請至少選擇一個買入策略"); return

        period_months = {"1y":12,"2y":24,"3y":36}[diag_period]
        cache = st.session_state.get("stock_cache", {})
        need_dl = [s for s in stocks if s not in cache]
        if need_dl:
            with st.spinner(f"下載 {len(need_dl)} 隻未緩存股票..."):
                extra = batch_download(need_dl, period=diag_period)
                cache.update(extra)
                st.session_state["stock_cache"] = cache

        diag_results = []
        pbar   = st.progress(0, text="診斷中...")
        status = st.empty()
        buy_active = [B_NAMES[k] for k, v in enumerate(buy_sigs) if v]

        for idx, ticker in enumerate(stocks):
            pbar.progress((idx+1)/len(stocks), text=f"診斷 {ticker} ({idx+1}/{len(stocks)})")
            status.text(f"⏳ {ticker}")
            df_s = cache.get(ticker)
            if df_s is None or df_s.empty or len(df_s) < 62:
                continue
            try:
                pre = precompute_signals(df_s)
                if not buy_active:
                    continue

                per_sig = {bk: int(pre[bk].sum()) for bk in buy_active}

                combined = pre[buy_active[0]].copy()
                for bk in buy_active[1:]:
                    combined = combined & pre[bk]
                combined_count = int(combined.sum())

                sell_active = [S_NAMES[k] for k, v in enumerate(sell_sigs) if v]
                sell_count = 0
                if sell_active:
                    sc = pre[sell_active[0]].copy()
                    for sk in sell_active[1:]:
                        sc = sc | pre[sk]
                    sell_count = int(sc.sum())

                if combined_count < min_trades_show:
                    continue

                avg_pm = round(combined_count / period_months, 2)
                wf_ok = avg_pm >= (min_trades_wf / period_months * (period_months/12))

                last_days = None
                if combined.any():
                    last_days = (df_s.index[-1] - combined[combined].index[-1]).days

                diag_results.append({
                    "代碼": ticker, "組合訊號數": combined_count,
                    "每月平均": avg_pm,
                    "WF適合度": "✅ 適合" if wf_ok else "⚠️ 不足",
                    "賣出訊號數": sell_count,
                    "距上次訊號(日)": last_days if last_days is not None else 999,
                    "數據長度(日)": len(df_s),
                    **{f"[{bk}]": per_sig.get(bk, 0) for bk in buy_active},
                })
            except Exception:
                continue

        pbar.empty(); status.empty()

        if not diag_results:
            st.warning("⚠️ 沒有股票達到最低訊號次數。")
            return

        diag_results.sort(key=lambda x: x["組合訊號數"], reverse=True)
        if top_n_diag > 0:
            diag_results = diag_results[:int(top_n_diag)]

        wf_count = sum(1 for r in diag_results if "✅" in r["WF適合度"])
        total_d  = len(diag_results)

        st.markdown(
            f"<div style='background:rgba(255,255,255,0.05);border-left:4px solid #f9a825;"
            f"padding:10px 16px;border-radius:6px;margin-bottom:12px'>"
            f"<b>📡 診斷完成</b>　有訊號：<b>{total_d}</b>　✅ 適合WF：<b>{wf_count}</b>　⚠️ 不足：<b>{total_d-wf_count}</b></div>",
            unsafe_allow_html=True,
        )

        display_cols = ["代碼","組合訊號數","每月平均","WF適合度","賣出訊號數","距上次訊號(日)","數據長度(日)"]
        breakdown = [c for c in diag_results[0].keys() if c.startswith("[")]
        df_diag = pd.DataFrame(diag_results)[display_cols + breakdown]

        def _cw(v):
            if "✅" in str(v): return "color:#26a69a;font-weight:bold"
            if "⚠️" in str(v): return "color:#f9a825"
            return ""

        st.dataframe(
            df_diag.style
                .map(_cw, subset=["WF適合度"])
                .format({"每月平均":"{:.2f}"}),
            use_container_width=True, hide_index=True,
            height=min(600, 36*len(df_diag)+40),
        )

        # 長條圖
        st.divider(); st.markdown("### 📊 每月平均訊號數分布")
        top20 = df_diag.head(20)
        threshold = min_trades_wf / period_months * (period_months/12)
        fig = go.Figure(go.Bar(
            x=top20["代碼"], y=top20["每月平均"],
            marker_color=["#26a69a" if r >= threshold else "#f9a825" for r in top20["每月平均"]],
            text=[f"{v:.2f}" for v in top20["每月平均"]], textposition="outside",
        ))
        fig.add_hline(y=threshold, line_dash="dot", line_color="#26a69a",
                      annotation_text=f"WF門檻 {threshold:.2f}/月", annotation_position="right")
        fig.update_layout(height=380, margin=dict(t=20,b=10), paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", yaxis_title="每月平均訊號數", xaxis_tickangle=-45)
        st.plotly_chart(fig, use_container_width=True)

        # WF 推薦
        wf_ready = df_diag[df_diag["WF適合度"].str.contains("✅")]
        if not wf_ready.empty:
            st.divider(); st.markdown("### 🎯 推薦用於 Walk-Forward 的股票")
            wf_tickers = wf_ready["代碼"].tolist()
            cols_per_row = 6
            for rs in range(0, len(wf_tickers), cols_per_row):
                chunk = wf_tickers[rs:rs+cols_per_row]
                cols = st.columns(cols_per_row)
                for col, tk in zip(cols, chunk):
                    r = wf_ready[wf_ready["代碼"]==tk].iloc[0]
                    col.metric(label=tk, value=f"{r['每月平均']:.2f}/月", delta=f"{int(r['組合訊號數'])}次/{diag_period}")
            st.info("💡 複製以上代碼，去「🔬 Walk-Forward」Tab 逐一驗證。")

            # 熱力圖
            st.divider(); st.markdown("### 🗓️ 訊號時間分布（前5隻）")
            month_labels = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]
            for tk in wf_tickers[:5]:
                df_tk = cache.get(tk)
                if df_tk is None or df_tk.empty:
                    continue
                try:
                    pre_tk = precompute_signals(df_tk)
                    sig_tk = pre_tk[buy_active[0]].copy()
                    for bk in buy_active[1:]:
                        sig_tk = sig_tk & pre_tk[bk]
                    sig_m = sig_tk.resample("ME").sum()
                    if sig_m.empty:
                        continue
                    years = sorted(sig_m.index.year.unique())
                    z, tz = [], []
                    for yr in years:
                        row, tr = [], []
                        for m in range(1, 13):
                            mask = (sig_m.index.year==yr) & (sig_m.index.month==m)
                            v = int(sig_m[mask].iloc[0]) if mask.any() else 0
                            row.append(v); tr.append(str(v) if v > 0 else "")
                        z.append(row); tz.append(tr)
                    fh = go.Figure(go.Heatmap(z=z, x=month_labels, y=[str(y) for y in years], text=tz, texttemplate="%{text}", textfont=dict(size=11), colorscale=[[0,"#1e1e2e"],[0.4,"#f9a825"],[1,"#26a69a"]], showscale=False))
                    fh.update_layout(title=dict(text=f"{tk} 訊號月分布", font=dict(size=13)), height=max(120,len(years)*40+60), margin=dict(t=35,b=5,l=50,r=10), paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", xaxis=dict(side="top"))
                    st.plotly_chart(fh, use_container_width=True)
                except Exception:
                    continue
        else:
            st.info("目前沒有股票達到 Walk-Forward 門檻。建議選單一條件或拉長週期。")

    with st.expander("📖 如何使用訊號頻率診斷？"):
        st.markdown("""
        **第一步**：選單一條件策略（如只勾「⑦ MACD金叉」）
        **第二步**：逐步加條件，觀察訊號數如何下降
        **第三步**：看時間分布熱力圖（均勻=穩健，集中=過擬合風險）
        **第四步**：去 Walk-Forward Tab 驗證推薦股票
        """)
