import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime
import requests
import os

st.set_page_config(page_title="港股狙擊手 V9.1.1", layout="wide")

# ══════════════════════════════════════════════════════════════════
# ① 所有函數定義（必須在 sidebar / UI 之前）
# ══════════════════════════════════════════════════════════════════

# ── 股票清單 ───────────────────────────────────────────────────────
def load_stocks_from_file() -> list:
    if os.path.exists("stocks.txt"):
        stocks = [line.split("#")[0].strip() for line in open("stocks.txt", "r", encoding="utf-8") if ".HK" in line]
        if stocks:
            return stocks
    return ["0700.HK", "9988.HK", "3690.HK"]

def load_stocks() -> list:
    if st.session_state.get("stocks"):
        return st.session_state["stocks"]
    stocks = load_stocks_from_file()
    st.session_state["stocks"] = stocks
    return stocks

# ── 時區安全處理（修復 tz_localize 報錯）────────────────────────────
def normalize_index(df: pd.DataFrame) -> pd.DataFrame:
    """統一處理時區：有時區先 convert，沒有就直接用"""
    try:
        if df.index.tz is not None:
            df.index = df.index.tz_convert("Asia/Hong_Kong").tz_localize(None)
        else:
            df.index = pd.to_datetime(df.index)
    except Exception:
        df.index = pd.to_datetime(df.index, utc=True).tz_localize(None)
    return df

# ── MultiIndex 展平（新版 yfinance 常見）─────────────────────────────
def flatten_columns(df: pd.DataFrame) -> pd.DataFrame:
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = [col[0] if col[1] == "" else col[0] for col in df.columns]
    df.columns = [str(c).strip() for c in df.columns]
    return df

# ── 單股下載（指數 / 分析 Tab 用）────────────────────────────────────
def get_stock_data(ticker: str, period: str = "1y") -> pd.DataFrame:
    try:
        if ticker == "^HSTECH":
            for sym in ["800700.HK", "^HSTECH", "3032.HK"]:
                df = yf.download(sym, period=period, progress=False, auto_adjust=True)
                if not df.empty:
                    break
        elif ticker == "^HSI":
            for sym in ["^HSI", "2800.HK"]:
                df = yf.download(sym, period=period, progress=False, auto_adjust=True)
                if not df.empty:
                    break
        else:
            df = yf.download(ticker, period=period, progress=False, auto_adjust=True)

        if df.empty:
            return pd.DataFrame()
        df = flatten_columns(df)
        df = normalize_index(df)
        return df.dropna(subset=["Close"])
    except Exception:
        return pd.DataFrame()

