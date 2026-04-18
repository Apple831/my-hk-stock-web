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

    # ── 3. 突破確認（原版）b1 + b8 ───────────────────────────────
    "⚡ 突破確認（breakout）": {
        "desc": "突破放量 + 趨勢確認（MA20>MA60），確保突破發生在上升趨勢中，減少假突破。",
        "buy":  (True,  False, False, False, False, False, False, True,  False, False),
        #        b1     b2     b3     b4     b5     b6     b7     b8     b9     b10
        "sell": (True,  False, False, True,  False, False, False),
        #        s1     s2     s3     s4     s5     s6     s7
    },

    # ── 5. 底部形態完成（原版）b4 + b7 ───────────────────────────
    # ✅ 通過 Walk-Forward 驗證（OOS +2.36%，退化率 22%）
    "🏗️ 底部形態完成（bottom）": {
        "desc": "底部突破MA20 + MACD金叉，WF驗證通過策略（OOS +2.36%，退化率22%）。",
        "buy":  (False, False, False, True,  False, False, True,  False, False, False),
        #        b1     b2     b3     b4     b5     b6     b7     b8     b9     b10
        "sell": (True,  False, False, False, False, True,  False),
        #        s1     s2     s3     s4     s5     s6     s7
    },

    # ── 6. 超賣反彈 b6 + b7 ──────────────────────────────────────
    "📉 超賣反彈（oversold bounce）": {
        "desc": "RSI超賣（<30）+ MACD金叉，極端超賣時反彈進場。",
        "buy":  (False, False, False, False, False, True,  True,  False, False, False),
        #        b1     b2     b3     b4     b5     b6     b7     b8     b9     b10
        "sell": (False, True,  False, False, True,  False, False),
        #        s1     s2     s3     s4     s5     s6     s7
    },

    # ── 7. 量化確認 b1 + b2 + b8 ─────────────────────────────────
    "📊 量化確認（quant confirm）": {
        "desc": "突破放量 + MA5金叉 + 趨勢確認（MA20>MA60）三重確認，信號少但品質高。",
        "buy":  (True,  True,  False, False, False, False, False, True,  False, False),
        #        b1     b2     b3     b4     b5     b6     b7     b8     b9     b10
        "sell": (True,  False, False, True,  False, False, False),
        #        s1     s2     s3     s4     s5     s6     s7
    },

    # ── 8. 均值回歸 b5 + b6，賣出 s2 + s5 ────────────────────────
    # ✅ WF 驗證：8/8 制度正回報，全天候策略
    # 入場：布林下軌（b5）OR RSI<30（b6），任一觸發即入場
    # 出場：布林上軌（s2）OR RSI>70（s5），超買即離場
    # 特性：均值回歸，熊市高波動效果最好（弱熊+8%/228筆，強熊+12.5%/204筆）
    # 注意：b5/b6 gate 已移除（indicators.py），行為與 WF 結果一致
    "📈 均值回歸（mean reversion）": {
        "desc": "布林下軌+RSI超賣買入，布林上軌+RSI超買賣出。WF驗證8/8制度正回報，全天候策略。",
        "buy":  (False, False, False, False, True,  True,  False, False, False, False),
        #        b1     b2     b3     b4     b5     b6     b7     b8     b9     b10
        "sell": (False, True,  False, False, True,  False, False),
        #        s1     s2     s3     s4     s5     s6     s7
    },


    # ── 8. 均值回歸 + MACD死叉出場 b5+b6 / s6 ───────────────────
    # WF 驗證通過（投資組合模式）
    # 相比均值回歸（s2+s5），改用 MACD死叉出場，持倉更長，捕捉更完整波段
    "🔄 均值回歸長持（mean reversion long）": {
        "desc": "布林下軌+RSI超賣買入，MACD死叉出場。比s2+s5版本持倉更長，適合捕捉完整反彈波段。",
        "buy":  (False, False, False, False, True,  True,  False, False, False, False),
        #        b1     b2     b3     b4     b5     b6     b7     b8     b9     b10
        "sell": (False, False, False, False, False, True,  False),
        #        s1     s2     s3     s4     s5     s6     s7
    },

    # ── 9. 底部形態完成 + 超買出場 b4+b7 / s2+s5 ─────────────────
    # WF 驗證通過（投資組合模式）
    # 原版 b4+b7 改賣出條件：原 s1+s6（結構出）→ s2+s5（超買出）
    # 讓反彈走到真正超買才離場，捕捉更完整的底部反彈波段
    "🏗️+ 底部形態超買出（bottom+overbought exit）": {
        "desc": "底部突破MA20+MACD金叉買入，布林上軌+RSI超買出場。在b4+b7基礎上改賣出條件，讓反彈走得更完整。",
        "buy":  (False, False, False, True,  False, False, True,  False, False, False),
        #        b1     b2     b3     b4     b5     b6     b7     b8     b9     b10
        "sell": (False, True,  False, False, True,  False, False),
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
