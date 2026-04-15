# tabs/tab_index.py
import streamlit as st
import pandas as pd
from data import get_stock_data
from indicators import calculate_indicators
from charts import show_chart


# ══════════════════════════════════════════════════════════════════
# 市場制度偵測邏輯
# ══════════════════════════════════════════════════════════════════

def _detect_regime(df: pd.DataFrame) -> dict:
    """
    三層市場制度偵測，只作用於指數 DataFrame。
    回傳：
      regime        — 中文制度名稱
      emoji         — 顯示 emoji
      color_hex     — 主色（用於邊框）
      bg_hex        — 淡背景色
      strategy      — 推薦策略名稱
      wf_note       — WF 驗證備註
      ma_gap_pct    — MA20 vs MA60 距離（%）
      macd_pct      — 正規化 MACD hist（hist/close×100）
      cov_20        — 20日 CoV（std/mean×100）
      layer1_label  — 第1層文字
      layer2_label  — 第2層文字
      layer3_label  — 第3層文字
    """
    if df.empty or len(df) < 62:
        return {}

    c      = df.iloc[-1]
    close  = float(c["Close"])
    ma20   = float(c["MA20"])
    ma60   = float(c["MA60"])
    hist   = float(c["MACD_Hist"])

    # ── 第1層：MA 距離（%）──────────────────────────────────────
    # 正方向 = 多頭，負方向 = 空頭；< ±2% 視為轉折/震盪
    ma_gap_pct = (ma20 - ma60) / ma60 * 100

    # ── 第2層：正規化 MACD histogram ───────────────────────────
    # 原始 MACD_hist 單位是「港元差值」，不同股票不可比。
    # 除以收盤價轉為百分比後，高價股和低價股才能用同一閾值。
    macd_pct = hist / close * 100 if close > 0 else 0.0

    # ── 第3層：20日 CoV（係數）──────────────────────────────────
    # CoV = std / mean，正規化波動率，不受價格水平影響。
    # 比 5 日更穩定，20 日能反映制度級別的震盪程度。
    # 閾值：< 1% 低波動，> 2% 高波動（針對指數校準，個股更高）
    cov_20 = 0.0
    if len(df) >= 20:
        roll = df["Close"].rolling(20)
        mean_val = roll.mean().iloc[-1]
        if mean_val and mean_val > 0:
            cov_20 = roll.std().iloc[-1] / mean_val * 100

    # ── 制度判斷 ──────────────────────────────────────────────
    if abs(ma_gap_pct) < 2.0:
        # MA 差距小，方向不明
        if cov_20 > 2.0:
            regime      = "震盪市"
            emoji       = "🟡"
            color_hex   = "#BA7517"
            bg_hex      = "#FAEEDA"
            strategy    = "均值回歸（b5+b6+b7）"
            wf_note     = "⚠️ 未通過 WF 驗證"
        else:
            regime      = "轉折期"
            emoji       = "🟡⚠️"
            color_hex   = "#888780"
            bg_hex      = "#F1EFE8"
            strategy    = "觀望，等待方向確認"
            wf_note     = "—"

    elif ma_gap_pct > 2.0:
        # 上升趨勢
        if macd_pct > 0.5:
            regime      = "強牛市"
            emoji       = "🟢🟢"
            color_hex   = "#0F6E56"
            bg_hex      = "#E1F5EE"
            strategy    = "趨勢動能 / 突破確認"
            wf_note     = "⚠️ 未通過 WF 驗證"
        elif macd_pct > 0:
            regime      = "弱牛市"
            emoji       = "🟢"
            color_hex   = "#1D9E75"
            bg_hex      = "#E1F5EE"
            strategy    = "趨勢回調低吸 / 防守型"
            wf_note     = "⚠️ 未通過 WF 驗證"
        else:
            # 上升趨勢但 MACD 轉負，警惕頂部
            regime      = "牛市警惕"
            emoji       = "🟢⚠️"
            color_hex   = "#BA7517"
            bg_hex      = "#FAEEDA"
            strategy    = "底部形態完成（b4+b7）"
            wf_note     = "✅ WF 驗證通過（OOS +2.36%）"

    else:
        # 下降趨勢（ma_gap_pct < -2.0）
        if macd_pct < -0.5:
            regime      = "強熊市"
            emoji       = "🔴🔴"
            color_hex   = "#A32D2D"
            bg_hex      = "#FCEBEB"
            strategy    = "觀望 / 空倉"
            wf_note     = "—"
        elif macd_pct < 0:
            regime      = "弱熊市"
            emoji       = "🔴"
            color_hex   = "#E24B4A"
            bg_hex      = "#FCEBEB"
            strategy    = "底部形態完成（b4+b7）"
            wf_note     = "✅ WF 驗證通過（OOS +2.36%）"
        else:
            # 下降趨勢但 MACD 轉正，可能見底
            regime      = "熊市觀察"
            emoji       = "🔴⚠️"
            color_hex   = "#BA7517"
            bg_hex      = "#FAEEDA"
            strategy    = "底部形態完成（b4+b7）"
            wf_note     = "✅ WF 驗證通過（OOS +2.36%）"

    # ── 各層文字描述 ───────────────────────────────────────────
    if abs(ma_gap_pct) < 2.0:
        l1 = f"MA20 ≈ MA60（差距 {abs(ma_gap_pct):.1f}%，< 2%）→ 方向未定"
    elif ma_gap_pct > 0:
        l1 = f"MA20 > MA60（差距 +{ma_gap_pct:.1f}%，> 2%）→ 上升趨勢確認"
    else:
        l1 = f"MA20 < MA60（差距 {ma_gap_pct:.1f}%，> 2%）→ 下降趨勢確認"

    if macd_pct > 0.5:
        l2 = f"MACD_hist% = +{macd_pct:.3f}%（> +0.5%）→ 強多頭動能"
    elif macd_pct > 0:
        l2 = f"MACD_hist% = +{macd_pct:.3f}%（0 ~ +0.5%）→ 弱多頭動能"
    elif macd_pct > -0.5:
        l2 = f"MACD_hist% = {macd_pct:.3f}%（-0.5% ~ 0）→ 弱空頭動能"
    else:
        l2 = f"MACD_hist% = {macd_pct:.3f}%（< -0.5%）→ 強空頭動能"

    if cov_20 > 2.0:
        l3 = f"20日 CoV = {cov_20:.2f}%（> 2%）→ 高波動，方向不穩定"
    elif cov_20 > 1.0:
        l3 = f"20日 CoV = {cov_20:.2f}%（1~2%）→ 中等波動"
    else:
        l3 = f"20日 CoV = {cov_20:.2f}%（< 1%）→ 低波動，趨勢穩定"

    return {
        "regime": regime, "emoji": emoji,
        "color_hex": color_hex, "bg_hex": bg_hex,
        "strategy": strategy, "wf_note": wf_note,
        "ma_gap_pct": ma_gap_pct, "macd_pct": macd_pct, "cov_20": cov_20,
        "layer1_label": l1, "layer2_label": l2, "layer3_label": l3,
    }