# ── 指標計算 ──────────────────────────────────────────────────────
def calculate_indicators(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["MA5"]  = df["Close"].rolling(5).mean()
    df["MA10"] = df["Close"].rolling(10).mean()
    df["MA20"] = df["Close"].rolling(20).mean()
    df["MA60"] = df["Close"].rolling(60).mean()

    exp1 = df["Close"].ewm(span=12, adjust=False).mean()
    exp2 = df["Close"].ewm(span=26, adjust=False).mean()
    df["DIF"]       = exp1 - exp2
    df["DEA"]       = df["DIF"].ewm(span=9, adjust=False).mean()
    df["MACD_Hist"] = df["DIF"] - df["DEA"]

    low9  = df["Low"].rolling(9).min()
    high9 = df["High"].rolling(9).max()
    denom = (high9 - low9).replace(0, 1)
    rsv   = (df["Close"] - low9) / denom * 100
    df["K"] = rsv.ewm(com=2, adjust=False).mean()
    df["D"] = df["K"].ewm(com=2, adjust=False).mean()
    df["J"] = 3 * df["K"] - 2 * df["D"]

    bb_mid         = df["Close"].rolling(20).mean()
    bb_std         = df["Close"].rolling(20).std()
    df["BB_upper"] = bb_mid + 2 * bb_std
    df["BB_mid"]   = bb_mid
    df["BB_lower"] = bb_mid - 2 * bb_std

    delta       = df["Close"].diff()
    gain        = delta.clip(lower=0).rolling(14).mean()
    loss        = (-delta.clip(upper=0)).rolling(14).mean()
    rs          = gain / loss.replace(0, 1e-9)
    df["RSI"]   = 100 - (100 / (1 + rs))

    return df

# ── 批量下載（掃描 Tab 用）────────────────────────────────────────
def batch_download(tickers: list, period: str = "1y") -> dict:
    cache = {}
    try:
        raw = yf.download(
            tickers, period=period,
            progress=False, auto_adjust=True,
            group_by="ticker", threads=True
        )
    except Exception:
        return cache

    if raw.empty:
        return cache

    # 新版 yfinance group_by="ticker" → MultiIndex level0=ticker, level1=OHLCV
    # 舊版可能是 level0=OHLCV, level1=ticker — 兩種都要處理
    if isinstance(raw.columns, pd.MultiIndex):
        lvl0 = raw.columns.get_level_values(0).unique().tolist()
        lvl1 = raw.columns.get_level_values(1).unique().tolist()
        # 判斷哪一層是 ticker
        ohlcv = {"Open", "High", "Low", "Close", "Volume"}
        if set(lvl0) & ohlcv:          # level0 = OHLCV → level1 = ticker
            ticker_level = 1
        else:                           # level0 = ticker → level1 = OHLCV
            ticker_level = 0
    else:
        ticker_level = None

    for ticker in tickers:
        try:
            if ticker_level is None:
                df = raw.copy()
            elif ticker_level == 1:
                if ticker not in raw.columns.get_level_values(1):
                    continue
                df = raw.xs(ticker, axis=1, level=1).copy()
            else:
                if ticker not in raw.columns.get_level_values(0):
                    continue
                df = raw.xs(ticker, axis=1, level=0).copy()

            df = flatten_columns(df)
            df = normalize_index(df)
            df = df.dropna(subset=["Close"])
            if len(df) < 60:
                continue
            cache[ticker] = calculate_indicators(df)
        except Exception:
            continue
    return cache

# ── TradingView Screener ──────────────────────────────────────────
TV_URL = "https://scanner.tradingview.com/hongkong/scan"
TV_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "Content-Type": "application/json",
    "Origin":  "https://www.tradingview.com",
    "Referer": "https://www.tradingview.com/",
}

def fetch_stocks_from_tradingview(min_cap_hkd: int = 10_000_000_000) -> list:
    payload = {
        "filter": [
            {"left": "market_cap_basic",             "operation": "greater", "right": min_cap_hkd / 7.8},
            {"left": "earnings_per_share_basic_ttm", "operation": "greater", "right": 0},
            {"left": "is_primary",                   "operation": "equal",   "right": True},
        ],
        "markets": ["hongkong"],
        "symbols": {"query": {"types": ["stock"]}, "tickers": []},
        "columns": ["name", "description", "close", "market_cap_basic", "earnings_per_share_basic_ttm"],
        "sort": {"sortBy": "market_cap_basic", "sortOrder": "desc"},
        "range": [0, 500],
    }
    resp = requests.post(TV_URL, headers=TV_HEADERS, json=payload, timeout=20)
    resp.raise_for_status()
    tickers = []
    for row in resp.json().get("data", []):
        d = row.get("d", [])
        if not d:
            continue
        try:
            tickers.append(f"{int(d[0]):04d}.HK")
        except (ValueError, TypeError):
            continue
    return tickers

# ── Cache 助手 ────────────────────────────────────────────────────
def get_cached(ticker: str) -> pd.DataFrame:
    cache = st.session_state.get("stock_cache", {})
    if ticker in cache:
        return cache[ticker]
    df = get_stock_data(ticker)
    if not df.empty:
        return calculate_indicators(df)
    return pd.DataFrame()

def get_cache_label() -> str:
    ts = st.session_state.get("cache_time")
    n  = len(st.session_state.get("stock_cache", {}))
    if ts and n:
        return f"✅ 已緩存 {n} 隻｜{ts}"
    return "⚠️ 尚未緩存"

