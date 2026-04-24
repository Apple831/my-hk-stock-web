"""
恒指制度監測模組
========================
Sidebar 常駐顯示當前市場制度、持續天數、上次切換時間。
邏輯與 tab_index.py / tab_multi_scan.py 一致（三層制度判定）。

使用方式：
    from regime_monitor import render_regime_sidebar
    # 在 app.py 的 sidebar 區塊最上方呼叫
    render_regime_sidebar()
"""
from __future__ import annotations

import pandas as pd
import numpy as np
import yfinance as yf
import streamlit as st


# ---------------------------------------------------------------------------
# 制度樣式
# ---------------------------------------------------------------------------

REGIME_STYLES = {
    "強牛市":   {"color": "#16a34a", "emoji": "🟢", "tier": "bull"},
    "弱牛市":   {"color": "#22c55e", "emoji": "🟢", "tier": "bull"},
    "牛市警惕": {"color": "#eab308", "emoji": "🟡", "tier": "warn"},
    "震盪":     {"color": "#64748b", "emoji": "⚪", "tier": "neutral"},
    "轉折期":   {"color": "#0ea5e9", "emoji": "🔵", "tier": "neutral"},
    "熊市觀察": {"color": "#f97316", "emoji": "🟠", "tier": "warn"},
    "弱熊市":   {"color": "#dc2626", "emoji": "🔴", "tier": "bear"},
    "強熊市":   {"color": "#991b1b", "emoji": "🔴", "tier": "bear"},
}


# ---------------------------------------------------------------------------
# 資料下載 & 指標計算
# ---------------------------------------------------------------------------

@st.cache_data(ttl=3600, show_spinner=False)
def _download_hsi(period: str = "2y") -> pd.DataFrame:
    """下載恒指日線資料（快取 1 小時）"""
    try:
        df = yf.download("^HSI", period=period, progress=False, auto_adjust=False)
        if df is None or df.empty:
            return pd.DataFrame()
        # 處理新版 yfinance 的 MultiIndex 欄位
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        return df
    except Exception:
        return pd.DataFrame()


def _compute_macd_hist(close: pd.Series, fast: int = 12, slow: int = 26,
                       signal: int = 9) -> pd.Series:
    """計算 MACD Histogram"""
    ema_fast = close.ewm(span=fast, adjust=False).mean()
    ema_slow = close.ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    return macd_line - signal_line


# ---------------------------------------------------------------------------
# 制度判定
# ---------------------------------------------------------------------------

def _classify_regime(gap_pct: float, macd_pct: float, cov_20: float) -> str | None:
    """依三層制度規則給出標籤（NaN 則回傳 None）"""
    if pd.isna(gap_pct) or pd.isna(macd_pct) or pd.isna(cov_20):
        return None

    if abs(gap_pct) < 2:
        return "震盪" if cov_20 > 2 else "轉折期"

    if gap_pct >= 2:
        if macd_pct > 0.5:
            return "強牛市"
        if macd_pct > 0:
            return "弱牛市"
        return "牛市警惕"

    # gap_pct <= -2
    if macd_pct < -0.5:
        return "強熊市"
    if macd_pct < 0:
        return "弱熊市"
    return "熊市觀察"


def detect_regime_series(hsi_df: pd.DataFrame) -> pd.Series:
    """對整段 HSI 資料計算每日制度（回傳字串 Series，index=date）"""
    if hsi_df is None or hsi_df.empty:
        return pd.Series(dtype=str)

    close = hsi_df["Close"]
    ma20 = close.rolling(20).mean()
    ma60 = close.rolling(60).mean()
    macd_hist = _compute_macd_hist(close)
    std20 = close.rolling(20).std()

    gap_pct = (ma20 - ma60) / ma60 * 100
    macd_pct = macd_hist / close * 100
    cov_20 = std20 / ma20 * 100  # 變異係數

    regimes = [_classify_regime(g, m, c) for g, m, c in zip(gap_pct, macd_pct, cov_20)]
    return pd.Series(regimes, index=hsi_df.index)


