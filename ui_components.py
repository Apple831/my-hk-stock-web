# ══════════════════════════════════════════════════════════════════
# ui_components.py — UI 通用組件
# ══════════════════════════════════════════════════════════════════

import streamlit as st
import pandas as pd
from datetime import datetime

from config import (
    STRATEGY_PRESETS, PRESET_NAMES, PRESET_CUSTOM,
    BUY_LABELS, SELL_LABELS,
)
from charts import (
    show_equity_curve, show_monthly_heatmap,
    show_backtest_chart,
)


def get_preset_sigs(preset_name: str, buy_custom: tuple, sell_custom: tuple):
    if preset_name == PRESET_CUSTOM:
        return buy_custom, sell_custom
    p = STRATEGY_PRESETS[preset_name]
    return p["buy"], p["sell"]


def preset_selector(key_prefix: str):
    preset = st.selectbox(
        "⚡ 快速選擇策略組合",
        PRESET_NAMES,
        key=f"{key_prefix}_preset",
        help="選擇預設組合一鍵套用，或選「自定義」自行勾選策略",
    )
    if preset != PRESET_CUSTOM:
        p = STRATEGY_PRESETS[preset]
        active_buy  = [BUY_LABELS[i]  for i, v in enumerate(p["buy"])  if v]
        active_sell = [SELL_LABELS[i] for i, v in enumerate(p["sell"]) if v]
        st.markdown(
            f"<div style='background:rgba(255,255,255,0.05);"
            f"border-left:3px solid #f9a825;"
            f"padding:8px 14px;border-radius:5px;margin:4px 0 8px 0'>"
            f"<div style='font-size:13px;opacity:0.85'>{p['desc'].replace(chr(10), '<br>')}</div>"
            f"<div style='margin-top:6px;font-size:12px'>"
            f"🟢 買入：{'、'.join(active_buy) or '無'}　　"
            f"🔴 賣出：{'、'.join(active_sell) or '無（只靠止損出場）'}"
            f"</div></div>",
            unsafe_allow_html=True,
        )
        return preset, False
    return preset, True


def cache_banner():
    cache = st.session_state.get("stock_cache", {})
    cache_dt = st.session_state.get("cache_datetime")
    if cache:
        ts = st.session_state.get("cache_time", "")
        stale_warn = ""
        if cache_dt:
            hours_old = (datetime.now() - cache_dt).total_seconds() / 3600
            if hours_old >= 4:
                stale_warn = f"  ⚠️ **數據已超過 {hours_old:.0f} 小時，建議重新下載！**"
        st.success(
            f"⚡ 使用緩存數據（{len(cache)} 隻，{ts} 下載）— 掃描將在數秒內完成{stale_warn}",
            icon="🚀",
        )
    else:
        st.warning(
            "⚠️ 尚未緩存數據，掃描將逐隻下載（較慢）。"
            "建議先點擊左側 **⬇️ 批量下載全部股票** 再掃描！",
            icon="🐢",
        )


def render_single_bt_result(ticker, metrics, equity_df, df_bt,
                             trades, trade_size, df_hsi_bt):
    avg_ret       = metrics["平均每筆回報%"]
    verdict_color = "#26a69a" if avg_ret > 0 else "#ef5350"
    verdict_icon  = "🟢" if avg_ret > 0 else "🔴"
    st.markdown(
        f"<div style='background:rgba(255,255,255,0.05);"
        f"border-left:4px solid {verdict_color};"
        f"padding:10px 16px;border-radius:6px;"
        f"font-size:18px;font-weight:bold'>"
        f"{verdict_icon} {ticker}　"
        f"平均每筆回報：{avg_ret:+.2f}%　｜　"
        f"共 {metrics['交易次數']} 次訊號　｜　"
        f"累計回報：{metrics['累計回報%']:+.2f}%"
        f"</div>",
        unsafe_allow_html=True,
    )
    st.write("")

    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("⭐ 平均每筆回報", f"{avg_ret:+.2f}%")
    m2.metric("交易次數",        f"{metrics['交易次數']} 次")
    m3.metric("勝率",            f"{metrics['勝率%']:.1f}%")
    m4.metric("最佳一筆",        f"{metrics['最佳一筆%']:+.2f}%")
    m5.metric("最差一筆",        f"{metrics['最差一筆%']:+.2f}%")

    a1, a2, a3, a4 = st.columns(4)
    pf_val = metrics["Profit Factor"]
    a1.metric("Profit Factor",  "∞" if pf_val == float("inf") else f"{pf_val:.2f}")
    a2.metric("最大連輸",       f"{metrics['最大連輸']} 次")
    a3.metric("最大回撤",       f"{metrics['最大回撤%']:.2f}%")
    a4.metric("平均持倉天數",   f"{metrics['平均持倉天數']:.0f} 天")

    b1, b2 = st.columns(2)
    b1.metric("平均盈利", f"{metrics['平均盈利%']:+.2f}%")
    b2.metric("平均虧損", f"{metrics['平均虧損%']:+.2f}%")

    st.divider()
    st.markdown("### 📈 累計回報走勢（每筆固定金額）")
    if not equity_df.empty:
        show_equity_curve(equity_df, trade_size, df_hsi_bt)

    st.divider()
    st.markdown("### 📅 月度回報熱力圖")
    if not equity_df.empty:
        show_monthly_heatmap(equity_df)

    st.divider()
    st.markdown(f"### 🎯 {ticker} 交易標記圖")
    show_backtest_chart(df_bt, trades)

    st.divider()
    st.markdown("### 📑 逐筆交易記錄")
    if trades:
        display_cols = ["買入日期","賣出日期","買入價","賣出價",
                        "回報%","盈虧(HKD)","持倉天數","賣出原因"]
        df_trades = pd.DataFrame(trades)[display_cols]
        def _cr(val):
            try:
                v = float(val)
                return "color:#26a69a" if v > 0 else ("color:#ef5350" if v < 0 else "")
            except Exception:
                return ""
        st.dataframe(
            df_trades.style.map(_cr, subset=["回報%","盈虧(HKD)"]),
            use_container_width=True, hide_index=True,
        )
    else:
        st.info("無交易記錄")