def cache_banner():
    cache = st.session_state.get("stock_cache", {})
    if cache:
        ts = st.session_state.get("cache_time", "")
        st.success(f"⚡ 使用緩存數據（{len(cache)} 隻，{ts} 下載）— 掃描將在數秒內完成", icon="🚀")
    else:
        st.warning(
            "⚠️ 尚未緩存數據，掃描將逐隻下載（較慢）。"
            "建議先點擊左側 **⬇️ 批量下載全部股票** 再掃描！",
            icon="🐢",
        )

# ── 繪圖 ──────────────────────────────────────────────────────────
def show_scan_metrics(results):
    cols_per_row = 4
    for row_start in range(0, len(results), cols_per_row):
        chunk = results[row_start: row_start + cols_per_row]
        cols  = st.columns(cols_per_row)
        for col, r in zip(cols, chunk):
            pct       = r["漲跌%"]
            arrow     = "🟢 ▲" if pct >= 0 else "🔴 ▼"
            delta_str = f"{'+' if pct >= 0 else ''}{pct:.2f}%"
            col.metric(label=f"{arrow} {r['代碼']}", value=f"${r['現價']:.2f}", delta=delta_str)

def show_chart(ticker: str, df: pd.DataFrame):
    fig = make_subplots(
        rows=4, cols=1, shared_xaxes=True,
        vertical_spacing=0.03,
        row_heights=[0.4, 0.15, 0.2, 0.2],
    )
    fig.add_trace(go.Candlestick(
        x=df.index, open=df["Open"], high=df["High"],
        low=df["Low"], close=df["Close"],
        increasing_line_color="#26a69a", decreasing_line_color="#ef5350", name="K線",
    ), row=1, col=1)

    for ma, color in zip(["MA5", "MA20", "MA60"], ["gray", "purple", "orange"]):
        fig.add_trace(go.Scatter(x=df.index, y=df[ma], name=ma,
                                 line=dict(width=1, color=color)), row=1, col=1)

    fig.add_trace(go.Scatter(x=df.index, y=df["BB_upper"], name="BB上",
        line=dict(width=1, color="rgba(100,180,255,0.6)", dash="dot")), row=1, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df["BB_lower"], name="BB下",
        line=dict(width=1, color="rgba(100,180,255,0.6)", dash="dot"),
        fill="tonexty", fillcolor="rgba(100,180,255,0.05)"), row=1, col=1)

    v_colors = ["#26a69a" if c >= o else "#ef5350" for c, o in zip(df["Close"], df["Open"])]
    fig.add_trace(go.Bar(x=df.index, y=df["Volume"], marker_color=v_colors, name="成交量"), row=2, col=1)

    h_colors = ["#26a69a" if v >= 0 else "#ef5350" for v in df["MACD_Hist"]]
    fig.add_trace(go.Bar(x=df.index, y=df["MACD_Hist"], marker_color=h_colors, name="MACD柱"), row=3, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df["DIF"], line=dict(color="#f9a825", width=1), name="DIF"), row=3, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df["DEA"], line=dict(color="#42a5f5", width=1), name="DEA"), row=3, col=1)

    fig.add_trace(go.Scatter(x=df.index, y=df["K"],   line=dict(color="#f9a825", width=1), name="K"), row=4, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df["D"],   line=dict(color="#42a5f5", width=1), name="D"), row=4, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df["J"],   line=dict(color="#ab47bc", width=1), name="J"), row=4, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df["RSI"], line=dict(color="#ff7043", width=1.5, dash="dot"), name="RSI"), row=4, col=1)
    for lvl, clr in [(30, "rgba(38,166,154,0.4)"), (70, "rgba(239,83,80,0.4)")]:
        fig.add_hline(y=lvl, line_dash="dot", line_color=clr, row=4, col=1)

    fig.update_layout(
        height=700, showlegend=False,
        xaxis_rangeslider_visible=False,
        margin=dict(t=10, b=10),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
    )
    st.plotly_chart(fig, use_container_width=True)

