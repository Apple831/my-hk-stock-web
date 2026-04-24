# tabs/tab_multi_scan.py
# ══════════════════════════════════════════════════════════════════
# 📡 多策略共振掃描
# 模式一：買入共振（按當前恒指制度過濾推薦策略）
# 模式二：持倉賣出警報（用戶輸入持倉列表，掃描賣出訊號）
# ══════════════════════════════════════════════════════════════════

import streamlit as st
import pandas as pd

from data import get_stock_data, get_cached
from indicators import calculate_indicators, precompute_signals
from config import (
    STRATEGY_PRESETS, B_NAMES, S_NAMES,
    BUY_LABELS, SELL_LABELS,
)
from ui_components import cache_banner


# ══════════════════════════════════════════════════════════════════
# 制度 → 推薦策略對應（基於制度矩陣 WF 結果）
# ══════════════════════════════════════════════════════════════════
REGIME_RECOMMENDATIONS = {
    "強牛市":   ["⚡ 突破確認（breakout）"],
    "弱牛市":   [
        "⚡ 突破確認（breakout）",
        "🎯 趨勢回調低吸（pullback）",
        "⚡+ 突破確認長持（breakout long, MIN30）",
        "🔄+ MACD+趨勢MIN30（macd+trend MIN30）",
    ],
    "牛市警惕": [
        "⚡ 突破確認（breakout）",
        "🎯 趨勢回調低吸（pullback）",
    ],
    "熊市觀察": ["🎯 趨勢回調低吸（pullback）"],
    "弱熊市":   [],   # 空 = 停止掃描
    "強熊市":   [],
    "震盪市":   ["⚡ 突破確認（breakout）"],
    "轉折期":   ["⚡ 突破確認（breakout）"],
}

REGIME_EMOJI = {
    "強牛市":   "🟢🟢", "弱牛市":   "🟢",    "牛市警惕": "🟢⚠️",
    "熊市觀察": "🔴⚠️", "弱熊市":   "🔴",    "強熊市":   "🔴🔴",
    "震盪市":   "🟡",   "轉折期":   "🟡⚠️",
}


# ══════════════════════════════════════════════════════════════════
# 判定當前制度（複用 tab_index 邏輯，避免循環 import 用簡化版）
# ══════════════════════════════════════════════════════════════════
def _detect_current_regime() -> dict:
    """只回傳 regime 名稱和 emoji；若 HSI 無法取得則回 None。"""
    df = get_stock_data("^HSI", period="6mo")
    if df.empty or len(df) < 62:
        return {}
    df = calculate_indicators(df)
    c = df.iloc[-1]
    close = float(c["Close"])
    ma20  = float(c["MA20"])
    ma60  = float(c["MA60"])
    hist  = float(c["MACD_Hist"])

    ma_gap_pct = (ma20 - ma60) / ma60 * 100
    macd_pct   = hist / close * 100 if close > 0 else 0.0
    cov_20 = 0.0
    if len(df) >= 20:
        roll = df["Close"].rolling(20)
        mean_v = roll.mean().iloc[-1]
        if mean_v and mean_v > 0:
            cov_20 = roll.std().iloc[-1] / mean_v * 100

    if abs(ma_gap_pct) < 2.0:
        regime = "震盪市" if cov_20 > 2.0 else "轉折期"
    elif ma_gap_pct > 2.0:
        if   macd_pct > 0.5: regime = "強牛市"
        elif macd_pct > 0:   regime = "弱牛市"
        else:                regime = "牛市警惕"
    else:
        if   macd_pct < -0.5: regime = "強熊市"
        elif macd_pct <  0:   regime = "弱熊市"
        else:                 regime = "熊市觀察"

    return {
        "regime":  regime,
        "emoji":   REGIME_EMOJI.get(regime, ""),
        "ma_gap":  ma_gap_pct,
        "macd_p":  macd_pct,
        "cov_20":  cov_20,
    }


