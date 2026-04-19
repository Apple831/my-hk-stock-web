# ══════════════════════════════════════════════════════════════════
# config.py — 策略組合預設 & 全局常量
# ══════════════════════════════════════════════════════════════════

# buy_sigs  tuple 順序：b1  b2  b3  b4  b5  b6  b7  b8  b9  b10
# sell_sigs tuple 順序：s1  s2  s3  s4  s5  s6  s7

STRATEGY_PRESETS = {

    # ── 1. 趨勢動能 b1+b8+b9 ─────────────────────────────────────
    # ❌ WF 結果：OOS -0.06%，退化率29.0%，正回報2/5，策略危險
    "🔥 趨勢動能（momentum）": {
        "desc": "突破放量+趨勢確認+52週新高。WF結果：OOS -0.06%（虧損），退化率29.0%，2/5正回報。港股近年弱勢市場效果差，不建議實盤。",
        "buy":  (True,  False, False, False, False, False, False, True,  True,  False),
        #        b1     b2     b3     b4     b5     b6     b7     b8     b9     b10
        "sell": (True,  False, False, True,  False, False, False),
        #        s1     s2     s3     s4     s5     s6     s7
    },

    # ── 2. 趨勢回調低吸 b8+b10 ───────────────────────────────────
    # ✅ WF 結果：OOS +0.94%，退化率-52.9%，正回報4/5，策略穩健
    "🎯 趨勢回調低吸（pullback）": {
        "desc": "上升趨勢中縮量回調至MA20再進場。WF結果：OOS +0.94%，退化率-52.9%（優），4/5正回報。",
        "buy":  (False, False, False, False, False, False, False, True,  False, True),
        #        b1     b2     b3     b4     b5     b6     b7     b8     b9     b10
        "sell": (True,  False, False, False, False, True,  False),
        #        s1     s2     s3     s4     s5     s6     s7
    },

    # ── 3. 突破確認 b1+b8 ─────────────────────────────────────────
    # ✅ WF 結果：OOS +1.12%，退化率-95.1%，正回報4/6，策略穩健
    "⚡ 突破確認（breakout）": {
        "desc": "突破放量+趨勢確認。WF結果：OOS +1.12%，退化率-95.1%（優），4/6正回報。制度矩陣：震盪市+4.5%/轉折期+4.2%最強。",
        "buy":  (True,  False, False, False, False, False, False, True,  False, False),
        #        b1     b2     b3     b4     b5     b6     b7     b8     b9     b10
        "sell": (True,  False, False, True,  False, False, False),
        #        s1     s2     s3     s4     s5     s6     s7
    },

    # ── 4. 底部形態完成 b4+b7 ─────────────────────────────────────
    # ✅ WF 結果：OOS +2.03%，退化率-164.6%，正回報4/5，策略穩健
    "🏗️ 底部形態完成（bottom）": {
        "desc": "底部突破MA20+MACD金叉。WF結果：OOS +2.03%，退化率-164.6%（優），4/5正回報。",
        "buy":  (False, False, False, True,  False, False, True,  False, False, False),
        #        b1     b2     b3     b4     b5     b6     b7     b8     b9     b10
        "sell": (True,  False, False, False, False, True,  False),
        #        s1     s2     s3     s4     s5     s6     s7
    },

    # ── 5. 超賣反彈 b6+b7 ─────────────────────────────────────────
    # 🟡 WF 結果：OOS +6.89%，退化率47.3%，但僅2/7有效Fold，信心低
    "📉 超賣反彈（oversold bounce）": {
        "desc": "RSI超賣+MACD金叉買入，布林上軌+RSI超買出場。WF結果：OOS +6.89%但僅2/7有效Fold，信號稀少需謹慎。",
        "buy":  (False, False, False, False, False, True,  True,  False, False, False),
        #        b1     b2     b3     b4     b5     b6     b7     b8     b9     b10
        "sell": (False, True,  False, False, True,  False, False),
        #        s1     s2     s3     s4     s5     s6     s7
    },

    # ── 6. 量化確認 b1+b2+b8 ──────────────────────────────────────
    # ⚠️ WF 結果：OOS +1.00%，退化率-88.7%，但正回報僅3/7，穩定性待提升
    "📊 量化確認（quant confirm）": {
        "desc": "突破放量+MA5金叉+趨勢確認三重確認。WF結果：OOS +1.00%，退化率-88.7%，但3/7正回報，穩定性待提升。",
        "buy":  (True,  True,  False, False, False, False, False, True,  False, False),
        #        b1     b2     b3     b4     b5     b6     b7     b8     b9     b10
        "sell": (True,  False, False, True,  False, False, False),
        #        s1     s2     s3     s4     s5     s6     s7
    },

    # ── 7. 均值回歸 b5+b6 ─────────────────────────────────────────
    # ✅✅ WF 結果：OOS +10.58%，退化率-38.8%，7/7正回報，7/7有效Fold
    # 全部策略中表現最佳，制度矩陣8/8制度正回報
    # b5/b6 gate 已移除（indicators.py），全天候觸發
    "📈 均值回歸（mean reversion）": {
        "desc": "布林下軌+RSI超賣買入，布林上軌+RSI超買出場。WF最佳策略：OOS +10.58%，退化率-38.8%，7/7正回報，8/8制度正回報。全天候。",
        "buy":  (False, False, False, False, True,  True,  False, False, False, False),
        #        b1     b2     b3     b4     b5     b6     b7     b8     b9     b10
        "sell": (False, True,  False, False, True,  False, False),
        #        s1     s2     s3     s4     s5     s6     s7
    },

    # ── 8. 均值回歸長持 b5+b6 / s6 ───────────────────────────────
    # ✅ WF 結果：OOS +2.73%，退化率16.7%，正回報4/6，策略穩健
    # 改用MACD死叉出場，持倉更長，比s2+s5版本回報低但退化率更正常
    "🔄 均值回歸長持（mean reversion long）": {
        "desc": "布林下軌+RSI超賣買入，MACD死叉出場。WF結果：OOS +2.73%，退化率16.7%，4/6正回報。持倉較長，捕捉完整反彈波段。",
        "buy":  (False, False, False, False, True,  True,  False, False, False, False),
        #        b1     b2     b3     b4     b5     b6     b7     b8     b9     b10
        "sell": (False, False, False, False, False, True,  False),
        #        s1     s2     s3     s4     s5     s6     s7
    },

    # ── 9. 底部形態超買出 b4+b7 / s2+s5 ──────────────────────────
    # ✅ WF 結果：OOS +3.62%，退化率-64.0%，6/6正回報，6/7有效Fold
    # 原版b4+b7改賣出條件，讓反彈走到超買才離場
    "🏗️+ 底部形態超買出（bottom+overbought exit）": {
        "desc": "底部突破MA20+MACD金叉買入，布林上軌+RSI超買出場。WF結果：OOS +3.62%，退化率-64.0%（優），6/6正回報。比原版更完整捕捉反彈。",
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