# ══════════════════════════════════════════════════════════════════
# ② Sidebar（所有函數已定義，安全呼叫）
# ══════════════════════════════════════════════════════════════════
with st.sidebar:
    st.markdown("### ⚙️ 數據控制台")
    n_stocks = len(st.session_state.get("stocks", []))
    st.caption(f"股票清單：{n_stocks or '讀取中'} 隻")

    if st.button("🔄 更新清單 (TradingView)"):
        with st.spinner("篩選中：主要上市｜市值>100億｜EPS>0..."):
            try:
                new_stocks = fetch_stocks_from_tradingview()
                if new_stocks:
                    st.session_state["stocks"] = new_stocks
                    st.session_state.pop("stock_cache", None)
                    st.session_state.pop("cache_time", None)
                    st.success(f"✅ 已更新！共 {len(new_stocks)} 隻")
                    st.rerun()
                else:
                    st.warning("⚠️ 沒有取得數據")
            except Exception as e:
                st.error(f"❌ 失敗：{e}")

    st.divider()
    st.markdown("### 🚀 批量下載數據")
    st.caption(get_cache_label())
    cache_period = st.selectbox("下載週期", ["6mo", "1y", "2y"], index=1, key="cache_period")

    if st.button("⬇️ 批量下載全部股票", type="primary"):
        stocks_to_dl = st.session_state.get("stocks") or load_stocks_from_file()
        if not stocks_to_dl:
            st.warning("請先載入股票清單")
        else:
            batch_size = 20
            all_cache  = {}
            batches    = [stocks_to_dl[i:i+batch_size] for i in range(0, len(stocks_to_dl), batch_size)]
            prog = st.progress(0, text="準備下載...")
            for bi, batch in enumerate(batches):
                prog.progress(
                    (bi + 1) / len(batches),
                    text=f"下載第 {bi+1}/{len(batches)} 批（每批 {batch_size} 隻）...",
                )
                all_cache.update(batch_download(batch, period=cache_period))
            prog.empty()
            st.session_state["stock_cache"] = all_cache
            st.session_state["cache_time"]  = datetime.now().strftime("%H:%M")
            st.success(f"✅ 完成！已緩存 {len(all_cache)} 隻股票數據")
            st.rerun()

    if st.session_state.get("stock_cache"):
        if st.button("🗑️ 清除緩存"):
            st.session_state.pop("stock_cache", None)
            st.session_state.pop("cache_time", None)
            st.rerun()

# ══════════════════════════════════════════════════════════════════
# ③ 主 UI
# ══════════════════════════════════════════════════════════════════
STOCKS = load_stocks()
st.title("🏹 港股狙擊手 V9.1.1")
tabs = st.tabs(["🌍 指數", "🏆 跑贏大市", "🟢 買入掃描", "🔴 賣出掃描", "🔍 分析"])

# ── TAB 0：指數 ───────────────────────────────────────────────────
with tabs[0]:
    st.subheader("🌍 主要指數走勢")
    indices = {
        "恆生指數 (^HSI)":    "^HSI",
        "恆生科技 (^HSTECH)": "^HSTECH",
        "恐慌指數 (^VIX)":    "^VIX",
    }
    col1, col2 = st.columns([1, 3])
    with col1:
        selected_index  = st.selectbox("選擇指數", list(indices.keys()))
        period          = st.selectbox("時間週期", ["3mo", "6mo", "1y", "2y"], index=2)
    with col2:
        ticker_code = indices[selected_index]
        with st.spinner(f"載入 {selected_index} 數據中..."):
            df_idx = get_stock_data(ticker_code, period=period)
        if df_idx.empty:
            st.error(f"❌ 無法載入 {selected_index} 數據，請稍後再試。")
        else:
            df_idx = calculate_indicators(df_idx)
            show_chart(ticker_code, df_idx)