# ══════════════════════════════════════════════════════════════════
# 掃描一隻股票某個策略在過去 N 天內是否觸發
# ══════════════════════════════════════════════════════════════════
def _strategy_triggered_recently(
    pre_sigs: dict, buy_tuple: tuple, lookback_days: int,
) -> int:
    """
    回傳：若過去 lookback_days 內有任一日完全觸發此策略，回傳「幾天前觸發」（0=今天）；
          未觸發回 -1。
    完全觸發 = 所有勾選的 buy signal 在同一根 K 線上都為 True。
    """
    active_names = [B_NAMES[k] for k, v in enumerate(buy_tuple) if v]
    if not active_names:
        return -1

    # 取最近 lookback_days+1 根 K 線
    combined = pre_sigs[active_names[0]].copy()
    for name in active_names[1:]:
        combined &= pre_sigs[name]

    # 從最新往回找
    recent = combined.tail(lookback_days + 1)
    if not recent.any():
        return -1
    # 最近一次觸發的索引位置（越接近 -1 越新）
    last_true = recent[recent].index[-1]
    days_ago = (recent.index[-1] - last_true).days
    return days_ago


def _sell_signal_hits(pre_sigs: dict, lookback_days: int) -> list:
    """
    掃描單隻股票在過去 lookback_days 內觸發的賣出訊號列表。
    回傳 [(signal_name, days_ago), ...]
    """
    hits = []
    for k, name in enumerate(S_NAMES):
        series = pre_sigs[name].tail(lookback_days + 1)
        if series.any():
            last_true = series[series].index[-1]
            days_ago = (series.index[-1] - last_true).days
            hits.append((SELL_LABELS[k], days_ago))
    return hits


# ══════════════════════════════════════════════════════════════════
# UI helpers
# ══════════════════════════════════════════════════════════════════
def _days_label(days_ago: int) -> str:
    if days_ago <= 0: return "今天"
    if days_ago == 1: return "1 天前"
    return f"{days_ago} 天前"


def _resonance_badge(n: int) -> tuple:
    """回傳 (文字, 背景色, 文字色, 邊框色)"""
    if n >= 3: return (f"{n} 策略共振", "#EAF3DE", "#3B6D11", "#3B6D11")
    if n == 2: return (f"{n} 策略共振", "#E1EEF9", "#1E4F84", "#1E4F84")
    return          (f"{n} 策略", "#F1EFE8", "#5F5E5A", None)


def _render_stock_card(ticker: str, price: float, pct: float,
                       triggers: list, n_strat: int):
    """triggers = [(strategy_name, days_ago), ...]"""
    badge_text, bg, fg, border = _resonance_badge(n_strat)
    border_style = f"border-left:3px solid {border};border-radius:0 8px 8px 0;" if border else ""

    pct_color = "#1D9E75" if pct >= 0 else "#E24B4A"
    pct_str   = f"{'+' if pct >= 0 else ''}{pct:.2f}%"

    strat_html = ""
    for name, d in triggers:
        # 取策略名稱縮寫（取到全形括號前）
        short = name.split("（")[0].strip()
        strat_html += (
            f"<span style='display:inline-block;padding:2px 7px;border-radius:4px;"
            f"background:#EEEDFE;color:#3C3489;font-size:11px;margin:2px 4px 2px 0'>"
            f"{short}（{_days_label(d)}）</span>"
        )

    st.markdown(
        f"<div style='background:var(--background-color,#fff);"
        f"border:0.5px solid rgba(128,128,128,0.3);{border_style}"
        f"border-radius:8px;padding:10px 14px;margin:0 0 8px 0'>"
        f"<div style='display:flex;justify-content:space-between;align-items:baseline'>"
        f"<div><b style='font-size:15px'>{ticker}</b> "
        f"<span style='color:#888;font-size:12px'>${price:.2f} "
        f"<span style='color:{pct_color}'>{pct_str}</span></span></div>"
        f"<span style='background:{bg};color:{fg};font-size:11px;"
        f"padding:2px 8px;border-radius:4px;font-weight:500'>{badge_text}</span>"
        f"</div>"
        f"<div style='margin-top:6px'>{strat_html}</div>"
        f"</div>",
        unsafe_allow_html=True,
    )


