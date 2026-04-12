# ══════════════════════════════════════════════════════════════════

# walk_forward.py — Walk-Forward 驗證引擎 & 報告渲染

# ══════════════════════════════════════════════════════════════════

import streamlit as st
import pandas as pd
import plotly.graph_objects as go

from indicators import calculate_indicators, precompute_signals
from backtest import run_backtest, calc_bt_metrics

# ══════════════════════════════════════════════════════════════════

# 單股 Walk-Forward（含 Fix 5：min_oos_trades 門檻）

# ══════════════════════════════════════════════════════════════════

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
min_oos_trades: int = 3,
) -> list:
if df.empty or len(df) < 60:
return []

```
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

    pre_is = precompute_signals(is_df)
    is_trades, is_equity, _ = run_backtest(
        is_df, buy_sigs, sell_sigs,
        trade_size=trade_size, slippage=slippage,
        stop_loss_pct=stop_loss_pct, take_profit_pct=take_profit_pct,
        max_hold_days=max_hold_days, _precomputed=pre_is,
    )
    is_metrics = calc_bt_metrics(is_trades, is_equity, trade_size)

    warmup_start = max(0, start + is_days - 61)
    oos_full     = df.iloc[warmup_start : start + is_days + oos_days].copy()
    oos_full     = calculate_indicators(oos_full)

    oos_trades_all, _, _ = run_backtest(
        oos_full, buy_sigs, sell_sigs,
        trade_size=trade_size, slippage=slippage,
        stop_loss_pct=stop_loss_pct, take_profit_pct=take_profit_pct,
        max_hold_days=max_hold_days, _precomputed=None,
    )

    oos_start_date = oos_df.index[0]
    oos_trades = [t for t in oos_trades_all if t["_buy_date"] >= oos_start_date]

    if oos_trades:
        sell_map: dict = {}
        for t in oos_trades:
            sell_map.setdefault(t["_sell_date"], []).append(t["回報%"])
        running_capital = trade_size
        eq_rows = []
        for date in oos_df.index:
            if date in sell_map:
                for pnl_pct in sell_map[date]:
                    running_capital *= (1 + pnl_pct / 100)
            eq_rows.append({"date": date, "equity": running_capital})
        oos_equity = pd.DataFrame(eq_rows).set_index("date")
    else:
        oos_equity = pd.DataFrame(
            {"equity": [trade_size] * len(oos_df)}, index=oos_df.index,
        )

    oos_metrics  = calc_bt_metrics(oos_trades, oos_equity, trade_size)
    oos_closed   = [t for t in oos_trades if "（持倉中）" not in t["賣出日期"]]
    valid_oos    = len(oos_closed) >= min_oos_trades

    results.append({
        "fold":            fold,
        "is_start":        is_df.index[0],  "is_end":   is_df.index[-1],
        "oos_start":       oos_df.index[0], "oos_end":  oos_df.index[-1],
        "is_metrics":      is_metrics  or {},
        "oos_metrics":     oos_metrics or {},
        "is_trades":       is_trades,
        "oos_trades":      oos_trades,
        "is_equity":       is_equity,
        "oos_equity":      oos_equity,
        "valid_oos":       valid_oos,
        "oos_trade_count": len(oos_closed),
        "n_stocks":        1,
    })

    start += step
    fold  += 1

return results
```

# ══════════════════════════════════════════════════════════════════

# FIX 4：投資組合 Walk-Forward

# ══════════════════════════════════════════════════════════════════

def _build_portfolio_equity(
trades: list,
date_range: pd.DatetimeIndex,
trade_size: float,
) -> pd.DataFrame:
“””
投資組合 equity curve（HKD P&L 累加法）。
每筆交易獨立佔用 trade_size，盈虧以 HKD 疊加。
equity = trade_size + cumulative_pnl_hkd
“””
if len(date_range) == 0:
return pd.DataFrame()