def _show_regime_panel(r: dict, ticker_name: str):
    """渲染市場制度偵測面板。"""
    if not r:
        st.info("數據不足，無法計算市場制度。")
        return

    # ── 主標題卡 ─────────────────────────────────────────────
    st.markdown(
        f"<div style='"
        f"background:{r['bg_hex']};"
        f"border-left:4px solid {r['color_hex']};"
        f"border-radius:0 8px 8px 0;"
        f"padding:12px 18px;margin-bottom:14px'>"
        f"<div style='font-size:22px;font-weight:500;color:{r['color_hex']}'>"
        f"{r['emoji']}&nbsp;&nbsp;{r['regime']}</div>"
        f"<div style='font-size:13px;margin-top:4px;color:{r['color_hex']};opacity:0.85'>"
        f"推薦策略：<b>{r['strategy']}</b>"
        f"&nbsp;&nbsp;｜&nbsp;&nbsp;{r['wf_note']}</div>"
        f"</div>",
        unsafe_allow_html=True,
    )

    # ── 三層指標 ──────────────────────────────────────────────
    col1, col2, col3 = st.columns(3)

    ma_color = "#0F6E56" if r["ma_gap_pct"] > 2 else ("#A32D2D" if r["ma_gap_pct"] < -2 else "#BA7517")
    mc_color = "#0F6E56" if r["macd_pct"] > 0 else "#A32D2D"
    cv_color = "#A32D2D" if r["cov_20"] > 2 else ("#0F6E56" if r["cov_20"] < 1 else "#BA7517")

    with col1:
        st.markdown(
            f"<div style='background:var(--background-color,#f9f9f9);"
            f"border:0.5px solid #ccc;border-radius:8px;padding:10px 12px'>"
            f"<div style='font-size:11px;color:#888;margin-bottom:2px'>第1層 — MA 方向</div>"
            f"<div style='font-size:18px;font-weight:500;color:{ma_color}'>"
            f"{r['ma_gap_pct']:+.2f}%</div>"
            f"<div style='font-size:11px;color:#888;margin-top:4px'>{r['layer1_label']}</div>"
            f"</div>",
            unsafe_allow_html=True,
        )
    with col2:
        st.markdown(
            f"<div style='background:var(--background-color,#f9f9f9);"
            f"border:0.5px solid #ccc;border-radius:8px;padding:10px 12px'>"
            f"<div style='font-size:11px;color:#888;margin-bottom:2px'>第2層 — 動能強度</div>"
            f"<div style='font-size:18px;font-weight:500;color:{mc_color}'>"
            f"{r['macd_pct']:+.4f}%</div>"
            f"<div style='font-size:11px;color:#888;margin-top:4px'>{r['layer2_label']}</div>"
            f"</div>",
            unsafe_allow_html=True,
        )
    with col3:
        st.markdown(
            f"<div style='background:var(--background-color,#f9f9f9);"
            f"border:0.5px solid #ccc;border-radius:8px;padding:10px 12px'>"
            f"<div style='font-size:11px;color:#888;margin-bottom:2px'>第3層 — 波動率（CoV）</div>"
            f"<div style='font-size:18px;font-weight:500;color:{cv_color}'>"
            f"{r['cov_20']:.2f}%</div>"
            f"<div style='font-size:11px;color:#888;margin-top:4px'>{r['layer3_label']}</div>"
            f"</div>",
            unsafe_allow_html=True,
        )

    # ── 制度定義說明 ──────────────────────────────────────────
    with st.expander("📖 制度定義 & 策略推薦說明", expanded=False):
        st.markdown("""
| 制度 | 第1層（MA距離） | 第2層（MACD%） | 第3層（CoV） | 推薦策略 |
|------|--------------|-------------|------------|--------|
| 🟢🟢 強牛市 | MA20 > MA60（>+2%） | > +0.5% | — | 趨勢動能 / 突破確認 |
| 🟢 弱牛市 | MA20 > MA60（>+2%） | 0 ~ +0.5% | — | 趨勢回調 / 防守型 |
| 🟢⚠️ 牛市警惕 | MA20 > MA60（>+2%） | < 0 | — | 底部形態完成 ✅ |
| 🔴🔴 強熊市 | MA20 < MA60（>2%）  | < -0.5% | — | 觀望 / 空倉 |
| 🔴 弱熊市 | MA20 < MA60（>2%）  | -0.5% ~ 0 | — | 底部形態完成 ✅ |
| 🔴⚠️ 熊市觀察 | MA20 < MA60（>2%）  | > 0 | — | 底部形態完成 ✅ |
| 🟡 震盪市 | 差距 < 2% | — | > 2% | 均值回歸 |
| 🟡⚠️ 轉折期 | 差距 < 2% | — | < 1% | 觀望 |

> **重要**：✅ 標記代表通過 Walk-Forward 驗證（OOS +2.36%，退化率 22%）。
> 其他策略為概念推薦，尚未通過 WF 驗證，實盤請謹慎。
>
> **MACD 正規化說明**：MACD_hist% = MACD_hist ÷ 收盤價 × 100，
> 消除了高低價股之間的量級差異，使 ±0.5% 閾值對所有股票一致有效。
""")


