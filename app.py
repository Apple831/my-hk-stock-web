# ══════════════════════════════════════════════════════════════════
# app.py — 港股狙擊手 V11.0  主入口
# ══════════════════════════════════════════════════════════════════

import streamlit as st
from datetime import datetime

st.set_page_config(page_title="港股狙擊手 V11.0", layout="wide")

from data import (
    load_stocks, load_stocks_from_file,
    fetch_stocks_from_tradingview, batch_download,
    get_cache_label,
)
from tabs import (
    tab_index, tab_beat, tab_buy_scan,
    tab_sell_scan, tab_analysis, tab_backtest,
    tab_walkforward, tab_diagnosis,
)

# ══════════════════════════════════════════════════════════════════
# Sidebar
# ══════════════════════════════════════════════════════════════════
with st.sidebar:
    st.markdown("### ⚙️ 數據控制台")
    n_stocks = len(st.session_state.get("stocks", []))
    st.caption(f"股票清單：{n_stocks or '讀取中'} 隻")

    tv_min_cap = st.selectbox("最低市值", ["50億","100億","500億"], index=1, key="tv_min_cap")
    tv_min_vol = st.selectbox("日均成交額下限", ["3000萬","5000萬","1億"], index=1, key="tv_min_vol")
    _cap_map = {"50億":5_000_000_000, "100億":10_000_000_000, "500億":50_000_000_000}
    _vol_map = {"3000萬":30_000_000, "5000萬":50_000_000, "1億":100_000_000}

    if st.button("🔄 更新清單 (TradingView)"):
        _cap, _vol = _cap_map[tv_min_cap], _vol_map[tv_min_vol]
        with st.spinner(f"篩選中..."):
            try:
                new = fetch_stocks_from_tradingview(min_cap_hkd=_cap, min_vol_hkd=_vol)
                if new:
                    st.session_state["stocks"] = new
                    st.session_state.pop("stock_cache", None)
                    st.session_state.pop("cache_time", None)
                    st.success(f"✅ 已更新！共 {len(new)} 隻")
                    st.rerun()
                else:
                    st.warning("⚠️ 沒有取得數據")
            except Exception as e:
                st.error(f"❌ 失敗：{e}")

    st.divider()
    st.markdown("### 🚀 批量下載數據")
    st.caption(get_cache_label())
    cache_period = st.selectbox("下載週期", ["6mo","1y","2y"], index=1, key="cache_period")

    if st.button("⬇️ 批量下載全部股票", type="primary"):
        stocks_dl = st.session_state.get("stocks") or load_stocks_from_file()
        if not stocks_dl:
            st.warning("請先載入股票清單")
        else:
            batch_size = 20
            all_cache  = {}
            batches = [stocks_dl[i:i+batch_size] for i in range(0, len(stocks_dl), batch_size)]
            prog = st.progress(0, text="準備下載...")
            for bi, batch in enumerate(batches):
                prog.progress((bi+1)/len(batches), text=f"下載第 {bi+1}/{len(batches)} 批...")
                all_cache.update(batch_download(batch, period=cache_period))
            prog.empty()
            st.session_state["stock_cache"]    = all_cache
            st.session_state["cache_time"]     = datetime.now().strftime("%H:%M")
            st.session_state["cache_datetime"] = datetime.now()
            st.success(f"✅ 完成！已緩存 {len(all_cache)} 隻")
            st.rerun()

    if st.session_state.get("stock_cache"):
        if st.button("🗑️ 清除緩存"):
            st.session_state.pop("stock_cache", None)
            st.session_state.pop("cache_time", None)
            st.rerun()

# ══════════════════════════════════════════════════════════════════
# Main UI — Tab routing
# ══════════════════════════════════════════════════════════════════
STOCKS = load_stocks()
st.title("🏹 港股狙擊手 V11.0")

tabs = st.tabs([
    "🌍 指數", "🏆 跑贏大市", "🟢 買入掃描", "🔴 賣出掃描",
    "🔍 分析", "📊 回測", "🔬 Walk-Forward", "📡 訊號診斷",
])

with tabs[0]:
    tab_index.render()
with tabs[1]:
    tab_beat.render(STOCKS)
with tabs[2]:
    tab_buy_scan.render(STOCKS)
with tabs[3]:
    tab_sell_scan.render(STOCKS)
with tabs[4]:
    tab_analysis.render()
with tabs[5]:
    tab_backtest.render(STOCKS)
with tabs[6]:
    # FIX: tab_walkforward.render() → render(STOCKS)
    # 新版 tab_walkforward 加入了投資組合模式，需要 stocks 清單
    tab_walkforward.render(STOCKS)
with tabs[7]:
    tab_diagnosis.render(STOCKS)
