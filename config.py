# ══════════════════════════════════════════════════════════════════
# config.py — 策略組合預設 & 全局常量
# ══════════════════════════════════════════════════════════════════

# buy_sigs  tuple 順序：b1 b2 b3 b4 b5 b6 b7 b8 b9 b10
# sell_sigs tuple 順序：s1 s2 s3 s4 s5 s6 s7

STRATEGY_PRESETS = {

    # ── 1. 趨勢動能（你的版本）b9+b1+b7 ────────────────────────────
    # 理由同意：b9 已隱含強勢趨勢，b8 的 MA20>MA60 確認是冗餘的；
    # b7 MACD金叉加入時機過濾，比純靠 b9 更精準。
    "🔥 趨勢動能（momentum）": {
        "desc":    "52週新高突破 + 放量確認 + MACD金叉三重過濾。\n只在最強上升行情中操作，信號少但質量高。",
        "buy":  (True,  False, False, False, False, False, True,  False, True,  False),
        #         b1     b2     b3     b4     b5     b6     b7     b8     b9     b10
        "sell": (True,  False, False, True,  False, False, False),
        #         s1     s2     s3     s4     s5     s6     s7
    },

    # ── 2. 趨勢回調低吸（你的版本）b8+b10+b6 ───────────────────────
    # 理由同意：b6 RSI<30 在上升趨勢回調中是合理的超賣確認。
    # 注意：b6 有 hsi_bullish gate，恒指熊市時自動停用（策略退化為 b8+b10）。
    "🎯 趨勢回調低吸（pullback）": {
        "desc":    "上升趨勢（MA20>MA60）中等待縮量回調至MA20 + RSI超賣再進場。\n風險最低，需要耐心等待，熊市時 RSI 條件自動停用。",
        "buy":  (False, False, False, False, False, True,  False, True,  False, True),
        #         b1     b2     b3     b4     b5     b6     b7     b8     b9     b10
        "sell": (True,  False, False, False, False, True,  False),
        #         s1     s2     s3     s4     s5     s6     s7
    },

    # ── 3. 底部背離反轉（修正版）b3+b7+b4 ──────────────────────────
    # 不同意你加 b5：b5 有 hsi_bullish gate，熊市自動停用；
    # 但底背離策略偏偏最適合熊市末期，等於在最需要它的時候關掉它。
    # 改為加 b4（底部形態突破MA20），b4 無 hsi_bullish gate，
    # 底背離 + MACD金叉 + 形態確認 = 三重底部信號，且熊市同樣有效。
    "💎 底部背離反轉（divergence）": {
        "desc":    "底背離（價創新低MACD未）+ MACD金叉 + 底部形態突破MA20三重確認。\n全市場環境有效（無牛熊過濾），信號最可靠但機會極少。",
        "buy":  (False, False, True,  True,  False, False, True,  False, False, False),
        #         b1     b2     b3     b4     b5     b6     b7     b8     b9     b10
        "sell": (False, False, False, False, False, True,  True),
        #         s1     s2     s3     s4     s5     s6     s7
    },

    # ── 4. 突破確認（你的版本）b1+b2+b9 ────────────────────────────
    # 理由同意：b2 MA5金叉確認短線動能有效性；b9 52週新高過濾弱勢突破。
    # 注意：三條件AND頻率低，建議配合訊號診斷Tab確認個股適用性。
    "⚡ 突破確認（breakout）": {
        "desc":    "突破放量 + MA5金叉 + 52週新高三重確認，減少假突破。\n中短線皆宜，信號頻率偏低需配合診斷Tab篩選適合股票。",
        "buy":  (True,  True,  False, False, False, False, False, False, True,  False),
        #         b1     b2     b3     b4     b5     b6     b7     b8     b9     b10
        "sell": (True,  False, False, True,  False, False, False),
        #         s1     s2     s3     s4     s5     s6     s7
    },

    # ── 5. 底部形態完成（修正版）b4+b7+b8 ──────────────────────────
    # 不同意加 b10：b4 要求成交量 >1.3x，b10 要求成交量 <0.8x，
    # 兩者物理衝突，疊加後信號幾乎為 0。
    # 改為加 b8（個股 MA20>MA60 趨勢確認），確保底部突破發生在上升趨勢中，
    # 這也是 WF 驗證中 底部形態完成 唯一通過測試的組合的改進方向。
    "🏗️ 底部形態完成（bottom）": {
        "desc":    "底部形態突破MA20 + MACD金叉 + 個股趨勢確認（MA20>MA60）。\n最保守的底部策略，等形態完全確認才入場，WF 驗證通過率最高。",
        "buy":  (False, False, False, True,  False, False, True,  True,  False, False),
        #         b1     b2     b3     b4     b5     b6     b7     b8     b9     b10
        "sell": (True,  False, False, False, False, True,  False),
        #         s1     s2     s3     s4     s5     s6     s7
    },

    # ── 6. 量化動能組合（修正版）b1+b2+b7 ──────────────────────────
    # 不同意加 b6：突破放量（b1）時股價上漲，RSI 通常 >50；
    # b6 要求 RSI<30（超賣），兩者語義矛盾，疊加後信號幾乎為 0。
    # 修正為 b1+b2+b7：三個動能信號疊加（突破+短線金叉+MACD金叉），
    # 邏輯一致，都是向上動能確認，勝率高且無矛盾。
    "📊 量化動能組合（quantitative momentum）": {
        "desc":    "突破放量 + MA5金叉 + MACD金叉三重動能確認。\n信號邏輯完全一致，去除了原版 RSI<30 的矛盾條件，勝率高但機會少。",
        "buy":  (True,  True,  False, False, False, False, True,  False, False, False),
        #         b1     b2     b3     b4     b5     b6     b7     b8     b9     b10
        "sell": (False, False, False, False, True,  True,  False),
        #         s1     s2     s3     s4     s5     s6     s7
    },

    # ── 7. 均值回歸組合（你的版本）b5+b6+b7 ────────────────────────
    # 理由同意：標準均值回歸組合，b5+b6 同時超賣確認極端位置，
    # b7 MACD金叉提供轉折時機。注意：b5/b6 均有 hsi_bullish gate，
    # 熊市自動停用，此策略在牛市震盪中效果最好。
    "🔄 均值回歸組合（mean reversion）": {
        "desc":    "布林下軌 + RSI超賣 + MACD金叉三重極端超賣確認。\n適合震盪牛市，兩個條件均有牛市過濾，熊市自動停用。",
        "buy":  (False, False, False, False, True,  True,  True,  False, False, False),
        #         b1     b2     b3     b4     b5     b6     b7     b8     b9     b10
        "sell": (False, True,  False, False, True,  False, False),
        #         s1     s2     s3     s4     s5     s6     s7
    },

    # ── 8. 多因子確認組合（你的版本）b8+b2+b3+b4 ───────────────────
    # 理由同意：4層確認，邏輯一致（趨勢確認+短線動能+底背離+形態突破）。
    # 預期信號極少，建議只對有歷史信號記錄的個股使用（先跑訊號診斷）。
    "🎯 多因子確認組合（multi-factor）": {
        "desc":    "MA20>MA60 + MA5金叉 + 底背離 + 底部突破MA20四重確認。\n最嚴格的篩選條件，信號極少但可靠性最高，務必先用訊號診斷Tab找適合股票。",
        "buy":  (False, True,  True,  True,  False, False, False, True,  False, False),
        #         b1     b2     b3     b4     b5     b6     b7     b8     b9     b10
        "sell": (True,  False, False, False, False, True,  False),
        #         s1     s2     s3     s4     s5     s6     s7
    },

    # ── 9. 防守型組合（修正版）b8+b9+b10 ───────────────────────────
    # 不同意你的 b8+b1+b9：那與舊版「趨勢動能 b1+b8+b9」完全相同，
    # 只是換了名字，毫無意義。
    # 真正的防守型邏輯：上升趨勢（b8）中，52週新高強勢股（b9）出現縮量回調（b10），
    # 等回調後再買入，比直接追高的風險更低。
    "🛡️ 防守型組合（defensive）": {
        "desc":    "上升趨勢（MA20>MA60）+ 52週強勢股 + 縮量回調至MA20才入場。\n等強勢股回調後低吸，比直接追高風險更低，適合保守型操作。",
        "buy":  (False, False, False, False, False, False, False, True,  True,  True),
        #         b1     b2     b3     b4     b5     b6     b7     b8     b9     b10
        "sell": (True,  False, False, False, False, True,  False),
        #         s1     s2     s3     s4     s5     s6     s7
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
