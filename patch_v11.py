#!/usr/bin/env python3
"""
港股狙擊手 V10.9 → V11.0 自動修補腳本
用法：python3 patch_v11.py
    讀取 app.py (V10.9)，輸出 app.py (V11.0)
    原檔備份至 app_v10.9_backup.py
"""
import sys
import shutil

INPUT  = "app.py"
BACKUP = "app_v10.9_backup.py"

def patch(content: str) -> str:
    fixes_applied = 0

    # ── FIX 1: _swing_lows window 5→10 ───────────────────────────
    old = 'def _swing_lows(close_ser: pd.Series, window: int = 5) -> pd.Series:'
    new = 'def _swing_lows(close_ser: pd.Series, window: int = 10) -> pd.Series:'
    if old in content:
        content = content.replace(old, new, 1)
        fixes_applied += 1
        print("  ✅ FIX 1: _swing_lows window 5→10")
    else:
        print("  ⚠️ FIX 1: 未找到目標（可能已修改）")

    # ── FIX 2: _compute_b3_series 加入 3% 價差過濾 ────────────────
    old_b3 = '    b3 = (\n        swing_lo &\n        (df["Close"] < prev_sl_close) &\n        (df["DIF"]   > prev_sl_dif)   &\n        (df["RSI"]   < 40)\n    )'
    new_b3 = '    # V11.0：兩個 swing low 之間至少跌 3%，過濾噪音背離\n    min_price_diff = (prev_sl_close - df["Close"]) / prev_sl_close > 0.03\n\n    b3 = (\n        swing_lo &\n        min_price_diff &\n        (df["Close"] < prev_sl_close) &\n        (df["DIF"]   > prev_sl_dif)   &\n        (df["RSI"]   < 40)\n    )'
    if old_b3 in content:
        content = content.replace(old_b3, new_b3, 1)
        fixes_applied += 1
        print("  ✅ FIX 2: b3 底背離加入 3% 最小價差過濾")
    else:
        print("  ⚠️ FIX 2: 未找到目標")

    # ── FIX 3: b9 真突破 — 移除 0.98 門檻 ─────────────────────────
    old = '    b9 = c["Close"] >= close_52w_high * 0.98'
    new = '    # V11.0: 真突破，移除 0.98 門檻\n    b9 = c["Close"] >= close_52w_high'
    if old in content:
        content = content.replace(old, new, 1)
        fixes_applied += 1
        print("  ✅ FIX 3: b9 真突破（移除 0.98）")
    else:
        print("  ⚠️ FIX 3: 未找到目標")

    # ── FIX 4a: run_backtest 簽名 commission→slippage ──────────────
    old = '    trade_size: float = 100_000,\n    commission: float = 0.002,\n    stop_loss_pct: float = None,\n    take_profit_pct: float = None,\n    max_hold_days: int = None,\n    _precomputed: dict = None,\n) -> tuple:'
    new = '    trade_size: float = 100_000,\n    slippage: float = 0.002,\n    stop_loss_pct: float = None,\n    take_profit_pct: float = None,\n    max_hold_days: int = None,\n    _precomputed: dict = None,\n) -> tuple:'
    if old in content:
        content = content.replace(old, new, 1)
        fixes_applied += 1
        print("  ✅ FIX 4a: run_backtest commission→slippage")
    else:
        print("  ⚠️ FIX 4a: 未找到目標")

    # ── FIX 4b: 新增 low_arr / high_arr ───────────────────────────
    old = '    close_arr = df["Close"].values.astype(float)\n    idx_arr   = df.index\n    n         = len(df)'
    new = '    close_arr = df["Close"].values.astype(float)\n    low_arr   = df["Low"].values.astype(float)      # V11.0: 用於止損判斷\n    high_arr  = df["High"].values.astype(float)      # V11.0: 用於止盈判斷\n    idx_arr   = df.index\n    n         = len(df)'
    if old in content:
        content = content.replace(old, new, 1)
        fixes_applied += 1
        print("  ✅ FIX 4b: 新增 low_arr / high_arr")
    else:
        print("  ⚠️ FIX 4b: 未找到目標")

    # ── FIX 4c: 買入價加滑點，移除佣金 ────────────────────────────
    old = '            entry_px   = close_arr[i + 1]\n            entry_date = idx_arr[i + 1]\n            entry_idx  = i + 1\n            shares = int(trade_size / (entry_px * (1 + commission)))\n            if shares > 0:\n                positions.append({\n                    "shares":     shares,\n                    "entry_px":   entry_px,\n                    "entry_date": entry_date,\n                    "entry_idx":  entry_idx,\n                    "cost":       shares * entry_px * (1 + commission),\n                })'
    new = '            entry_px   = close_arr[i + 1] * (1 + slippage)   # V11.0: 滑點買高\n            entry_date = idx_arr[i + 1]\n            entry_idx  = i + 1\n            shares = int(trade_size / entry_px)\n            if shares > 0:\n                positions.append({\n                    "shares":     shares,\n                    "entry_px":   entry_px,\n                    "entry_date": entry_date,\n                    "entry_idx":  entry_idx,\n                    "cost":       shares * entry_px,\n                })'
    if old in content:
        content = content.replace(old, new, 1)
        fixes_applied += 1
        print("  ✅ FIX 4c: 買入滑點 + 移除佣金")
    else:
        print("  ⚠️ FIX 4c: 未找到目標")

    # ── FIX 4d: 迴圈變數 ──────────────────────────────────────────
    old = '        close = close_arr[i]\n        date  = idx_arr[i]\n\n        # 先記錄今日的已實現累計（賣出平倉後才更新，所以先記昨日值）\n        # → 我們在迴圈末尾記錄，這樣當日賣出的利潤會反映在當日\n\n        # 買入（跳過最後一天'
    new = '        close  = close_arr[i]\n        low_i  = low_arr[i]       # V11.0: 用於止損\n        high_i = high_arr[i]      # V11.0: 用於止盈\n        date   = idx_arr[i]\n\n        # 買入（跳過最後一天'
    if old in content:
        content = content.replace(old, new, 1)
        fixes_applied += 1
        print("  ✅ FIX 4d: 迴圈新增 low_i / high_i")
    else:
        print("  ⚠️ FIX 4d: 未找到目標")

    # ── FIX 4e: 止損/止盈/賣出邏輯 ────────────────────────────────
    old = '''            reason    = None
            if stop_loss_pct   and close <= ep * (1 - stop_loss_pct / 100):
                reason = f"止損 -{stop_loss_pct:.0f}%"
            elif take_profit_pct and close >= ep * (1 + take_profit_pct / 100):
                reason = f"止盈 +{take_profit_pct:.0f}%"
            elif max_hold_days  and days_held >= max_hold_days:
                reason = f"超時 {max_hold_days}日"
            elif sell_arr[i]:
                reason = "策略訊號"

            if reason:
                proceeds  = pos["shares"] * close * (1 - commission)
                pnl_pct   = (close - ep) / ep * 100
                pnl_hkd   = proceeds - pos["cost"]'''
    new = '''            reason    = None
            exit_px   = close  # 預設用收盤價

            # V11.0: 止損用 Low 判斷（模擬盤中止損單）
            if stop_loss_pct and low_i <= ep * (1 - stop_loss_pct / 100):
                exit_px = ep * (1 - stop_loss_pct / 100)
                reason = f"止損 -{stop_loss_pct:.0f}%"
            # V11.0: 止盈用 High 判斷（模擬盤中止盈單）
            elif take_profit_pct and high_i >= ep * (1 + take_profit_pct / 100):
                exit_px = ep * (1 + take_profit_pct / 100)
                reason = f"止盈 +{take_profit_pct:.0f}%"
            elif max_hold_days  and days_held >= max_hold_days:
                exit_px = close * (1 - slippage)
                reason = f"超時 {max_hold_days}日"
            elif sell_arr[i]:
                exit_px = close * (1 - slippage)   # V11.0: 賣出滑點
                reason = "策略訊號"

            if reason:
                proceeds  = pos["shares"] * exit_px
                pnl_pct   = (exit_px - ep) / ep * 100
                pnl_hkd   = proceeds - pos["cost"]'''
    if old in content:
        content = content.replace(old, new, 1)
        fixes_applied += 1
        print("  ✅ FIX 4e: 止損Low/止盈High/賣出滑點")
    else:
        print("  ⚠️ FIX 4e: 未找到目標")

    # ── FIX 4f: 期末平倉 ──────────────────────────────────────────
    old = '        last_close = close_arr[-1]\n        proceeds   = pos["shares"] * last_close * (1 - commission)'
    new = '        last_close = close_arr[-1] * (1 - slippage)   # V11.0: 滑點\n        proceeds   = pos["shares"] * last_close'
    if old in content:
        content = content.replace(old, new, 1)
        fixes_applied += 1
        print("  ✅ FIX 4f: 期末平倉滑點")
    else:
        print("  ⚠️ FIX 4f: 未找到目標")

    # ── FIX 5: run_grid_search ─────────────────────────────────────
    old = '    trade_size: float,\n    commission: float,\n    sort_metric: str = "平均每筆%",'
    new = '    trade_size: float,\n    slippage: float,\n    sort_metric: str = "平均每筆%",'
    if old in content:
        content = content.replace(old, new, 1)
        fixes_applied += 1
        print("  ✅ FIX 5: run_grid_search commission→slippage")

    # ── FIX 6: run_walk_forward ────────────────────────────────────
    # 第二次出現的 commission 參數（run_walk_forward 簽名）
    old = '    trade_size: float = 100_000,\n    commission: float = 0.002,\n    stop_loss_pct'
    new = '    trade_size: float = 100_000,\n    slippage: float = 0.002,\n    stop_loss_pct'
    if old in content:
        content = content.replace(old, new, 1)
        fixes_applied += 1
        print("  ✅ FIX 6: run_walk_forward commission→slippage")

    # ── 全局替換剩餘的 commission 引用 ────────────────────────────
    # 函數內部調用: commission=commission → slippage=slippage
    content = content.replace('commission=commission', 'slippage=slippage')
    # bt_commission → bt_slippage
    content = content.replace('commission=bt_commission', 'slippage=bt_slippage')
    content = content.replace('bt_commission', 'bt_slippage')
    # wf_commission → wf_slippage
    content = content.replace('commission=wf_commission', 'slippage=wf_slippage')
    content = content.replace('wf_commission', 'wf_slippage')

    # ── FIX 7: UI sliders ─────────────────────────────────────────
    old = '佣金率 (%, 港股建議 0.20)", 0.0, 0.5, 0.20, 0.05, key="bt_slippage"'
    new = '滑點 (%, 港股建議 0.10-0.30)", 0.0, 1.0, 0.20, 0.05, key="bt_slippage"'
    if old in content:
        content = content.replace(old, new, 1)
        fixes_applied += 1
        print("  ✅ FIX 7a: 回測 Tab 佣金→滑點 slider")

    old = '佣金率 (%)", 0.0, 0.5, 0.20, 0.05, key="wf_slippage"'
    new = '滑點 (%)", 0.0, 1.0, 0.20, 0.05, key="wf_slippage"'
    if old in content:
        content = content.replace(old, new, 1)
        fixes_applied += 1
        print("  ✅ FIX 7b: Walk-Forward Tab 佣金→滑點 slider")

    # ── FIX 8: evaluate_signals 描述 ───────────────────────────────
    old = '需RSI<40 + swing low背離",'
    new = '需RSI<40 + swing low背離 + 價差>3%",'
    if old in content:
        content = content.replace(old, new, 1)
        fixes_applied += 1
        print("  ✅ FIX 8a: b3 描述更新")

    old = '("⑨ 52週新高突破",\n         f"現價 {c[\'Close\']:.2f}  52週高點區域",'
    new = '("⑨ 52週新高突破（真突破）",\n         f"現價 {c[\'Close\']:.2f}  需 >= 52週高點（不含0.98折扣）",'
    if old in content:
        content = content.replace(old, new, 1)
        fixes_applied += 1
        print("  ✅ FIX 8b: b9 描述更新")

    # ── 標題版本號 ────────────────────────────────────────────────
    content = content.replace('港股狙擊手 V10.9', '港股狙擊手 V11.0')
    content = content.replace('策略回測系統 V10.9', '策略回測系統 V11.0')

    print(f"\n  總計套用 {fixes_applied} 個修補")
    return content


def main():
    print(f"📖 讀取 {INPUT}...")
    try:
        with open(INPUT, "r", encoding="utf-8") as f:
            original = f.read()
    except FileNotFoundError:
        print(f"❌ 找不到 {INPUT}，請確保此腳本與 app.py 在同一目錄")
        sys.exit(1)

    print(f"   原始：{len(original)} 字元，{original.count(chr(10))} 行")

    shutil.copy2(INPUT, BACKUP)
    print(f"💾 備份 → {BACKUP}")

    print("\n🔧 套用 V11.0 修補...")
    patched = patch(original)

    with open(INPUT, "w", encoding="utf-8") as f:
        f.write(patched)

    print(f"\n✅ {INPUT} 已更新為 V11.0（{len(patched)} 字元）")
    print(f"\n📋 修改摘要：")
    print("   1. swing low window 5→10（減少噪音）")
    print("   2. b3 底背離加 3% 最小價差過濾")
    print("   3. b9 真突破（移除 0.98 門檻）")
    print("   4. 止損改用 Low / 止盈改用 High（模擬盤中觸發）")
    print("   5. 新增滑點參數（預設 0.2%，取代佣金）")
    print("   6. UI 佣金 slider → 滑點 slider")


if __name__ == "__main__":
    main()