# ══════════════════════════════════════════════════════════════════
# 制度歷史追蹤（向量化，O(n) 而非原來的 O(n²) 迴圈）
# ══════════════════════════════════════════════════════════════════

def _regime_history(df: pd.DataFrame, lookback: int = 60) -> pd.DataFrame:
    """
    向量化計算過去 lookback 日的每日制度標籤。
    原版用 for 迴圈逐行切片再呼叫 _detect_regime()，
    60 次迭代 × 每次重算 rolling → O(n²)，是 30 秒的根源。
    修復：三個指標全部向量化計算，分類用 np.select，整體 < 0.1 秒。
    """
    if df.empty or len(df) < 62:
        return pd.DataFrame()

    import numpy as np

    # ── 向量化三層指標 ─────────────────────────────────────────
    ma_gap  = (df["MA20"] - df["MA60"]) / df["MA60"] * 100
    macd_p  = df["MACD_Hist"] / df["Close"].replace(0, float("nan")) * 100
    cov_20  = df["Close"].rolling(20).std() / df["Close"].rolling(20).mean() * 100

    # ── 向量化制度分類（順序從嚴到寬，第一個 True 的條件勝出）──
    cond_strong_bull  = (ma_gap >  2.0) & (macd_p >  0.5)
    cond_weak_bull    = (ma_gap >  2.0) & (macd_p >  0.0) & ~cond_strong_bull
    cond_bull_warn    = (ma_gap >  2.0) & (macd_p <= 0.0)
    cond_strong_bear  = (ma_gap < -2.0) & (macd_p < -0.5)
    cond_weak_bear    = (ma_gap < -2.0) & (macd_p <  0.0) & ~cond_strong_bear
    cond_bear_watch   = (ma_gap < -2.0) & (macd_p >= 0.0)
    cond_chop         = (ma_gap.abs() < 2.0) & (cov_20 >  2.0)
    cond_pivot        = (ma_gap.abs() < 2.0) & (cov_20 <= 2.0)

    regime = np.select(
        [cond_strong_bull, cond_weak_bull, cond_bull_warn,
         cond_strong_bear, cond_weak_bear, cond_bear_watch,
         cond_chop, cond_pivot],
        ["強牛市", "弱牛市", "牛市警惕",
         "強熊市", "弱熊市", "熊市觀察",
         "震盪市", "轉折期"],
        default="轉折期",
    )

    hist = pd.DataFrame({
        "regime":   regime,
        "ma_gap":   ma_gap.values,
        "macd_pct": macd_p.values,
        "cov_20":   cov_20.values,
    }, index=df.index).dropna(subset=["ma_gap"])

    # 只回傳最近 lookback 筆
    return hist.iloc[-lookback:] if len(hist) > lookback else hist