```
sell_map: dict = {}
for t in trades:
    if "（持倉中）" not in t.get("賣出日期", ""):
        pnl_hkd = trade_size * t["回報%"] / 100
        sell_map.setdefault(t["_sell_date"], []).append(pnl_hkd)

running_pnl = 0.0
eq_rows = []
for date in date_range:
    if date in sell_map:
        running_pnl += sum(sell_map[date])
    eq_rows.append({"date": date, "equity": trade_size + running_pnl})

return pd.DataFrame(eq_rows).set_index("date")
```

def run_portfolio_walk_forward(
stock_data: dict,
buy_sigs: tuple,
sell_sigs: tuple,
is_months: int = 12,
oos_months: int = 6,
trade_size: float = 100_000,
slippage: float = 0.002,
stop_loss_pct: float = None,
take_profit_pct: float = None,
max_hold_days: int = None,
min_oos_trades: int = 5,
) -> list:
“””
投資組合級別 Walk-Forward。
聚合所有股票的交易解決單股樣本不足問題。
IS/OOS 按日曆日期對齊所有股票，equity 用 HKD P&L 累加。
“””
if not stock_data:
return []

```
ref_df     = max(stock_data.values(), key=len)
all_dates  = ref_df.index
total_days = len(all_dates)
is_days    = int(is_months  * 21)
oos_days   = int(oos_months * 21)

if total_days < is_days + oos_days:
    return []

results        = []
fold           = 1
start          = 0
n_total_folds  = max(1, (total_days - is_days) // oos_days)

pbar   = st.progress(0, text="投資組合 Walk-Forward 啟動...")
status = st.empty()

while start + is_days + oos_days <= total_days:
    pbar.progress(
        min((fold - 1) / n_total_folds, 0.99),
        text=f"Fold {fold}／約 {n_total_folds} — 正在跑 {len(stock_data)} 隻股票...",
    )

    is_start_date  = all_dates[start]
    is_end_date    = all_dates[start + is_days - 1]
    oos_start_date = all_dates[start + is_days]
    oos_end_idx    = min(start + is_days + oos_days - 1, total_days - 1)
    oos_end_date   = all_dates[oos_end_idx]

    all_is_trades  = []
    all_oos_trades = []
    n_stocks_run   = 0

    for ticker, full_df in stock_data.items():
        if full_df is None or full_df.empty or len(full_df) < 62:
            continue
        status.text(f"Fold {fold} — {ticker}")

        # IS 切片
        is_mask = (full_df.index >= is_start_date) & (full_df.index <= is_end_date)
        is_df   = full_df[is_mask].copy()
        if len(is_df) < 62:
            continue

        pre_is = precompute_signals(is_df)
        is_t, _, _ = run_backtest(
            is_df, buy_sigs, sell_sigs,
            trade_size=trade_size, slippage=slippage,
            stop_loss_pct=stop_loss_pct, take_profit_pct=take_profit_pct,
            max_hold_days=max_hold_days, _precomputed=pre_is,
        )
        for t in is_t:
            t["ticker"] = ticker
        all_is_trades.extend(is_t)

        # OOS 切片（含 61 日 warmup）
        oos_start_pos = full_df.index.searchsorted(oos_start_date)
        warmup_pos    = max(0, oos_start_pos - 61)
        oos_full_df   = full_df.iloc[warmup_pos:].copy()
        oos_full_df   = oos_full_df[oos_full_df.index <= oos_end_date].copy()
        oos_full_df   = calculate_indicators(oos_full_df)

        if len(oos_full_df) < 10:
            continue

        oos_t_all, _, _ = run_backtest(
            oos_full_df, buy_sigs, sell_sigs,
            trade_size=trade_size, slippage=slippage,
            stop_loss_pct=stop_loss_pct, take_profit_pct=take_profit_pct,
            max_hold_days=max_hold_days, _precomputed=None,
        )
        oos_t = [t for t in oos_t_all if t["_buy_date"] >= oos_start_date]
        for t in oos_t:
            t["ticker"] = ticker
        all_oos_trades.extend(oos_t)
        n_stocks_run += 1

    # equity curves
    is_date_range  = ref_df.index[(ref_df.index >= is_start_date)  & (ref_df.index <= is_end_date)]
    oos_date_range = ref_df.index[(ref_df.index >= oos_start_date) & (ref_df.index <= oos_end_date)]

    is_equity  = _build_portfolio_equity(all_is_trades,  is_date_range,  trade_size)
    oos_equity = _build_portfolio_equity(all_oos_trades, oos_date_range, trade_size)

    if oos_equity.empty:
        oos_equity = pd.DataFrame(
            {"equity": [trade_size] * len(oos_date_range)}, index=oos_date_range,
        )

    is_metrics  = calc_bt_metrics(all_is_trades,  is_equity,  trade_size)
    oos_metrics = calc_bt_metrics(all_oos_trades, oos_equity, trade_size)

    oos_closed = [t for t in all_oos_trades if "（持倉中）" not in t["賣出日期"]]
    valid_oos  = len(oos_closed) >= min_oos_trades

    results.append({
        "fold":            fold,
        "is_start":        is_start_date,  "is_end":   is_end_date,
        "oos_start":       oos_start_date, "oos_end":  oos_end_date,
        "is_metrics":      is_metrics  or {},
        "oos_metrics":     oos_metrics or {},
        "is_trades":       all_is_trades,
        "oos_trades":      all_oos_trades,
        "is_equity":       is_equity,
        "oos_equity":      oos_equity,
        "valid_oos":       valid_oos,
        "oos_trade_count": len(oos_closed),
        "n_stocks":        n_stocks_run,
    })

    start += oos_days
    fold  += 1

pbar.empty()
status.empty()
return results
```