def _render_sell_card(ticker: str, price: float, pct: float, hits: list):
    """hits = [(signal_label, days_ago), ...]"""
    n = len(hits)
    if n >= 2:
        border_color = "#A32D2D"
        badge_bg, badge_fg = "#FCEBEB", "#A32D2D"
        badge_text = f"🚨 {n} 賣出訊號"
    elif n == 1:
        border_color = "#BA7517"
        badge_bg, badge_fg = "#FAEEDA", "#854F0B"
        badge_text = f"⚠️ {n} 賣出訊號"
    else:
        border_color = None
        badge_bg, badge_fg = "#F1EFE8", "#5F5E5A"
        badge_text = "✅ 無訊號"

    pct_color = "#1D9E75" if pct >= 0 else "#E24B4A"
    pct_str   = f"{'+' if pct >= 0 else ''}{pct:.2f}%"

    sig_html = ""
    for label, d in hits:
        sig_html += (
            f"<span style='display:inline-block;padding:2px 7px;border-radius:4px;"
            f"background:#EEEDFE;color:#3C3489;font-size:11px;margin:2px 4px 2px 0'>"
            f"{label}（{_days_label(d)}）</span>"
        )

    border_style = (
        f"border-left:3px solid {border_color};border-radius:0 8px 8px 0;"
        if border_color else ""
    )
    opacity = "" if n > 0 else "opacity:0.6;"

    st.markdown(
        f"<div style='background:var(--background-color,#fff);"
        f"border:0.5px solid rgba(128,128,128,0.3);{border_style}{opacity}"
        f"border-radius:8px;padding:10px 14px;margin:0 0 8px 0'>"
        f"<div style='display:flex;justify-content:space-between;align-items:baseline'>"
        f"<div><b style='font-size:15px'>{ticker}</b> "
        f"<span style='color:#888;font-size:12px'>${price:.2f} "
        f"<span style='color:{pct_color}'>{pct_str}</span></span></div>"
        f"<span style='background:{badge_bg};color:{badge_fg};font-size:11px;"
        f"padding:2px 8px;border-radius:4px;font-weight:500'>{badge_text}</span>"
        f"</div>"
        + (f"<div style='margin-top:6px'>{sig_html}</div>" if sig_html else "")
        + "</div>",
        unsafe_allow_html=True,
    )


