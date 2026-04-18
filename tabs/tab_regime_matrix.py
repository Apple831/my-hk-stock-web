# tabs/tab_regime_matrix.py
# ══════════════════════════════════════════════════════════════════
# 制度 × 策略矩陣
# 兩種模式：
#   A. 全預設策略模式 — 跑所有預設，輸出完整矩陣
#   B. 自定義策略模式 — 只跑一個自定義組合，輸出該組合在各制度的表現
# ══════════════════════════════════════════════════════════════════

import streamlit as st
import pandas as pd
import numpy as np

from data import get_stock_data
from indicators import calculate_indicators
from walk_forward import run_portfolio_walk_forward
from config import STRATEGY_PRESETS, PRESET_NAMES, PRESET_CUSTOM
from ui_components import preset_selector, get_preset_sigs

REGIMES_ORDER = [
    "強牛市", "弱牛市", "牛市警惕",
    "熊市觀察", "弱熊市", "強熊市",
    "震盪市", "轉折期",
]
REGIME_EMOJI = {
    "強牛市": "🟢🟢", "弱牛市": "🟢",   "牛市警惕": "🟢⚠️",
    "熊市觀察": "🔴⚠️", "弱熊市": "🔴", "強熊市":  "🔴🔴",
    "震盪市": "🟡",    "轉折期": "🟡⚠️",
}


# ── 向量化計算 HSI 每日制度標籤 ──────────────────────────────────
def _calc_daily_regimes(hsi_df: pd.DataFrame) -> pd.Series:
    if hsi_df.empty or len(hsi_df) < 62:
        return pd.Series(dtype=str)

    ma_gap = (hsi_df["MA20"] - hsi_df["MA60"]) / hsi_df["MA60"] * 100
    macd_p = hsi_df["MACD_Hist"] / hsi_df["Close"].replace(0, float("nan")) * 100
    cov_20 = (hsi_df["Close"].rolling(20).std() /
              hsi_df["Close"].rolling(20).mean() * 100)

    regime = np.select(
        [
            (ma_gap >  2.0) & (macd_p >  0.5),
            (ma_gap >  2.0) & (macd_p >  0.0) & ~((ma_gap >  2.0) & (macd_p >  0.5)),
            (ma_gap >  2.0) & (macd_p <= 0.0),
            (ma_gap < -2.0) & (macd_p < -0.5),
            (ma_gap < -2.0) & (macd_p <  0.0) & ~((ma_gap < -2.0) & (macd_p < -0.5)),
            (ma_gap < -2.0) & (macd_p >= 0.0),
            (ma_gap.abs() < 2.0) & (cov_20 >  2.0),
            (ma_gap.abs() < 2.0) & (cov_20 <= 2.0),
        ],
        ["強牛市", "弱牛市", "牛市警惕",
         "強熊市", "弱熊市", "熊市觀察",
         "震盪市", "轉折期"],
        default="轉折期",
    )
    return pd.Series(regime, index=hsi_df.index, name="regime")


# ── 為每筆交易標注入場時的制度 ─────────────────────────────────────
def _tag_trades_with_regime(trades: list, daily_regimes: pd.Series) -> list:
    if daily_regimes.empty or not trades:
        return [{**t, "regime": "轉折期"} for t in trades]
    dates  = daily_regimes.index
    tagged = []
    for t in trades:
        buy_date = t["_buy_date"]
        pos      = dates.searchsorted(buy_date, side="right") - 1
        regime   = str(daily_regimes.iloc[pos]) if pos >= 0 else "轉折期"
        tagged.append({**t, "regime": regime})
    return tagged


# ── 跑單策略 WF，按制度聚合，回傳 bucket dict ──────────────────────
def _run_one_strategy(
    stock_data: dict, buy_sigs: tuple, sell_sigs: tuple,
    daily_regimes: pd.Series,
    is_months: int, oos_months: int,
    trade_size: float, slippage: float, min_oos_trades: int,
) -> dict:
    wf_res = run_portfolio_walk_forward(
        stock_data,
        buy_sigs=buy_sigs, sell_sigs=sell_sigs,
        is_months=is_months, oos_months=oos_months,
        trade_size=trade_size, slippage=slippage,
        min_oos_trades=min_oos_trades,
    )
    all_oos = []
    for fold in wf_res:
        if fold.get("valid_oos"):
            all_oos.extend(fold["oos_trades"])
    if not all_oos:
        return {}

    tagged  = _tag_trades_with_regime(all_oos, daily_regimes)
    buckets: dict = {}
    for t in tagged:
        r = t.get("regime", "轉折期")
        buckets.setdefault(r, []).append(t["回報%"])
    return {
        r: {
            "avg":  round(sum(v) / len(v), 2),
            "n":    len(v),
            "wins": sum(1 for x in v if x > 0),
        }
        for r, v in buckets.items()
    }


