# ══════════════════════════════════════════════════════════════════
# config.py — 策略組合預設 & 全局常量
# ══════════════════════════════════════════════════════════════════
#
# v16 更新（2026-04-25）：
# • 💎+s2 M30 三重出場版正式升級為【實盤主力冠軍】
#   - 移除 [新] 標記，移到策略池第一位
#   - WF +7.67% / 延伸 +12.68% / 樣本 2126 / 退化率 -2.5%（策略池最健康）
#   - 已通過跨對照組驗證：MIN30 在三重出場下貢獻 +3.86%（最大）
#
# v15 更新（2026-04-25）：
# • 💎++ M30 標記為 [BIAS-勿實盤]
# • 新增 💎+s2 無MIN 對照組，證實 MIN30 必要性
#
# v14 更新（2026-04-25）：
# • 新增 #15 💎++ M30 趨勢過濾版（已驗證失敗）
# • 新增 #16 💎+s2 M30 三重出場版（WF +7.67%）
#
# v13 更新（2026-04-25）：
# • 新增 b11（KDJ超賣金叉）、s8（KDJ高位死叉）兩個訊號
# • 策略池從 25 個精簡到 14 個
#
# 每個策略 dict 欄位：
#   desc           - UI 顯示的策略說明
#   buy            - 11 個買入信號的 tuple (b1~b11)
#   sell           - 8 個賣出信號的 tuple (s1~s8)
#   min_hold_days  - (可選) 策略級最小持倉天數
#
# buy  tuple 順序：b1  b2  b3  b4  b5  b6  b7  b8  b9  b10  b11
# sell tuple 順序：s1  s2  s3  s4  s5  s6  s7  s8