# ══════════════════════════════════════════════════════════════════
# 模式一：買入共振掃描
# ══════════════════════════════════════════════════════════════════
def _render_buy_mode(stocks: list, regime_info: dict, lookback: int,
                     use_all_strategies: bool):
    regime = regime_info.get("regime", "")
    emoji  = regime_info.get("emoji", "")

    # ── 決定要掃描的策略 ────────────────────────────────────────
    if use_all_strategies:
        target_strategies = list(STRATEGY_PRESETS.keys())
        mode_label = f"全部 {len(target_strategies)} 個策略"
    else:
        target_strategies = REGIME_RECOMMENDATIONS.get(regime, [])
        mode_label = f"當前制度推薦 {len(target_strategies)}/{len(STRATEGY_PRESETS)} 個策略"

    # ── 熊市禁令 ────────────────────────────────────────────────
    if not use_all_strategies and regime in ("弱熊市", "強熊市"):
        st.markdown(
            f"<div style='background:#FCEBEB;border-left:4px solid #A32D2D;"
            f"padding:12px 18px;border-radius:0 8px 8px 0;margin-bottom:14px'>"
            f"<div style='font-size:16px;font-weight:500;color:#A32D2D'>"
            f"⛔ 當前制度：{emoji} {regime} — 不建議進場</div>"
            f"<div style='font-size:12px;margin-top:4px;color:#A32D2D;opacity:0.85'>"
            f"制度矩陣數據顯示所有策略在此制度均虧損。建議清倉觀望。"
            f"<br>若要強行掃描，勾選「切換到全策略」。</div>"
            f"</div>",
            unsafe_allow_html=True,
        )
        return

    if not target_strategies:
        st.warning("⚠️ 當前制度沒有推薦策略。請切換到「全策略」模式，或拉長觀察時間。")
        return

    # ── 資訊 banner ─────────────────────────────────────────────
    strat_list_html = "".join(
        f"<span style='display:inline-block;padding:2px 8px;margin:2px 4px 2px 0;"
        f"background:rgba(255,255,255,0.1);border-radius:4px;font-size:11px'>{s.split('（')[0]}</span>"
        for s in target_strategies
    )
    st.markdown(
        f"<div style='background:var(--color-background-info,rgba(29,158,117,0.08));"
        f"border-radius:8px;padding:10px 14px;margin-bottom:14px'>"
        f"<div style='font-size:13px;font-weight:500'>"
        f"🌐 當前制度：{emoji} {regime}　｜　掃描 {mode_label}</div>"
        f"<div style='font-size:11px;margin-top:4px;opacity:0.85'>{strat_list_html}</div>"
        f"</div>",
        unsafe_allow_html=True,
    )

    # ── 掃描 ────────────────────────────────────────────────────
    cache = st.session_state.get("stock_cache", {})
    if not cache:
        st.warning("⚠️ 尚未緩存股票數據。請先點側欄「⬇️ 批量下載全部股票」。")
        return

    results = []   # [(ticker, price, pct, [(strategy, days_ago), ...])]
    pbar    = st.progress(0, text="掃描中...")

    for i, ticker in enumerate(stocks):
        pbar.progress((i + 1) / len(stocks), text=f"掃描 {ticker}...")
        df = cache.get(ticker)
        if df is None or df.empty or len(df) < 62:
            continue
        try:
            pre = precompute_signals(df)
            triggers = []
            for strat_name in target_strategies:
                strat = STRATEGY_PRESETS[strat_name]
                d = _strategy_triggered_recently(pre, strat["buy"], lookback)
                if d >= 0:
                    triggers.append((strat_name, d))
            if triggers:
                c, p = df.iloc[-1], df.iloc[-2]
                price = float(c["Close"])
                pct   = (price - float(p["Close"])) / float(p["Close"]) * 100
                results.append((ticker, price, pct, triggers))
        except Exception:
            continue

    pbar.empty()

    if not results:
        st.info("目前沒有任何股票觸發推薦策略。")
        return

    # ── 分組 ────────────────────────────────────────────────────
    results.sort(key=lambda x: (-len(x[3]), x[0]))   # 先按共振數，再按 ticker
    triple = [r for r in results if len(r[3]) >= 3]
    double = [r for r in results if len(r[3]) == 2]
    single = [r for r in results if len(r[3]) == 1]

    total = len(results)
    st.markdown(
        f"<div style='margin-bottom:10px;font-size:12px;color:#888'>"
        f"共 <b>{total}</b> 隻觸發訊號：🔥 {len(triple)} 三重 ｜ 💪 {len(double)} 雙重 ｜ ⚪ {len(single)} 單策略"
        f"</div>",
        unsafe_allow_html=True,
    )

    if triple:
        st.markdown("### 🔥 3+ 策略共振（最強訊號）")
        for ticker, price, pct, trigs in triple:
            _render_stock_card(ticker, price, pct, trigs, len(trigs))

    if double:
        st.markdown("### 💪 2 策略共振")
        for ticker, price, pct, trigs in double:
            _render_stock_card(ticker, price, pct, trigs, len(trigs))

    if single:
        with st.expander(f"⚪ 單策略觸發（{len(single)} 隻）", expanded=False):
            rows = []
            for ticker, price, pct, trigs in single:
                name, d = trigs[0]
                rows.append({
                    "代碼": ticker,
                    "策略": name.split("（")[0],
                    "觸發日": _days_label(d),
                    "現價":  f"${price:.2f}",
                    "漲跌%": f"{'+' if pct >= 0 else ''}{pct:.2f}%",
                })
            df_s = pd.DataFrame(rows)
            st.dataframe(df_s, use_container_width=True, hide_index=True)


