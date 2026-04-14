# ══════════════════════════════════════════════════════════════════
# config.py — 策略組合預設 & 全局常量
# ══════════════════════════════════════════════════════════════════

# buy_sigs  tuple 順序：b1 b2 b3 b4 b5 b6 b7 b8 b9 b10
# sell_sigs tuple 順序：s1 s2 s3 s4 s5 s6 s7

STRATEGY_PRESETS = {
    "🔥 趨勢動能（52週新高）": {
        "desc":    "追強勢股：52週新高突破 + 突破放量，頭部跌破MA20離場。\n適合牛市，勝率最高。",
        "buy":  (True,  False, False, False, False, False, False, False, True,  False),
        "sell": (True,  False, False, True,  False, False, False),
    },
    "🎯 趨勢回調低吸": {
        "desc":    "上升趨勢中縮量回調至MA20，低風險加倉點。\n每筆風險最小，適合中線持有。",
        "buy":  (False, False, False, False, False, False, False, True,  False, True),
        "sell": (True,  False, False, False, False, True,  False),
    },
    "💎 底部背離反轉": {
        "desc":    "底背離 + MACD金叉確認，中線底部建倉。\n訊號少但準，需要耐心等待。",
        "buy":  (False, False, True,  False, False, False, True,  False, False, False),
        "sell": (False, False, False, False, False, True,  True),
    },
    "⚡ 突破確認": {
        "desc":    "個股趨勢向上 + 突破放量，雙重確認減少假突破。\n中短線皆宜。",
        "buy":  (True,  True, False, False, False, False, False, True,  False, False),
        "sell": (True,  False, False, True,  False, False, False),
    },
    "🏗️ 底部形態完成": {
        "desc":    "底部形態突破MA20 + MACD金叉，等形態完全確認才入場。\n較保守，適合風險較低的操作。",
        "buy":  (False, False, False, True,  False, False, True,  False, False, False),
        "sell": (True,  False, False, False, False, True,  False),
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
