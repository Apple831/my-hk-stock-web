# tabs/tab_buy_scan.py
#
# v17 修復（2026-04-26）:
# 🔴 Bug 4: hsi_bullish 已是 dead param 但 UI 文案仍顯示「b5/b6 已過濾」
#   修復：明確告訴用戶 b5/b6 不會自動過濾，建議手動勾選 b8 趨勢確認
#
# 🟡 補充：勾選介面新增 b11 / s8（與 indicators / signals 對應）

import streamlit as st
import pandas as pd
from data import get_stock_data, get_cached
from indicators import calculate_indicators, precompute_signals
from signals import signal_strength_score
from charts import show_chart, show_scan_metrics
from ui_components import cache_banner, preset_selector, get_preset_sigs
from config import B_NAMES


def render(stocks: list):
    st.subheader("🟢 買入策略掃描")
    cache_banner()

    _preset, _custom = preset_selector("tab2")

    if _custom:
        st.caption("🟢 買入策略（勾選一個或多個，多個條件需同時符合）")
        col_a, col_b = st.columns(2)
        b1  = col_a.checkbox("① 突破阻力位 + 成交量放大",      help="收盤 > 前20日最高價，且成交量 > 20日均量 1.5 倍")
        b2  = col_a.checkbox("② MA5 金叉 MA20",                help="5日均線今日上穿20日均線（趨勢轉強）")
        b3  = col_a.checkbox("③ 底背離（價創新低 MACD未）",     help="swing low 背離：價格新低但 DIF 未新低，RSI < 40")
        b4  = col_a.checkbox("④ 底部形態突破（放量站上MA20）",  help="近期均線低位，今日放量站上 MA20，底部確認")
        b5  = col_a.checkbox("⑤ 布林帶下軌買入",                help="收盤跌穿布林下軌。⚠️ 不會自動過濾熊市，建議搭配 b8 使用")
        b6  = col_b.checkbox("⑥ RSI 超賣（< 30）",             help="RSI 低於 30。⚠️ 不會自動過濾熊市，建議搭配 b8 使用")
        b7  = col_b.checkbox("⑦ MACD 金叉（DIF上穿DEA）",      help="DIF 今日上穿 DEA，動能由弱轉強，中線入場訊號")
        b8  = col_b.checkbox("⑧ 個股趨勢確認（MA20 > MA60）",  help="【推薦常開】確保個股本身在上升趨勢")
        b9  = col_b.checkbox("⑨ 52週新高突破",                  help="【動能策略】接近或突破52週高點，強者恆強")
        b10 = col_b.checkbox("⑩ 縮量回調至 MA20",              help="【低風險入場】上升趨勢中回調至MA20附近且成交量萎縮")
        b11 = col_b.checkbox("⑪ KDJ 超賣金叉",                  help="K<20, D<20 且 K 上穿 D，深度超賣訊號")
        buy_custom = (b1,b2,b3,b4,b5,b6,b7,b8,b9,b10,b11)

        st.caption("🔴 賣出策略（可額外勾選，不選則只靠止損出場）")
        col_sa, col_sb = st.columns(2)
        s1 = col_sa.checkbox("⑫ 頭部跌破 MA20（放量）",  key="t2_s1")
        s2 = col_sa.checkbox("⑬ 布林帶上軌賣出",          key="t2_s2")
        s3 = col_sa.checkbox("⑭ 上漲縮量警惕頂部",        key="t2_s3")
        s4 = col_sa.checkbox("⑮ 放量急跌",                key="t2_s4")
        s5 = col_sb.checkbox("⑯ RSI 超買（> 70）",        key="t2_s5")
        s6 = col_sb.checkbox("⑰ MACD 死叉",               key="t2_s6")
        s7 = col_sb.checkbox("⑱ 三日陰線 + 跌破MA20",     key="t2_s7")
        s8 = col_sb.checkbox("⑲ KDJ 高位死叉",            key="t2_s8")
        sell_custom = (s1,s2,s3,s4,s5,s6,s7,s8)
    else:
        buy_custom  = (False,)*11
        sell_custom = (False,)*8

    buy_sigs, _ = get_preset_sigs(_preset, buy_custom, sell_custom)

    top_n_buy = st.number_input("只顯示評分最高前 N 名（0 = 全部）", value=10, min_value=0, step=5, key="top_n_buy")

    if st.button("🟢 開始掃描買點"):
        if not any(buy_sigs):
            st.warning("⚠️ 請至少勾選一個買入策略（或選擇一個組合）")
            return

        df_hsi_scan = get_stock_data("^HSI", period="3mo")
        hsi_bull = True
        if not df_hsi_scan.empty:
            df_hsi_scan = calculate_indicators(df_hsi_scan)
            hsi_bull = bool(df_hsi_scan["MA20"].iloc[-1] > df_hsi_scan["MA60"].iloc[-1])

        results, hits_dfs = [], {}
        pbar   = st.progress(0)
        status = st.empty()
        for i, s in enumerate(stocks):
            pbar.progress((i + 1) / len(stocks))
            status.text(f"正在分析 {s}...")
            df = get_cached(s)
            if df.empty or len(df) < 62:
                continue
            try:
                # hsi_bullish 已是 dead param，傳入只為向後相容
                pre = precompute_signals(df, hsi_bullish=hsi_bull)
                n_hit = 0
                all_hit = True
                for k, flag in enumerate(buy_sigs):
                    if flag:
                        if bool(pre[B_NAMES[k]].iloc[-1]):
                            n_hit += 1
                        else:
                            all_hit = False
                            break
                if not all_hit or n_hit == 0:
                    continue

                c   = df.iloc[-1]
                p   = df.iloc[-2]
                pct = (float(c["Close"]) - float(p["Close"])) / float(p["Close"]) * 100
                bb_range = float(c["BB_upper"]) - float(c["BB_lower"])
                bb_pct   = (float(c["Close"]) - float(c["BB_lower"])) / bb_range * 100 if bb_range > 0 else 50
                score    = signal_strength_score(df, n_hit)
                results.append({
                    "代碼": s, "評分": score,
                    "現價": round(float(c["Close"]), 2),
                    "漲跌%": round(pct, 2),
                    "RSI": round(float(c["RSI"]), 1),
                    "J值": round(float(c["J"]), 1),
                    "BB位置": f"{bb_pct:.0f}%",
                    "訊號數": n_hit,
                })
                hits_dfs[s] = df
            except Exception:
                continue

        status.empty(); pbar.empty()
        if results:
            results.sort(key=lambda x: x["評分"], reverse=True)
            if top_n_buy > 0:
                results = results[:int(top_n_buy)]

            # ── 🔴 Bug 4 修復：文案改為提醒用戶手動過濾 ─────────────
            if hsi_bull:
                hsi_label = "🟢 多頭"
            else:
                hsi_label = "🔴 空頭（提醒：b5/b6 不會自動過濾，建議手動勾選 ⑧ 個股趨勢確認）"

            st.success(f"✅ 發現 {len(results)} 個買入標的　｜　恆指趨勢：{hsi_label}")
            show_scan_metrics(results)
            st.divider()
            df_show = pd.DataFrame(results)
            df_show["現價"]  = df_show["現價"].map(lambda x: f"{x:.2f}")
            df_show["漲跌%"] = df_show["漲跌%"].map(lambda x: f"{'+' if x>=0 else ''}{x:.2f}%")
            df_show["J值"]   = df_show["J值"].map(lambda x: f"{x:.1f}")
            st.dataframe(
                df_show.style.map(
                    lambda v: (
                        f"background-color:rgba(38,166,154,{min(float(v),100)/100*0.6+0.1:.2f});"
                        f"color:#fff;font-weight:bold"
                        if isinstance(v, (int, float)) else ""
                    ), subset=["評分"]
                ), use_container_width=True,
            )
            for r in results:
                s = r["代碼"]
                st.write(f"### 🎯 {s}　評分 {r['評分']}")
                show_chart(s, hits_dfs[s])
        else:
            st.warning("⚠️ 沒有符合條件的股票，請嘗試減少勾選的條件數量。")
