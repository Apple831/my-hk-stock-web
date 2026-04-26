# ══════════════════════════════════════════════════════════════════
# backtest.py — 回測引擎、績效指標、網格搜索
# ══════════════════════════════════════════════════════════════════
#
# v17 修復（2026-04-26）— 來自策略邏輯審查報告：
# 🔴 Bug 1: 新部位被同一 bar 立即檢查出場（race condition）
#   修復：內層迴圈最前面加 entry_idx > i guard，跳過尚未真正成交的部位
#
# 🔴 Bug 2: 策略 sell 同日執行（look-ahead bias）
#   修復：策略 sell 也改為 T+1 close 出場（與進場對稱）
#   注意：止損/止盈仍用 low/high（盤中觸價單，正確）
#
# 🟡 Bug 3: 港股交易成本被低估
#   修復：新增 commission_pct 參數（預設 0.0013 = 印花稅+佣金+交易費）
#         舊版 slippage 參數仍向後相容
#
# 🟡 Bug 4: 回測邊界 i+1 < n-1 太保守
#   修復：改為 i+1 < n（少漏一根 bar）
#
# 🟡 Bug 5: min/max hold days 互斥檢查
#   修復：入口加 assert
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
    # ── v17 新增：拆分交易成本（向後相容）─────────────────────────
    # 舊版 slippage=0.002 = 0.2% 包含一切（雙邊 0.4%）
    # 新版可拆分為：
    #   slippage_pct  = 純價格滑點（單邊，例如 0.001 = 0.1%）
    #   commission_pct = 印花稅+佣金+交易費（單邊，例如 0.0013 = 0.13%）
    # 雙邊合計 = (slippage_pct + commission_pct) × 2
    #
    # 若兩者均為 None：回退舊行為（slippage 當作完整單邊成本）
    slippage_pct: float = None,
    commission_pct: float = None,
    stop_loss_pct: float = None,
    take_profit_pct: float = None,
    max_hold_days: int = None,
    min_hold_days: int = None,
    _precomputed: dict = None,
    market_filter_series: pd.Series = None,
) -> tuple:
    # ── 🟡 Bug 5: min/max hold days 互斥檢查 ───────────────────────
    if min_hold_days and max_hold_days:
        assert min_hold_days < max_hold_days, (
            f"min_hold_days ({min_hold_days}) 必須小於 max_hold_days ({max_hold_days})"
        )

    # ── 計算單邊交易成本 ──────────────────────────────────────────
    if slippage_pct is not None or commission_pct is not None:
        # 新版：用戶顯式指定拆分
        one_side_cost = (slippage_pct or 0.0) + (commission_pct or 0.0)
    else:
        # 舊版相容：把 slippage 當作完整單邊成本
        one_side_cost = slippage

    sigs = _precomputed if _precomputed is not None else precompute_signals(df)

    buy_active  = [B_NAMES[k] for k, v in enumerate(buy_sigs)  if v]
    sell_active = [S_NAMES[k] for k, v in enumerate(sell_sigs) if v]

    if buy_active:
        buy_signal = sigs[buy_active[0]].copy()
        for nm in buy_active[1:]:
            buy_signal &= sigs[nm]
    else:
        buy_signal = pd.Series(False, index=df.index)

    if market_filter_series is not None and not market_filter_series.empty:
        hsi_aligned = (
            market_filter_series
            .reindex(df.index, method="ffill")
            .fillna(True)
        )
        buy_signal = buy_signal & hsi_aligned

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

        # ── 🟡 Bug 4: 邊界從 i+1 < n-1 改為 i+1 < n ─────────────────
        # 舊版會多忽略一根 bar，造成最後一個訊號被跳過
        if buy_arr[i] and i + 1 < n:
            entry_px   = close_arr[i + 1] * (1 + one_side_cost)
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
            # ── 🔴 Bug 1: race condition guard（含同日防護）──────
            # 跳過尚未真正成交的新部位（entry_idx > i）
            # 也跳過剛剛成交的當天 (entry_idx == i)，因為實盤無法當天買又當天賣
            # 持倉天數從 1 開始算 (i+1 才開始檢查出場)
            if pos["entry_idx"] >= i:
                keep.append(pos)
                continue

            days_held = i - pos["entry_idx"]
            ep        = pos["entry_px"]
            reason    = None
            exit_px   = close

            strategy_sell_allowed = True
            if min_hold_days and days_held < min_hold_days:
                strategy_sell_allowed = False

            if stop_loss_pct and low_i <= ep * (1 - stop_loss_pct / 100):
                # 止損：盤中觸價，正確
                exit_px = ep * (1 - stop_loss_pct / 100)
                reason  = f"止損 -{stop_loss_pct:.0f}%"
            elif take_profit_pct and high_i >= ep * (1 + take_profit_pct / 100):
                # 止盈：盤中觸價，正確
                exit_px = ep * (1 + take_profit_pct / 100)
                reason  = f"止盈 +{take_profit_pct:.0f}%"
            elif max_hold_days and days_held >= max_hold_days:
                # ── 🔴 Bug 2: 超時也改 T+1 出場 ─────────────────────
                if i + 1 < n:
                    exit_px = close_arr[i + 1] * (1 - one_side_cost)
                    exit_date = idx_arr[i + 1]
                else:
                    exit_px = close * (1 - one_side_cost)
                    exit_date = date
                reason  = f"超時 {max_hold_days}日"
            elif sell_arr[i] and strategy_sell_allowed:
                # ── 🔴 Bug 2: 策略 sell 改 T+1 出場 ────────────────
                # 訊號在 T 收盤產生，實盤無法 T 收盤就賣（已收盤）
                # 必須延後到 T+1 close 出場（與進場對稱）
                if i + 1 < n:
                    exit_px = close_arr[i + 1] * (1 - one_side_cost)
                    exit_date = idx_arr[i + 1]
                else:
                    # 最後一根 bar 的訊號無法 T+1 出場，視為未觸發
                    keep.append(pos)
                    continue
                reason  = "策略訊號"

            if reason:
                # 決定 sell_date（止損/止盈用今天，T+1 出場用明天）
                if reason in ("策略訊號",) or reason.startswith("超時"):
                    sell_date_obj = exit_date if i + 1 < n else date
                    sell_date_str = sell_date_obj.strftime("%Y-%m-%d")
                else:
                    sell_date_obj = date
                    sell_date_str = date.strftime("%Y-%m-%d")

                proceeds = pos["shares"] * exit_px
                pnl_pct  = (exit_px - ep) / ep * 100
                pnl_hkd  = proceeds - pos["cost"]
                running_capital *= (1 + pnl_pct / 100)
                trades.append({
                    "買入日期": pos["entry_date"].strftime("%Y-%m-%d"),
                    "賣出日期": sell_date_str,
                    "買入價": round(ep, 3), "賣出價": round(exit_px, 3),
                    "回報%": round(pnl_pct, 2), "盈虧(HKD)": round(pnl_hkd, 0),
                    "持倉天數": days_held, "賣出原因": reason,
                    "_buy_date": pos["entry_date"], "_sell_date": sell_date_obj,
                    "_win": pnl_pct > 0,
                })
            else:
                keep.append(pos)
        positions = keep
        daily_equity.append({"date": date, "equity": running_capital})

    # 期末持倉強制平倉
    for pos in positions:
        last_close = close_arr[-1] * (1 - one_side_cost)
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


def build_hsi_filter(hsi_df: pd.DataFrame) -> pd.Series:
    """
    輸入：已含 MA20 / MA60 的恒指 DataFrame
    輸出：pd.Series[bool]，True = 恒指 MA20 > MA60（允許入場）
    """
    if hsi_df.empty or "MA20" not in hsi_df.columns or "MA60" not in hsi_df.columns:
        return pd.Series(dtype=bool)
    return (hsi_df["MA20"] > hsi_df["MA60"]).rename("hsi_bullish")