# ── TAB 1：跑贏大市 ───────────────────────────────────────────────
with tabs[1]:
    st.subheader("🏆 跑贏大市排行（僅顯示強勢股）")
    cache_banner()

    period_options = {
        "1日":   2,
        "1週":   6,
        "1個月": 22,
        "3個月": 63,
        "6個月": 126,
    }
    period_beat = st.selectbox("比較週期", list(period_options.keys()), index=2, key="beat_period")

    if st.button("📊 開始計算跑贏大市"):
        lb     = period_options[period_beat]
        df_hsi = get_stock_data("^HSI", period="6mo")
        if df_hsi.empty:
            st.error("無法取得恆指數據")
        else:
            si      = -lb if len(df_hsi) >= lb else 0
            hsi_ret = (df_hsi["Close"].iloc[-1] - df_hsi["Close"].iloc[si]) / df_hsi["Close"].iloc[si] * 100

            results = []
            pbar    = st.progress(0)
            for i, s in enumerate(STOCKS):
                pbar.progress((i + 1) / len(STOCKS))
                df_s = get_cached(s)
                if df_s.empty or len(df_s) < 2:
                    continue
                si_s      = -lb if len(df_s) >= lb else 0
                stock_ret = (df_s["Close"].iloc[-1] - df_s["Close"].iloc[si_s]) / df_s["Close"].iloc[si_s] * 100
                results.append({
                    "代碼":      s,
                    "現價":      round(float(df_s["Close"].iloc[-1]), 2),
                    "股票升幅%": stock_ret,
                    "恆指升幅%": hsi_ret,
                    "超額回報%": stock_ret - hsi_ret,
                })
            pbar.empty()

            if results:
                df_res = pd.DataFrame(results)
                df_res = df_res[df_res["超額回報%"] > 0].sort_values("超額回報%", ascending=False)
                if not df_res.empty:
                    st.success(f"✅ {len(df_res)} 隻跑贏大市，恆指回報：{hsi_ret:.2f}%")
                    st.dataframe(df_res.style.format({
                        "現價": "${:.2f}",
                        "股票升幅%": "{:+.2f}%",
                        "恆指升幅%": "{:+.2f}%",
                        "超額回報%": "{:+.2f}%",
                    }).map(
                        lambda x: "color:#26a69a" if x > 0 else ("color:#ef5350" if x < 0 else ""),
                        subset=["股票升幅%", "超額回報%"],
                    ), use_container_width=True)
                else:
                    st.warning(f"⚠️ 沒有股票跑贏大市（恆指回報：{hsi_ret:.2f}%）")

