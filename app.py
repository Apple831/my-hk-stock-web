import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime
import requests
import os

st.set_page_config(page_title="港股狙擊手 V10.5", layout="wide")

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

# ── 異常值過濾（單日成交量 >10x 或價格 >30% 變動）────────────────
def filter_anomalies(df: pd.DataFrame) -> pd.DataFrame:
    """移除明顯的數據錯誤：極端成交量 & 極端價格跳動"""
    if df.empty:
        return df
    vol_ma = df["Volume"].rolling(20, min_periods=5).median()
    price_chg = df["Close"].pct_change().abs()
    bad = (df["Volume"] > vol_ma * 10) | (price_chg > 0.30)
    return df[~bad].copy()

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
        df = df.dropna(subset=["Close"])
        df = filter_anomalies(df)   # ← 異常值過濾
        return df
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

    # RSI — Wilder 平滑法（alpha=1/14），比 SMA 更標準
    delta       = df["Close"].diff()
    gain        = delta.clip(lower=0).ewm(alpha=1/14, adjust=False).mean()
    loss        = (-delta.clip(upper=0)).ewm(alpha=1/14, adjust=False).mean()
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
            # 流動性過濾：日均成交額 > 3000 萬港元（≈ 384 萬 USD）
            {"left": "average_volume_30d_calc",      "operation": "greater", "right": 3_000_000 / 7.8},
        ],
        "markets": ["hongkong"],
        "symbols": {"query": {"types": ["stock"]}, "tickers": []},
        "columns": ["name", "description", "close", "market_cap_basic",
                    "earnings_per_share_basic_ttm", "average_volume_30d_calc"],
        "sort": {"sortBy": "market_cap_basic", "sortOrder": "desc"},
        "range": [0, 1000],   # 上限從 500 → 1000
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


# ── 訊號強度評分 ──────────────────────────────────────────────────
def signal_strength_score(df: pd.DataFrame, n_signals_hit: int) -> float:
    """
    綜合評分（0–100）：
      - 觸發條件數量   (0–40分)
      - 成交量倍數     (0–30分)
      - RSI 距離超賣區 (0–15分)
      - J 值距離超賣區 (0–15分)
    """
    if df.empty or len(df) < 2:
        return 0.0
    c      = df.iloc[-1]
    vol_ma = df["Volume"].rolling(20).mean().iloc[-1]

    # 條件數量分（每個訊號 10 分，最高 40）
    sig_score = min(n_signals_hit * 10, 40)

    # 成交量倍數分（1x=0, 3x=30，線性）
    vol_ratio = float(c["Volume"]) / float(vol_ma) if vol_ma > 0 else 1.0
    vol_score = min((vol_ratio - 1) / 2 * 30, 30)

    # RSI 超賣距離（RSI=30→15分, RSI=60→0分）
    rsi_score = max(0, (30 - float(c["RSI"])) / 30 * 15) if float(c["RSI"]) <= 50 else 0

    # J 值超賣距離（J=10→15分, J=50→0分）
    j_score = max(0, (10 - float(c["J"])) / 10 * 15) if float(c["J"]) <= 50 else 0

    return round(sig_score + vol_score + rsi_score + j_score, 1)



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

# ── 向量化信號預計算（比逐行快 8-10x）────────────────────────────
def _swing_lows(close_ser: pd.Series, window: int = 5) -> pd.Series:
    """向量化識別 swing low：左右各 window 根都比當前高"""
    lo = close_ser.copy()
    result = pd.Series(False, index=close_ser.index)
    for k in range(1, window + 1):
        result = result | (lo < lo.shift(k)) | (lo < lo.shift(-k))
    # 反轉：True = 當前是局部低點（左右都比它高）
    left_min  = close_ser.rolling(window, min_periods=window).min().shift(1)
    right_min = close_ser[::-1].rolling(window, min_periods=window).min().shift(1)[::-1]
    return (close_ser <= left_min) & (close_ser <= right_min)


def precompute_signals(df: pd.DataFrame,
                       hsi_bullish: bool = True) -> dict:
    """
    一次性向量化計算所有買賣訊號。
    hsi_bullish: 恆指是否處於多頭（MA20 > MA60）；
                 False 時過濾均值回歸買入訊號（b4/b7/b8）。
    """
    c      = df
    p      = df.shift(1)
    vol_ma = df["Volume"].rolling(20).mean()

    # ── 買入訊號 ──────────────────────────────────────────────────

    # b1 突破阻力 + 放量
    resist = df["High"].shift(1).rolling(20).max()
    b1 = (c["Close"] > resist) & (c["Volume"] > vol_ma * 1.5)

    # b2 MA5 金叉 MA20
    b2 = (c["MA5"] > c["MA20"]) & (p["MA5"] <= p["MA20"])

    # b3 真正雙底背離：需要兩個 swing low，第二低點 DIF 未創新低
    swing_lo  = _swing_lows(df["Close"], window=5)
    prev_sl_close = df["Close"].where(swing_lo).ffill().shift(1)   # 上一個 swing low 收盤
    prev_sl_dif   = df["DIF"].where(swing_lo).ffill().shift(1)     # 上一個 swing low DIF
    b3 = (
        swing_lo &                                   # 當前本身是 swing low
        (c["Close"] < prev_sl_close) &               # 價格創新低
        (c["DIF"]   > prev_sl_dif)  &                # DIF 未創新低（背離）
        (c["RSI"]   < 40)                            # 處於弱勢區
    )

    # b4 KDJ 超賣 J<10（熊市過濾）
    b4_raw = c["J"] < 10
    b4 = b4_raw if hsi_bullish else pd.Series(False, index=df.index)

    # b5 缺口低開 + 確認：需要成交量放大或當日收陽
    gap_down   = c["Open"] < p["Low"]
    vol_up     = c["Volume"] > vol_ma * 1.2
    close_up   = c["Close"] > c["Open"]              # 當日收陽
    b5 = gap_down & (vol_up | close_up)              # 增加確認，避免接刀

    # b6 底部突破 MA20 放量
    close_ma10  = df["Close"].rolling(10).mean().shift(1)
    ma60_ma10   = df["MA60"].rolling(10).mean().shift(1)
    was_below   = close_ma10 < ma60_ma10
    b6 = was_below & (c["Close"] > c["MA20"]) & (p["Close"] <= p["MA20"]) & (c["Volume"] > vol_ma * 1.3)

    # b7 布林下軌（熊市過濾）
    b7_raw = c["Close"] < c["BB_lower"]
    b7 = b7_raw if hsi_bullish else pd.Series(False, index=df.index)

    # b8 RSI 超賣（熊市過濾）
    b8_raw = c["RSI"] < 30
    b8 = b8_raw if hsi_bullish else pd.Series(False, index=df.index)

    # b9 MACD 金叉
    b9 = (c["DIF"] > c["DEA"]) & (p["DIF"] <= p["DEA"])

    # ── 賣出訊號 ──────────────────────────────────────────────────
    s1 = c["Open"] > p["High"]

    close_ma10u = df["Close"].rolling(10).mean().shift(1)
    ma60_ma10u  = df["MA60"].rolling(10).mean().shift(1)
    was_above   = close_ma10u > ma60_ma10u
    s2 = was_above & (c["Close"] < c["MA20"]) & (p["Close"] >= p["MA20"]) & (c["Volume"] > vol_ma * 1.3)

    s3 = c["Close"] > c["BB_upper"]

    close_max10 = df["Close"].rolling(10).max()
    s4 = (c["Close"] >= close_max10 * 0.995) & (c["Volume"] < vol_ma * 0.6)

    pct_chg = c["Close"].pct_change() * 100
    s5 = (pct_chg < -2) & (c["Volume"] > vol_ma * 1.5)

    s6 = (c["MA5"] < c["MA20"]) & (p["MA5"] >= p["MA20"])
    s7 = c["RSI"] > 70
    s8 = (c["DIF"] < c["DEA"]) & (p["DIF"] >= p["DEA"])

    # 前61行數據不足，強制設 False
    mask = pd.Series(False, index=df.index)
    mask.iloc[:61] = True



    sigs = {}
    for name, s in [("b1",b1),("b2",b2),("b3",b3),("b4",b4),("b5",b5),
                    ("b6",b6),("b7",b7),("b8",b8),("b9",b9),
                    ("s1",s1),("s2",s2),("s3",s3),("s4",s4),("s5",s5),
                    ("s6",s6),("s7",s7),("s8",s8)]:
        sigs[name] = s.fillna(False) & ~mask
    return sigs