# ══════════════════════════════════════════════════════════════════

# 共用：退化率

# ══════════════════════════════════════════════════════════════════

def _wf_degradation(is_ret: float, oos_ret: float) -> float:
if abs(is_ret) < 1e-9:
return 0.0
return (is_ret - oos_ret) / abs(is_ret) * 100

# ══════════════════════════════════════════════════════════════════

# 共用：結果展示（單股 & 投資組合均適用）

# ══════════════════════════════════════════════════════════════════

def show_walk_forward_results(wf_results: list, trade_size: float, is_portfolio: bool = False):
if not wf_results:
st.warning(“⚠️ 沒有足夠數據完成 Walk-Forward，請拉長回測週期或縮短 IS/OOS 窗口。”)
return

```
# ── 1. 彙總 rows ─────────────────────────────────────────────
rows = []
for r in wf_results:
    im  = r["is_metrics"]
    om  = r["oos_metrics"]
    is_ret  = im.get("平均每筆回報%", 0.0)
    oos_ret = om.get("平均每筆回報%", 0.0)
    deg     = _wf_degradation(is_ret, oos_ret)
    row = {
        "Fold":        r["fold"],
        "IS 期間":     f"{r['is_start'].strftime('%Y-%m')} → {r['is_end'].strftime('%Y-%m')}",
        "OOS 期間":    f"{r['oos_start'].strftime('%Y-%m')} → {r['oos_end'].strftime('%Y-%m')}",
        "IS 均回報%":  round(is_ret, 2),
        "OOS 均回報%": round(oos_ret, 2),
        "退化率%":     round(deg, 1),
        "IS 勝率%":    round(im.get("勝率%", 0.0), 1),
        "OOS 勝率%":   round(om.get("勝率%", 0.0), 1),
        "IS 交易數":   im.get("交易次數", 0),
        "OOS 交易數":  r["oos_trade_count"],
        "有效":        "✅" if r["valid_oos"] else f"⚠️ 僅{r['oos_trade_count']}筆",
    }
    if is_portfolio:
        row["股票數"] = r.get("n_stocks", "-")
    rows.append(row)

df_summary = pd.DataFrame(rows)

# ── 2. 整體評分（只用有效 Fold）──────────────────────────────
valid_rows    = [r for r in rows if "✅" in r["有效"]]
invalid_count = len(rows) - len(valid_rows)

if invalid_count > 0:
    hint = "建議改用投資組合模式或拉長 OOS 窗口至 6 個月。" if not is_portfolio \
           else "建議增加股票數量或減少入場條件。"
    st.warning(f"⚠️ **{invalid_count} 個 Fold** OOS 交易不足門檻，已排除在評分之外。{hint}")

if not valid_rows:
    st.error("❌ 所有 Fold 均未達最低交易次數門檻，無法評估策略。")
    _show_summary_table(df_summary, is_portfolio)
    return

avg_is       = sum(r["IS 均回報%"]  for r in valid_rows) / len(valid_rows)
avg_oos      = sum(r["OOS 均回報%"] for r in valid_rows) / len(valid_rows)
avg_deg      = sum(r["退化率%"]     for r in valid_rows) / len(valid_rows)
oos_positive = sum(1 for r in valid_rows if r["OOS 均回報%"] > 0)
oos_rate     = oos_positive / len(valid_rows) * 100

if avg_oos > 0 and avg_deg < 40 and oos_rate >= 60:
    verdict, verdict_color = "🟢 策略穩健（具備真實 Alpha）", "#26a69a"
    verdict_detail = f"OOS 正回報比率 {oos_rate:.0f}%，退化率 {avg_deg:.1f}% < 40%，策略很可能在實盤有效。"
elif avg_oos > 0 and avg_deg < 65 and oos_rate >= 50:
    verdict, verdict_color = "🟡 策略尚可（輕度過擬合）", "#f9a825"
    verdict_detail = f"OOS 仍有正回報但退化率 {avg_deg:.1f}% 偏高。建議加入更嚴格條件或延長驗證期。"
elif avg_oos <= 0:
    verdict, verdict_color = "🔴 策略危險（OOS 虧損）", "#ef5350"
    verdict_detail = f"OOS 平均回報 {avg_oos:.2f}%，策略在未見過的數據上虧損，不應實盤使用。"
else:
    verdict, verdict_color = "🔴 策略過擬合（嚴重退化）", "#ef5350"
    verdict_detail = f"退化率 {avg_deg:.1f}% 過高，IS 回報無法在 OOS 重現。"

mode_label = "（投資組合）" if is_portfolio else "（單股）"
st.markdown(
    f"<div style='background:rgba(255,255,255,0.05);"
    f"border-left:4px solid {verdict_color};"
    f"padding:12px 18px;border-radius:6px;margin-bottom:12px'>"
    f"<div style='font-size:20px;font-weight:bold'>{verdict} {mode_label}</div>"
    f"<div style='font-size:13px;margin-top:4px;opacity:0.85'>{verdict_detail}</div>"
    f"<div style='font-size:12px;margin-top:6px;opacity:0.6'>"
    f"有效 Fold：{len(valid_rows)}/{len(rows)}　｜　無效（交易不足）：{invalid_count}</div>"
    f"</div>",
    unsafe_allow_html=True,
)

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("IS 平均每筆%",    f"{avg_is:+.2f}%")
c2.metric("OOS 平均每筆%",   f"{avg_oos:+.2f}%",
          delta=f"{avg_oos - avg_is:+.2f}%", delta_color="normal")
c3.metric("平均退化率",      f"{avg_deg:.1f}%",
          delta="優" if avg_deg < 40 else ("可接受" if avg_deg < 65 else "過高"),
          delta_color="off")
c4.metric("OOS 正回報 Fold", f"{oos_positive}/{len(valid_rows)}")
c5.metric("有效 Fold 數",    f"{len(valid_rows)}/{len(rows)}")

st.divider()

# ── 3. IS vs OOS 長條圖 ───────────────────────────────────────
st.markdown("### 📊 逐 Fold IS vs OOS 平均每筆回報%")
fold_labels = [
    f"Fold {r['Fold']}\n{r['OOS 期間'].split(' → ')[0]}"
    + ("" if r["有效"] == "✅" else " ⚠️")
    for r in rows
]
fig_bar = go.Figure()
fig_bar.add_trace(go.Bar(
    name="In-Sample", x=fold_labels,
    y=[r["IS 均回報%"] for r in rows],
    marker_color=[
        "rgba(100,180,255,0.7)" if r["有效"] == "✅" else "rgba(100,180,255,0.25)"
        for r in rows
    ],
    text=[f"{v:+.1f}%" for v in [r["IS 均回報%"] for r in rows]],
    textposition="outside",
))
fig_bar.add_trace(go.Bar(
    name="Out-of-Sample", x=fold_labels,
    y=[r["OOS 均回報%"] for r in rows],
    marker_color=[
        ("#26a69a" if r["OOS 均回報%"] >= 0 else "#ef5350") if r["有效"] == "✅"
        else "rgba(128,128,128,0.3)"
        for r in rows
    ],
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

# ── 4. 退化率趨勢 ─────────────────────────────────────────────
st.markdown("### 📉 退化率趨勢（灰色 = 無效 Fold）")
fig_deg = go.Figure()
fig_deg.add_trace(go.Scatter(
    x=[f"Fold {r['Fold']}" for r in rows],
    y=[r["退化率%"] for r in rows],
    mode="lines+markers+text",
    text=[f"{v:.0f}%" for v in [r["退化率%"] for r in rows]],
    textposition="top center",
    line=dict(color="#f9a825", width=2),
    marker=dict(
        size=10,
        color=[
            "rgba(150,150,150,0.4)" if not wf_r["valid_oos"]
            else ("#26a69a" if r["退化率%"] < 40 else ("#f9a825" if r["退化率%"] < 65 else "#ef5350"))
            for r, wf_r in zip(rows, wf_results)
        ],
    ),
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

# ── 5. OOS 拼接曲線（只含有效 Fold）─────────────────────────
st.markdown("### 📈 OOS 拼接資金曲線（只含有效 Fold）")
oos_pieces      = []
running_capital = trade_size
for r in wf_results:
    if not r["valid_oos"]:
        continue
    eq = r["oos_equity"]
    if eq.empty:
        continue
    scale = running_capital / trade_size
    piece = eq["equity"] * scale
    oos_pieces.append(piece)
    running_capital = float(piece.iloc[-1])

if oos_pieces:
    oos_combined = pd.concat(oos_pieces)
    oos_combined = oos_combined[~oos_combined.index.duplicated(keep="last")].sort_index()
    oos_norm     = oos_combined / trade_size * 100 - 100
    final_ret    = float(oos_norm.iloc[-1])

    fig_oos = go.Figure()
    fig_oos.add_trace(go.Scatter(
        x=oos_norm.index, y=oos_norm,
        fill="tozeroy",
        line=dict(color="#26a69a" if final_ret >= 0 else "#ef5350", width=2),
        fillcolor="rgba(38,166,154,0.12)" if final_ret >= 0 else "rgba(239,83,80,0.12)",
    ))
    fig_oos.add_hline(y=0, line_dash="dash", line_color="rgba(255,255,255,0.3)")
    fig_oos.add_annotation(
        text=f"OOS 總回報：{final_ret:+.1f}%",
        xref="paper", yref="paper", x=0.02, y=0.95, showarrow=False,
        font=dict(size=14, color="#26a69a" if final_ret >= 0 else "#ef5350"),
    )
    fig_oos.update_layout(
        height=300, margin=dict(t=20, b=10),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        yaxis_ticksuffix="%",
    )
    st.plotly_chart(fig_oos, use_container_width=True)
else:
    st.info("沒有有效 Fold，無法繪製 OOS 拼接曲線。")

# ── 6. 彙總表 ─────────────────────────────────────────────────
st.divider()
st.markdown("### 📑 逐 Fold 詳細數據")
_show_summary_table(df_summary, is_portfolio)

# ── 7. 逐 Fold 展開詳情 ───────────────────────────────────────
st.divider()
st.markdown("### 🔬 逐 Fold 交易記錄")
for r, row in zip(wf_results, rows):
    fold_n = r["fold"]
    im     = r["is_metrics"]
    om     = r["oos_metrics"]
    valid  = r["valid_oos"]
    label  = (
        f"{'✅' if valid else '⚠️'} Fold {fold_n}  ｜  "
        f"OOS: {r['oos_start'].strftime('%Y-%m-%d')} → {r['oos_end'].strftime('%Y-%m-%d')}  ｜  "
        f"IS {im.get('平均每筆回報%', 0):+.2f}%  →  OOS {om.get('平均每筆回報%', 0):+.2f}%"
        + (f"  ｜  ⚠️ 僅 {r['oos_trade_count']} 筆OOS" if not valid else "")
    )
    with st.expander(label):
        if not valid:
            st.warning(
                f"⚠️ 此 Fold OOS 僅 **{r['oos_trade_count']} 筆**交易，統計上不可靠，已排除在評分之外。"
            )
        if is_portfolio and r.get("n_stocks"):
            st.caption(f"本 Fold 實際跑 {r['n_stocks']} 隻股票")

        col_is, col_oos = st.columns(2)
        with col_is:
            st.markdown("**📘 In-Sample**")
            if im:
                st.metric("均回報%",  f"{im.get('平均每筆回報%', 0):+.2f}%")
                st.metric("勝率",     f"{im.get('勝率%', 0):.1f}%")
                st.metric("交易次數", f"{im.get('交易次數', 0)}")
                pf = im.get("Profit Factor", 0)
                st.metric("Profit F", "∞" if pf == float("inf") else f"{pf:.2f}")
                st.metric("最大回撤", f"{im.get('最大回撤%', 0):.2f}%")
            else:
                st.info("無交易")
        with col_oos:
            st.markdown("**📗 Out-of-Sample**")
            if om:
                oos_ret = om.get("平均每筆回報%", 0)
                st.metric("均回報%",  f"{oos_ret:+.2f}%",
                          delta=f"退化 {_wf_degradation(im.get('平均每筆回報%', 0), oos_ret):.1f}%",
                          delta_color="off")
                st.metric("勝率",     f"{om.get('勝率%', 0):.1f}%")
                st.metric("交易次數", f"{om.get('交易次數', 0)}")
                pf = om.get("Profit Factor", 0)
                st.metric("Profit F", "∞" if pf == float("inf") else f"{pf:.2f}")
                st.metric("最大回撤", f"{om.get('最大回撤%', 0):.2f}%")
            else:
                st.info("無交易（OOS 期間無訊號）")

        if r["oos_trades"]:
            display_cols = ["買入日期", "賣出日期", "買入價", "賣出價",
                            "回報%", "盈虧(HKD)", "持倉天數", "賣出原因"]
            if is_portfolio:
                display_cols = ["ticker"] + display_cols
            avail  = [c for c in display_cols if c in r["oos_trades"][0]]
            df_t   = pd.DataFrame(r["oos_trades"])[avail]

            def _cr(val):
                try:
                    v = float(val)
                    return "color:#26a69a" if v > 0 else ("color:#ef5350" if v < 0 else "")
                except Exception:
                    return ""

            scols = [c for c in ["回報%", "盈虧(HKD)"] if c in df_t.columns]
            st.dataframe(
                df_t.style.map(_cr, subset=scols),
                use_container_width=True, hide_index=True,
            )
```

def _show_summary_table(df_summary: pd.DataFrame, is_portfolio: bool):
def _color_ret(val):
try:
v = float(val)
if v > 0: return “color:#26a69a;font-weight:bold”
if v < 0: return “color:#ef5350;font-weight:bold”
except Exception:
pass
return “”

```
def _color_deg(val):
    try:
        v = float(val)
        if v < 40:  return "color:#26a69a"
        if v < 65:  return "color:#f9a825"
        return "color:#ef5350;font-weight:bold"
    except Exception:
        pass
    return ""

def _color_valid(val):
    if "✅" in str(val): return "color:#26a69a;font-weight:bold"
    if "⚠️" in str(val): return "color:#f9a825"
    return ""

st.dataframe(
    df_summary.style
    .map(_color_ret,   subset=["IS 均回報%", "OOS 均回報%"])
    .map(_color_deg,   subset=["退化率%"])
    .map(_color_valid, subset=["有效"])
    .format({
        "IS 均回報%":  "{:+.2f}%",
        "OOS 均回報%": "{:+.2f}%",
        "退化率%":     "{:.1f}%",
        "IS 勝率%":    "{:.1f}%",
        "OOS 勝率%":   "{:.1f}%",
    }),
    use_container_width=True, hide_index=True,
)
```