def get_current_regime_info(hsi_df: pd.DataFrame) -> dict:
    """
    取得當前制度資訊：
        current       : 當前制度
        change_date   : 上次切換日期（當前制度第一天出現的日期）
        days_hold     : 已持續天數（calendar days）
        previous      : 前一個制度（若無則 None）
        last_update   : 最新資料日
    """
    series = detect_regime_series(hsi_df).dropna()
    if series.empty:
        return {
            "current": None, "change_date": None, "days_hold": 0,
            "previous": None, "last_update": None,
        }

    current = series.iloc[-1]
    last_update = series.index[-1]

    # 從後往前尋找第一個不同的制度
    previous = None
    change_idx = 0
    for i in range(len(series) - 1, -1, -1):
        if series.iloc[i] != current:
            change_idx = i + 1  # 切換日 = 不同制度的下一天
            previous = series.iloc[i]
            break

    change_date = series.index[change_idx]
    days_hold = (last_update - change_date).days

    return {
        "current": current,
        "change_date": change_date,
        "days_hold": days_hold,
        "previous": previous,
        "last_update": last_update,
    }


# ---------------------------------------------------------------------------
# Sidebar 渲染
# ---------------------------------------------------------------------------

def render_regime_sidebar() -> None:
    """在 sidebar 顯示制度監測卡片（呼叫一次即可）"""
    with st.sidebar:
        st.markdown("### 📡 恒指制度監測")

        hsi = _download_hsi("2y")
        if hsi.empty:
            st.warning("無法取得恒指資料")
            st.caption("重試：點選 Rerun 或稍後再試")
            return

        info = get_current_regime_info(hsi)
        if info["current"] is None:
            st.warning("資料不足（<60 日）")
            return

        regime = info["current"]
        style = REGIME_STYLES.get(regime, {"color": "#64748b", "emoji": "⚪"})
        days = info["days_hold"]
        previous = info["previous"]

        # 3 天內切換 → 警報框
        alert_html = ""
        if previous is not None and days <= 3:
            alert_html = (
                '<div style="background:#fef3c7;color:#92400e;'
                'padding:6px 10px;border-radius:6px;font-size:12px;'
                'font-weight:bold;margin-bottom:8px;text-align:center;">'
                '🚨 近期剛切換制度</div>'
            )

        previous_html = ""
        if previous:
            previous_html = (
                f'<div style="font-size:11px;color:#64748b;margin-top:6px;">'
                f'上次：{previous}</div>'
            )

        change_str = info["change_date"].strftime("%Y-%m-%d")
        update_str = info["last_update"].strftime("%Y-%m-%d")

        card_html = f"""
        <div style="background:linear-gradient(135deg,{style['color']}22,{style['color']}08);
                    border-left:4px solid {style['color']};
                    padding:12px 14px;border-radius:8px;margin-bottom:10px;">
            {alert_html}
            <div style="font-size:20px;font-weight:bold;color:{style['color']};
                        line-height:1.2;">
                {style['emoji']} {regime}
            </div>
            <div style="font-size:13px;color:#334155;margin-top:6px;">
                已持續 <b>{days}</b> 天
            </div>
            <div style="font-size:11px;color:#64748b;margin-top:2px;">
                切換日期：{change_str}
            </div>
            {previous_html}
            <div style="font-size:10px;color:#94a3b8;margin-top:8px;
                        border-top:1px solid #e2e8f0;padding-top:4px;">
                資料截至：{update_str}
            </div>
        </div>
        """
        st.markdown(card_html, unsafe_allow_html=True)

        # 實盤紀律提示
        tier = style.get("tier")
        if tier == "bear":
            st.error(f"⛔ **{regime}：實盤禁區**\n\n所有策略歷史均虧損，建議清倉觀望")
        elif regime == "牛市警惕":
            st.warning("⚠️ 牛市動能衰退，收緊止損")
        elif regime == "熊市觀察":
            st.warning("⚠️ 下跌但動能未確認，審慎短打")
