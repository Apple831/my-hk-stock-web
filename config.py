# ══════════════════════════════════════════════════════════════════
# config.py — 策略組合預設 & 全局常量
# ══════════════════════════════════════════════════════════════════

# buy_sigs  tuple 順序：b1  b2  b3  b4  b5  b6  b7  b8  b9  b10
# sell_sigs tuple 順序：s1  s2  s3  s4  s5  s6  s7

STRATEGY_PRESETS = {

    # ── 1. 趨勢動能（原版）b1 + b8 + b9 ─────────────────────────
    "🔥 趨勢動能（momentum）": {
        "desc": "突破放量 + 趨勢確認（MA20>MA60）+ 52週新高，只在最強上升行情操作。",
        "buy":  (True,  False, False, False, False, False, False, True,  True,  False),
        #        b1     b2     b3     b4     b5     b6     b7     b8     b9     b10
        "sell": (True,  False, False, True,  False, False, False),
        #        s1     s2     s3     s4     s5     s6     s7
    },

    # ── 2. 趨勢回調低吸（原版）b8 + b10 ──────────────────────────
    "🎯 趨勢回調低吸（pullback）": {
        "desc": "上升趨勢（MA20>MA60）中等待縮量回調至MA20再進場，低風險等待機會。",
        "buy":  (False, False, False, False, False, False, False, True,  False, True),
        #        b1     b2     b3     b4     b5     b6     b7     b8     b9     b10
        "sell": (True,  False, False, False, False, True,  False),
        #        s1     s2     s3     s4     s5     s6     s7
    },

    # ── 3. 底部背離反轉（原版）b3 + b7 ───────────────────────────
    "💎 底部背離反轉（divergence）": {
        "desc": "底背離（價創新低但MACD未跟）+ MACD金叉，熊市末期最有效，信號少但可靠。",
        "buy":  (False, False, True,  False, False, False, True,  False, False, False),
        #        b1     b2     b3     b4     b5     b6     b7     b8     b9     b10
        "sell": (False, False, False, False, False, True,  True),
        #        s1     s2     s3     s4     s5     s6     s7
    },

    # ── 4. 突破確認（原版）b1 + b8 ───────────────────────────────
    "⚡ 突破確認（breakout）": {
        "desc": "突破放量 + 趨勢確認（MA20>MA60），確保突破發生在上升趨勢中，減少假突破。",
        "buy":  (True,  False, False, False, False, False, False, True,  False, False),
        #        b1     b2     b3     b4     b5     b6     b7     b8     b9     b10
        "sell": (True,  False, False, True,  False, False, False),
        #        s1     s2     s3     s4     s5     s6     s7
    },

    # ── 5. 底部形態完成（原版）b4 + b7 ───────────────────────────
    # ✅ 唯一通過 Walk-Forward 驗證的策略（OOS +2.36%，退化率 22%）
    "🏗️ 底部形態完成（bottom）": {
        "desc": "底部突破MA20 + MACD金叉，WF驗證唯一通過策略（OOS +2.36%，退化率22%）。",
        "buy":  (False, False, False, True,  False, False, True,  False, False, False),
        #        b1     b2     b3     b4     b5     b6     b7     b8     b9     b10
        "sell": (True,  False, False, False, False, True,  False),
        #        s1     s2     s3     s4     s5     s6     s7
    },

    # ── 6. 超賣反彈 b6 + b7 ──────────────────────────────────────
    # ⚠️ b6（RSI<30）有 hsi_bullish gate，熊市自動停用。
    # 熊市時退化為單條件 b7（MACD金叉），信號頻率大幅上升但質量下降。
    # 最適合牛市中的短暫超賣回調，不適合系統性下跌行情。
    "📉 超賣反彈（oversold bounce）": {
        "desc": "RSI超賣（<30）+ MACD金叉，極端超賣時反彈進場。\n注：RSI條件在熊市自動停用（僅剩MACD金叉），牛市震盪時效果最好。",
        "buy":  (False, False, False, False, False, True,  True,  False, False, False),
        #        b1     b2     b3     b4     b5     b6     b7     b8     b9     b10
        "sell": (False, True,  False, False, True,  False, False),
        #        s1     s2     s3     s4     s5     s6     s7
    },

    # ── 7. 量化確認 b1 + b2 + b8 ─────────────────────────────────
    # 三層動能確認：放量突破（短線）+ MA5金叉（短線確認）+ MA20>MA60（中線趨勢）
    # 無信號衝突，無 gate 問題，邏輯完全一致。
    # 信號頻率較低，但每個信號都有三重確認，品質較高。
    "📊 量化確認（quant confirm）": {
        "desc": "突破放量 + MA5金叉 + 趨勢確認（MA20>MA60）三重確認，信號少但品質高。",
        "buy":  (True,  True,  False, False, False, False, False, True,  False, False),
        #        b1     b2     b3     b4     b5     b6     b7     b8     b9     b10
        "sell": (True,  False, False, True,  False, False, False),
        #        s1     s2     s3     s4     s5     s6     s7
    },
}

PRESET_NAMES  = ["✏️ 自定義"] + list(STRATEGY_PRESETS.keys())
PRESET_CUSTOM = "✏️ 自定義"

BUY_LABELS = [
    "①突破放量", "②MA5金叉", "③底背離", "④底部突破",
    "⑤布林下軌", "⑥RSI超賣", "⑦MACD金叉", "⑧趨勢確認",
    "⑨52週新高", "⑩縮量回調",
]
SELL_LABELS = [
    "⑪頭部破MA20", "⑫布林上軌", "⑬縮量頂部", "⑭放量急跌",
    "⑮RSI超買", "⑯MACD死叉", "⑰三日陰線",
]

B_NAMES = ["b1", "b2", "b3", "b4", "b5", "b6", "b7", "b8", "b9", "b10"]
S_NAMES = ["s1", "s2", "s3", "s4", "s5", "s6", "s7"]

# TradingView Screener
TV_URL = "https://scanner.tradingview.com/hongkong/scan"
TV_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "Content-Type": "application/json",
    "Origin":  "https://www.tradingview.com",
    "Referer": "https://www.tradingview.com/",
}