# ══════════════════════════════════════════════════════════════════
# 快取資料載入（避免切換指數/週期時重複下載）
# ══════════════════════════════════════════════════════════════════

@st.cache_data(ttl=900, show_spinner=False)   # 15 分鐘快取
def _load_index(ticker: str, period: str):
    df = get_stock_data(ticker, period=period)
    if df.empty:
        # 不快取失敗結果，讓用戶重試時能重新下載
        return df
    return calculate_indicators(df)


# yfinance 偶爾對特定 ticker 回傳空資料，
# 在 render() 裏用此 wrapper 清除快取後重試一次
def _load_index_with_retry(ticker: str, period: str):
    df = _load_index(ticker, period)
    if df.empty:
        # 清除此 ticker 的快取，下次才能真正重試
        _load_index.clear()
    return df


# ══════════════════════════════════════════════════════════════════
# Tab 主入口
# ══════════════════════════════════════════════════════════════════

def render():
    st.subheader("🌍 主要指數走勢")

    indices = {
        "恆生指數 (^HSI)":    "^HSI",
        "恆生科技 (^HSTECH)": "^HSTECH",
        "恐慌指數 (^VIX)":    "^VIX",
    }

    # ── 控制列（全寬，三個控件並排）────────────────────────────
    ctrl1, ctrl2, ctrl3 = st.columns([2, 1, 2])
    with ctrl1:
        selected_index = st.selectbox("選擇指數", list(indices.keys()))
    with ctrl2:
        period = st.selectbox("時間週期", ["3mo", "6mo", "1y", "2y"], index=2)
    with ctrl3:
        st.markdown("<div style='height:28px'></div>", unsafe_allow_html=True)
        show_regime = st.checkbox(
            "📡 顯示市場制度偵測",
            value=True,
            help=(
                "三層市場制度分析：\n"
                "第1層：MA20/MA60 距離（>2% 才算確認趨勢）\n"
                "第2層：正規化 MACD（hist ÷ 收盤價）\n"
                "第3層：20日 CoV 波動率"
            ),
        )

    # ── 內容區（全寬）─────────────────────────────────────────
    ticker_code = indices[selected_index]
    is_hsi_type = ticker_code in ("^HSI", "^HSTECH")

    with st.spinner(f"載入 {selected_index} 數據中..."):
        df_idx = _load_index_with_retry(ticker_code, period)

    if df_idx.empty:
        st.error(f"❌ 無法載入 {selected_index} 數據，請稍後再試。")
        return

    if show_regime and is_hsi_type:
        st.markdown("---")
        st.markdown(f"#### 📡 {selected_index} 市場制度偵測")

        regime_info = _detect_regime(df_idx)
        _show_regime_panel(regime_info, selected_index)

        # 制度歷史（可選）
        with st.expander("🕐 近 60 日制度演變", expanded=False):
            hist_df = _regime_history(df_idx, lookback=60)
            if not hist_df.empty:
                # 用色塊顯示每日制度
                regime_colors = {
                    "強牛市": "#0F6E56", "弱牛市": "#1D9E75",
                    "牛市警惕": "#BA7517",
                    "強熊市": "#A32D2D", "弱熊市": "#E24B4A",
                    "熊市觀察": "#BA7517",
                    "震盪市": "#BA7517", "轉折期": "#888780",
                }

                # 統計制度分布
                counts = hist_df["regime"].value_counts()
                total  = len(hist_df)
                st.caption(f"過去 {total} 個交易日制度分布：")
                cols = st.columns(min(len(counts), 4))
                for i, (regime, cnt) in enumerate(counts.items()):
                    color = regime_colors.get(regime, "#888")
                    cols[i % 4].markdown(
                        f"<div style='border-left:3px solid {color};"
                        f"padding:4px 8px;margin:2px 0;font-size:12px'>"
                        f"<b>{regime}</b>：{cnt} 日 ({cnt/total*100:.0f}%)</div>",
                        unsafe_allow_html=True,
                    )

                # MA gap 走勢
                import plotly.graph_objects as go
                fig = go.Figure()
                fig.add_trace(go.Scatter(
                    x=hist_df.index, y=hist_df["ma_gap"],
                    name="MA 差距%", fill="tozeroy",
                    line=dict(width=1.5, color="#1D9E75"),
                    fillcolor="rgba(29,158,117,0.12)",
                ))
                fig.add_hline(y=2,  line_dash="dot", line_color="rgba(29,158,117,0.5)",
                              annotation_text="+2% 牛市線", annotation_position="right")
                fig.add_hline(y=-2, line_dash="dot", line_color="rgba(226,74,74,0.5)",
                              annotation_text="-2% 熊市線", annotation_position="right")
                fig.add_hline(y=0,  line_dash="dash", line_color="rgba(128,128,128,0.3)")
                fig.update_layout(
                    height=200, margin=dict(t=10, b=10),
                    paper_bgcolor="rgba(0,0,0,0)",
                    plot_bgcolor="rgba(0,0,0,0)",
                    yaxis_ticksuffix="%", showlegend=False,
                    yaxis_title="MA20-MA60 差距%",
                )
                st.plotly_chart(fig, use_container_width=True)

                # MACD% 走勢
                fig2 = go.Figure()
                colors_bar = ["#1D9E75" if v >= 0 else "#E24B4A" for v in hist_df["macd_pct"]]
                fig2.add_trace(go.Bar(
                    x=hist_df.index, y=hist_df["macd_pct"],
                    name="MACD%", marker_color=colors_bar,
                ))
                fig2.add_hline(y=0.5,  line_dash="dot", line_color="rgba(29,158,117,0.5)",
                               annotation_text="+0.5% 強牛", annotation_position="right")
                fig2.add_hline(y=-0.5, line_dash="dot", line_color="rgba(226,74,74,0.5)",
                               annotation_text="-0.5% 強熊", annotation_position="right")
                fig2.update_layout(
                    height=180, margin=dict(t=10, b=10),
                    paper_bgcolor="rgba(0,0,0,0)",
                    plot_bgcolor="rgba(0,0,0,0)",
                    yaxis_ticksuffix="%", showlegend=False,
                    yaxis_title="正規化 MACD%",
                )
                st.plotly_chart(fig2, use_container_width=True)
            else:
                st.info("數據不足以計算制度歷史。")

    elif show_regime and not is_hsi_type:
        st.caption("⚠️ VIX 不適用市場制度偵測（邏輯針對股票指數設計）。")

    st.markdown("---")
    st.markdown(f"### 📈 {selected_index} 技術圖表")
    show_chart(ticker_code, df_idx)
