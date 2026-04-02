import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import os

st.set_page_config(page_title="港股狙擊手 V8.9.3", layout="wide")

# --- 1. 核心數據抓取 ---
def get_stock_data(ticker, period="1y"):
    try:
        if ticker == "^HSTECH":
            df = yf.download("800700.HK", period=period, progress=False, auto_adjust=True)
            if df.empty:
                df = yf.download("^HSTECH", period=period, progress=False, auto_adjust=True)
            if df.empty:
                df = yf.download("3032.HK", period=period, progress=False, auto_adjust=True)
        elif ticker == "^HSI":
            df = yf.download("^HSI", period=period, progress=False, auto_adjust=True)
            if df.empty:
                df = yf.download("2800.HK", period=period, progress=False, auto_adjust=True)
        else:
            df = yf.download(ticker, period=period, progress=False, auto_adjust=True)

        if df.empty:
            return pd.DataFrame()

        # 修復：統一處理 MultiIndex（新版 yfinance 常見問題）
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = [col[0] for col in df.columns]

        # 確保欄位名稱正確
        df.columns = [str(c).strip() for c in df.columns]

        df.index = pd.to_datetime(df.index).tz_localize(None)
        return df.dropna(subset=['Close'])
    except Exception as e:
        return pd.DataFrame()

# --- 2. 指標計算函數 ---
def calculate_indicators(df):
    df = df.copy()
    df['MA5']  = df['Close'].rolling(5).mean()
    df['MA10'] = df['Close'].rolling(10).mean()
    df['MA20'] = df['Close'].rolling(20).mean()
    df['MA60'] = df['Close'].rolling(60).mean()

    exp1 = df['Close'].ewm(span=12, adjust=False).mean()
    exp2 = df['Close'].ewm(span=26, adjust=False).mean()
    df['DIF'] = exp1 - exp2
    df['DEA'] = df['DIF'].ewm(span=9, adjust=False).mean()
    df['MACD_Hist'] = df['DIF'] - df['DEA']

    low_list  = df['Low'].rolling(9).min()
    high_list = df['High'].rolling(9).max()
    denom = high_list - low_list
    denom = denom.replace(0, 1)  # 防止除以零
    rsv = (df['Close'] - low_list) / denom * 100
    df['K'] = rsv.ewm(com=2, adjust=False).mean()
    df['D'] = df['K'].ewm(com=2, adjust=False).mean()
    df['J'] = 3 * df['K'] - 2 * df['D']

    return df

# --- 3. 掃描結果 Metric 卡片 ---
def show_scan_metrics(results):
    """在表格上方顯示每個標的的現價 + 漲跌% 卡片"""
    cols_per_row = 4
    for row_start in range(0, len(results), cols_per_row):
        chunk = results[row_start: row_start + cols_per_row]
        cols = st.columns(cols_per_row)
        for col, r in zip(cols, chunk):
            pct = r['漲跌%']
            arrow = "🟢 ▲" if pct >= 0 else "🔴 ▼"
            delta_str = f"{'+' if pct >= 0 else ''}{pct:.2f}%"
            col.metric(
                label=f"{arrow} {r['代碼']}",
                value=f"${r['現價']:.2f}",
                delta=delta_str,
            )

