# ══════════════════════════════════════════════════════════════════
# backtest.py — 回測引擎、績效指標、網格搜索
# ══════════════════════════════════════════════════════════════════

import pandas as pd
import streamlit as st
from indicators import precompute_signals
from config import B_NAMES, S_NAMES


def run_backtest(
    df: pd.DataFrame,
    buy_sigs: tuple, sell_sigs: tuple,
    trade_size: float = 100_000,
    slippage: float = 0.002,
    stop_loss_pct: float = None,
    take_profit_pct: float = None,
    max_hold_days: int = None,
    _precomputed: dict = None,
    # ── 改進二：恒指市場過濾器 ─────────────────────────────────────
    # pd.Series[bool]，index 為交易日，True = 恒指 MA20 > MA60（牛市）
    # None = 不啟用過濾，維持原有行為
    market_filter_series: pd.Series = None,
) -> tuple:
    sigs = _precomputed if _precomputed is not None else precompute_signals(df)

    buy_active  = [B_NAMES[k] for k, v in enumerate(buy_sigs)  if v]
    sell_active = [S_NAMES[k] for k, v in enumerate(sell_sigs) if v]

    if buy_active:
        buy_signal = sigs[buy_active[0]].copy()
        for nm in buy_active[1:]:
            buy_signal &= sigs[nm]
    else:
        buy_signal = pd.Series(False, index=df.index)

    # ── 改進二：把恒指過濾器疊加到 buy_signal ─────────────────────
    # 用 reindex + ffill 對齊日期（HSI 和個股的交易日可能略有不同）
    # 未對齊的日期 fillna(True) — 寧可放行，不誤殺
    if market_filter_series is not None and not market_filter_series.empty:
        hsi_aligned = (
            market_filter_series
            .reindex(df.index, method="ffill")
            .fillna(True)
        )
        buy_signal = buy_signal & hsi_aligned
    # ── END 改進二 ────────────────────────────────────────────────

    if sell_active:
        sell_signal = sigs[sell_active[0]].copy()
        for nm in sell_active[1:]:
            sell_signal |= sigs[nm]
    else:
        sell_signal = pd.Series(False, index=df.index)

    buy_arr   = buy_signal.values
    sell_arr  = sell_signal.values
    close_arr = df["Close"].values.astype(float)
    low_arr   = df["Low"].values.astype(float)
    high_arr  = df["High"].values.astype(float)
    idx_arr   = df.index
    n         = len(df)

    positions = []
    trades    = []
    running_capital = trade_size
    daily_equity    = []

    for i in range(61, n):
        close  = close_arr[i]
        low_i  = low_arr[i]
        high_i = high_arr[i]
        date   = idx_arr[i]

        if buy_arr[i] and i + 1 < n - 1:
            entry_px   = close_arr[i + 1] * (1 + slippage)
            entry_date = idx_arr[i + 1]
            entry_idx  = i + 1
            shares = int(trade_size / entry_px)
            if shares > 0:
                positions.append({
                    "shares": shares, "entry_px": entry_px,
                    "entry_date": entry_date, "entry_idx": entry_idx,
                    "cost": shares * entry_px,
                })

        keep = []
        for pos in positions:
            days_held = i - pos["entry_idx"]
            ep        = pos["entry_px"]
            reason    = None
            exit_px   = close

            if stop_loss_pct and low_i <= ep * (1 - stop_loss_pct / 100):
                exit_px = ep * (1 - stop_loss_pct / 100)
                reason  = f"止損 -{stop_loss_pct:.0f}%"
            elif take_profit_pct and high_i >= ep * (1 + take_profit_pct / 100):
                exit_px = ep * (1 + take_profit_pct / 100)
                reason  = f"止盈 +{take_profit_pct:.0f}%"
            elif max_hold_days and days_held >= max_hold_days:
                exit_px = close * (1 - slippage)
                reason  = f"超時 {max_hold_days}日"
            elif sell_arr[i]:
                exit_px = close * (1 - slippage)
                reason  = "策略訊號"

            if reason:
                proceeds = pos["shares"] * exit_px
                pnl_pct  = (exit_px - ep) / ep * 100
                pnl_hkd  = proceeds - pos["cost"]
                running_capital *= (1 + pnl_pct / 100)
                trades.append({
                    "買入日期": pos["entry_date"].strftime("%Y-%m-%d"),
                    "賣出日期": date.strftime("%Y-%m-%d"),
                    "買入價": round(ep, 3), "賣出價": round(close, 3),
                    "回報%": round(pnl_pct, 2), "盈虧(HKD)": round(pnl_hkd, 0),
                    "持倉天數": days_held, "賣出原因": reason,
                    "_buy_date": pos["entry_date"], "_sell_date": date,
                    "_win": pnl_pct > 0,
                })
            else:
                keep.append(pos)
        positions = keep
        daily_equity.append({"date": date, "equity": running_capital})

    # 期末持倉強制平倉
    for pos in positions:
        last_close = close_arr[-1] * (1 - slippage)
        proceeds   = pos["shares"] * last_close
        pnl_pct    = (last_close - pos["entry_px"]) / pos["entry_px"] * 100
        pnl_hkd    = proceeds - pos["cost"]
        running_capital *= (1 + pnl_pct / 100)
        trades.append({
            "買入日期": pos["entry_date"].strftime("%Y-%m-%d"),
            "賣出日期": idx_arr[-1].strftime("%Y-%m-%d") + "（持倉中）",
            "買入價": round(pos["entry_px"], 3), "賣出價": round(last_close, 3),
            "回報%": round(pnl_pct, 2), "盈虧(HKD)": round(pnl_hkd, 0),
            "持倉天數": len(df) - 1 - pos["entry_idx"], "賣出原因": "期末持倉",
            "_buy_date": pos["entry_date"], "_sell_date": idx_arr[-1],
            "_win": pnl_pct > 0,
        })

    if daily_equity:
        equity_df = pd.DataFrame(daily_equity).set_index("date")[["equity"]]
    else:
        equity_df = pd.DataFrame()

    return trades, equity_df, trade_size