# ── TAB 2：買入掃描 ───────────────────────────────────────────────
with tabs[2]:
    st.subheader("🟢 買入策略掃描")
    cache_banner()

    with st.expander("💡 策略組合建議（點擊展開）", expanded=True):
        st.markdown("""
        > 勾選**多個策略**可提高訊號可靠度（條件越多 = 越嚴格）。以下是經實戰驗證的黃金組合：

        | 組合 | 勾選策略 | 適用場景 | 勝率參考 |
        |------|---------|---------|---------|
        | 🔥 **穩健趨勢追蹤** | ② 金叉 ＋ ① 突破放量 | 中長線，趨勢剛起步 | ⭐⭐⭐⭐ |
        | 💎 **三重超賣抄底** | ④ KDJ超賣 ＋ ⑦ 布林下軌 ＋ ⑧ RSI超賣 | 超跌反彈，短線 | ⭐⭐⭐⭐ |
        | 🎯 **底部背離入場** | ③ 底背離 ＋ ④ KDJ超賣 | 中線底部建倉 | ⭐⭐⭐⭐⭐ |
        | ⚡ **突破強勢股** | ① 突破放量 ＋ ⑨ MACD金叉 | 動能強勢，短中線 | ⭐⭐⭐⭐ |
        | 🌊 **缺口反轉** | ⑤ 缺口低開 ＋ ④ KDJ超賣 | 極端恐慌後反彈 | ⭐⭐⭐ |
        | 🏗️ **底部確認** | ⑥ 底部突破 ＋ ② 金叉 | 底部形態完成後追入 | ⭐⭐⭐⭐ |

        **⚠️ 不建議組合：**
        - ③ 底背離 ＋ ① 突破放量 → 邏輯矛盾（一個在低位，一個在高位）
        - ⑤ 缺口低開 單獨使用 → 假訊號多，需配合超賣指標
        """)

    st.caption("勾選一個或多個策略（多個條件需同時符合）")
    col_a, col_b = st.columns(2)
    b1 = col_a.checkbox("① 突破阻力位 + 成交量放大",    help="收盤 > 前20日最高價，且成交量 > 20日均量 1.5 倍")
    b2 = col_a.checkbox("② MA5 金叉 MA20",              help="5日均線今日上穿20日均線（趨勢轉強）")
    b3 = col_a.checkbox("③ 底背離（價創新低 MACD未）",   help="收盤創20日新低，但 DIF 未創新低（看漲背離）")
    b4 = col_a.checkbox("④ KDJ 超賣（J < 10）",         help="KDJ 的 J 值低於 10，極度超賣")
    b5 = col_a.checkbox("⑤ 缺口低開回補做多",            help="今日開盤低於昨日最低（跳空低開），短期反彈回補")
    b6 = col_b.checkbox("⑥ 底部形態突破（放量站上MA20）", help="近期處於低位（MA60以下），今日放量站上 MA20")
    b7 = col_b.checkbox("⑦ 布林帶下軌買入",              help="收盤跌穿布林帶下軌，均值回歸買點")
    b8 = col_b.checkbox("⑧ RSI 超賣（RSI < 30）",       help="RSI低於30，超賣區間。比KDJ更穩定，假訊號少")
    b9 = col_b.checkbox("⑨ MACD 金叉（DIF上穿DEA）",    help="DIF 今日上穿 DEA，動能由弱轉強，中線入場訊號")

    if st.button("🟢 開始掃描買點"):
        if not any([b1, b2, b3, b4, b5, b6, b7, b8, b9]):
            st.warning("⚠️ 請至少勾選一個策略")
        else:
            results, hits_dfs = [], {}
            pbar   = st.progress(0)
            status = st.empty()
            for i, s in enumerate(STOCKS):
                pbar.progress((i + 1) / len(STOCKS))
                status.text(f"正在分析 {s}...")
                df = get_cached(s)
                if df.empty or len(df) < 60:
                    continue
                c, p    = df.iloc[-1], df.iloc[-2]
                vol_avg = df["Volume"].rolling(20).mean().iloc[-1]

                checks = []
                if b1:
                    resist = df["High"].iloc[-21:-1].max()
                    checks.append(bool(c["Close"] > resist) and bool(c["Volume"] > vol_avg * 1.5))
                if b2:
                    checks.append(bool(c["MA5"] > c["MA20"]) and bool(p["MA5"] <= p["MA20"]))
                if b3:
                    pl = df["Close"].iloc[-20:].min()
                    dl = df["DIF"].iloc[-20:].min()
                    checks.append(bool(c["Close"] <= pl * 1.005) and bool(c["DIF"] > dl * 1.01))
                if b4:
                    checks.append(bool(c["J"] < 10))
                if b5:
                    checks.append(bool(c["Open"] < p["Low"]))
                if b6:
                    was_below = bool(df["Close"].iloc[-10:-1].mean() < df["MA60"].iloc[-10:-1].mean())
                    checks.append(was_below and bool(c["Close"] > c["MA20"]) and
                                  bool(p["Close"] <= p["MA20"]) and bool(c["Volume"] > vol_avg * 1.3))
                if b7:
                    checks.append(bool(c["Close"] < c["BB_lower"]))
                if b8:
                    checks.append(bool(c["RSI"] < 30))
                if b9:
                    checks.append(bool(c["DIF"] > c["DEA"]) and bool(p["DIF"] <= p["DEA"]))

                if checks and all(checks):
                    pct      = ((c["Close"] - p["Close"]) / p["Close"]) * 100
                    bb_range = c["BB_upper"] - c["BB_lower"]
                    bb_pct   = (c["Close"] - c["BB_lower"]) / bb_range * 100 if bb_range > 0 else 50
                    results.append({
                        "代碼":   s,
                        "現價":   round(float(c["Close"]), 2),
                        "漲跌%":  round(float(pct), 2),
                        "RSI":    round(float(c["RSI"]), 1),
                        "J值":    round(float(c["J"]), 1),
                        "BB位置": f"{bb_pct:.0f}%",
                    })
                    hits_dfs[s] = df

            status.empty(); pbar.empty()
            if results:
                st.success(f"✅ 發現 {len(results)} 個買入標的")
                show_scan_metrics(results)
                st.divider()
                df_show = pd.DataFrame(results)
                df_show["現價"]  = df_show["現價"].map(lambda x: f"{x:.2f}")
                df_show["漲跌%"] = df_show["漲跌%"].map(lambda x: f"{'+' if x>=0 else ''}{x:.2f}%")
                df_show["J值"]   = df_show["J值"].map(lambda x: f"{x:.1f}")
                st.dataframe(df_show, use_container_width=True)
                for s in hits_dfs:
                    st.write(f"### 🎯 {s}")
                    show_chart(s, hits_dfs[s])
            else:
                st.warning("⚠️ 沒有符合條件的股票，請嘗試減少勾選的條件數量。")