# ── 從 matrix_raw 建立顯示用 DataFrame ───────────────────────────
def _build_display_dfs(matrix_raw: dict) -> tuple:
    active_regimes = [r for r in REGIMES_ORDER if any(
        r in matrix_raw.get(s, {}) for s in matrix_raw
    )]
    col_labels = {r: f"{REGIME_EMOJI.get(r, '')} {r}" for r in active_regimes}
    cols       = [col_labels[r] for r in active_regimes]

    df_val  = pd.DataFrame(float("nan"), index=list(matrix_raw.keys()), columns=cols)
    df_n    = pd.DataFrame(0,            index=list(matrix_raw.keys()), columns=cols)
    df_disp = pd.DataFrame("—",          index=list(matrix_raw.keys()), columns=cols)

    for strat_name, data in matrix_raw.items():
        for regime in active_regimes:
            col = col_labels[regime]
            if regime not in data:
                continue
            cell  = data[regime]
            avg_r = cell["avg"]
            n     = cell["n"]
            wr    = round(cell["wins"] / n * 100) if n > 0 else 0
            df_val.loc[strat_name, col]  = avg_r
            df_n.loc[strat_name, col]    = n
            sign = "+" if avg_r >= 0 else ""
            df_disp.loc[strat_name, col] = f"{sign}{avg_r:.1f}%  ({n}筆 {wr}%勝)"

    return df_val, df_n, df_disp, active_regimes, col_labels


# ── 矩陣渲染 ──────────────────────────────────────────────────────
def _render_matrix(df_val, df_n, df_disp, active_regimes, col_labels):
    def _color_val(v):
        try:
            v = float(v)
        except (TypeError, ValueError):
            return ""
        if pd.isna(v): return ""
        if v >  3:  return "background-color:#085041;color:#9FE1CB;font-weight:500"
        if v >  0:  return "background-color:#1D9E75;color:#E1F5EE"
        if v > -3:  return "background-color:#D85A30;color:#FAECE7;font-weight:500"
        return              "background-color:#791F1F;color:#F7C1C1;font-weight:500"

    try:
        style_df = df_val.map(_color_val)
    except AttributeError:
        style_df = df_val.applymap(_color_val)

    st.dataframe(
        df_disp.style.apply(lambda _: style_df, axis=None),
        use_container_width=True,
    )

    # 每個制度最佳策略摘要
    best_rows = []
    for regime in active_regimes:
        col   = col_labels[regime]
        clean = df_val[col].dropna()
        if clean.empty:
            continue
        best_s  = clean.idxmax()
        worst_s = clean.idxmin()
        best_n  = int(df_n.loc[best_s, col]) if best_s in df_n.index else 0
        best_rows.append({
            "制度":         f"{REGIME_EMOJI.get(regime,'')} {regime}",
            "最佳策略":     best_s,
            "OOS 均回報%":  f"{'+'if clean.max()>=0 else ''}{clean.max():.1f}%",
            "交易筆數":     best_n,
            "最差策略":     worst_s,
            "最差 OOS%":    f"{clean.min():.1f}%",
        })

    if best_rows:
        st.divider()
        st.markdown("### 🏆 每個制度的最佳策略")

        def _cr(val):
            s = str(val)
            if s.startswith("+"): return "color:#1D9E75;font-weight:500"
            if s.startswith("-"): return "color:#E24B4A;font-weight:500"
            return ""

        st.dataframe(
            pd.DataFrame(best_rows).style.map(_cr, subset=["OOS 均回報%", "最差 OOS%"]),
            use_container_width=True, hide_index=True,
        )