STRATEGY_PRESETS = {

    # ══════════════════════════════════════════════════════════════
    # 🏆 實盤主力（1 個冠軍）
    # ══════════════════════════════════════════════════════════════

    # ── 1. 💎+s2 M30 三重出場版【實盤主力冠軍】───────────────────
    "💎+s2 M30 三重出場版【實盤冠軍】": {
        "desc": "【🏆 實盤主力冠軍】b6 (RSI<30) 進場，s2+s6+s8 三重出場（布林上軌 / MACD死叉 / KDJ高位死叉），最少持倉30天。WF +7.67%（策略池最高）/ 延伸 +12.68% / 樣本 2126 / 勝率 69.2% / 退化率 -2.5%（最健康）。MIN30 在此策略中獨立貢獻 +3.86% alpha（防止 s2 過早觸發），是策略池史上最健康+最強的組合。",
        "buy":  (False, False, False, False, False, True,  False, False, False, False, False),
        "sell": (False, True,  False, False, False, True,  False, True),
        "min_hold_days": 30,
    },

    # ══════════════════════════════════════════════════════════════
    # 🥈 實盤候選（4 個，可作分散組合或備用）
    # ══════════════════════════════════════════════════════════════

    # ── 2. 💎+ M30 RSI 進雙出 MIN30 ──────────────────────────────
    "💎+ M30 RSI進雙出MIN30": {
        "desc": "【實盤候選】b6 進場，s6+s8 雙出場，MIN30。WF +6.80% / 延伸 +15.07% / 樣本 2339 / 勝率 68.6%。比 💎M30 略強（+0.24% WF），可作為💎+s2的進取版（持倉更長、延伸更高）。",
        "buy":  (False, False, False, False, False, True,  False, False, False, False, False),
        "sell": (False, False, False, False, False, True,  False, True),
        "min_hold_days": 30,
    },

    # ── 3. 💎M30 純粹均值回歸 MIN30 ──────────────────────────────
    "💎M30 純粹均值回歸MIN30": {
        "desc": "【實盤候選】RSI<30 買入，MACD死叉出，最少持倉30天。WF +6.56% / 延伸 +15.89% / 樣本 2379 / 勝率 69.7%。經典基準策略，邏輯最簡單，可作為實盤對照基準。",
        "buy":  (False, False, False, False, False, True,  False, False, False, False, False),
        "sell": (False, False, False, False, False, True,  False, False),
        "min_hold_days": 30,
    },

    # ── 4. 🔄🔄M30 均值回歸長持 MIN30 ────────────────────────────
    "🔄🔄M30 均值回歸長持MIN30": {
        "desc": "【實盤組合】布林下軌+RSI超賣，MACD死叉出，最少持倉30天。WF +5.42% / 延伸 +15.00% / 樣本 871。比 💎M30 更挑剔但同等強。可與冠軍策略搭配分散風險。",
        "buy":  (False, False, False, False, True,  True,  False, False, False, False, False),
        "sell": (False, False, False, False, False, True,  False, False),
        "min_hold_days": 30,
    },

    # ── 5. ⚡ 突破確認（強牛市專用）──────────────────────────────
    "⚡ 突破確認": {
        "desc": "【強牛市專用】突破放量+趨勢確認，跌破MA20或放量急跌出。WF +1.21% / 延伸 +7.11%。制度矩陣全能冠軍，6/8 制度正回報。適合趨勢明確時搭配使用。",
        "buy":  (True,  False, False, False, False, False, False, True,  False, False, False),
        "sell": (True,  False, False, True,  False, False, False, False),
    },

    # ── 6. 🔄+ MACD+趨勢 MIN30 ──────────────────────────────────
    "🔄+ MACD+趨勢MIN30": {
        "desc": "【趨勢市備用】MACD金叉+趨勢確認，MACD死叉出，MIN30。WF +4.80% / 延伸 +4.92%。WF≈延伸無 bias，數字真實可信。趨勢明確時的穩健選擇。",
        "buy":  (False, False, False, False, False, False, True,  True,  False, False, False),
        "sell": (False, False, False, False, False, True,  False, False),
        "min_hold_days": 30,
    },

    # ══════════════════════════════════════════════════════════════
    # 🎯 精選股策略（2 個，樣本少但延伸極高，適合精選）
    # ══════════════════════════════════════════════════════════════

    # ── 7. 💎K+ M30 雙超賣雙出 MIN30 ─────────────────────────────
    "💎K+ M30 雙超賣雙出MIN30 [精選]": {
        "desc": "【🎯 精選股策略】b6+b11 進場，s6+s8 雙出場，MIN30。WF +5.73% / 延伸 +21.76% / 樣本 133 / 勝率 65.4%。完整 KDJ 強化版均值回歸，樣本少但延伸極高。",
        "buy":  (False, False, False, False, False, True,  False, False, False, False, True),
        "sell": (False, False, False, False, False, True,  False, True),
        "min_hold_days": 30,
    },

    # ── 8. 💎KK30 RSI+KDJ 雙超賣 MIN30 ───────────────────────────
    "💎KK30 RSI+KDJ雙超賣MIN30 [精選]": {
        "desc": "【🎯 精選股策略】b6+b11 進場，MACD死叉出，MIN30。WF +5.08% / 延伸 +21.99% / 樣本 133 / 勝率 66.2%。雙重超賣確認，適合資金有限時挑最佳機會。",
        "buy":  (False, False, False, False, False, True,  False, False, False, False, True),
        "sell": (False, False, False, False, False, True,  False, False),
        "min_hold_days": 30,
    },

    # ══════════════════════════════════════════════════════════════
    # 🔬 診斷對照（用於檢驗 bias 或對照參數，僅供參考）
    # ══════════════════════════════════════════════════════════════

    # ── 9. 💎 純粹均值回歸（無 MIN 對照）─────────────────────────
    "💎 純粹均值回歸 [對照]": {
        "desc": "【MIN 對照】純粹的 b6/s6，無 MIN 限制。WF +4.91% / 延伸 +12.55% / 樣本 1331。對照 💎M30 證實 MIN30 alpha +1.65%。",
        "buy":  (False, False, False, False, False, True,  False, False, False, False, False),
        "sell": (False, False, False, False, False, True,  False, False),
    },

    # ── 10. 💎+s2 三重出場（無 MIN 對照）─────────────────────────
    "💎+s2 三重出場 [無MIN對照]": {
        "desc": "【MIN 貢獻證明】b6/s2+s6+s8 無 MIN。WF +3.81% / 延伸 +10.64% / 樣本 885 / 平均持倉 23 天。對照冠軍 💎+s2 M30 (+7.67%)，證實 MIN30 在三重出場下獨立貢獻 +3.86% alpha。",
        "buy":  (False, False, False, False, False, True,  False, False, False, False, False),
        "sell": (False, True,  False, False, False, True,  False, True),
    },

    # ── 11. 💎M20 純粹均值回歸 MIN20（MIN 參數對照）──────────────
    "💎M20 純粹均值回歸MIN20 [對照]": {
        "desc": "【MIN 參數對照】b6/s6 MIN20。WF +3.52% / 延伸 +16.47% / 樣本 1914。延伸最高但 WF 過於保守，證實 MIN30 才是最優參數。",
        "buy":  (False, False, False, False, False, True,  False, False, False, False, False),
        "sell": (False, False, False, False, False, True,  False, False),
        "min_hold_days": 20,
    },

    # ── 12. 🔄基準 純MACD週期（無 MIN 對照）──────────────────────
    "🔄基準 純MACD週期 [對照]": {
        "desc": "【MIN 貢獻對照】純 b7/s6 無任何過濾。WF +0.42% / 延伸 +8.80% / 樣本 512。對比🔄M30的+4.60%，可量化 MIN30 帶來的 alpha 約 +4.18%。",
        "buy":  (False, False, False, False, False, False, True,  False, False, False, False),
        "sell": (False, False, False, False, False, True,  False, False),
    },

    # ── 13. 💎K30 純 KDJ 超賣 MIN30（已驗證失敗）─────────────────
    "💎K30 純KDJ超賣MIN30 [已驗證]": {
        "desc": "【⚠️ 純 KDJ 失敗】WF +1.50% / 延伸 +10.46% / 樣本 599。KDJ 單獨進場效果遠不如 RSI。證實 b6 比 b11 更適合作主進場訊號。",
        "buy":  (False, False, False, False, False, False, False, False, False, False, True),
        "sell": (False, False, False, False, False, True,  False, False),
        "min_hold_days": 30,
    },

    # ══════════════════════════════════════════════════════════════
    # ❌ 已驗證 BIAS（保留作為教訓紀錄，勿實盤）
    # ══════════════════════════════════════════════════════════════

    # ── 14. 📈 均值回歸（已驗證 BIAS）────────────────────────────
    "📈 均值回歸 [BIAS-勿實盤]": {
        "desc": "【⚠️ 已驗證 Survivorship Bias】WF +10.33% 看似最高，但延伸僅 +3.81% （49.8% 勝率）。原本的高 OOS 數字只統計『跑完全程』的贏家。保留作為 bias 警示對照。",
        "buy":  (False, False, False, False, True,  True,  False, False, False, False, False),
        "sell": (False, True,  False, False, True,  False, False, False),
    },

    # ── 15. 🏗️M30 底部形態 MIN30（新發現 BIAS）────────────────
    "🏗️M30 底部形態MIN30 [BIAS-勿實盤]": {
        "desc": "【⚠️ Survivorship Bias】底部突破+MACD金叉 MIN30。WF +6.53% 但延伸僅 +2.19% （49.1% 勝率）。MIN30 強行抓底部假突破。底部形態類不適合 MIN。",
        "buy":  (False, False, False, True,  False, False, True,  False, False, False, False),
        "sell": (False, False, False, False, False, True,  False, False),
        "min_hold_days": 30,
    },

    # ── 16. ⚡+ 突破確認長持（已知 BIAS）─────────────────────────
    "⚡+ 突破確認長持MIN30 [BIAS-勿實盤]": {
        "desc": "【⚠️ Survivorship Bias】b1+b8 + MACD死叉 + MIN30。WF +6.20% / 延伸僅 +3.82%。WF 數字過於樂觀。",
        "buy":  (True,  False, False, False, False, False, False, True,  False, False, False),
        "sell": (False, False, False, False, False, True,  False, False),
        "min_hold_days": 30,
    },

    # ── 17. 💎++ M30 趨勢過濾版（已驗證嚴重過擬合）─────────────
    "💎++ M30 趨勢過濾版 [BIAS-勿實盤]": {
        "desc": "【⚠️ 嚴重過擬合】b6+b8 進場，s6+s8 雙出場，MIN30。WF 僅 +0.22% / 退化率 90.5% / 樣本暴跌至 126（vs 💎+ M30 的 2339，減 95%）。原因：b6（RSI<30）通常出現在下跌中，此時個股 MA20 已破 MA60，b8 不成立。教訓：b6 與 b8 邏輯互斥，不能組合。",
        "buy":  (False, False, False, False, False, True,  False, True,  False, False, False),
        "sell": (False, False, False, False, False, True,  False, True),
        "min_hold_days": 30,
    },

}

PRESET_NAMES  = ["✏️ 自定義"] + list(STRATEGY_PRESETS.keys())
PRESET_CUSTOM = "✏️ 自定義"

BUY_LABELS = [
    "①突破放量", "②MA5金叉", "③底背離", "④底部突破",
    "⑤布林下軌", "⑥RSI超賣", "⑦MACD金叉", "⑧趨勢確認",
    "⑨52週新高", "⑩縮量回調", "⑪KDJ超賣金叉",
]
SELL_LABELS = [
    "⑫頭部破MA20", "⑬布林上軌", "⑭縮量頂部", "⑮放量急跌",
    "⑯RSI超買", "⑰MACD死叉", "⑱三日陰線", "⑲KDJ高位死叉",
]

B_NAMES = ["b1", "b2", "b3", "b4", "b5", "b6", "b7", "b8", "b9", "b10", "b11"]
S_NAMES = ["s1", "s2", "s3", "s4", "s5", "s6", "s7", "s8"]

# TradingView Screener
TV_URL = "https://scanner.tradingview.com/hongkong/scan"
TV_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "Content-Type": "application/json",
    "Origin":  "https://www.tradingview.com",
    "Referer": "https://www.tradingview.com/",
}