# ── TAB 3：賣出掃描 ───────────────────────────────────────────────
with tabs[3]:
    st.subheader("🔴 賣出 / 做空策略掃描")
    cache_banner()

    with st.expander("💡 策略組合建議（點擊展開）", expanded=True):
        st.markdown("""
        > 勾選**多個策略**可提高訊號可靠度。以下是經實戰驗證的黃金組合：

        | 組合 | 勾選策略 | 適用場景 | 勝率參考 |
        |------|---------|---------|---------|
        | 🔥 **雙重超買出貨** | ⑦ 布林上軌 ＋ ⑨ RSI超買 | 頂部回調，短線 | ⭐⭐⭐⭐ |
        | 💀 **趨勢反轉確認** | ⑥ 頭部破位 ＋ ② 死叉 | 確認下跌趨勢，中線 | ⭐⭐⭐⭐⭐ |
        | ⚡ **恐慌急跌跟進** | ⑧ 放量急跌 ＋ ② 死叉 | 短線動能做空 | ⭐⭐⭐ |
        | 🌊 **缺口回補做空** | ⑤ 缺口高開 ＋ ⑨ RSI超買 | 高開後回補，日內/短線 | ⭐⭐⭐ |
        | 🏗️ **量價背離出逃** | ⑧ 上漲縮量 ＋ ⑩ MACD死叉 | 頂部出貨訊號 | ⭐⭐⭐⭐ |

        **⚠️ 不建議組合：**
        - ⑤ 缺口高開 ＋ ⑧ 放量急跌 → 兩個條件同時觸發概率極低
        - ⑨ RSI超買 單獨在強勢行情使用 → 強趨勢中 RSI 可長期高位，需配合形態
        """)

    st.caption("勾選一個或多個策略（多個條件需同時符合）")
    col_c, col_d = st.columns(2)
    s1 = col_c.checkbox("⑤ 缺口高開回補做空",           help="今日開盤高於昨日最高（跳空高開），短期大概率回補")
    s2 = col_c.checkbox("⑥ 頭部形態跌破 MA20（放量）",  help="近期均線高位，今日放量跌破 MA20，頭部確認")
    s3 = col_c.checkbox("⑦ 布林帶上軌賣出",             help="收盤突破布林帶上軌，均值回歸賣點")
    s4 = col_c.checkbox("⑧ 上漲縮量（警惕頂部）",       help="價格創10日新高，但成交量萎縮（量能不足，假突破）")
    s5 = col_d.checkbox("⑧ 放量急跌（跟進做空）",        help="收盤跌幅 > 2%，且成交量 > 20日均量 1.5 倍")
    s6 = col_d.checkbox("② MA5 死叉 MA20",             help="5日均線今日下穿20日均線（趨勢轉弱）")
    s7 = col_d.checkbox("⑨ RSI 超買（RSI > 70）",      help="RSI 高於 70，超買區間。比 KDJ 穩定，回調概率高")
    s8 = col_d.checkbox("⑩ MACD 死叉（DIF下穿DEA）",   help="DIF 今日下穿 DEA，動能由強轉弱，中線出場訊號")

    if st.button("🔴 開始掃描賣點"):
        if not any([s1, s2, s3, s4, s5, s6, s7, s8]):
            st.warning("⚠️ 請至少勾選一個策略")
        else:
            results, hits_dfs = [], {}
            pbar   = st.progress(0)
            status = st.empty()
            for i, ticker in enumerate(STOCKS):
                pbar.progress((i + 1) / len(STOCKS))
                status.text(f"正在分析 {ticker}...")
                df = get_cached(ticker)
                if df.empty or len(df) < 60:
                    continue
                c, p    = df.iloc[-1], df.iloc[-2]
                vol_avg = df["Volume"].rolling(20).mean().iloc[-1]

                checks = []
                if s1:
                    checks.append(bool(c["Open"] > p["High"]))
                if s2:
                    was_above = bool(df["Close"].iloc[-10:-1].mean() > df["MA60"].iloc[-10:-1].mean())
                    checks.append(was_above and bool(c["Close"] < c["MA20"]) and
                                  bool(p["Close"] >= p["MA20"]) and bool(c["Volume"] > vol_avg * 1.3))
                if s3:
                    checks.append(bool(c["Close"] > c["BB_upper"]))
                if s4:
                    ph = df["Close"].iloc[-10:].max()
                    checks.append(bool(c["Close"] >= ph * 0.995) and bool(c["Volume"] < vol_avg * 0.6))
                if s5:
                    pct_chg = (c["Close"] - p["Close"]) / p["Close"] * 100
                    checks.append(bool(pct_chg < -2) and bool(c["Volume"] > vol_avg * 1.5))
                if s6:
                    checks.append(bool(c["MA5"] < c["MA20"]) and bool(p["MA5"] >= p["MA20"]))
                if s7:
                    checks.append(bool(c["RSI"] > 70))
                if s8:
                    checks.append(bool(c["DIF"] < c["DEA"]) and bool(p["DIF"] >= p["DEA"]))

                if checks and all(checks):
                    pct      = ((c["Close"] - p["Close"]) / p["Close"]) * 100
                    bb_range = c["BB_upper"] - c["BB_lower"]
                    bb_pct   = (c["Close"] - c["BB_lower"]) / bb_range * 100 if bb_range > 0 else 50
                    results.append({
                        "代碼":   ticker,
                        "現價":   round(float(c["Close"]), 2),
                        "漲跌%":  round(float(pct), 2),
                        "RSI":    round(float(c["RSI"]), 1),
                        "J值":    round(float(c["J"]), 1),
                        "BB位置": f"{bb_pct:.0f}%",
                    })
                    hits_dfs[ticker] = df

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