# ── 單策略在各制度的直條圖 ────────────────────────────────────────
def _render_single_strategy(bucket: dict, strat_label: str):
    import plotly.graph_objects as go

    rows = []
    for r in REGIMES_ORDER:
        if r not in bucket:
            continue
        c = bucket[r]
        wr = round(c["wins"] / c["n"] * 100) if c["n"] > 0 else 0
        rows.append({
            "制度": f"{REGIME_EMOJI.get(r,'')} {r}",
            "OOS 均回報%": round(c["avg"], 2),
            "交易筆數": c["n"],
            "勝率%": wr,
            "_low": c["n"] < 15,
        })

    if not rows:
        st.warning("⚠️ 沒有有效交易，請檢查策略設定或拉長週期。")
        return

    df = pd.DataFrame(rows)

    colors = [
        ("#1D9E75" if v > 0 else "#E24B4A") if not low
        else ("#9FE1CB" if v > 0 else "#F09595")
        for v, low in zip(df["OOS 均回報%"], df["_low"])
    ]

    fig = go.Figure(go.Bar(
        x=df["制度"], y=df["OOS 均回報%"],
        marker_color=colors,
        text=[
            f"{'+' if v >= 0 else ''}{v:.1f}%<br>({n}筆 {w}%勝)"
            for v, n, w in zip(df["OOS 均回報%"], df["交易筆數"], df["勝率%"])
        ],
        textposition="outside",
    ))
    fig.add_hline(y=0, line_dash="dash", line_color="rgba(136,135,128,0.4)")
    fig.update_layout(
        height=380, margin=dict(t=30, b=10),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        yaxis_ticksuffix="%", xaxis_tickangle=-20,
        yaxis_title="OOS 均每筆回報%",
        annotations=[dict(
            text="淡色 = 樣本 < 15 筆（低信心）",
            xref="paper", yref="paper", x=1, y=1.04,
            showarrow=False,
            font=dict(size=11, color="rgba(136,135,128,0.8)"),
            xanchor="right",
        )],
    )
    st.plotly_chart(fig, use_container_width=True)

    st.markdown("### 📋 制度明細")
    disp_df = df.drop(columns=["_low"]).rename(columns={
        "OOS 均回報%": "OOS 均回報", "交易筆數": "筆數", "勝率%": "勝率"
    })
    def _cr(val):
        try:
            v = float(val)
            if v > 0: return "color:#1D9E75;font-weight:500"
            if v < 0: return "color:#E24B4A;font-weight:500"
        except Exception: pass
        return ""
    st.dataframe(
        disp_df.style.map(_cr, subset=["OOS 均回報"]),
        use_container_width=True, hide_index=True,
    )


# ── 共用：下載 HSI + 股票數據 ─────────────────────────────────────
def _load_data(stocks: list, period: str) -> tuple:
    with st.spinner("下載恒指數據並計算每日制度..."):
        df_hsi = get_stock_data("^HSI", period=period)
    if df_hsi.empty:
        st.error("❌ 無法取得恒指數據")
        return None, None, None

    df_hsi        = calculate_indicators(df_hsi)
    daily_regimes = _calc_daily_regimes(df_hsi)

    regime_dist = daily_regimes.value_counts()
    st.success(
        "✅ 恒指 " + "  ".join(
            f"{REGIME_EMOJI.get(r,'')} {r} {regime_dist.get(r,0)}日"
            for r in REGIMES_ORDER if regime_dist.get(r, 0) > 0
        )
    )

    st.markdown("#### 📥 準備股票數據")
    stock_data: dict = {}
    dl_pbar = st.progress(0, text="下載中...")
    for i, ticker in enumerate(stocks):
        dl_pbar.progress((i + 1) / max(len(stocks), 1), text=f"下載 {ticker}...")
        df_t = get_stock_data(ticker, period=period)
        if not df_t.empty and len(df_t) >= 62:
            stock_data[ticker] = calculate_indicators(df_t)
    dl_pbar.empty()

    if not stock_data:
        st.error("❌ 無有效股票數據")
        return None, None, None

    st.success(f"✅ 準備好 **{len(stock_data)}** 隻股票")
    return df_hsi, daily_regimes, stock_data


# ══════════════════════════════════════════════════════════════════
# Tab 主入口
# ══════════════════════════════════════════════════════════════════

