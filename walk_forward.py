# ══════════════════════════════════════════════════════════════════
# walk_forward.py — Walk-Forward 驗證引擎 & 報告渲染
# ══════════════════════════════════════════════════════════════════

import streamlit as st
import pandas as pd
import plotly.graph_objects as go

from indicators import calculate_indicators, precompute_signals
from backtest import run_backtest, calc_bt_metrics


def run_walk_forward(
    df: pd.DataFrame,
    buy_sigs: tuple, sell_sigs: tuple,
    is_months: int = 12,
    oos_months: int = 3,
    trade_size: float = 100_000,
    slippage: float = 0.002,
    stop_loss_pct: float = None,
    take_profit_pct: float = None,
    max_hold_days: int = None,
) -> list:
    if df.empty or len(df) < 60:
        return []

    results    = []
    total_days = len(df)
    is_days    = int(is_months  * 21)
    oos_days   = int(oos_months * 21)
    step       = oos_days
    fold       = 1
    start      = 0

    while start + is_days + oos_days <= total_days:
        is_df  = df.iloc[start : start + is_days].copy()
        oos_df = df.iloc[start + is_days : start + is_days + oos_days].copy()

        if len(is_df) < 62 or len(oos_df) < 10:
            break

        # IS
        pre_is = precompute_signals(is_df)
        is_trades, is_equity, _ = run_backtest(
            is_df, buy_sigs, sell_sigs,
            trade_size=trade_size, slippage=slippage,
            stop_loss_pct=stop_loss_pct,
            take_profit_pct=take_profit_pct,
            max_hold_days=max_hold_days,
            _precomputed=pre_is,
        )
        is_metrics = calc_bt_metrics(is_trades, is_equity, trade_size)

        # OOS
        warmup_start = max(0, start + is_days - 61)
        oos_full     = df.iloc[warmup_start : start + is_days + oos_days].copy()
        oos_full     = calculate_indicators(oos_full)

        oos_trades_all, _, _ = run_backtest(
            oos_full, buy_sigs, sell_sigs,
            trade_size=trade_size, slippage=slippage,
            stop_loss_pct=stop_loss_pct,
            take_profit_pct=take_profit_pct,
            max_hold_days=max_hold_days,
            _precomputed=None,
        )

        oos_start_date = oos_df.index[0]
        oos_trades = [t for t in oos_trades_all if t["_buy_date"] >= oos_start_date]

        if oos_trades:
            cum = 0.0
            sell_map: dict = {}
            for t in oos_trades:
                sd = t["賣出日期"].replace("（持倉中）", "")
                sell_map.setdefault(sd, []).append(t["回報%"])
            eq_rows = []
            for date in oos_df.index:
                d_str = date.strftime("%Y-%m-%d")
                if d_str in sell_map:
                    for r in sell_map[d_str]:
                        cum += r
                eq_rows.append({"date": date, "equity": trade_size * (1 + cum / 100)})
            oos_equity = pd.DataFrame(eq_rows).set_index("date")
        else:
            oos_equity = pd.DataFrame(
                {"equity": [trade_size] * len(oos_df)}, index=oos_df.index,
            )

        oos_metrics = calc_bt_metrics(oos_trades, oos_equity, trade_size)

        results.append({
            "fold": fold,
            "is_start":   is_df.index[0],  "is_end":   is_df.index[-1],
            "oos_start":  oos_df.index[0],  "oos_end":  oos_df.index[-1],
            "is_metrics":  is_metrics  or {},
            "oos_metrics": oos_metrics or {},
            "is_trades": is_trades, "oos_trades": oos_trades,
            "is_equity": is_equity, "oos_equity": oos_equity,
        })

        start += step
        fold  += 1

    return results


def _wf_degradation(is_ret: float, oos_ret: float) -> float:
    if abs(is_ret) < 1e-9:
        return 0.0
    return (is_ret - oos_ret) / abs(is_ret) * 100