# ── TAB 4：分析 ───────────────────────────────────────────────────
with tabs[4]:
    st.subheader("🔍 個股技術分析")
    col_left, col_right = st.columns([1, 3])
    with col_left:
        custom_ticker   = st.text_input("輸入股票代碼", value="0700.HK").upper()
        analysis_period = st.selectbox("週期", ["3mo", "6mo", "1y", "2y"], index=2, key="analysis_period")
        analyze_btn     = st.button("🔍 分析")
    with col_right:
        if analyze_btn:
            with st.spinner(f"正在分析 {custom_ticker}..."):
                df_a = get_stock_data(custom_ticker, period=analysis_period)
            if df_a.empty:
                st.error(f"❌ 無法取得 {custom_ticker} 數據，請確認代碼正確。")
            else:
                df_a = calculate_indicators(df_a)
                c    = df_a.iloc[-1]
                m1, m2, m3, m4 = st.columns(4)
                m1.metric("現價",    f"{c['Close']:.2f}")
                m2.metric("MA20",   f"{c['MA20']:.2f}", f"{((c['Close']-c['MA20'])/c['MA20']*100):.1f}%")
                m3.metric("RSI",    f"{c['RSI']:.1f}")
                m4.metric("MACD柱", f"{c['MACD_Hist']:.4f}")
                show_chart(custom_ticker, df_a)
