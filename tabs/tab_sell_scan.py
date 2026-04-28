# tabs/tab_sell_scan.py
#
# V18 修復（2026-04-27）-- 來自 V17.0 策略複審報告 🔴-3：
#   • 自定義模式 sell_custom 從 7 元素擴到 8 元素（補上 s8 KDJ 高位死叉）
#   • get_preset_sigs 的 buy_custom hardcode 從 (False,)*10 改為 (False,)*11
#   • 用戶現在可以在自定義模式選 s8 訊號
import streamlit as st
import pandas as pd
from data import get_cached
from indicators import precompute_signals
from charts import show_chart, show_scan_metrics
from ui_components import cache_banner, preset_selector, get_preset_sigs
from config import S_NAMES


def render(stocks: list):
    st.subheader("🔴 賣出 / 做空策略掃描")
    cache_banner()

    _preset, _custom = preset_selector("tab3")

    if _custom:
        st.caption("🔴 賣出策略（勾選一個或多個，不選則只靠止損出場）")
        col_c, col_d = st.columns(2)
        s1 = col_c.checkbox("⑫ 頭部形態跌破 MA20（放量）",  key="t3_s1")
        s2 = col_c.checkbox("⑬ 布林帶上軌賣出",              key="t3_s2")
        s3 = col_c.checkbox("⑭ 上漲縮量（警惕頂部）",        key="t3_s3")
        s4 = col_c.checkbox("⑮ 放量急跌",                    key="t3_s4")
        s5 = col_d.checkbox("⑯ RSI 超買（> 70）",            key="t3_s5")
        s6 = col_d.checkbox("⑰ MACD 死叉（DIF下穿DEA）",     key="t3_s6")
        s7 = col_d.checkbox("⑱ 三日陰線 + 跌破MA20",         key="t3_s7")
        # 🔴-3 V18：補上 s8 KDJ 高位死叉
        s8 = col_d.checkbox("⑲ KDJ 高位死叉（K>80, D>80, K下穿D）", key="t3_s8")
        sell_custom = (s1, s2, s3, s4, s5, s6, s7, s8)
    else:
        # 🔴-3 V18：(False,)*7 → (False,)*8
        sell_custom = (False,) * 8

    # 🔴-3 V18：buy_custom hardcode (False,)*10 → (False,)*11
    _, scan_sigs = get_preset_sigs(_preset, (False,) * 11, sell_custom)

    if st.button("🔴 開始掃描賣點"):
        if not any(scan_sigs):
            st.warning("⚠️ 請至少勾選一個賣出策略")
            return

        results, hits_dfs = [], {}
        pbar   = st.progress(0)
        status = st.empty()

        for i, ticker in enumerate(stocks):
            pbar.progress((i + 1) / len(stocks))
            status.text(f"正在分析 {ticker}...")
            df = get_cached(ticker)
            if df.empty or len(df) < 62:
                continue
            try:
                pre = precompute_signals(df)
                n_hit = 0
                all_hit = True
                for k, flag in enumerate(scan_sigs):
                    if flag:
                        if bool(pre[S_NAMES[k]].iloc[-1]):
                            n_hit += 1
                        else:
                            all_hit = False
                            break
                if not all_hit or n_hit == 0:
                    continue

                c   = df.iloc[-1]
                p   = df.iloc[-2]
                vol_avg  = df["Volume"].rolling(20).mean().iloc[-1]
                pct      = (float(c["Close"]) - float(p["Close"])) / float(p["Close"]) * 100
                bb_range = float(c["BB_upper"]) - float(c["BB_lower"])
                bb_pct   = (float(c["Close"]) - float(c["BB_lower"])) / bb_range * 100 if bb_range > 0 else 50
                results.append({
                    "代碼": ticker, "現價": round(float(c["Close"]), 2),
                    "漲跌%": round(pct, 2), "RSI": round(float(c["RSI"]), 1),
                    "J值": round(float(c["J"]), 1),
                    "BB位置": f"{bb_pct:.0f}%", "訊號數": n_hit,
                })
                hits_dfs[ticker] = df
            except Exception:
                continue

        status.empty(); pbar.empty()
        if results:
            st.error(f"🔴 發現 {len(results)} 個賣出標的")
            show_scan_metrics(results)
            st.divider()
            df_show = pd.DataFrame(results)
            df_show["現價"]  = df_show["現價"].map(lambda x: f"{x:.2f}")
            df_show["漲跌%"] = df_show["漲跌%"].map(lambda x: f"{'+' if x>=0 else ''}{x:.2f}%")
            df_show["J值"]   = df_show["J值"].map(lambda x: f"{x:.1f}")
            st.dataframe(df_show, use_container_width=True)
            for ticker in hits_dfs:
                st.write(f"### ⚠️ {ticker}")
                show_chart(ticker, hits_dfs[ticker])
        else:
            st.warning("目前沒有符合賣出條件的股票，請嘗試減少勾選的條件數量。")