def calc_bt_metrics(trades, equity_df, trade_size=100_000):
    if not trades:
        return {}
    closed = [t for t in trades if "（持倉中）" not in t["賣出日期"]]
    total  = len(closed)
    if total == 0:
        return {}
    wins   = sum(1 for t in closed if t["_win"])
    losses = total - wins
    win_rate = wins / total * 100

    rets     = [t["回報%"]    for t in closed]
    days_arr = [t["持倉天數"] for t in closed]
    wins_arr = [t["回報%"] for t in closed if t["_win"]]
    loss_arr = [t["回報%"] for t in closed if not t["_win"]]

    avg_ret     = sum(rets)  / total
    avg_win     = sum(wins_arr) / wins   if wins   else 0.0
    avg_loss    = sum(loss_arr) / losses if losses else 0.0
    avg_days    = sum(days_arr) / total
    best_trade  = max(rets)
    worst_trade = min(rets)

    gross_win  = sum(wins_arr)
    gross_loss = abs(sum(loss_arr))
    profit_factor = round(gross_win / gross_loss, 2) if gross_loss > 0 else (
        float("inf") if gross_win > 0 else 0.0)

    max_consec_loss = cur_consec = 0
    for t in closed:
        cur_consec = cur_consec + 1 if not t["_win"] else 0
        max_consec_loss = max(max_consec_loss, cur_consec)

    max_dd = 0.0
    if not equity_df.empty:
        eq = equity_df["equity"]
        roll_max = eq.cummax()
        dd = (eq - roll_max) / roll_max * 100
        max_dd = float(dd.min()) if not eq.empty and roll_max.max() > 0 else 0.0

    if not equity_df.empty:
        final_equity  = float(equity_df["equity"].iloc[-1])
        total_ret_pct = (final_equity - trade_size) / trade_size * 100
    else:
        final_equity  = trade_size * (1 + avg_ret / 100) ** total
        total_ret_pct = (final_equity - trade_size) / trade_size * 100

    return {
        "平均每筆回報%":  round(avg_ret, 2),
        "交易次數":       total,
        "勝率%":          round(win_rate, 1),
        "平均盈利%":      round(avg_win, 2),
        "平均虧損%":      round(avg_loss, 2),
        "最佳一筆%":      round(best_trade, 2),
        "最差一筆%":      round(worst_trade, 2),
        "平均持倉天數":   round(avg_days, 1),
        "Profit Factor":  profit_factor,
        "最大連輸":       max_consec_loss,
        "最大回撤%":      round(max_dd, 2),
        "累計回報%":      round(total_ret_pct, 2),
        "總回報%":        round(total_ret_pct, 2),
        "最終資金":       round(final_equity, 0),
    }


def run_grid_search(
    df: pd.DataFrame,
    buy_sigs: tuple, sell_sigs: tuple,
    trade_size: float,
    slippage: float,
    sort_metric: str = "平均每筆%",
    market_filter_series: pd.Series = None,
):
    sl_grid = [0, 5, 10, 15, 20]
    tp_grid = [0, 15, 30, 50]
    md_grid = [0, 20, 40, 60]

    combos  = [(sl, tp, md) for sl in sl_grid for tp in tp_grid for md in md_grid]
    total_c = len(combos)
    results = []

    pre_s = precompute_signals(df)

    pbar = st.progress(0, text="網格搜索中...")
    for ci, (sl, tp, md) in enumerate(combos):
        pbar.progress((ci + 1) / total_c, text=f"網格搜索 {ci+1}/{total_c}...")
        t, eq, _ = run_backtest(
            df, buy_sigs, sell_sigs,
            trade_size=trade_size, slippage=slippage,
            stop_loss_pct=sl  if sl  > 0 else None,
            take_profit_pct=tp if tp > 0 else None,
            max_hold_days=md   if md  > 0 else None,
            _precomputed=pre_s,
            market_filter_series=market_filter_series,
        )
        m = calc_bt_metrics(t, eq, trade_size)
        if m and m["交易次數"] >= 2:
            results.append({
                "止損%":     f"{sl}%" if sl > 0 else "不限",
                "止盈%":     f"{tp}%" if tp > 0 else "不限",
                "最長持倉":  f"{md}日" if md > 0 else "不限",
                "平均每筆%": m["平均每筆回報%"],
                "勝率%":     m["勝率%"],
                "Profit F":  m["Profit Factor"],
                "最大回撤%": m["最大回撤%"],
                "交易次數":  m["交易次數"],
                "最大連輸":  m["最大連輸"],
            })
    pbar.empty()

    if not results:
        return pd.DataFrame()

    df_gs = pd.DataFrame(results)
    asc   = (sort_metric == "最大回撤%")
    return df_gs.sort_values(sort_metric, ascending=asc).reset_index(drop=True)


# ── 改進二：從 HSI DataFrame 計算恒指過濾器 Series ──────────────────
def build_hsi_filter(hsi_df: pd.DataFrame) -> pd.Series:
    """
    輸入：已含 MA20 / MA60 的恒指 DataFrame
    輸出：pd.Series[bool]，True = 恒指 MA20 > MA60（允許入場）
    """
    if hsi_df.empty or "MA20" not in hsi_df.columns or "MA60" not in hsi_df.columns:
        return pd.Series(dtype=bool)
    return (hsi_df["MA20"] > hsi_df["MA60"]).rename("hsi_bullish")