# --- 4. 繪圖（綠漲紅跌）---
def show_chart(ticker, df):
    fig = make_subplots(
        rows=4, cols=1, shared_xaxes=True,
        vertical_spacing=0.03,
        row_heights=[0.4, 0.15, 0.2, 0.2]
    )

    fig.add_trace(go.Candlestick(
        x=df.index, open=df['Open'], high=df['High'],
        low=df['Low'], close=df['Close'],
        increasing_line_color='#26a69a',
        decreasing_line_color='#ef5350',
        name='K線'
    ), row=1, col=1)

    for ma, col in zip(['MA5', 'MA20', 'MA60'], ['gray', 'purple', 'orange']):
        fig.add_trace(go.Scatter(
            x=df.index, y=df[ma], name=ma,
            line=dict(width=1, color=col)
        ), row=1, col=1)

    colors = ['#26a69a' if c >= o else '#ef5350'
              for c, o in zip(df['Close'], df['Open'])]
    fig.add_trace(go.Bar(
        x=df.index, y=df['Volume'],
        marker_color=colors, name='成交量'
    ), row=2, col=1)

    h_colors = ['#26a69a' if v >= 0 else '#ef5350' for v in df['MACD_Hist']]
    fig.add_trace(go.Bar(
        x=df.index, y=df['MACD_Hist'],
        marker_color=h_colors, name='MACD'
    ), row=3, col=1)
    fig.add_trace(go.Scatter(
        x=df.index, y=df['DIF'],
        line=dict(color='#f9a825', width=1), name='DIF'
    ), row=3, col=1)
    fig.add_trace(go.Scatter(
        x=df.index, y=df['DEA'],
        line=dict(color='#42a5f5', width=1), name='DEA'
    ), row=3, col=1)

    fig.add_trace(go.Scatter(
        x=df.index, y=df['K'],
        line=dict(color='#f9a825', width=1), name='K'
    ), row=4, col=1)
    fig.add_trace(go.Scatter(
        x=df.index, y=df['D'],
        line=dict(color='#42a5f5', width=1), name='D'
    ), row=4, col=1)
    fig.add_trace(go.Scatter(
        x=df.index, y=df['J'],
        line=dict(color='#ab47bc', width=1), name='J'
    ), row=4, col=1)

    fig.update_layout(
        height=700, showlegend=False,
        xaxis_rangeslider_visible=False,
        margin=dict(t=10, b=10),
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)'
    )
    st.plotly_chart(fig, use_container_width=True)

# --- 4. 載入股票清單 ---
def load_stocks():
    if not os.path.exists('stocks.txt'):
        return ["0700.HK", "9988.HK", "3690.HK"]
    with open('stocks.txt', 'r') as f:
        return [line.split('#')[0].strip() for line in f if ".HK" in line]

STOCKS = load_stocks()

# --- 5. 主程式 UI ---
st.title("🏹 港股狙擊手 V8.9.1")

tabs = st.tabs(["🌍 指數", "🏆 跑贏大市", "🟢 買入掃描", "🔴 賣出掃描", "🔍 分析"])

# ===================== TAB 0：指數 =====================
with tabs[0]:
    st.subheader("🌍 主要指數走勢")
    indices = {
        "恆生指數 (^HSI)": "^HSI",
        "恆生科技 (^HSTECH)": "^HSTECH",
        "滬深300 (000300.SS)": "000300.SS",
    }
    col1, col2 = st.columns([1, 3])
    with col1:
        selected_index = st.selectbox("選擇指數", list(indices.keys()))
        period = st.selectbox("時間週期", ["3mo", "6mo", "1y", "2y"], index=2)
    with col2:
        ticker_code = indices[selected_index]
        with st.spinner(f"載入 {selected_index} 數據中..."):
            df_idx = get_stock_data(ticker_code, period=period)
        if df_idx.empty:
            st.error(f"❌ 無法載入 {selected_index} 數據，請稍後再試。")
        else:
            df_idx = calculate_indicators(df_idx)
            show_chart(ticker_code, df_idx)

# ===================== TAB 1：跑贏大市 =====================
with tabs[1]:
    st.subheader("🏆 跑贏大市排行")
    period_beat = st.selectbox("比較週期", ["1mo", "3mo", "6mo"], index=1, key="beat_period")

    if st.button("📊 開始計算跑贏大市"):
        with st.spinner("正在比較各股與恆指表現..."):
            df_hsi = get_stock_data("^HSI", period=period_beat)
            if df_hsi.empty:
                st.error("無法取得恆指數據")
            else:
                hsi_ret = (df_hsi['Close'].iloc[-1] - df_hsi['Close'].iloc[0]) / df_hsi['Close'].iloc[0] * 100

                results = []
                pbar = st.progress(0)
                for i, s in enumerate(STOCKS):
                    pbar.progress((i + 1) / len(STOCKS))
                    df_s = get_stock_data(s, period=period_beat)
                    if df_s.empty or len(df_s) < 5:
                        continue
                    stock_ret = (df_s['Close'].iloc[-1] - df_s['Close'].iloc[0]) / df_s['Close'].iloc[0] * 100
                    excess = stock_ret - hsi_ret
                    results.append({
                        "代碼": s,
                        "股票回報%": round(float(stock_ret), 2),
                        "恆指回報%": round(float(hsi_ret), 2),
                        "超額回報%": round(float(excess), 2),
                    })
                pbar.empty()

                if results:
                    df_res = pd.DataFrame(results).sort_values("超額回報%", ascending=False)
                    st.success(f"共分析 {len(df_res)} 隻股票，恆指回報：{hsi_ret:.2f}%")
                    st.dataframe(
                        df_res.style.map(
                            lambda x: 'color: #26a69a' if x > 0 else 'color: #ef5350',
                            subset=['超額回報%', '股票回報%']
                        ),
                        use_container_width=True
                    )
                else:
                    st.warning("無法取得足夠數據")

