# ══════════════════════════════════════════════════════════════════
# charts.py — 所有 Plotly 圖表函數
# ══════════════════════════════════════════════════════════════════

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots


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


def show_backtest_chart(df: pd.DataFrame, trades: list):
    fig = make_subplots(
        rows=3, cols=1, shared_xaxes=True,
        vertical_spacing=0.03,
        row_heights=[0.55, 0.2, 0.25],
    )
    fig.add_trace(go.Candlestick(
        x=df.index, open=df["Open"], high=df["High"],
        low=df["Low"],  close=df["Close"],
        increasing_line_color="#26a69a", decreasing_line_color="#ef5350", name="K線",
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

    buy_x, buy_y = [], []
    sell_win_x, sell_win_y = [], []
    sell_loss_x, sell_loss_y = [], []
    df_index_set = set(df.index)
    for t in trades:
        bd, sd, win = t["_buy_date"], t["_sell_date"], t["_win"]
        if bd in df_index_set:
            buy_x.append(bd)
            buy_y.append(float(df.loc[bd, "Low"]) * 0.985)
        if sd in df_index_set:
            (sell_win_x if win else sell_loss_x).append(sd)
            (sell_win_y if win else sell_loss_y).append(float(df.loc[sd, "High"]) * 1.015)
    if buy_x:
        fig.add_trace(go.Scatter(x=buy_x, y=buy_y, mode="markers+text",
            marker=dict(symbol="triangle-up", size=12, color="#00e676"),
            text=["買"]*len(buy_x), textposition="bottom center",
            textfont=dict(size=9, color="#00e676"), showlegend=False), row=1, col=1)
    if sell_win_x:
        fig.add_trace(go.Scatter(x=sell_win_x, y=sell_win_y, mode="markers+text",
            marker=dict(symbol="triangle-down", size=12, color="#26a69a"),
            text=["賣"]*len(sell_win_x), textposition="top center",
            textfont=dict(size=9, color="#26a69a"), showlegend=False), row=1, col=1)
    if sell_loss_x:
        fig.add_trace(go.Scatter(x=sell_loss_x, y=sell_loss_y, mode="markers+text",
            marker=dict(symbol="triangle-down", size=12, color="#ef5350"),
            text=["賣"]*len(sell_loss_x), textposition="top center",
            textfont=dict(size=9, color="#ef5350"), showlegend=False), row=1, col=1)

    v_colors = ["#26a69a" if c >= o else "#ef5350" for c, o in zip(df["Close"], df["Open"])]
    fig.add_trace(go.Bar(x=df.index, y=df["Volume"], marker_color=v_colors, name="成交量"), row=2, col=1)

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
        z=z, x=month_names,
        y=[str(yr) for yr in years],
        text=text_vals, texttemplate="%{text}",
        textfont=dict(size=11),
        colorscale=[
            [0.0, "#b71c1c"], [0.35, "#ef5350"],
            [0.5, "#1e1e2e"],
            [0.65, "#26a69a"], [1.0, "#004d40"],
        ],
        zmid=0, showscale=True,
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