def show_walk_forward_results(wf_results: list, trade_size: float):
    if not wf_results:
        st.warning("⚠️ 沒有足夠數據完成 Walk-Forward，請拉長回測週期或縮短 IS/OOS 窗口。")
        return

    # ── 1. 彙總表 ──────────────────────────────────────────────────
    rows = []
    for r in wf_results:
        im = r["is_metrics"]
        om = r["oos_metrics"]
        is_ret  = im.get("平均每筆回報%", 0.0)
        oos_ret = om.get("平均每筆回報%", 0.0)
        deg     = _wf_degradation(is_ret, oos_ret)
        rows.append({
            "Fold":        r["fold"],
            "IS 期間":     f"{r['is_start'].strftime('%Y-%m')} → {r['is_end'].strftime('%Y-%m')}",
            "OOS 期間":    f"{r['oos_start'].strftime('%Y-%m')} → {r['oos_end'].strftime('%Y-%m')}",
            "IS 均回報%":  round(is_ret, 2),
            "OOS 均回報%": round(oos_ret, 2),
            "退化率%":     round(deg, 1),
            "IS 勝率%":    round(im.get("勝率%", 0.0), 1),
            "OOS 勝率%":   round(om.get("勝率%", 0.0), 1),
            "IS 交易數":   im.get("交易次數", 0),
            "OOS 交易數":  om.get("交易次數", 0),
        })

    df_summary = pd.DataFrame(rows)

    # ── 2. 整體評分 ────────────────────────────────────────────────
    valid = [r for r in rows if r["IS 交易數"] >= 2]
    if not valid:
        st.warning("⚠️ 多數 Fold 交易次數不足，結果參考價值有限。")
        return

    avg_is  = sum(r["IS 均回報%"]  for r in valid) / len(valid)
    avg_oos = sum(r["OOS 均回報%"] for r in valid) / len(valid)
    avg_deg = sum(r["退化率%"]     for r in valid) / len(valid)
    oos_positive = sum(1 for r in valid if r["OOS 均回報%"] > 0)
    oos_rate     = oos_positive / len(valid) * 100

    if avg_oos > 0 and avg_deg < 40 and oos_rate >= 60:
        verdict, verdict_color = "🟢 策略穩健（具備真實 Alpha）", "#26a69a"
        verdict_detail = f"OOS 正回報比率 {oos_rate:.0f}%，退化率 {avg_deg:.1f}% < 40%，策略很可能在實盤有效。"
    elif avg_oos > 0 and avg_deg < 65 and oos_rate >= 50:
        verdict, verdict_color = "🟡 策略尚可（輕度過擬合）", "#f9a825"
        verdict_detail = f"OOS 仍有正回報但退化率 {avg_deg:.1f}% 偏高。建議加入更嚴格的條件或延長驗證期。"
    elif avg_oos <= 0:
        verdict, verdict_color = "🔴 策略危險（OOS 虧損）", "#ef5350"
        verdict_detail = f"OOS 平均回報 {avg_oos:.2f}%，策略在未見過的數據上虧損。這套策略不應實盤使用。"
    else:
        verdict, verdict_color = "🔴 策略過擬合（嚴重退化）", "#ef5350"
        verdict_detail = f"退化率 {avg_deg:.1f}% 過高，IS 回報無法在 OOS 重現。策略可能只是記住了歷史噪音。"

    st.markdown(
        f"<div style='background:rgba(255,255,255,0.05);"
        f"border-left:4px solid {verdict_color};"
        f"padding:12px 18px;border-radius:6px;margin-bottom:12px'>"
        f"<div style='font-size:20px;font-weight:bold'>{verdict}</div>"
        f"<div style='font-size:13px;margin-top:4px;opacity:0.85'>{verdict_detail}</div>"
        f"</div>",
        unsafe_allow_html=True,
    )

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("IS 平均每筆%",  f"{avg_is:+.2f}%")
    c2.metric("OOS 平均每筆%", f"{avg_oos:+.2f}%",
              delta=f"{avg_oos - avg_is:+.2f}%", delta_color="normal")
    c3.metric("平均退化率",    f"{avg_deg:.1f}%",
              delta="優" if avg_deg < 40 else ("可接受" if avg_deg < 65 else "過高"),
              delta_color="off")
    c4.metric("OOS 正回報 Fold", f"{oos_positive}/{len(valid)}")
    c5.metric("有效 Fold 數",  str(len(valid)))

    st.divider()

    # ── 3. IS vs OOS 長條圖 ───────────────────────────────────────
    st.markdown("### 📊 逐 Fold IS vs OOS 平均每筆回報%")
    fold_labels = [f"Fold {r['Fold']}\n{r['OOS 期間'].split(' → ')[0]}" for r in rows]
    fig_bar = go.Figure()
    fig_bar.add_trace(go.Bar(
        name="In-Sample", x=fold_labels,
        y=[r["IS 均回報%"] for r in rows],
        marker_color="rgba(100,180,255,0.7)",
        text=[f"{v:+.1f}%" for v in [r["IS 均回報%"] for r in rows]],
        textposition="outside",
    ))
    fig_bar.add_trace(go.Bar(
        name="Out-of-Sample", x=fold_labels,
        y=[r["OOS 均回報%"] for r in rows],
        marker_color=["#26a69a" if v >= 0 else "#ef5350" for v in [r["OOS 均回報%"] for r in rows]],
        text=[f"{v:+.1f}%" for v in [r["OOS 均回報%"] for r in rows]],
        textposition="outside",
    ))
    fig_bar.add_hline(y=0, line_dash="dash", line_color="rgba(255,255,255,0.3)")
    fig_bar.update_layout(
        barmode="group", height=380, margin=dict(t=20, b=20),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        yaxis_ticksuffix="%",
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
    )
    st.plotly_chart(fig_bar, use_container_width=True)

    # ── 4. 退化率趨勢線 ───────────────────────────────────────────
    st.markdown("### 📉 退化率趨勢（< 40% 為健康）")
    fig_deg = go.Figure()
    fig_deg.add_trace(go.Scatter(
        x=[f"Fold {r['Fold']}" for r in rows],
        y=[r["退化率%"] for r in rows],
        mode="lines+markers+text",
        text=[f"{v:.0f}%" for v in [r["退化率%"] for r in rows]],
        textposition="top center",
        line=dict(color="#f9a825", width=2),
        marker=dict(size=10,
                    color=["#26a69a" if v < 40 else ("#f9a825" if v < 65 else "#ef5350")
                           for v in [r["退化率%"] for r in rows]]),
    ))
    fig_deg.add_hline(y=40, line_dash="dot", line_color="rgba(38,166,154,0.6)",
                      annotation_text="40% 健康線", annotation_position="right")
    fig_deg.add_hline(y=65, line_dash="dot", line_color="rgba(239,83,80,0.6)",
                      annotation_text="65% 警戒線", annotation_position="right")
    fig_deg.update_layout(
        height=280, margin=dict(t=20, b=20),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        yaxis_ticksuffix="%", yaxis_title="退化率%",
    )
    st.plotly_chart(fig_deg, use_container_width=True)

    # ── 5. OOS 拼接資金曲線 ───────────────────────────────────────
    st.markdown("### 📈 OOS 拼接資金曲線（最真實的策略表現）")
    oos_equity_pieces = []
    running_capital = trade_size
    for r in wf_results:
        eq = r["oos_equity"]
        if eq.empty:
            continue
        scale = running_capital / trade_size
        piece = eq["equity"] * scale
        oos_equity_pieces.append(piece)
        running_capital = float(piece.iloc[-1])

    if oos_equity_pieces:
        oos_combined = pd.concat(oos_equity_pieces)
        oos_combined = oos_combined[~oos_combined.index.duplicated(keep='last')]
        oos_combined = oos_combined.sort_index()
        oos_norm = oos_combined / trade_size * 100 - 100

        fig_oos = go.Figure()
        fig_oos.add_trace(go.Scatter(
            x=oos_norm.index, y=oos_norm,
            name="OOS 累計回報%", fill="tozeroy",
            line=dict(color="#26a69a" if float(oos_norm.iloc[-1]) >= 0 else "#ef5350", width=2),
            fillcolor="rgba(38,166,154,0.12)" if float(oos_norm.iloc[-1]) >= 0 else "rgba(239,83,80,0.12)",
        ))
        fig_oos.add_hline(y=0, line_dash="dash", line_color="rgba(255,255,255,0.3)")
        total_oos_ret = float(oos_norm.iloc[-1])
        fig_oos.add_annotation(
            text=f"OOS 總回報：{total_oos_ret:+.1f}%",
            xref="paper", yref="paper", x=0.02, y=0.95, showarrow=False,
            font=dict(size=14, color="#26a69a" if total_oos_ret >= 0 else "#ef5350"),
        )
        fig_oos.update_layout(
            height=300, margin=dict(t=20, b=10),
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            yaxis_ticksuffix="%",
        )
        st.plotly_chart(fig_oos, use_container_width=True)

    # ── 6. 詳細彙總表 ─────────────────────────────────────────────
    st.divider()
    st.markdown("### 📑 逐 Fold 詳細數據")

    def _color_ret(val):
        try:
            v = float(val)
            if v > 0:  return "color:#26a69a;font-weight:bold"
            if v < 0:  return "color:#ef5350;font-weight:bold"
        except Exception:
            pass
        return ""

    def _color_deg(val):
        try:
            v = float(val)
            if v < 40:  return "color:#26a69a"
            if v < 65:  return "color:#f9a825"
            return "color:#ef5350;font-weight:bold"
        except Exception:
            pass
        return ""

    st.dataframe(
        df_summary.style
            .map(_color_ret, subset=["IS 均回報%", "OOS 均回報%"])
            .map(_color_deg, subset=["退化率%"])
            .format({
                "IS 均回報%":  "{:+.2f}%", "OOS 均回報%": "{:+.2f}%",
                "退化率%": "{:.1f}%", "IS 勝率%": "{:.1f}%", "OOS 勝率%": "{:.1f}%",
            }),
        use_container_width=True, hide_index=True,
    )

    # ── 7. 逐 Fold 展開詳情 ───────────────────────────────────────
    st.divider()
    st.markdown("### 🔬 逐 Fold 交易記錄")
    for r in wf_results:
        fold_n = r["fold"]
        im     = r["is_metrics"]
        om     = r["oos_metrics"]
        with st.expander(
            f"Fold {fold_n}  ｜  OOS: {r['oos_start'].strftime('%Y-%m-%d')} → "
            f"{r['oos_end'].strftime('%Y-%m-%d')}  ｜  "
            f"IS {im.get('平均每筆回報%', 0):+.2f}%  →  OOS {om.get('平均每筆回報%', 0):+.2f}%"
        ):
            col_is, col_oos = st.columns(2)
            with col_is:
                st.markdown("**📘 In-Sample**")
                if im:
                    st.metric("均回報%",  f"{im.get('平均每筆回報%', 0):+.2f}%")
                    st.metric("勝率",     f"{im.get('勝率%', 0):.1f}%")
                    st.metric("交易次數", f"{im.get('交易次數', 0)}")
                    st.metric("Profit F", f"{im.get('Profit Factor', 0):.2f}" if im.get('Profit Factor') != float('inf') else "∞")
                    st.metric("最大回撤", f"{im.get('最大回撤%', 0):.2f}%")
                else:
                    st.info("無交易")
            with col_oos:
                st.markdown("**📗 Out-of-Sample**")
                if om:
                    oos_ret = om.get('平均每筆回報%', 0)
                    st.metric("均回報%",  f"{oos_ret:+.2f}%",
                              delta=f"退化 {_wf_degradation(im.get('平均每筆回報%',0), oos_ret):.1f}%",
                              delta_color="off")
                    st.metric("勝率",     f"{om.get('勝率%', 0):.1f}%")
                    st.metric("交易次數", f"{om.get('交易次數', 0)}")
                    st.metric("Profit F", f"{om.get('Profit Factor', 0):.2f}" if om.get('Profit Factor') != float('inf') else "∞")
                    st.metric("最大回撤", f"{om.get('最大回撤%', 0):.2f}%")
                else:
                    st.info("無交易（OOS 期間無訊號）")

            if r["oos_trades"]:
                display_cols = ["買入日期","賣出日期","買入價","賣出價",
                                "回報%","盈虧(HKD)","持倉天數","賣出原因"]
                df_t = pd.DataFrame(r["oos_trades"])[display_cols]
                def _cr(val):
                    try:
                        v = float(val)
                        return "color:#26a69a" if v > 0 else ("color:#ef5350" if v < 0 else "")
                    except Exception:
                        return ""
                st.dataframe(
                    df_t.style.map(_cr, subset=["回報%","盈虧(HKD)"]),
                    use_container_width=True, hide_index=True,
                )