# ===================== TAB 2：買入掃描 =====================
with tabs[2]:
    st.subheader("🟢 買入訊號庫")
    col_a, col_b = st.columns(2)
    b1 = col_a.checkbox("📈 價格 > 60MA（多頭趨勢）")
    b2 = col_a.checkbox("🔥 均線多頭（5>10>20）")
    b3 = col_a.checkbox("🚀 20日高點突破 + 爆量")
    b4 = col_b.checkbox("💥 MACD 剛翻紅（金叉）")
    b5 = col_b.checkbox("📉 KDJ 超賣（J < 10）")
    b6 = col_b.checkbox("🪃 站上 20MA（轉強）")

    if st.button("🟢 開始掃描買點"):
        if not any([b1, b2, b3, b4, b5, b6]):
            st.warning("⚠️ 請至少勾選一個條件")
        else:
            results = []
            hits_dfs = {}
            pbar = st.progress(0)
            status = st.empty()

            for i, s in enumerate(STOCKS):
                pbar.progress((i + 1) / len(STOCKS))
                status.text(f"正在分析 {s}...")
                df = get_stock_data(s)
                if df.empty or len(df) < 60:
                    continue

                df = calculate_indicators(df)
                c = df.iloc[-1]
                p = df.iloc[-2]
                vol_avg = df['Volume'].iloc[-21:-1].mean()

                checks = []
                if b1: checks.append(bool(c['Close'] > c['MA60']))
                if b2: checks.append(bool(c['MA5'] > c['MA10']) and bool(c['MA10'] > c['MA20']))
                # 修復：拆開 and 條件，避免 pandas Series 布林歧義錯誤
                if b3:
                    high_break = bool(c['Close'] > df['High'].iloc[-21:-1].max())
                    vol_break  = bool(c['Volume'] > vol_avg * 1.5)
                    checks.append(high_break and vol_break)
                if b4: checks.append(bool(c['MACD_Hist'] > 0) and bool(p['MACD_Hist'] <= 0))
                if b5: checks.append(bool(c['J'] < 10))
                if b6: checks.append(bool(c['Close'] > c['MA20']) and bool(p['Close'] <= p['MA20']))

                if checks and all(checks):
                    pct = ((c['Close'] - p['Close']) / p['Close']) * 100
                    results.append({
                        "代碼": s,
                        "現價": round(float(c['Close']), 2),
                        "漲跌%": round(float(pct), 2),
                        "J值": round(float(c['J']), 1)
                    })
                    hits_dfs[s] = df

            status.empty()
            pbar.empty()

            if results:
                st.success(f"✅ 發現 {len(results)} 個標的")
                # 現價 + 漲跌% 卡片
                show_scan_metrics(results)
                st.divider()
                # 明細表格（小數 2 位）
                df_show = pd.DataFrame(results)
                df_show['現價']  = df_show['現價'].map(lambda x: f"{x:.2f}")
                df_show['漲跌%'] = df_show['漲跌%'].map(lambda x: f"{'+' if x>=0 else ''}{x:.2f}%")
                df_show['J值']   = df_show['J值'].map(lambda x: f"{x:.1f}")
                st.dataframe(df_show, use_container_width=True)
                for s in hits_dfs:
                    st.write(f"### 🎯 {s}")
                    show_chart(s, hits_dfs[s])
            else:
                st.warning("⚠️ 沒有符合條件的股票。請嘗試只勾選一個條件（例如：MACD 翻紅）來測試連線是否正常。")

