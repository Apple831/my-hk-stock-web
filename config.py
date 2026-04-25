# ══════════════════════════════════════════════════════════════════
# config.py — 策略組合預設 & 全局常量
# ══════════════════════════════════════════════════════════════════
#
# v13 更新（2026-04-25）：
# • 新增 b11（KDJ超賣金叉）、s8（KDJ高位死叉）兩個訊號
# • 策略池從 25 個精簡到 14 個：5 實盤 + 5 診斷 + 4 KDJ 新實驗
# • 已移除確認 survivorship bias 或表現平庸的策略
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
    # 🏆 實盤候選（5 個，已驗證 alpha，可實盤使用）
    # ══════════════════════════════════════════════════════════════

    # ── 1. 💎M30 純粹均值回歸MIN30（策略池冠軍）─────────────────
    "💎M30 純粹均值回歸MIN30": {
        "desc": "【實盤冠軍】RSI<30買入，MACD死叉出，最少持倉30天。WF +6.56% / 延伸 +15.89% / 樣本 2379 / 真實勝率 69.7%。延伸>>WF 證實有真實 alpha，無 bias。建議作為實盤主力策略。",
        "buy":  (False, False, False, False, False, True,  False, False, False, False, False),
        "sell": (False, False, False, False, False, True,  False, False),
        "min_hold_days": 30,
    },

    # ── 2. 🔄🔄M30 均值回歸長持MIN30 ─────────────────────────────
    "🔄🔄M30 均值回歸長持MIN30": {
        "desc": "【實盤組合】布林下軌+RSI超賣，MACD死叉出，最少持倉30天。WF +5.42% / 延伸 +15.00% / 樣本 871。比💎M30更挑剔但同等強。可與💎M30搭配分散。",
        "buy":  (False, False, False, False, True,  True,  False, False, False, False, False),
        "sell": (False, False, False, False, False, True,  False, False),
        "min_hold_days": 30,
    },

    # ── 3. 💎 純粹均值回歸（無 MIN 對照）─────────────────────────
    "💎 純粹均值回歸": {
        "desc": "【實盤對照】純粹的 b6/s6，無 MIN 限制。WF +4.91% / 延伸 +12.55% / 樣本 1331。作為💎M30的對照組保留，可比較 MIN30 帶來多少額外 alpha。",
        "buy":  (False, False, False, False, False, True,  False, False, False, False, False),
        "sell": (False, False, False, False, False, True,  False, False),
    },

    # ── 4. ⚡ 突破確認（強牛市專用）──────────────────────────────
    "⚡ 突破確認": {
        "desc": "【強牛市專用】突破放量+趨勢確認，跌破MA20或放量急跌出。WF +1.21% / 延伸 +7.11%。制度矩陣全能冠軍，6/8 制度正回報。適合趨勢明確時搭配使用。",
        "buy":  (True,  False, False, False, False, False, False, True,  False, False, False),
        "sell": (True,  False, False, True,  False, False, False, False),
    },

    # ── 5. 🔄+ MACD+趨勢MIN30 ───────────────────────────────────
    "🔄+ MACD+趨勢MIN30": {
        "desc": "【趨勢市備用】MACD金叉+趨勢確認，MACD死叉出，最少持倉30天。WF +4.80% / 延伸 +4.92%。WF≈延伸，無 bias，數字真實可信。趨勢明確時的穩健選擇。",
        "buy":  (False, False, False, False, False, False, True,  True,  False, False, False),
        "sell": (False, False, False, False, False, True,  False, False),
        "min_hold_days": 30,
    },

    # ══════════════════════════════════════════════════════════════
    # 🔬 診斷對照（5 個，用於檢驗 bias 或對照參數）
    # ══════════════════════════════════════════════════════════════

    # ── 6. 📈 均值回歸（已驗證 BIAS，僅供對照）────────────────────
    "📈 均值回歸 [BIAS-勿實盤]": {
        "desc": "【⚠️ 已驗證 Survivorship Bias】WF +10.33% 看似最高，但延伸僅 +3.81% （49.8% 勝率）。原本的高 OOS 數字只統計『跑完全程』的贏家。保留作為 bias 警示對照。",
        "buy":  (False, False, False, False, True,  True,  False, False, False, False, False),
        "sell": (False, True,  False, False, True,  False, False, False),
    },

    # ── 7. 🏗️M30 底部形態MIN30（新發現 BIAS）─────────────────────
    "🏗️M30 底部形態MIN30 [BIAS-勿實盤]": {
        "desc": "【⚠️ 新發現 Survivorship Bias】底部突破+MACD金叉，MIN30。WF +6.53% 但延伸僅 +2.19% （49.1% 勝率）。MIN30 強行抓底部假突破。底部形態類不適合 MIN。",
        "buy":  (False, False, False, True,  False, False, True,  False, False, False, False),
        "sell": (False, False, False, False, False, True,  False, False),
        "min_hold_days": 30,
    },

    # ── 8. ⚡+ 突破確認長持（已知 BIAS）──────────────────────────
    "⚡+ 突破確認長持MIN30 [BIAS-勿實盤]": {
        "desc": "【⚠️ Survivorship Bias】b1+b8 + MACD死叉 + MIN30。WF +6.20% / 延伸僅 +3.82%。WF 數字過於樂觀。保留對照。",
        "buy":  (True,  False, False, False, False, False, False, True,  False, False, False),
        "sell": (False, False, False, False, False, True,  False, False),
        "min_hold_days": 30,
    },

    # ── 9. 💎M20 純粹均值回歸MIN20（MIN 參數對照）────────────────
    "💎M20 純粹均值回歸MIN20 [對照]": {
        "desc": "【MIN 參數對照】b6/s6 MIN20。WF +3.52% / 延伸 +16.47% / 樣本 1914。延伸最高但 WF 過於保守，證實 MIN30 才是最優參數。保留作為 MIN 敏感度分析。",
        "buy":  (False, False, False, False, False, True,  False, False, False, False, False),
        "sell": (False, False, False, False, False, True,  False, False),
        "min_hold_days": 20,
    },

    # ── 10. 🔄基準 純MACD週期（無 MIN 對照）──────────────────────
    "🔄基準 純MACD週期 [對照]": {
        "desc": "【MIN 貢獻對照】純 b7/s6 無任何過濾。WF +0.42% / 延伸 +8.80% / 樣本 512。對比🔄M30的+4.60%，可量化 MIN30 帶來的 alpha 約 +4.18%。",
        "buy":  (False, False, False, False, False, False, True,  False, False, False, False),
        "sell": (False, False, False, False, False, True,  False, False),
    },

    # ══════════════════════════════════════════════════════════════
    # 🆕 KDJ 新實驗（4 個，待 WF 驗證）
    # ══════════════════════════════════════════════════════════════

    # ── 11. 💎K30 純 KDJ 超賣 MIN30 ──────────────────────────────
    "💎K30 純KDJ超賣MIN30 [新]": {
        "desc": "【🆕 新實驗】KDJ超賣金叉(K<20,D<20,K上穿D)買入，MACD死叉出，最少持倉30天。比 b6 (RSI<30) 更嚴格的雙重深度超賣確認。預期樣本較少但精度更高。",
        "buy":  (False, False, False, False, False, False, False, False, False, False, True),
        "sell": (False, False, False, False, False, True,  False, False),
        "min_hold_days": 30,
    },

    # ── 12. 💎KK30 RSI+KDJ 雙超賣 MIN30 ──────────────────────────
    "💎KK30 RSI+KDJ雙超賣MIN30 [新]": {
        "desc": "【🆕 新實驗】b6 + b11 同時觸發（RSI<30 且 KDJ超賣金叉），MACD死叉出，MIN30。最嚴格的均值回歸進場條件，預期樣本少但精度極高。",
        "buy":  (False, False, False, False, False, True,  False, False, False, False, True),
        "sell": (False, False, False, False, False, True,  False, False),
        "min_hold_days": 30,
    },

    # ── 13. 💎+ M30 RSI 進 + 雙出場 ──────────────────────────────
    "💎+ M30 RSI進雙出MIN30 [新]": {
        "desc": "【🆕 新實驗】b6 (RSI<30) 買入，s6 (MACD死叉) 或 s8 (KDJ高位死叉) 任一觸發出場，MIN30。給冠軍策略💎M30加 KDJ 出場確認，預期更早抓到頂部。",
        "buy":  (False, False, False, False, False, True,  False, False, False, False, False),
        "sell": (False, False, False, False, False, True,  False, True),
        "min_hold_days": 30,
    },

    # ── 14. 💎K+ M30 雙超賣 + 雙出場 ─────────────────────────────
    "💎K+ M30 雙超賣雙出MIN30 [新]": {
        "desc": "【🆕 新實驗】b6+b11 雙超賣進場，s6+s8 雙出場，MIN30。最完整的 KDJ 強化版均值回歸。預期樣本最少但每筆品質最高。",
        "buy":  (False, False, False, False, False, True,  False, False, False, False, True),
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