# ══════════════════════════════════════════════════════════════════
# 模式二：持倉賣出警報
# ══════════════════════════════════════════════════════════════════
def _render_sell_mode(lookback: int):
    st.markdown("#### 📋 輸入持倉清單（每行一個代碼）")
    holdings_text = st.text_area(
        "例如：0700.HK",
        value=st.session_state.get("holdings_text", "0700.HK\n3690.HK\n9988.HK"),
        height=110, key="holdings_input",
    )
    st.session_state["holdings_text"] = holdings_text

    run = st.button("🔍 掃描賣出訊號", type="primary", key="run_sell_scan")
    if not run:
        return

    # ── 解析持倉 ────────────────────────────────────────────────
    tickers = []
    for line in holdings_text.split("\n"):
        t = line.strip().split("#")[0].strip().upper()
        if t and ".HK" in t:
            tickers.append(t)
    if not tickers:
        st.warning("⚠️ 請輸入至少一個 .HK 代碼。")
        return

    st.markdown(f"#### 📊 持倉賣出訊號（共 {len(tickers)} 隻）")

    # ── 掃描 ────────────────────────────────────────────────────
    results = []
    pbar    = st.progress(0, text="掃描中...")

    for i, ticker in enumerate(tickers):
        pbar.progress((i + 1) / len(tickers), text=f"掃描 {ticker}...")
        df = get_cached(ticker)
        if df.empty or len(df) < 62:
            results.append((ticker, None, None, None))
            continue
        try:
            pre = precompute_signals(df)
            hits = _sell_signal_hits(pre, lookback)
            c, p = df.iloc[-1], df.iloc[-2]
            price = float(c["Close"])
            pct   = (price - float(p["Close"])) / float(p["Close"]) * 100
            results.append((ticker, price, pct, hits))
        except Exception:
            results.append((ticker, None, None, None))

    pbar.empty()

    # ── 排序：訊號多的放前面 ─────────────────────────────────────
    def _sort_key(r):
        hits = r[3]
        if hits is None: return (99, r[0])
        return (-len(hits), r[0])
    results.sort(key=_sort_key)

    n_alert = sum(1 for r in results if r[3] and len(r[3]) >= 2)
    n_warn  = sum(1 for r in results if r[3] and len(r[3]) == 1)
    n_safe  = sum(1 for r in results if r[3] == [])

    st.markdown(
        f"<div style='margin-bottom:10px;font-size:12px;color:#888'>"
        f"🚨 強烈建議出場 <b>{n_alert}</b> ｜ ⚠️ 警惕 <b>{n_warn}</b> ｜ ✅ 無訊號 <b>{n_safe}</b>"
        f"</div>",
        unsafe_allow_html=True,
    )

    for ticker, price, pct, hits in results:
        if hits is None:
            st.markdown(
                f"<div style='opacity:0.5;font-size:12px;padding:6px 14px;"
                f"border:0.5px dashed rgba(128,128,128,0.4);border-radius:6px;margin-bottom:6px'>"
                f"<b>{ticker}</b> — ⚠️ 數據不足或下載失敗</div>",
                unsafe_allow_html=True,
            )
            continue
        _render_sell_card(ticker, price, pct, hits)


# ══════════════════════════════════════════════════════════════════
# Tab 主入口
# ══════════════════════════════════════════════════════════════════
def render(stocks: list):
    st.subheader("📡 多策略共振掃描")

    st.markdown(
        "> 把所有策略一次跑完，找出**同時觸發多個策略**的強訊號股票。"
        "買入模式按當前恒指制度推薦策略（強調紀律），賣出模式掃描你的持倉。"
    )
    st.divider()

    # ── 模式選擇 ──────────────────────────────────────────────────
    mode = st.radio(
        "掃描模式",
        ["🟢 買入共振（全市場）", "🔴 持倉賣出警報"],
        horizontal=True, key="ms_mode",
    )
    st.divider()

    # ── 共用參數 ──────────────────────────────────────────────────
    col1, col2 = st.columns([1, 2])
    with col1:
        lookback = st.selectbox(
            "訊號回溯天數",
            [3, 5, 10], index=1, key="ms_lookback",
            help="過去 N 天內有任一日觸發策略即算命中",
        )

    # ══════════════════════════════════════════════════════════════
    # 模式一：買入共振
    # ══════════════════════════════════════════════════════════════
    if mode.startswith("🟢"):
        # 取當前制度
        with st.spinner("判定當前市場制度..."):
            regime_info = _detect_current_regime()

        if not regime_info:
            st.error("❌ 無法取得恒指數據，無法判定制度。請檢查網絡。")
            return

        with col2:
            use_all = st.checkbox(
                "切換到「全策略」模式（忽略制度過濾）",
                value=False, key="ms_use_all",
                help="預設只掃描當前制度推薦的策略以強調紀律。勾選後掃描全部 15 個策略。",
            )

        cache_banner()
        _render_buy_mode(stocks, regime_info, int(lookback), use_all)

    # ══════════════════════════════════════════════════════════════
    # 模式二：持倉賣出警報
    # ══════════════════════════════════════════════════════════════
    else:
        with col2:
            st.caption(
                "💡 掃描你手動輸入的持倉清單，檢查過去 N 天內是否觸發任何賣出訊號。"
                "2+ 訊號 = 強烈建議出場，1 訊號 = 警惕。"
            )
        _render_sell_mode(int(lookback))