def run_backtest(
    df: pd.DataFrame,
    buy_sigs: tuple, sell_sigs: tuple,
    trade_size: float = 100_000,
    commission: float = 0.002,        # 港股實際單向成本（含印花稅、手續費）
    stop_loss_pct: float = None,
    take_profit_pct: float = None,
    max_hold_days: int = None,
    _precomputed: dict = None,
) -> tuple:
    """
    訊號分析模式（Signal Analyzer）：
    - 訊號在第 i 日收盤確認，次日（i+1）以收盤價成交（消除前視偏差）
    - 每筆固定 trade_size，互相獨立
    - equity_df 記錄累計已實現 PnL 走勢
    """
    sigs = _precomputed if _precomputed is not None else precompute_signals(df)

    b_names = ["b1","b2","b3","b4","b5","b6","b7","b8","b9"]
    s_names = ["s1","s2","s3","s4","s5","s6","s7","s8"]
    buy_active  = [b_names[k] for k, v in enumerate(buy_sigs)  if v]
    sell_active = [s_names[k] for k, v in enumerate(sell_sigs) if v]

    if buy_active:
        buy_signal = sigs[buy_active[0]].copy()
        for nm in buy_active[1:]:
            buy_signal &= sigs[nm]
    else:
        buy_signal = pd.Series(False, index=df.index)

    if sell_active:
        sell_signal = sigs[sell_active[0]].copy()
        for nm in sell_active[1:]:
            sell_signal &= sigs[nm]
    else:
        sell_signal = pd.Series(False, index=df.index)

    buy_arr   = buy_signal.values
    sell_arr  = sell_signal.values
    close_arr = df["Close"].values.astype(float)
    idx_arr   = df.index
    n         = len(df)

    positions       = []   # 每筆獨立倉位
    trades          = []
    cum_pnl_pct     = 0.0
    equity          = []

    for i in range(61, n):
        close = close_arr[i]
        date  = idx_arr[i]

        # ── equity 追蹤 ───────────────────────────────────────────
        equity.append({"date": date, "equity": cum_pnl_pct})

        # ── 買入：訊號在第 i 日確認，次日 (i+1) 成交 ─────────────
        # （前視偏差修正：唔用當日收盤，用次日收盤模擬次日開盤成交）
        if buy_arr[i] and i + 1 < n:
            entry_px   = close_arr[i + 1]          # 次日收盤
            entry_date = idx_arr[i + 1]
            entry_idx  = i + 1
            shares = int(trade_size / (entry_px * (1 + commission)))
            if shares > 0:
                positions.append({
                    "shares":     shares,
                    "entry_px":   entry_px,
                    "entry_date": entry_date,
                    "entry_idx":  entry_idx,
                    "cost":       shares * entry_px * (1 + commission),
                })

        # ── 賣出：逐倉位獨立檢查（同樣用當日收盤平倉）──────────────
        keep = []
        for pos in positions:
            days_held = i - pos["entry_idx"]
            ep        = pos["entry_px"]
            reason    = None
            if stop_loss_pct  and close <= ep * (1 - stop_loss_pct / 100):
                reason = f"止損 -{stop_loss_pct:.0f}%"
            elif take_profit_pct and close >= ep * (1 + take_profit_pct / 100):
                reason = f"止盈 +{take_profit_pct:.0f}%"
            elif max_hold_days and days_held >= max_hold_days:
                reason = f"超時 {max_hold_days}日"
            elif sell_arr[i]:
                reason = "策略訊號"

            if reason:
                proceeds  = pos["shares"] * close * (1 - commission)
                pnl_pct   = (close - ep) / ep * 100
                pnl_hkd   = proceeds - pos["cost"]
                cum_pnl_pct += pnl_pct          # 累計已實現
                trades.append({
                    "買入日期": pos["entry_date"].strftime("%Y-%m-%d"),
                    "賣出日期": date.strftime("%Y-%m-%d"),
                    "買入價": round(ep, 3), "賣出價": round(close, 3),
                    "回報%": round(pnl_pct, 2), "盈虧(HKD)": round(pnl_hkd, 0),
                    "持倉天數": days_held, "賣出原因": reason,
                    "_buy_date": pos["entry_date"], "_sell_date": date,
                    "_win": pnl_pct > 0,
                })
            else:
                keep.append(pos)
        positions = keep

    # ── 期末持倉強制平倉 ──────────────────────────────────────────
    for pos in positions:
        last_close = close_arr[-1]
        proceeds   = pos["shares"] * last_close * (1 - commission)
        pnl_pct    = (last_close - pos["entry_px"]) / pos["entry_px"] * 100
        pnl_hkd    = proceeds - pos["cost"]
        trades.append({
            "買入日期": pos["entry_date"].strftime("%Y-%m-%d"),
            "賣出日期": idx_arr[-1].strftime("%Y-%m-%d") + "（持倉中）",
            "買入價": round(pos["entry_px"], 3), "賣出價": round(last_close, 3),
            "回報%": round(pnl_pct, 2), "盈虧(HKD)": round(pnl_hkd, 0),
            "持倉天數": len(df) - 1 - pos["entry_idx"], "賣出原因": "期末持倉",
            "_buy_date": pos["entry_date"], "_sell_date": idx_arr[-1],
            "_win": pnl_pct > 0,
        })

    # equity_df 記錄「累計已實現回報%」走勢，供畫曲線用
    equity_df = pd.DataFrame(equity).set_index("date") if equity else pd.DataFrame()
    # 重命名 equity 欄位為 equity（保持下游兼容）
    if not equity_df.empty:
        # 轉成累計已實現PnL的簡化版本：用 trade_size 代入算金額
        realized_series = []
        running = trade_size  # 模擬「每筆都係 trade_size」的累計資產
        for t in trades:
            running += t["盈虧(HKD)"]
        # 重新建立日度equity用累計PnL%走勢
        cum = 0.0
        trade_by_sell = {}
        for t in trades:
            sd = t["賣出日期"].replace("（持倉中）", "")
            trade_by_sell.setdefault(sd, []).append(t["回報%"])
        eq2 = []
        for row in equity:
            d_str = row["date"].strftime("%Y-%m-%d") if hasattr(row["date"], "strftime") else str(row["date"])
            if d_str in trade_by_sell:
                for r in trade_by_sell[d_str]:
                    cum += r
            eq2.append({"date": row["date"], "equity": trade_size * (1 + cum / 100)})
        equity_df = pd.DataFrame(eq2).set_index("date")

    return trades, equity_df, trade_size






