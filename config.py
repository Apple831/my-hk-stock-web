# ══════════════════════════════════════════════════════════════════
# config.py — 策略組合預設 & 全局常量
# ══════════════════════════════════════════════════════════════════
#
# 每個策略 dict 欄位：
#   desc           - UI 顯示的策略說明
#   buy            - 10 個買入信號的 tuple (b1~b10)
#   sell           - 7 個賣出信號的 tuple (s1~s7)
#   min_hold_days  - (可選) 策略級最小持倉天數，過濾快死叉的假突破
#
# buy  tuple 順序：b1  b2  b3  b4  b5  b6  b7  b8  b9  b10
# sell tuple 順序：s1  s2  s3  s4  s5  s6  s7

STRATEGY_PRESETS = {

    # ── 1. 趨勢動能 b1+b8+b9 ─────────────────────────────────────
    "🔥 趨勢動能（momentum）": {
        "desc": "突破放量+趨勢確認+52週新高。WF OOS -0.06%（原生虧損），延伸追蹤 +6.76%。原版不建議實盤。",
        "buy":  (True,  False, False, False, False, False, False, True,  True,  False),
        "sell": (True,  False, False, True,  False, False, False),
    },

    # ── 2. 趨勢回調低吸 b8+b10 ───────────────────────────────────
    "🎯 趨勢回調低吸（pullback）": {
        "desc": "上升趨勢中縮量回調至MA20再進場。WF OOS +1.14%，延伸 +2.52%，1571筆大樣本，穩健但回報偏低。",
        "buy":  (False, False, False, False, False, False, False, True,  False, True),
        "sell": (True,  False, False, False, False, True,  False),
    },

    # ── 3. 突破確認 b1+b8 ─────────────────────────────────────────
    "⚡ 突破確認（breakout）": {
        "desc": "突破放量+趨勢確認。WF OOS +1.21%，延伸 +7.11%（59%勝率），WF被大幅低估。制度矩陣：震盪/轉折市+4%。",
        "buy":  (True,  False, False, False, False, False, False, True,  False, False),
        "sell": (True,  False, False, True,  False, False, False),
    },

    # ── 4. 底部形態完成 b4+b7 / s1+s6 ─────────────────────────────
    "🏗️ 底部形態完成（bottom）": {
        "desc": "底部突破MA20+MACD金叉，破MA20或MACD死叉出場。WF OOS +1.63%，延伸 +9.67%（70.5%勝率），被嚴重低估。",
        "buy":  (False, False, False, True,  False, False, True,  False, False, False),
        "sell": (True,  False, False, False, False, True,  False),
    },

    # ── 5. 超賣反彈 b6+b7 / s2+s5 ─────────────────────────────────
    "📉 超賣反彈（oversold bounce）": {
        "desc": "RSI超賣+MACD金叉買入，超買賣出。WF OOS +6.33%，延伸 +11.41%但僅16筆，樣本過小需更多驗證。",
        "buy":  (False, False, False, False, False, True,  True,  False, False, False),
        "sell": (False, True,  False, False, True,  False, False),
    },

    # ── 6. 量化確認 b1+b2+b8 ──────────────────────────────────────
    "📊 量化確認（quant confirm）": {
        "desc": "突破放量+MA5金叉+趨勢確認三重確認。WF OOS +0.97%，延伸 +8.60%（74%勝率），WF嚴重低估策略價值。",
        "buy":  (True,  True,  False, False, False, False, False, True,  False, False),
        "sell": (True,  False, False, True,  False, False, False),
    },

    # ── 7. 均值回歸 b5+b6 / s2+s5 ─────────────────────────────────
    "📈 均值回歸（mean reversion）": {
        "desc": "布林下軌+RSI超賣買入，超買出場。⚠️ WF OOS +10.33%但延伸僅 +3.81%，疑似survivorship bias，實際僅中等策略。",
        "buy":  (False, False, False, False, True,  True,  False, False, False, False),
        "sell": (False, True,  False, False, True,  False, False),
    },

    # ── 8. 均值回歸長持 b5+b6 / s6 ───────────────────────────────
    "🔄 均值回歸長持（mean reversion long）": {
        "desc": "布林下軌+RSI超賣買入，MACD死叉出場。WF OOS +3.26%，延伸 +13.75%（66.8%勝率）。耐心出場捕捉完整波段。",
        "buy":  (False, False, False, False, True,  True,  False, False, False, False),
        "sell": (False, False, False, False, False, True,  False),
    },

    # ── 9. 純粹均值回歸 b6 / s6 ───────────────────────────────────
    "💎 純粹均值回歸（pure mean reversion）": {
        "desc": "RSI超賣買入，MACD死叉出場。WF最強：OOS +4.91%，延伸 +12.55%（65.9%勝率），1331筆大樣本。比b5+b6/s6進場頻率高2.7倍。",
        "buy":  (False, False, False, False, False, True,  False, False, False, False),
        "sell": (False, False, False, False, False, True,  False),
    },

    # ── 10. 突破確認長持 MIN30 b1+b8 / s6 ────────────────────────
    # ✅ WF OOS +6.20%｜延伸 +3.82% (1207 筆, 49% 勝率)｜MIN30 假設驗證成功
    "⚡+ 突破確認長持（breakout long, MIN30）": {
        "desc": "突破放量+趨勢確認，MACD死叉出場，最少持倉30天過濾假突破。WF OOS +6.20%（-105.6%退化率優），延伸+3.82%，55天持倉。min_hold_days驗證：30天前死叉=假突破，30天後才是真趨勢。",
        "buy":  (True,  False, False, False, False, False, False, True,  False, False),
        "sell": (False, False, False, False, False, True,  False),
        "min_hold_days": 30,
    },

    # ── 11. 底部形態 + MACD死叉出場 b4+b7 / s6 ────────────────────
    # ✅ WF OOS +1.84%｜退化率 -141.8%（優）｜延伸 +10.67% (64 筆, 73.4% 勝率)
    "🏗️s6 底部形態死叉出（bottom+s6）": {
        "desc": "底部突破MA20+MACD金叉，MACD死叉出場。WF OOS +1.84%，退化率-141.8%（優），延伸+10.67%（73.4%勝率）。比s1+s6版本更乾淨，s1無貢獻。",
        "buy":  (False, False, False, True,  False, False, True,  False, False, False),
        "sell": (False, False, False, False, False, True,  False),
    },

    # ── 12. 突破確認 MIN20 b1+b8 / s1+s4 ─────────────────────────
    # 🔬 實驗：原版 b1+b8/s1+s4 WF +1.21%，延伸 +7.11%（59%勝率），持倉 14 天
    "⚡M20 突破確認MIN20（breakout MIN20）": {
        "desc": "突破放量+趨勢確認，破MA20或放量急跌出場，最少持倉20天。原版WF +1.21%但持倉僅14天，延伸+7.11%（59%勝率），加MIN20過濾快出場的假突破。",
        "buy":  (True,  False, False, False, False, False, False, True,  False, False),
        "sell": (True,  False, False, True,  False, False, False),
        "min_hold_days": 20,
    },

    # ── 13. MACD金叉死叉週期 b7 / s6 ─────────────────────────────
    # 🔬 實驗：原版 b7/s6 WF +0.22%，延伸 +8.31%（77.8%勝率），持倉 15 天
    "🔄M20 MACD週期MIN20（macd cycle MIN20）": {
        "desc": "MACD金叉入場，MACD死叉出場，最少持倉20天。原版WF +0.22%但持倉僅15天，延伸+8.31%（77.8%勝率），加MIN20過濾15天內的快速假金叉。",
        "buy":  (False, False, False, False, False, False, True,  False, False, False),
        "sell": (False, False, False, False, False, True,  False),
        "min_hold_days": 20,
    },

    # ── 14. 突破確認 MIN30 b1+b8 / s1+s4 ─────────────────────────
    # 🔬 實驗：⚡M20 WF +1.79%（提升有限），試 MIN30 看能否推高
    # 對比 ⚡+ b1+b8/s6 MIN30 WF +6.20%，推測 s1+s4 較 s6 慢觸發
    "⚡M30 突破確認MIN30（breakout MIN30）": {
        "desc": "突破放量+趨勢確認，破MA20或放量急跌出場，最少持倉30天。MIN20版本 WF +1.79%提升有限，試MIN30看能否推高。",
        "buy":  (True,  False, False, False, False, False, False, True,  False, False),
        "sell": (True,  False, False, True,  False, False, False),
        "min_hold_days": 30,
    },

    # ── 15. MACD金叉死叉週期 MIN30 b7 / s6 ───────────────────────
    # 🔬 實驗：🔄M20 WF +3.23%（大幅提升），試 MIN30 能否再推高
    # MACD 金叉最易假信號，MIN20 已過濾很多，MIN30 或許捕捉更完整週期
    "🔄M30 MACD週期MIN30（macd cycle MIN30）": {
        "desc": "MACD金叉入場，MACD死叉出場，最少持倉30天。MIN20版本 WF +3.23%已驗證過濾假金叉有效，試MIN30捕捉完整MACD週期。",
        "buy":  (False, False, False, False, False, False, True,  False, False, False),
        "sell": (False, False, False, False, False, True,  False),
        "min_hold_days": 30,
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