def render(stocks: list):
    st.subheader("🗺️ 制度 × 策略矩陣")
    st.markdown(
        "> 按每筆 OOS 交易**入場時的恒指制度**分類聚合，"
        "找出哪個策略在哪個制度表現最穩。"
    )
    st.divider()

    # ── 模式選擇 ──────────────────────────────────────────────────
    rm_mode = st.radio(
        "測試模式",
        ["📊 全預設策略矩陣", "✏️ 自定義策略"],
        horizontal=True, key="rm_mode",
    )
    st.divider()

    # ── 共用參數 ──────────────────────────────────────────────────
    with st.expander("⚙️ 參數設定", expanded=True):
        c1, c2 = st.columns(2)
        with c1:
            rm_period = st.selectbox("總數據週期", ["3y", "5y", "10y"], index=1, key="rm_period")
            rm_is     = st.slider("IS 窗口（月）",  6, 24, 12, 3, key="rm_is")
            rm_oos    = st.slider("OOS 窗口（月）", 3, 12,  6, 1, key="rm_oos")
        with c2:
            rm_capital = st.number_input("每筆金額 (HKD)", value=100_000, step=10_000,
                                         min_value=10_000, key="rm_capital")
            rm_slip    = st.slider("滑點 (%)", 0.0, 1.0, 0.20, 0.05, key="rm_slip") / 100
            rm_min     = st.number_input("每 Fold 最低有效 OOS 交易數",
                                         value=5, min_value=1, key="rm_min")
        total_m   = {"3y": 36, "5y": 60, "10y": 120}[rm_period]
        est_folds = max(0, (total_m - rm_is) // rm_oos)

    # ══════════════════════════════════════════════════════════════
    # 模式 A：全預設策略矩陣
    # ══════════════════════════════════════════════════════════════
    if rm_mode == "📊 全預設策略矩陣":
        n_strats = len(STRATEGY_PRESETS)
        st.info(
            f"預計跑 **{n_strats} 個策略** × 約 **{est_folds} 個 Fold** × {len(stocks)} 隻股票，"
            f"全程約 **{n_strats * 2}–{n_strats * 3} 分鐘**。"
        )

        run_clicked = st.button(
            f"🚀 開始跑全部 {n_strats} 個策略",
            type="primary", key="run_rm_all",
        )

        if run_clicked:
            df_hsi, daily_regimes, stock_data = _load_data(stocks, rm_period)
            if stock_data is None:
                return

            st.markdown("#### 🔬 逐策略執行 Walk-Forward")
            matrix_raw: dict = {}
            outer_pbar   = st.progress(0, text="等待中...")
            strat_status = st.empty()

            for si, (strat_name, strat_cfg) in enumerate(STRATEGY_PRESETS.items()):
                outer_pbar.progress(si / n_strats, text=f"策略 {si+1}/{n_strats}：{strat_name}")
                strat_status.info(f"正在跑：**{strat_name}**")
                bucket = _run_one_strategy(
                    stock_data, strat_cfg["buy"], strat_cfg["sell"],
                    daily_regimes, rm_is, rm_oos,
                    float(rm_capital), rm_slip, int(rm_min),
                )
                matrix_raw[strat_name] = bucket

            outer_pbar.progress(1.0, text="✅ 全部完成！")
            strat_status.empty()
            outer_pbar.empty()

            st.session_state["rm_all_done"]       = True
            st.session_state["rm_all_matrix_raw"] = matrix_raw

        if not st.session_state.get("rm_all_done"):
            return

        matrix_raw = st.session_state.get("rm_all_matrix_raw", {})
        if not matrix_raw:
            st.warning("⚠️ 沒有策略產生有效 OOS 交易。")
            return

        df_val, df_n, df_disp, active_regimes, col_labels = _build_display_dfs(matrix_raw)
        if not active_regimes:
            st.warning("⚠️ 沒有制度有足夠數據。")
            return

        st.divider()
        st.markdown("### 📊 制度 × 策略矩陣")
        st.caption("格式：均每筆 OOS 回報%（筆數 勝率%）｜虛線 = 低信心（n<15）")
        _render_matrix(df_val, df_n, df_disp, active_regimes, col_labels)

    # ══════════════════════════════════════════════════════════════
    # 模式 B：自定義策略
    # ══════════════════════════════════════════════════════════════
    else:
        st.markdown("#### 策略選擇")
        _preset, _custom = preset_selector("rm_custom")

        if _custom:
            st.markdown("##### 🟢 買入策略")
            c1, c2 = st.columns(2)
            b1  = c1.checkbox("① 突破放量",       key="rm_b1")
            b2  = c1.checkbox("② MA5金叉",         key="rm_b2")
            b3  = c1.checkbox("③ 底背離",          key="rm_b3")
            b4  = c1.checkbox("④ 底部突破MA20",    key="rm_b4")
            b5  = c1.checkbox("⑤ 布林下軌",        key="rm_b5")
            b6  = c2.checkbox("⑥ RSI超賣",         key="rm_b6")
            b7  = c2.checkbox("⑦ MACD金叉",        key="rm_b7")
            b8  = c2.checkbox("⑧ 趨勢確認",        key="rm_b8")
            b9  = c2.checkbox("⑨ 52週新高",        key="rm_b9")
            b10 = c2.checkbox("⑩ 縮量回調",        key="rm_b10")
            buy_custom = (b1,b2,b3,b4,b5,b6,b7,b8,b9,b10)

            st.markdown("##### 🔴 賣出策略")
            d1, d2 = st.columns(2)
            s1  = d1.checkbox("⑪ 頭部跌破MA20",   key="rm_s1")
            s2  = d1.checkbox("⑫ 布林上軌",        key="rm_s2")
            s3  = d1.checkbox("⑬ 上漲縮量",        key="rm_s3")
            s4  = d1.checkbox("⑭ 放量急跌",        key="rm_s4")
            s5  = d2.checkbox("⑮ RSI超買",         key="rm_s5")
            s6  = d2.checkbox("⑯ MACD死叉",        key="rm_s6")
            s7  = d2.checkbox("⑰ 三日陰線",        key="rm_s7")
            sell_custom = (s1,s2,s3,s4,s5,s6,s7)
        else:
            buy_custom  = (False,)*10
            sell_custom = (False,)*7

        buy_sigs, sell_sigs = get_preset_sigs(_preset, buy_custom, sell_custom)

        # 策略標籤（用於顯示）
        if _custom:
            from config import BUY_LABELS, SELL_LABELS
            buy_names  = [BUY_LABELS[i]  for i, v in enumerate(buy_sigs)  if v]
            sell_names = [SELL_LABELS[i] for i, v in enumerate(sell_sigs) if v]
            strat_label = f"自定義（{'＋'.join(buy_names) or '無買入'}）"
        else:
            strat_label = _preset

        st.info(
            f"預計跑 **1 個策略** × 約 **{est_folds} 個 Fold** × {len(stocks)} 隻股票，"
            f"約 **1–3 分鐘**。"
        )

        run_custom = st.button("🚀 開始測試此策略", type="primary", key="run_rm_custom")

        if run_custom:
            if not any(buy_sigs):
                st.warning("⚠️ 請至少勾選一個買入策略"); return
            if not any(sell_sigs):
                st.warning("⚠️ 請至少勾選一個賣出策略"); return

            df_hsi, daily_regimes, stock_data = _load_data(stocks, rm_period)
            if stock_data is None:
                return

            with st.spinner(f"執行 Walk-Forward：{strat_label}..."):
                bucket = _run_one_strategy(
                    stock_data, buy_sigs, sell_sigs,
                    daily_regimes, rm_is, rm_oos,
                    float(rm_capital), rm_slip, int(rm_min),
                )

            st.session_state["rm_custom_done"]   = True
            st.session_state["rm_custom_bucket"] = bucket
            st.session_state["rm_custom_label"]  = strat_label

        if not st.session_state.get("rm_custom_done"):
            return

        bucket      = st.session_state.get("rm_custom_bucket", {})
        saved_label = st.session_state.get("rm_custom_label", strat_label)

        if not bucket:
            st.warning("⚠️ 沒有產生有效的 OOS 交易，請調整策略或參數。")
            return

        st.divider()
        st.markdown(f"### 📊 制度分析：{saved_label}")
        st.caption("淡色 bar = 樣本 < 15 筆（低信心）")
        _render_single_strategy(bucket, saved_label)