def calc_bt_metrics(trades, equity_df, trade_size=100_000):
    """
    訊號分析模式績效計算。
    核心指標：平均每筆回報%、勝率、Profit Factor。
    不再追蹤「總資產」，盈虧(HKD)基於固定 trade_size。
    """
    if not trades:
        return {}
    closed = [t for t in trades if "（持倉中）" not in t["賣出日期"]]
    total  = len(closed)
    if total == 0:
        return {}
    wins   = sum(1 for t in closed if t["_win"])
    losses = total - wins
    win_rate = wins / total * 100

    avg_ret  = sum(t["回報%"] for t in closed) / total
    avg_win  = sum(t["回報%"] for t in closed if t["_win"])  / wins   if wins   else 0.0
    avg_loss = sum(t["回報%"] for t in closed if not t["_win"]) / losses if losses else 0.0
    avg_days = sum(t["持倉天數"] for t in closed) / total
    best_trade  = max(t["回報%"] for t in closed)
    worst_trade = min(t["回報%"] for t in closed)

    # ── Profit Factor（用回報%算，比HKD更準因每筆金額相同）─────
    gross_win  = sum(t["回報%"] for t in closed if t["_win"])
    gross_loss = abs(sum(t["回報%"] for t in closed if not t["_win"]))
    profit_factor = round(gross_win / gross_loss, 2) if gross_loss > 0 else (
        float("inf") if gross_win > 0 else 0.0)

    # ── 最大連輸 ──────────────────────────────────────────────────
    max_consec_loss = cur_consec = 0
    for t in closed:
        cur_consec = cur_consec + 1 if not t["_win"] else 0
        max_consec_loss = max(max_consec_loss, cur_consec)

    # ── 最大回撤（基於累計回報%走勢）────────────────────────────
    max_dd = 0.0
    if not equity_df.empty:
        eq = equity_df["equity"]
        roll_max = eq.cummax()
        dd = (eq - roll_max) / roll_max * 100
        max_dd = float(dd.min()) if not eq.empty and roll_max.max() > 0 else 0.0

    total_ret_equiv = avg_ret * total

    return {
        "平均每筆回報%":  round(avg_ret, 2),
        "交易次數":       total,
        "勝率%":          round(win_rate, 1),
        "平均盈利%":      round(avg_win, 2),
        "平均虧損%":      round(avg_loss, 2),
        "最佳一筆%":      round(best_trade, 2),
        "最差一筆%":      round(worst_trade, 2),
        "平均持倉天數":   round(avg_days, 1),
        "Profit Factor":  profit_factor,
        "最大連輸":       max_consec_loss,
        "最大回撤%":      round(max_dd, 2),
        "累計回報%":      round(total_ret_equiv, 2),
        "總回報%":        round(avg_ret, 2),
        "最終資金":       round(trade_size * (1 + avg_ret / 100), 0),
    }




def show_backtest_chart(df: pd.DataFrame, trades: list):
    """K線圖 + 買賣標記"""
    fig = make_subplots(
        rows=3, cols=1, shared_xaxes=True,
        vertical_spacing=0.03,
        row_heights=[0.55, 0.2, 0.25],
    )
    fig.add_trace(go.Candlestick(
        x=df.index, open=df["Open"], high=df["High"],
        low=df["Low"],  close=df["Close"],
        increasing_line_color="#26a69a", decreasing_line_color="#ef5350",
        name="K線",
    ), row=1, col=1)
    for ma, color in [("MA20", "purple"), ("MA60", "orange")]:
        fig.add_trace(go.Scatter(x=df.index, y=df[ma], name=ma,
                                 line=dict(width=1, color=color)), row=1, col=1)
    fig.add_trace(go.Scatter(
        x=df.index, y=df["BB_upper"], name="BB上",
        line=dict(width=1, color="rgba(100,180,255,0.5)", dash="dot")), row=1, col=1)
    fig.add_trace(go.Scatter(
        x=df.index, y=df["BB_lower"], name="BB下",
        line=dict(width=1, color="rgba(100,180,255,0.5)", dash="dot"),
        fill="tonexty", fillcolor="rgba(100,180,255,0.05)"), row=1, col=1)

    # 買賣點標記
    for t in trades:
        bd = t["_buy_date"]
        sd = t["_sell_date"]
        win = t["_win"]
        if bd in df.index:
            fig.add_trace(go.Scatter(
                x=[bd], y=[float(df.loc[bd, "Low"]) * 0.985],
                mode="markers+text",
                marker=dict(symbol="triangle-up", size=12, color="#00e676"),
                text=["買"], textposition="bottom center",
                textfont=dict(size=9, color="#00e676"),
                showlegend=False,
            ), row=1, col=1)
        if sd in df.index:
            marker_color = "#26a69a" if win else "#ef5350"
            fig.add_trace(go.Scatter(
                x=[sd], y=[float(df.loc[sd, "High"]) * 1.015],
                mode="markers+text",
                marker=dict(symbol="triangle-down", size=12, color=marker_color),
                text=["賣"], textposition="top center",
                textfont=dict(size=9, color=marker_color),
                showlegend=False,
            ), row=1, col=1)

    # 成交量
    v_colors = ["#26a69a" if c >= o else "#ef5350"
                for c, o in zip(df["Close"], df["Open"])]
    fig.add_trace(go.Bar(x=df.index, y=df["Volume"],
                         marker_color=v_colors, name="成交量"), row=2, col=1)

    # RSI
    fig.add_trace(go.Scatter(
        x=df.index, y=df["RSI"],
        line=dict(color="#ff7043", width=1.5), name="RSI"), row=3, col=1)
    for lvl, clr in [(30, "rgba(38,166,154,0.4)"), (70, "rgba(239,83,80,0.4)")]:
        fig.add_hline(y=lvl, line_dash="dot", line_color=clr, row=3, col=1)

    fig.update_layout(
        height=680, showlegend=False,
        xaxis_rangeslider_visible=False,
        margin=dict(t=10, b=10),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
    )
    st.plotly_chart(fig, use_container_width=True)


def show_equity_curve(equity_df: pd.DataFrame, initial_capital: float,
                      benchmark_df: pd.DataFrame = None):
    """資金曲線圖（可疊加恆指基準）"""
    fig = go.Figure()
    eq_norm = equity_df["equity"] / initial_capital * 100 - 100
    fig.add_trace(go.Scatter(
        x=equity_df.index, y=eq_norm,
        name="策略回報%", fill="tozeroy",
        line=dict(color="#26a69a", width=2),
        fillcolor="rgba(38,166,154,0.15)",
    ))
    if benchmark_df is not None and not benchmark_df.empty:
        common_start = equity_df.index[0]
        bm = benchmark_df["Close"].loc[benchmark_df.index >= common_start]
        if not bm.empty:
            bm_norm = bm / bm.iloc[0] * 100 - 100
            fig.add_trace(go.Scatter(
                x=bm_norm.index, y=bm_norm,
                name="恆生指數%",
                line=dict(color="#f9a825", width=1.5, dash="dot"),
            ))
    fig.add_hline(y=0, line_dash="dash", line_color="rgba(255,255,255,0.3)")
    fig.update_layout(
        height=300,
        margin=dict(t=10, b=10),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
        yaxis_ticksuffix="%",
    )
    st.plotly_chart(fig, use_container_width=True)


def show_monthly_heatmap(equity_df: pd.DataFrame):
    """月度回報熱力圖"""
    if equity_df.empty or len(equity_df) < 20:
        st.info("數據不足，無法生成月度熱力圖")
        return

    month_names = ["Jan","Feb","Mar","Apr","May","Jun",
                   "Jul","Aug","Sep","Oct","Nov","Dec"]
    monthly     = equity_df["equity"].resample("ME").last()
    monthly_ret = monthly.pct_change().dropna() * 100

    years = sorted(monthly_ret.index.year.unique())
    z, text_vals = [], []

    for year in years:
        row, trow = [], []
        for m in range(1, 13):
            mask = (monthly_ret.index.year == year) & (monthly_ret.index.month == m)
            if mask.any():
                v = float(monthly_ret[mask].iloc[0])
                row.append(v)
                trow.append(f"{v:+.1f}%")
            else:
                row.append(None)
                trow.append("")
        z.append(row)
        text_vals.append(trow)

    fig = go.Figure(go.Heatmap(
        z=z,
        x=month_names,
        y=[str(yr) for yr in years],
        text=text_vals,
        texttemplate="%{text}",
        textfont=dict(size=11),
        colorscale=[
            [0.0, "#b71c1c"], [0.35, "#ef5350"],
            [0.5, "#1e1e2e"],
            [0.65, "#26a69a"], [1.0, "#004d40"],
        ],
        zmid=0,
        showscale=True,
        colorbar=dict(ticksuffix="%", len=0.8),
    ))
    fig.update_layout(
        height=max(200, len(years) * 52 + 90),
        margin=dict(t=10, b=10, l=60, r=10),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(side="top"),
    )
    st.plotly_chart(fig, use_container_width=True)