# ===================== TAB 3：賣出掃描 =====================
with tabs[3]:
    st.subheader("🔴 賣出訊號庫")
    col_c, col_d = st.columns(2)
    s1 = col_c.checkbox("📉 價格 < 60MA（空頭趨勢）")
    s4 = col_d.checkbox("💔 MACD 剛翻綠（死叉）")
    s5 = col_d.checkbox("📈 KDJ 超買（J > 90）")

    if st.button("🔴 開始掃描賣點"):
        if not any([s1, s4, s5]):
            st.warning("⚠️ 請至少勾選一個條件")
        else:
            results = []
            hits_dfs = {}
            pbar = st.progress(0)
            status = st.empty()

            for i, s in enumerate(STOCKS):
                pbar.progress((i + 1) / len(STOCKS))
                status.text(f"正在分析 {s}...")
                df = get_stock_data(s)
                if df.empty or len(df) < 60:
                    continue
                df = calculate_indicators(df)
                c = df.iloc[-1]
                p = df.iloc[-2]

                checks = []
                if s1: checks.append(bool(c['Close'] < c['MA60']))
                if s4: checks.append(bool(c['MACD_Hist'] < 0) and bool(p['MACD_Hist'] >= 0))
                if s5: checks.append(bool(c['J'] > 90))

                if checks and all(checks):
                    pct = ((c['Close'] - p['Close']) / p['Close']) * 100
                    results.append({
                        "代碼": s,
                        "現價": round(float(c['Close']), 2),
                        "漲跌%": round(float(pct), 2),
                        "J值": round(float(c['J']), 1)
                    })
                    hits_dfs[s] = df

            status.empty()
            pbar.empty()

            if results:
                st.error(f"🔴 發現 {len(results)} 個標的")
                # 現價 + 漲跌% 卡片
                show_scan_metrics(results)
                st.divider()
                # 明細表格（小數 2 位）
                df_show = pd.DataFrame(results)
                df_show['現價']  = df_show['現價'].map(lambda x: f"{x:.2f}")
                df_show['漲跌%'] = df_show['漲跌%'].map(lambda x: f"{'+' if x>=0 else ''}{x:.2f}%")
                df_show['J值']   = df_show['J值'].map(lambda x: f"{x:.1f}")
                st.dataframe(df_show, use_container_width=True)
                for s in hits_dfs:
                    st.write(f"### ⚠️ {s}")
                    show_chart(s, hits_dfs[s])
            else:
                st.warning("目前沒有符合賣出條件的股票。")

# ===================== TAB 4：分析 =====================
with tabs[4]:
    st.subheader("🔍 個股技術分析")
    col_left, col_right = st.columns([1, 3])
    with col_left:
        custom_ticker = st.text_input("輸入股票代碼", value="0700.HK").upper()
        analysis_period = st.selectbox("週期", ["3mo", "6mo", "1y", "2y"], index=2, key="analysis_period")
        analyze_btn = st.button("🔍 分析")
    with col_right:
        if analyze_btn:
            with st.spinner(f"正在分析 {custom_ticker}..."):
                df_a = get_stock_data(custom_ticker, period=analysis_period)
            if df_a.empty:
                st.error(f"❌ 無法取得 {custom_ticker} 數據，請確認代碼正確。")
            else:
                df_a = calculate_indicators(df_a)
                c = df_a.iloc[-1]
                m1, m2, m3, m4 = st.columns(4)
                m1.metric("現價", f"{c['Close']:.2f}")
                m2.metric("MA20", f"{c['MA20']:.2f}", f"{((c['Close']-c['MA20'])/c['MA20']*100):.1f}%")
                m3.metric("J值", f"{c['J']:.1f}")
                m4.metric("MACD柱", f"{c['MACD_Hist']:.4f}")
                show_chart(custom_ticker, df_a)