def run_grid_search(
    df: pd.DataFrame,
    buy_sigs: tuple, sell_sigs: tuple,
    trade_size: float,
    commission: float,
    sort_metric: str = "平均每筆%",
):
    """網格搜索最佳止損 / 止盈 / 最長持倉組合"""
    sl_grid  = [0, 5, 10, 15, 20]
    tp_grid  = [0, 15, 30, 50]
    md_grid  = [0, 20, 40, 60]

    combos   = [(sl, tp, md) for sl in sl_grid for tp in tp_grid for md in md_grid]
    total_c  = len(combos)
    results  = []

    pre_s = precompute_signals(df)

    pbar = st.progress(0, text="網格搜索中...")
    for ci, (sl, tp, md) in enumerate(combos):
        pbar.progress((ci + 1) / total_c, text=f"網格搜索 {ci+1}/{total_c}...")
        t, eq, _ = run_backtest(
            df, buy_sigs, sell_sigs,
            trade_size=trade_size,
            commission=commission,
            stop_loss_pct=sl  if sl  > 0 else None,
            take_profit_pct=tp if tp > 0 else None,
            max_hold_days=md   if md  > 0 else None,
            _precomputed=pre_s,
        )
        m = calc_bt_metrics(t, eq, trade_size)
        if m and m["交易次數"] >= 2:
            results.append({
                "止損%":      f"{sl}%" if sl  > 0 else "不限",
                "止盈%":      f"{tp}%" if tp  > 0 else "不限",
                "最長持倉":   f"{md}日" if md > 0 else "不限",
                "平均每筆%":  m["平均每筆回報%"],
                "勝率%":      m["勝率%"],
                "Profit F":   m["Profit Factor"],
                "最大回撤%":  m["最大回撤%"],
                "交易次數":   m["交易次數"],
                "最大連輸":   m["最大連輸"],
            })
    pbar.empty()

    if not results:
        return pd.DataFrame()

    df_gs = pd.DataFrame(results)
    asc   = (sort_metric == "最大回撤%")
    return df_gs.sort_values(sort_metric, ascending=asc).reset_index(drop=True)


def _render_single_bt_result(ticker, metrics, equity_df, df_bt,
                              trades, trade_size, df_hsi_bt):
    """單股回測結果渲染（訊號分析模式）"""
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

    # ── 第一行：核心指標 ─────────────────────────────────────────
    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("⭐ 平均每筆回報", f"{avg_ret:+.2f}%")
    m2.metric("交易次數",        f"{metrics['交易次數']} 次")
    m3.metric("勝率",            f"{metrics['勝率%']:.1f}%")
    m4.metric("最佳一筆",        f"{metrics['最佳一筆%']:+.2f}%")
    m5.metric("最差一筆",        f"{metrics['最差一筆%']:+.2f}%")

    # ── 第二行：風險指標（已移除 Sharpe/Sortino/Calmar）─────────
    a1, a2, a3, a4 = st.columns(4)
    pf_val = metrics["Profit Factor"]
    a1.metric("Profit Factor",  "∞" if pf_val == float("inf") else f"{pf_val:.2f}")
    a2.metric("最大連輸",       f"{metrics['最大連輸']} 次")
    a3.metric("最大回撤",       f"{metrics['最大回撤%']:.2f}%")
    a4.metric("平均持倉天數",   f"{metrics['平均持倉天數']:.0f} 天")

    # ── 第三行：盈虧對比 ─────────────────────────────────────────
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



# ══════════════════════════════════════════════════════════════════
# ② Sidebar（所有函數已定義，安全呼叫）
# ══════════════════════════════════════════════════════════════════
with st.sidebar:
    st.markdown("### ⚙️ 數據控制台")
    n_stocks = len(st.session_state.get("stocks", []))
    st.caption(f"股票清單：{n_stocks or '讀取中'} 隻")

    if st.button("🔄 更新清單 (TradingView)"):
        with st.spinner("篩選中：主要上市 ｜ 市值>100億 ｜ EPS>0 ｜ 日均成交額>3000萬..."):
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
            st.session_state["stock_cache"]    = all_cache
            st.session_state["cache_time"]     = datetime.now().strftime("%H:%M")
            st.session_state["cache_datetime"] = datetime.now()
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
st.title("🏹 港股狙擊手 V10.5")
tabs = st.tabs(["🌍 指數", "🏆 跑贏大市", "🟢 買入掃描", "🔴 賣出掃描", "🔍 分析", "📊 回測"])

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

    top_n_buy = st.number_input("只顯示評分最高前 N 名（0 = 全部）", value=10, min_value=0, step=5, key="top_n_buy")

    if st.button("🟢 開始掃描買點"):
        if not any([b1, b2, b3, b4, b5, b6, b7, b8, b9]):
            st.warning("⚠️ 請至少勾選一個策略")
        else:
            # 恆指趨勢判斷（供 b4/b7/b8 熊市過濾用）
            df_hsi_scan = get_stock_data("^HSI", period="3mo")
            hsi_bull = True
            if not df_hsi_scan.empty:
                df_hsi_scan = calculate_indicators(df_hsi_scan)
                hsi_bull = bool(df_hsi_scan["MA20"].iloc[-1] > df_hsi_scan["MA60"].iloc[-1])

            buy_tuple = (b1,b2,b3,b4,b5,b6,b7,b8,b9)
            results, hits_dfs = [], {}
            pbar   = st.progress(0)
            status = st.empty()
            for i, s in enumerate(STOCKS):
                pbar.progress((i + 1) / len(STOCKS))
                status.text(f"正在分析 {s}...")
                df = get_cached(s)
                if df.empty or len(df) < 62:
                    continue
                try:
                    pre = precompute_signals(df, hsi_bullish=hsi_bull)
                    b_names = ["b1","b2","b3","b4","b5","b6","b7","b8","b9"]
                    n_hit = 0
                    all_hit = True
                    for k, flag in enumerate(buy_tuple):
                        if flag:
                            sig_val = bool(pre[b_names[k]].iloc[-1])
                            if sig_val:
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
                        "代碼":   s,
                        "評分":   score,
                        "現價":   round(float(c["Close"]), 2),
                        "漲跌%":  round(pct, 2),
                        "RSI":    round(float(c["RSI"]), 1),
                        "J值":    round(float(c["J"]), 1),
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
                hsi_label = "🟢 多頭" if hsi_bull else "🔴 空頭（b4/b7/b8 已過濾）"
                st.success(f"✅ 發現 {len(results)} 個買入標的　｜　恆指趨勢：{hsi_label}")
                show_scan_metrics(results)
                st.divider()
                df_show = pd.DataFrame(results)
                df_show["現價"]  = df_show["現價"].map(lambda x: f"{x:.2f}")
                df_show["漲跌%"] = df_show["漲跌%"].map(lambda x: f"{'+' if x>=0 else ''}{x:.2f}%")
                df_show["J值"]   = df_show["J值"].map(lambda x: f"{x:.1f}")
                st.dataframe(
                    df_show.style.background_gradient(subset=["評分"], cmap="Greens"),
                    use_container_width=True,
                )
                for r in results:
                    s = r["代碼"]
                    st.write(f"### 🎯 {s}　評分 {r['評分']}")
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
        | 🔥 **雙重超買出貨** | ⑫ 布林上軌 ＋ ⑯ RSI超買 | 頂部回調，短線 | ⭐⭐⭐⭐ |
        | 💀 **趨勢反轉確認** | ⑪ 頭部破位 ＋ ⑮ 死叉 | 確認下跌趨勢，中線 | ⭐⭐⭐⭐⭐ |
        | ⚡ **恐慌急跌跟進** | ⑭ 放量急跌 ＋ ⑮ 死叉 | 短線動能做空 | ⭐⭐⭐ |
        | 🌊 **缺口回補做空** | ⑩ 缺口高開 ＋ ⑯ RSI超買 | 高開後回補，日內/短線 | ⭐⭐⭐ |
        | 🏗️ **量價背離出逃** | ⑬ 上漲縮量 ＋ ⑰ MACD死叉 | 頂部出貨訊號 | ⭐⭐⭐⭐ |

        **⚠️ 不建議組合：**
        - ⑩ 缺口高開 ⑭ 放量急跌 → 兩個條件同時觸發概率極低
        - ⑯ RSI超買 單獨在強勢行情使用 → 強趨勢中 RSI 可長期高位，需配合形態
        """)

    st.caption("勾選一個或多個策略（多個條件需同時符合）")
    col_c, col_d = st.columns(2)
    s1 = col_c.checkbox("⑩ 缺口高開回補做空",           help="今日開盤高於昨日最高（跳空高開），短期大概率回補")
    s2 = col_c.checkbox("⑪ 頭部形態跌破 MA20（放量）",  help="近期均線高位，今日放量跌破 MA20，頭部確認")
    s3 = col_c.checkbox("⑫ 布林帶上軌賣出",             help="收盤突破布林帶上軌，均值回歸賣點")
    s4 = col_c.checkbox("⑬ 上漲縮量（警惕頂部）",       help="價格創10日新高，但成交量萎縮（量能不足，假突破）")
    s5 = col_d.checkbox("⑭ 放量急跌（跟進做空）",        help="收盤跌幅 > 2%，且成交量 > 20日均量 1.5 倍")
    s6 = col_d.checkbox("⑮ MA5 死叉 MA20",             help="5日均線今日下穿20日均線（趨勢轉弱）")
    s7 = col_d.checkbox("⑯ RSI 超買（RSI > 70）",      help="RSI 高於 70，超買區間。比 KDJ 穩定，回調概率高")
    s8 = col_d.checkbox("⑰ MACD 死叉（DIF下穿DEA）",   help="DIF 今日下穿 DEA，動能由強轉弱，中線出場訊號")

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
def evaluate_signals(df: pd.DataFrame) -> dict:
    """
    對單支股票評估所有買入/賣出策略，
    回傳 {"buy": [(name, desc, True/False), ...], "sell": [...]}
    """
    if df.empty or len(df) < 60:
        return {"buy": [], "sell": []}

    c, p    = df.iloc[-1], df.iloc[-2]
    vol_avg = df["Volume"].rolling(20).mean().iloc[-1]

    # ── 買入策略 ──────────────────────────────────────────────────
    resist    = df["High"].iloc[-21:-1].max()
    b1_hit    = bool(c["Close"] > resist) and bool(c["Volume"] > vol_avg * 1.5)

    b2_hit    = bool(c["MA5"] > c["MA20"]) and bool(p["MA5"] <= p["MA20"])

    pl        = df["Close"].iloc[-20:].min()
    dl        = df["DIF"].iloc[-20:].min()
    b3_hit    = bool(c["Close"] <= pl * 1.005) and bool(c["DIF"] > dl * 1.01)

    b4_hit    = bool(c["J"] < 10)

    b5_hit    = bool(c["Open"] < p["Low"])

    was_below = bool(df["Close"].iloc[-10:-1].mean() < df["MA60"].iloc[-10:-1].mean())
    b6_hit    = was_below and bool(c["Close"] > c["MA20"]) and bool(p["Close"] <= p["MA20"]) and bool(c["Volume"] > vol_avg * 1.3)

    b7_hit    = bool(c["Close"] < c["BB_lower"])

    b8_hit    = bool(c["RSI"] < 30)

    b9_hit    = bool(c["DIF"] > c["DEA"]) and bool(p["DIF"] <= p["DEA"])

    buy_signals = [
        ("① 突破阻力位 + 放量",    f"收盤 {c['Close']:.2f} {'>' if b1_hit else '<='} 前高 {resist:.2f}，量比 {c['Volume']/vol_avg:.1f}x",     b1_hit),
        ("② MA5 金叉 MA20",        f"MA5={c['MA5']:.2f}  MA20={c['MA20']:.2f}  昨MA5={p['MA5']:.2f}",                                          b2_hit),
        ("③ 底背離（MACD未新低）",  f"收盤={c['Close']:.2f}  20日低={pl:.2f}  DIF={c['DIF']:.4f}  DIF低={dl:.4f}",                              b3_hit),
        ("④ KDJ 超賣（J < 10）",   f"J值 = {c['J']:.1f}",                                                                                       b4_hit),
        ("⑤ 缺口低開",             f"今開 {c['Open']:.2f} {'<' if b5_hit else '>='} 昨低 {p['Low']:.2f}",                                       b5_hit),
        ("⑥ 底部形態突破 MA20",    f"均線低位={was_below}  站上MA20={'是' if bool(c['Close']>c['MA20']) else '否'}  量比={c['Volume']/vol_avg:.1f}x", b6_hit),
        ("⑦ 布林帶下軌",           f"收盤 {c['Close']:.2f}  BB下軌 {c['BB_lower']:.2f}",                                                         b7_hit),
        ("⑧ RSI 超賣（< 30）",     f"RSI = {c['RSI']:.1f}",                                                                                      b8_hit),
        ("⑨ MACD 金叉",            f"DIF={c['DIF']:.4f}  DEA={c['DEA']:.4f}  昨DIF={p['DIF']:.4f}",                                             b9_hit),
    ]

    # ── 賣出策略 ──────────────────────────────────────────────────
    s1_hit    = bool(c["Open"] > p["High"])

    was_above = bool(df["Close"].iloc[-10:-1].mean() > df["MA60"].iloc[-10:-1].mean())
    s2_hit    = was_above and bool(c["Close"] < c["MA20"]) and bool(p["Close"] >= p["MA20"]) and bool(c["Volume"] > vol_avg * 1.3)

    s3_hit    = bool(c["Close"] > c["BB_upper"])

    ph        = df["Close"].iloc[-10:].max()
    s4_hit    = bool(c["Close"] >= ph * 0.995) and bool(c["Volume"] < vol_avg * 0.6)

    pct_chg   = (c["Close"] - p["Close"]) / p["Close"] * 100
    s5_hit    = bool(pct_chg < -2) and bool(c["Volume"] > vol_avg * 1.5)

    s6_hit    = bool(c["MA5"] < c["MA20"]) and bool(p["MA5"] >= p["MA20"])

    s7_hit    = bool(c["RSI"] > 70)

    s8_hit    = bool(c["DIF"] < c["DEA"]) and bool(p["DIF"] >= p["DEA"])

    sell_signals = [
        ("⑩ 缺口高開",             f"今開 {c['Open']:.2f} {'>' if s1_hit else '<='} 昨高 {p['High']:.2f}",                                      s1_hit),
        ("⑪ 頭部形態跌破 MA20",    f"均線高位={was_above}  跌破MA20={'是' if bool(c['Close']<c['MA20']) else '否'}  量比={c['Volume']/vol_avg:.1f}x", s2_hit),
        ("⑫ 布林帶上軌",           f"收盤 {c['Close']:.2f}  BB上軌 {c['BB_upper']:.2f}",                                                         s3_hit),
        ("⑬ 上漲縮量",             f"近高={ph:.2f}  量比={c['Volume']/vol_avg:.1f}x（需<0.6x）",                                                  s4_hit),
        ("⑭ 放量急跌",             f"跌幅={pct_chg:.2f}%  量比={c['Volume']/vol_avg:.1f}x",                                                      s5_hit),
        ("⑮ MA5 死叉 MA20",        f"MA5={c['MA5']:.2f}  MA20={c['MA20']:.2f}  昨MA5={p['MA5']:.2f}",                                           s6_hit),
        ("⑯ RSI 超買（> 70）",     f"RSI = {c['RSI']:.1f}",                                                                                      s7_hit),
        ("⑰ MACD 死叉",            f"DIF={c['DIF']:.4f}  DEA={c['DEA']:.4f}  昨DIF={p['DIF']:.4f}",                                             s8_hit),
    ]

    return {"buy": buy_signals, "sell": sell_signals}


with tabs[4]:
    st.subheader("🔍 個股深度分析")

    col_left, col_right = st.columns([1, 3])
    with col_left:
        custom_ticker   = st.text_input("輸入股票代碼", value="0700.HK").upper()
        analysis_period = st.selectbox("週期", ["3mo", "6mo", "1y", "2y"], index=2, key="analysis_period")
        analyze_btn     = st.button("🔍 開始分析", type="primary")

    with col_right:
        if analyze_btn:
            with st.spinner(f"正在分析 {custom_ticker}..."):
                df_a = get_stock_data(custom_ticker, period=analysis_period)

            if df_a.empty:
                st.error(f"❌ 無法取得 {custom_ticker} 數據，請確認代碼正確。")
            else:
                df_a = calculate_indicators(df_a)
                c    = df_a.iloc[-1]
                p    = df_a.iloc[-2]

                # ── 頂部 Metrics ──────────────────────────────────
                pct_1d = (c["Close"] - p["Close"]) / p["Close"] * 100
                m1, m2, m3, m4, m5, m6 = st.columns(6)
                m1.metric("現價 (HKD)",  f"{c['Close']:.2f}",  f"{pct_1d:+.2f}%")
                m2.metric("MA20",        f"{c['MA20']:.2f}",   f"{((c['Close']-c['MA20'])/c['MA20']*100):+.1f}%")
                m3.metric("MA60",        f"{c['MA60']:.2f}",   f"{((c['Close']-c['MA60'])/c['MA60']*100):+.1f}%")
                m4.metric("RSI (14)",    f"{c['RSI']:.1f}",    "超賣" if c["RSI"] < 30 else ("超買" if c["RSI"] > 70 else "中性"))
                m5.metric("J 值",        f"{c['J']:.1f}",      "超賣" if c["J"] < 10 else ("超買" if c["J"] > 90 else "中性"))
                m6.metric("MACD 柱",     f"{c['MACD_Hist']:.4f}", "多頭" if c["MACD_Hist"] > 0 else "空頭")

                st.divider()

                # ── 策略訊號面板 ──────────────────────────────────
                signals = evaluate_signals(df_a)
                buy_hits  = [s for s in signals["buy"]  if s[2]]
                sell_hits = [s for s in signals["sell"] if s[2]]
                buy_miss  = [s for s in signals["buy"]  if not s[2]]
                sell_miss = [s for s in signals["sell"] if not s[2]]

                # 整體評分
                buy_score  = len(buy_hits)
                sell_score = len(sell_hits)
                total_b    = len(signals["buy"])
                total_s    = len(signals["sell"])

                if buy_score > sell_score and buy_score >= 2:
                    verdict_color = "#26a69a"
                    verdict       = f"🟢 偏多訊號（{buy_score} 買 / {sell_score} 賣）"
                elif sell_score > buy_score and sell_score >= 2:
                    verdict_color = "#ef5350"
                    verdict       = f"🔴 偏空訊號（{buy_score} 買 / {sell_score} 賣）"
                else:
                    verdict_color = "#f9a825"
                    verdict       = f"🟡 中性觀望（{buy_score} 買 / {sell_score} 賣）"

                st.markdown(
                    f"<div style='background:rgba(255,255,255,0.05);border-left:4px solid {verdict_color};"
                    f"padding:10px 16px;border-radius:6px;font-size:18px;font-weight:bold'>{verdict}</div>",
                    unsafe_allow_html=True,
                )
                st.caption("策略訊號以最新一根 K 線數據為準")
                st.divider()

                # ── 買入 / 賣出訊號兩欄並排 ──────────────────────
                col_buy, col_sell = st.columns(2)

                with col_buy:
                    st.markdown("### 🟢 買入策略")
                    if buy_hits:
                        for name, detail, _ in buy_hits:
                            with st.container():
                                st.success(f"✅ **{name}**")
                                st.caption(detail)
                    else:
                        st.info("目前沒有觸發任何買入策略")

                    if buy_miss:
                        with st.expander(f"未觸發的買入策略（{len(buy_miss)} 個）"):
                            for name, detail, _ in buy_miss:
                                st.markdown(f"⬜ **{name}**")
                                st.caption(detail)

                with col_sell:
                    st.markdown("### 🔴 賣出策略")
                    if sell_hits:
                        for name, detail, _ in sell_hits:
                            with st.container():
                                st.error(f"🚨 **{name}**")
                                st.caption(detail)
                    else:
                        st.info("目前沒有觸發任何賣出策略")

                    if sell_miss:
                        with st.expander(f"未觸發的賣出策略（{len(sell_miss)} 個）"):
                            for name, detail, _ in sell_miss:
                                st.markdown(f"⬜ **{name}**")
                                st.caption(detail)

                st.divider()

                # ── K 線圖 ────────────────────────────────────────
                st.markdown(f"### 📈 {custom_ticker} 技術圖表")
                show_chart(custom_ticker, df_a)

# ── TAB 5：回測 ───────────────────────────────────────────────────
with tabs[5]:
    st.subheader("📊 策略回測系統 V10.5")

    # ── 模式切換 ─────────────────────────────────────────────────
    bt_mode = st.radio(
        "回測模式",
        ["🔍 單股回測", "🚀 全倉掃描回測（所有股票）"],
        horizontal=True, key="bt_mode",
    )

    st.divider()

    # ── 共用：策略選擇 ─────────────────────────────────────────
    st.markdown("#### 🟢 買入策略")
    bc1, bc2 = st.columns(2)
    bb1 = bc1.checkbox("① 突破阻力位 + 放量",    key="bb1", help="收盤>前20日高點，成交量>均量1.5倍")
    bb2 = bc1.checkbox("② MA5 金叉 MA20",         key="bb2")
    bb3 = bc1.checkbox("③ 底背離（MACD未新低）",  key="bb3")
    bb4 = bc1.checkbox("④ KDJ 超賣（J < 10）",   key="bb4")
    bb5 = bc1.checkbox("⑤ 缺口低開回補",          key="bb5")
    bb6 = bc2.checkbox("⑥ 底部形態突破 MA20",     key="bb6")
    bb7 = bc2.checkbox("⑦ 布林帶下軌買入",        key="bb7")
    bb8 = bc2.checkbox("⑧ RSI 超賣（< 30）",      key="bb8")
    bb9 = bc2.checkbox("⑨ MACD 金叉",             key="bb9")

    st.markdown("#### 🔴 賣出策略")
    st.caption("⚠️ 若不勾選任何賣出策略，只靠止損 / 止盈 / 最長持倉天數出場")
    sc1, sc2 = st.columns(2)
    bs1 = sc1.checkbox("⑩ 缺口高開做空",          key="bs1")
    bs2 = sc1.checkbox("⑪ 頭部跌破 MA20（放量）", key="bs2")
    bs3 = sc1.checkbox("⑫ 布林帶上軌賣出",        key="bs3")
    bs4 = sc1.checkbox("⑬ 上漲縮量警惕頂部",      key="bs4")
    bs5 = sc2.checkbox("⑭ 放量急跌跟進做空",      key="bs5")
    bs6 = sc2.checkbox("⑮ MA5 死叉 MA20",          key="bs6")
    bs7 = sc2.checkbox("⑯ RSI 超買（> 70）",       key="bs7")
    bs8 = sc2.checkbox("⑰ MACD 死叉",             key="bs8")

    buy_sigs  = (bb1,bb2,bb3,bb4,bb5,bb6,bb7,bb8,bb9)
    sell_sigs = (bs1,bs2,bs3,bs4,bs5,bs6,bs7,bs8)

    st.divider()

    # ── 共用：參數 ────────────────────────────────────────────
    with st.expander("⚙️ 回測參數", expanded=True):
        p_col1, p_col2 = st.columns(2)
        with p_col1:
            bt_period     = st.selectbox("回測週期", ["1y", "2y", "5y"], index=1, key="bt_period")
            bt_capital    = st.number_input("每筆交易金額 (HKD)", value=100_000, step=10_000,
                                             min_value=10_000, key="bt_capital",
                                             help="每次買入訊號觸發時的固定投入金額，各筆互相獨立")
            bt_commission = st.slider("佣金率 (%, 港股建議 0.20)", 0.0, 0.5, 0.20, 0.05, key="bt_commission") / 100
        with p_col2:
            bt_sl      = st.number_input("止損 % (0=不啟用)",       value=0.0, step=1.0,
                                          min_value=0.0, max_value=50.0,  key="bt_sl")
            bt_tp      = st.number_input("止盈 % (0=不啟用)",       value=0.0, step=5.0,
                                          min_value=0.0, max_value=200.0, key="bt_tp")
            bt_maxdays = st.number_input("最長持倉天數 (0=不限)", value=0, step=5,
                                          min_value=0, key="bt_maxdays")
        st.caption("💡 有買入訊號 + 有現金 → 自動全倉買入；有賣出訊號 → 逐筆平倉。無倉位數量限制。")

        # 只在單股模式顯示股票輸入
        if bt_mode == "🔍 單股回測":
            bt_ticker = st.text_input("股票代碼", value="0700.HK", key="bt_ticker").upper()
        else:
            bt_min_trades = st.number_input(
                "最少交易次數篩選（低於此數不顯示）", value=2, min_value=1, step=1,
                key="bt_min_trades",
                help="過濾掉回測期間幾乎沒有訊號的股票，避免結果失真",
            )
            bt_sort_col = st.selectbox(
                "排行榜排序依據",
                ["平均每筆%", "勝率%", "Profit F", "交易次數", "最大回撤%"],
                key="bt_sort_col",
            )
            bt_top_charts = st.number_input(
                "自動展示前 N 名 K 線圖（0=不展示）", value=3, min_value=0, max_value=10,
                key="bt_top_charts",
            )

    sl_val = bt_sl     if bt_sl     > 0 else None
    tp_val = bt_tp     if bt_tp     > 0 else None
    md_val = int(bt_maxdays) if bt_maxdays > 0 else None

    # ════════════════════════════════════════════════════════════
    # 模式 A：單股回測
    # ════════════════════════════════════════════════════════════
    if bt_mode == "🔍 單股回測":
        col_run, col_gs = st.columns([1, 1])
        run_btn = col_run.button("🚀 開始單股回測", type="primary", key="run_bt_single")
        gs_btn  = col_gs.button("🔁 網格搜索最佳參數", key="run_gs")

        if run_btn:
            if not any(buy_sigs):
                st.warning("⚠️ 請至少勾選一個買入策略")
            elif not any(sell_sigs) and not bt_sl and not bt_tp and not bt_maxdays:
                st.warning("⚠️ 請設定至少一種出場條件")
            else:
                with st.spinner(f"正在下載 {bt_ticker} 並執行回測..."):
                    df_bt     = get_stock_data(bt_ticker, period=bt_period)
                    df_hsi_bt = get_stock_data("^HSI",    period=bt_period)

                if df_bt.empty:
                    st.error(f"❌ 無法取得 {bt_ticker} 數據，請確認代碼正確。")
                else:
                    df_bt   = calculate_indicators(df_bt)
                    trades, equity_df, _ = run_backtest(
                        df_bt, buy_sigs, sell_sigs,
                        trade_size=float(bt_capital),
                        commission=bt_commission,
                        stop_loss_pct=sl_val, take_profit_pct=tp_val, max_hold_days=md_val,
                    )
                    metrics = calc_bt_metrics(trades, equity_df, float(bt_capital))

                    if not metrics:
                        st.warning("⚠️ 回測期間內沒有觸發任何交易，請嘗試放寬策略條件或拉長週期。")
                    else:
                        _render_single_bt_result(
                            bt_ticker, metrics, equity_df, df_bt,
                            trades, float(bt_capital), df_hsi_bt
                        )

        if gs_btn:
            if not any(buy_sigs):
                st.warning("⚠️ 請至少勾選一個買入策略")
            else:
                with st.spinner(f"正在下載 {bt_ticker}..."):
                    df_bt_gs = get_stock_data(bt_ticker, period=bt_period)
                if df_bt_gs.empty:
                    st.error(f"❌ 無法取得 {bt_ticker} 數據")
                else:
                    df_bt_gs = calculate_indicators(df_bt_gs)
                    st.divider()
                    st.markdown("### 🔁 網格搜索結果")
                    st.caption(
                        f"遍歷 止損×止盈×持倉天數 共 80 種組合，策略：{bt_ticker}，週期：{bt_period}"
                    )
                    gs_sort = st.selectbox(
                        "排序指標", ["平均每筆%", "勝率%", "Profit F", "交易次數", "最大回撤%"],
                        key="gs_sort"
                    )
                    df_gs = run_grid_search(
                        df_bt_gs, buy_sigs, sell_sigs,
                        trade_size=float(bt_capital),
                        commission=bt_commission,
                        sort_metric=gs_sort,
                    )
                    if df_gs.empty:
                        st.warning("⚠️ 所有組合均無交易，請放寬買入策略。")
                    else:
                        def _gs_color(val):
                            try:
                                v = float(val)
                                if v > 0:   return "color:#26a69a;font-weight:bold"
                                if v < 0:   return "color:#ef5350"
                            except Exception:
                                pass
                            return ""

                        st.dataframe(
                            df_gs.head(20).style
                                .map(_gs_color, subset=["平均每筆%"])
                                .map(lambda v: "color:#ef5350" if isinstance(v, (int,float)) and v < -15 else "",
                                     subset=["最大回撤%"])
                                .format({
                                    "平均每筆%": "{:+.2f}%",
                                    "勝率%":     "{:.1f}%",
                                    "最大回撤%": "{:.2f}%",
                                    "Profit F":  "{:.2f}",
                                }),
                            use_container_width=True,
                            hide_index=True,
                        )
                        best = df_gs.iloc[0]
                        st.success(
                            f"🏆 最佳組合（按{gs_sort}）：止損 {best['止損%']} ｜ "
                            f"止盈 {best['止盈%']} ｜ 最長持倉 {best['最長持倉']} ｜ "
                            f"平均每筆 {best['平均每筆%']:+.2f}% ｜ 勝率 {best['勝率%']:.1f}%"
                        )


    # ════════════════════════════════════════════════════════════
    # 模式 B：全倉掃描回測
    # ════════════════════════════════════════════════════════════
    else:
        cache_banner()
        n_stocks = len(STOCKS)
        st.info(
            f"📋 將對 **{n_stocks} 隻**股票套用相同策略進行回測。"
            f"建議先在左側 **⬇️ 批量下載** 緩存數據，速度快 10 倍。"
        )
        run_batch_btn = st.button(
            f"🚀 開始全倉掃描回測（{n_stocks} 隻）", type="primary", key="run_bt_batch"
        )

        if run_batch_btn:
            if not any(buy_sigs):
                st.warning("⚠️ 請至少勾選一個買入策略")
            elif not any(sell_sigs) and not bt_sl and not bt_tp and not bt_maxdays:
                st.warning("⚠️ 請設定至少一種出場條件")
            else:
                # ── 下載 / 使用緩存 ───────────────────────────
                cache = st.session_state.get("stock_cache", {})
                need_download = [s for s in STOCKS if s not in cache]
                if need_download:
                    with st.spinner(f"批量下載 {len(need_download)} 隻未緩存股票..."):
                        extra = batch_download(need_download, period=bt_period)
                        cache.update(extra)
                        st.session_state["stock_cache"] = cache

                df_hsi_bt = get_stock_data("^HSI", period=bt_period)

                # ── 逐股回測 ──────────────────────────────────
                batch_results  = []
                batch_dfs      = {}
                batch_trades   = {}
                batch_equities = {}   # ✅ 正確儲存 equity_df，修復 drill-down bug
                pbar   = st.progress(0, text="準備中...")
                status = st.empty()

                for idx, ticker in enumerate(STOCKS):
                    pbar.progress((idx + 1) / n_stocks, text=f"回測 {ticker}  ({idx+1}/{n_stocks})")
                    status.text(f"⏳ {ticker}")

                    df_s = cache.get(ticker)
                    if df_s is None or df_s.empty or len(df_s) < 62:
                        continue

                    try:
                        pre_s = precompute_signals(df_s)   # ⚡ 預計算一次，grid也可複用
                        trades_s, equity_s, _ = run_backtest(
                            df_s, buy_sigs, sell_sigs,
                            trade_size=float(bt_capital),
                            commission=bt_commission,
                            stop_loss_pct=sl_val, take_profit_pct=tp_val, max_hold_days=md_val,
                            _precomputed=pre_s,
                        )
                        m = calc_bt_metrics(trades_s, equity_s, float(bt_capital))
                        if not m or m["交易次數"] < bt_min_trades:
                            continue
                        batch_results.append({
                            "代碼":       ticker,
                            "平均每筆%":  m["平均每筆回報%"],
                            "勝率%":      m["勝率%"],
                            "交易次數":   m["交易次數"],
                            "Profit F":   m["Profit Factor"],
                            "最大回撤%":  m["最大回撤%"],
                            "最大連輸":   m["最大連輸"],
                            "平均持倉天": m["平均持倉天數"],
                        })
                        batch_dfs[ticker]      = df_s
                        batch_trades[ticker]   = trades_s
                        batch_equities[ticker] = equity_s
                    except Exception:
                        continue

                pbar.empty(); status.empty()

                if not batch_results:
                    st.warning("⚠️ 沒有任何股票符合條件，請放寬策略或減少最少交易次數。")
                else:
                    df_rank = pd.DataFrame(batch_results)

                    sort_asc = (bt_sort_col == "最大回撤%")
                    df_rank  = df_rank.sort_values(bt_sort_col, ascending=sort_asc).reset_index(drop=True)
                    df_rank.index += 1

                    n_pos   = int((df_rank["平均每筆%"] > 0).sum())
                    n_neg   = int((df_rank["平均每筆%"] <= 0).sum())
                    avg_ret = float(df_rank["平均每筆%"].mean())

                    st.divider()
                    st.markdown("### 🏆 全倉掃描回測結果")
                    st.markdown(
                        f"<div style='background:rgba(255,255,255,0.05);"
                        f"border-left:4px solid #f9a825;"
                        f"padding:10px 16px;border-radius:6px;font-size:16px;font-weight:bold'>"
                        f"📊 共回測 <b>{len(batch_results)}</b> 隻 ｜ "
                        f"🟢 正回報 <b>{n_pos}</b> 隻 ｜ "
                        f"🔴 負回報 <b>{n_neg}</b> 隻 ｜ "
                        f"平均每筆 <b>{avg_ret:+.2f}%</b>"
                        f"</div>",
                        unsafe_allow_html=True,
                    )
                    st.write("")

                    # ── 排行榜 ────────────────────────────────
                    def _color_val(val):
                        try:
                            v = float(val)
                            if v > 0:  return "color:#26a69a;font-weight:bold"
                            if v < 0:  return "color:#ef5350;font-weight:bold"
                        except Exception:
                            pass
                        return ""

                    st.dataframe(
                        df_rank.style
                            .map(_color_val, subset=["平均每筆%", "勝率%"])
                            .map(lambda v: "color:#ef5350;font-weight:bold"
                                 if (isinstance(v, (int,float)) and v < -15) else "", subset=["最大回撤%"])
                            .format({
                                "平均每筆%": "{:+.2f}%",
                                "勝率%":     "{:.1f}%",
                                "Profit F":  "{:.2f}",
                                "最大回撤%": "{:.2f}%",
                                "平均持倉天":"{:.0f}",
                            }),
                        use_container_width=True,
                        height=min(600, 35 * len(df_rank) + 40),
                    )

                    # ── 平均每筆回報分布長條圖 ────────────────
                    st.divider()
                    st.markdown("### 📊 平均每筆回報分布")
                    colors_bar = ["#26a69a" if v > 0 else "#ef5350"
                                  for v in df_rank["平均每筆%"]]
                    fig_bar = go.Figure(go.Bar(
                        x=df_rank["代碼"],
                        y=df_rank["平均每筆%"],
                        marker_color=colors_bar,
                        text=[f"{v:+.1f}%" for v in df_rank["平均每筆%"]],
                        textposition="outside",
                    ))
                    fig_bar.update_layout(
                        height=350,
                        margin=dict(t=10, b=10),
                        paper_bgcolor="rgba(0,0,0,0)",
                        plot_bgcolor="rgba(0,0,0,0)",
                        yaxis_ticksuffix="%",
                        xaxis_tickangle=-45,
                        yaxis_title="平均每筆回報%",
                    )
                    st.plotly_chart(fig_bar, use_container_width=True)


                    # ── 前 N 名詳細圖表 ───────────────────────
                    if bt_top_charts > 0:
                        st.divider()
                        st.markdown(f"### 🎯 前 {bt_top_charts} 名 K 線標記圖")
                        top_tickers = df_rank["代碼"].head(int(bt_top_charts)).tolist()
                        for tk in top_tickers:
                            m_row = next(r for r in batch_results if r["代碼"] == tk)
                            ret   = m_row["平均每筆%"]
                            icon  = "🟢" if ret > 0 else "🔴"
                            st.markdown(
                                f"**{icon} {tk}**　平均每筆 {ret:+.2f}%　"
                                f"勝率 {m_row['勝率%']:.1f}%　"
                                f"交易 {m_row['交易次數']} 次　"
                                f"PF {m_row['Profit F']:.2f}"
                            )
                            show_backtest_chart(batch_dfs[tk], batch_trades[tk])
                            st.write("")

                    # ── 儲存結果供單股深挖 ───────────────────
                    st.session_state["bt_batch_results"]  = batch_results
                    st.session_state["bt_batch_dfs"]      = batch_dfs
                    st.session_state["bt_batch_trades"]   = batch_trades
                    st.session_state["bt_batch_equities"] = batch_equities

                    # ── 單股深挖（✅ 修復 equity curve bug）────
                    st.divider()
                    st.markdown("### 🔬 單股深挖")
                    drill_options = df_rank["代碼"].tolist()
                    drill_ticker  = st.selectbox(
                        "選擇股票查看詳細回測結果", drill_options, key="bt_drill"
                    )
                    if st.button("📋 查看詳細結果", key="bt_drill_btn"):
                        d_df      = batch_dfs[drill_ticker]
                        d_trades  = batch_trades[drill_ticker]
                        d_eq      = batch_equities[drill_ticker]   # ✅ 直接使用已計算的 equity_df
                        d_m       = calc_bt_metrics(d_trades, d_eq, float(bt_capital))
                        _render_single_bt_result(
                            drill_ticker, d_m, d_eq, d_df,
                            d_trades, float(bt_capital), df_hsi_bt
                        )
