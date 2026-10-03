"""app_insider.py — Insider Signals Dashboard (Bloomberg style, auto-refresh)"""
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime
from streamlit_autorefresh import st_autorefresh

import insider_database as idb


st.set_page_config(
    page_title="Insider Signals",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="expanded",
)

st_autorefresh(interval=5 * 60 * 1000, key="data_refresh")


st.markdown("""
<style>
    .stApp { background-color: #000000; }
    html, body, [class*="css"] {
        font-family: 'Consolas', 'Monaco', 'Courier New', monospace;
        color: #e6e6e6;
        font-size: 13px;
    }
    section[data-testid="stSidebar"] {
        background-color: #0a0a0a;
        border-right: 1px solid #333;
    }
    section[data-testid="stSidebar"] h2,
    section[data-testid="stSidebar"] h3 {
        color: #ff6600 !important;
        font-size: 0.8rem !important;
        text-transform: uppercase;
        letter-spacing: 1.5px;
        font-weight: 700;
        border-bottom: 1px solid #333;
        padding-bottom: 0.3rem;
        margin-bottom: 0.8rem;
    }
    section[data-testid="stSidebar"] input,
    section[data-testid="stSidebar"] select {
        background-color: #111 !important;
        color: #ffcc00 !important;
        border: 1px solid #333 !important;
        border-radius: 0 !important;
        font-family: 'Consolas', monospace !important;
        font-size: 12px !important;
    }
    .bb-topbar {
        background: linear-gradient(90deg, #ff6600 0%, #cc5200 100%);
        padding: 0.5rem 1rem;
        margin: -1rem -1rem 1rem -1rem;
        display: flex;
        justify-content: space-between;
        align-items: center;
        border-bottom: 2px solid #ff6600;
    }
    .bb-topbar .brand {
        color: #000;
        font-weight: 900;
        font-size: 1rem;
        letter-spacing: 3px;
        font-family: 'Consolas', monospace;
    }
    .bb-topbar .clock {
        color: #000;
        font-weight: 700;
        font-size: 0.85rem;
        font-family: 'Consolas', monospace;
    }
    .bb-kpi {
        background: #0a0a0a;
        border: 1px solid #333;
        padding: 0.6rem 0.8rem;
        border-left: 3px solid #ff6600;
        font-family: 'Consolas', monospace;
        height: 100%;
        min-height: 75px;
    }
    .bb-kpi-label {
        color: #888;
        font-size: 0.68rem;
        text-transform: uppercase;
        letter-spacing: 1px;
        margin-bottom: 0.25rem;
    }
    .bb-kpi-value {
        color: #ffffff;
        font-size: 1.5rem;
        font-weight: 700;
        line-height: 1.1;
        margin: 0;
        letter-spacing: -0.5px;
    }
    .bb-kpi-value.small { font-size: 1.1rem; }
    .bb-kpi-sub {
        color: #666;
        font-size: 0.7rem;
        margin-top: 0.2rem;
    }
    .bb-score-high { color: #4CAF50; }
    .bb-score-mid { color: #ff6600; }
    .bb-score-low { color: #888; }
    .bb-section {
        color: #ff6600;
        font-size: 0.8rem;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 1.5px;
        margin: 1.2rem 0 0.6rem 0;
        padding-bottom: 0.3rem;
        border-bottom: 1px solid #333;
    }
    .bb-signal-card {
        background: #0a0a0a;
        border: 1px solid #333;
        border-left: 4px solid #ff6600;
        padding: 0.8rem 1rem;
        margin-bottom: 0.6rem;
        font-family: 'Consolas', monospace;
    }
    .bb-signal-card.high { border-left-color: #4CAF50; }
    .bb-signal-card.mid { border-left-color: #ff6600; }
    .bb-signal-card.low { border-left-color: #666; }
    .bb-signal-head {
        display: flex;
        justify-content: space-between;
        align-items: baseline;
        margin-bottom: 0.3rem;
    }
    .bb-signal-ticker {
        color: #ffffff;
        font-size: 1.1rem;
        font-weight: 700;
        letter-spacing: 1px;
    }
    .bb-signal-score {
        font-size: 1.1rem;
        font-weight: 700;
    }
    .bb-signal-insider {
        color: #ffcc00;
        font-size: 0.85rem;
        margin-bottom: 0.2rem;
    }
    .bb-signal-details {
        color: #888;
        font-size: 0.75rem;
        line-height: 1.5;
    }
    .stTabs [data-baseweb="tab-list"] {
        gap: 0;
        background-color: #000;
        border-bottom: 1px solid #333;
    }
    .stTabs [data-baseweb="tab"] {
        background-color: transparent;
        color: #888;
        border-radius: 0;
        padding: 8px 20px;
        font-weight: 600;
        font-size: 0.78rem;
        font-family: 'Consolas', monospace;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }
    .stTabs [aria-selected="true"] {
        background-color: transparent !important;
        color: #ff6600 !important;
        border-bottom: 2px solid #ff6600 !important;
    }
    .stButton > button {
        background-color: #1a1a1a;
        color: #ff6600;
        border: 1px solid #333;
        border-radius: 0;
        font-weight: 600;
        padding: 0.4rem 0.8rem;
        font-size: 0.78rem;
        font-family: 'Consolas', monospace;
        text-transform: uppercase;
        letter-spacing: 1px;
    }
    .stButton > button:hover {
        background-color: #ff6600;
        color: #000;
        border-color: #ff6600;
    }
    .stDataFrame {
        border-radius: 0;
        border: 1px solid #333;
        font-family: 'Consolas', monospace;
    }
    section[data-testid="stSidebar"] .stRadio label {
        font-size: 0.8rem !important;
        padding: 4px 0 !important;
        color: #ccc !important;
        font-family: 'Consolas', monospace !important;
    }
    [data-testid="stMetricValue"] {
        font-family: 'Consolas', monospace !important;
        font-size: 1.1rem !important;
        color: #ffffff !important;
    }
    [data-testid="stMetricLabel"] {
        font-family: 'Consolas', monospace !important;
        font-size: 0.72rem !important;
        color: #888 !important;
        text-transform: uppercase;
    }
    .stAlert {
        background-color: #0a0a0a !important;
        color: #e6e6e6 !important;
        border: 1px solid #333 !important;
        border-radius: 0 !important;
        font-family: 'Consolas', monospace !important;
    }
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
</style>
""", unsafe_allow_html=True)


@st.cache_data(ttl=60)
def load_signals(min_score=0, limit=None):
    return idb.get_all_signals(limit=limit, min_score=min_score)


@st.cache_data(ttl=60)
def load_stats():
    return idb.statistics()


def fmt_money(v):
    try:
        v = float(v)
    except (TypeError, ValueError):
        return "-"
    if v >= 1_000_000_000:
        return f"${v/1_000_000_000:.2f}B"
    if v >= 1_000_000:
        return f"${v/1_000_000:.2f}M"
    if v >= 1_000:
        return f"${v/1_000:.1f}K"
    return f"${v:.0f}"


def fmt_datetime(dt_str):
    """Format ISO datetime string (2026-10-03T19:04:53) to readable format."""
    if not dt_str:
        return "never"
    return str(dt_str).replace("T", " ")[:19]


# ============================================================
# Topbar
# ============================================================
now = datetime.now().strftime("%H:%M:%S  %d-%m-%Y")
stats = load_stats()

st.markdown(f"""
<div class="bb-topbar">
    <div class="brand">🎯 INSIDER SIGNALS</div>
    <div class="clock">
        DB: {stats['total_signals']:,} signals
        &nbsp; · &nbsp; LAST SCAN: {fmt_datetime(stats['last_scan'])}
        &nbsp; · &nbsp; {now}
    </div>
</div>
""", unsafe_allow_html=True)


# ============================================================
# Sidebar
# ============================================================
with st.sidebar:
    st.markdown("### FILTERS")

    min_score = st.slider("Minimum score", 0, 100, 40, 5)
    limit = st.number_input("Max signals to show", value=200, step=50, min_value=10)

    st.markdown("---")
    st.markdown("### KEYWORDS")

    ticker_filter = st.text_input("Ticker contains", "").strip().upper()
    role_filter = st.selectbox(
        "Role",
        ["All", "CEO", "CFO", "Chairman", "President", "Director", "Officer", "10% Owner"]
    )
    cluster_only = st.checkbox("Only clusters (2+ insiders)", value=False)

    st.markdown("---")
    if st.button("🔄 Refresh data", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

    st.markdown("---")
    st.markdown(f"""
<div style="font-family: 'Consolas', monospace; font-size: 0.7rem; color: #666;">
AUTO-REFRESH: <span style="color:#ff6600;">every 5 min</span><br>
DB ROWS: <span style="color:#ff6600;">{stats['total_signals']:,}</span><br>
LAST SCAN: <span style="color:#ff6600;">{fmt_datetime(stats['last_scan'])}</span>
</div>
""", unsafe_allow_html=True)


# ============================================================
# Load & filter
# ============================================================
df = load_signals(min_score=min_score, limit=limit)

if df.empty:
    st.markdown("""
    <div class="bb-kpi">
        <div class="bb-kpi-label">NO DATA</div>
        <p class="bb-kpi-value small">No signals found</p>
        <div class="bb-kpi-sub">Run `python insider_scanner.py fast 10` to collect signals</div>
    </div>
    """, unsafe_allow_html=True)
    st.stop()

if ticker_filter:
    df = df[df["ticker"].str.contains(ticker_filter, na=False)]
if role_filter != "All":
    df = df[df["role"].str.contains(role_filter, case=False, na=False)]
if cluster_only:
    df = df[df["cluster"] >= 2]

if df.empty:
    st.warning("No signals match the current filters.")
    st.stop()

df = df.reset_index(drop=True)
df["score"] = pd.to_numeric(df["score"], errors="coerce").fillna(0).astype(int)
df["value"] = pd.to_numeric(df["value"], errors="coerce").fillna(0)


# ============================================================
# KPI Cards
# ============================================================
total_value = float(df["value"].sum())
top_score = int(df["score"].max())
n_high = int((df["score"] >= 70).sum())
n_clusters = int((df["cluster"] >= 2).sum())

c1, c2, c3, c4, c5 = st.columns(5)
with c1:
    st.markdown(f'''<div class="bb-kpi">
        <div class="bb-kpi-label">SIGNALS SHOWN</div>
        <p class="bb-kpi-value">{len(df)}</p>
        <div class="bb-kpi-sub">score ≥ {min_score}</div>
    </div>''', unsafe_allow_html=True)
with c2:
    st.markdown(f'''<div class="bb-kpi">
        <div class="bb-kpi-label">TOTAL VALUE</div>
        <p class="bb-kpi-value">{fmt_money(total_value)}</p>
        <div class="bb-kpi-sub">combined insider buys</div>
    </div>''', unsafe_allow_html=True)
with c3:
    st.markdown(f'''<div class="bb-kpi">
        <div class="bb-kpi-label">TOP SCORE</div>
        <p class="bb-kpi-value bb-score-high">{top_score}/100</p>
        <div class="bb-kpi-sub">{df.iloc[0]["ticker"]}</div>
    </div>''', unsafe_allow_html=True)
with c4:
    st.markdown(f'''<div class="bb-kpi">
        <div class="bb-kpi-label">STRONG (≥70)</div>
        <p class="bb-kpi-value">{n_high}</p>
        <div class="bb-kpi-sub">high-conviction</div>
    </div>''', unsafe_allow_html=True)
with c5:
    st.markdown(f'''<div class="bb-kpi">
        <div class="bb-kpi-label">CLUSTERS</div>
        <p class="bb-kpi-value">{n_clusters}</p>
        <div class="bb-kpi-sub">2+ insiders/ticker</div>
    </div>''', unsafe_allow_html=True)


# ============================================================
# Tabs
# ============================================================
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "🏆 TOP SIGNALS", "📋 ALL SIGNALS", "🎯 BY TICKER", "👤 BY INSIDER", "📊 STATS"
])


with tab1:
    st.markdown('<div class="bb-section">TOP 10 — Highest score</div>',
                unsafe_allow_html=True)

    top10 = df.sort_values("score", ascending=False).head(10)

    for i, r in top10.iterrows():
        score = int(r["score"])
        if score >= 70:
            cls = "high"
            score_cls = "bb-score-high"
        elif score >= 50:
            cls = "mid"
            score_cls = "bb-score-mid"
        else:
            cls = "low"
            score_cls = "bb-score-low"

        value_str = fmt_money(r["value"])
        insider = str(r["insider"]).title()
        role = str(r["role"])[:40] if r["role"] else "Insider"
        company = str(r["company"])[:50] if r["company"] else r["ticker"]
        reasons = str(r["reasons"]).replace(" | ", " · ")
        pct = float(r["pct_holding"]) if pd.notna(r["pct_holding"]) else 0

        st.markdown(f"""
<div class="bb-signal-card {cls}">
    <div class="bb-signal-head">
        <span class="bb-signal-ticker">{r['ticker']}</span>
        <span class="bb-signal-score {score_cls}">SCORE {score}/100</span>
    </div>
    <div class="bb-signal-insider">{insider} — {role}</div>
    <div class="bb-signal-details">
        <b>{value_str}</b> at {company} · {r['date']}<br>
        Position: +{pct:.0f}% · Trades: {int(r['n_transactions'])} · Cluster: {int(r['cluster'])}<br>
        <span style="color:#ff6600;">→ {reasons}</span>
    </div>
</div>
""", unsafe_allow_html=True)


with tab2:
    st.markdown('<div class="bb-section">All signals (sorted by score)</div>',
                unsafe_allow_html=True)

    display_cols = ["ticker", "company", "insider", "role", "score",
                    "date", "value", "shares", "price", "pct_holding",
                    "n_transactions", "cluster"]
    df_show = df[display_cols].sort_values("score", ascending=False).copy()
    df_show.columns = ["Ticker", "Company", "Insider", "Role", "Score",
                       "Date", "Value", "Shares", "Price", "% Holding",
                       "Trades", "Cluster"]
    df_show["Value"] = df_show["Value"].apply(
        lambda v: fmt_money(v)
    )
    df_show["Price"] = df_show["Price"].apply(
        lambda v: f"${v:.2f}" if pd.notna(v) else "-"
    )
    df_show["% Holding"] = df_show["% Holding"].apply(
        lambda v: f"{v:.1f}%" if pd.notna(v) else "-"
    )

    st.dataframe(df_show, use_container_width=True, hide_index=True, height=500)

    st.markdown('<div class="bb-section">Top 20 signals by score</div>',
                unsafe_allow_html=True)

    top20 = df.sort_values("score", ascending=False).head(20)
    colors = ["#4CAF50" if s >= 70 else ("#ff6600" if s >= 50 else "#666")
              for s in top20["score"]]

    fig = go.Figure(data=[go.Bar(
        x=top20["ticker"] + " — " + top20["insider"].str[:15],
        y=top20["score"],
        marker_color=colors,
        text=top20["score"].astype(str),
        textposition="outside",
        textfont=dict(color="#e6e6e6", size=10, family="Consolas"),
    )])
    fig.add_hline(y=70, line_dash="dot", line_color="#4CAF50",
                  annotation_text="Strong")
    fig.add_hline(y=50, line_dash="dot", line_color="#ff6600",
                  annotation_text="Moderate")
    fig.update_layout(
        height=450, showlegend=False,
        paper_bgcolor="#000000", plot_bgcolor="#0a0a0a",
        font=dict(color="#e6e6e6", size=10, family="Consolas"),
        xaxis_title="", yaxis_title="Score",
        xaxis=dict(tickangle=45),
    )
    fig.update_xaxes(gridcolor="#222")
    fig.update_yaxes(gridcolor="#222", range=[0, 105])
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

    st.markdown('<div class="bb-section">Top 20 signals by value</div>',
                unsafe_allow_html=True)

    top20v = df.nlargest(20, "value")
    fig2 = go.Figure(data=[go.Bar(
        x=top20v["ticker"] + " — " + top20v["insider"].str[:15],
        y=top20v["value"] / 1_000_000,
        marker_color="#ff6600",
        text=[fmt_money(v) for v in top20v["value"]],
        textposition="outside",
        textfont=dict(color="#e6e6e6", size=10, family="Consolas"),
    )])
    fig2.update_layout(
        height=450, showlegend=False,
        paper_bgcolor="#000000", plot_bgcolor="#0a0a0a",
        font=dict(color="#e6e6e6", size=10, family="Consolas"),
        xaxis_title="", yaxis_title="Value ($M)",
        xaxis=dict(tickangle=45),
    )
    fig2.update_xaxes(gridcolor="#222")
    fig2.update_yaxes(gridcolor="#222")
    st.plotly_chart(fig2, use_container_width=True, config={"displayModeBar": False})


with tab3:
    st.markdown('<div class="bb-section">Grouped by ticker</div>',
                unsafe_allow_html=True)

    ticker_summary = df.groupby("ticker").agg(
        signals=("ticker", "count"),
        total_value=("value", "sum"),
        avg_score=("score", "mean"),
        max_score=("score", "max"),
        last_date=("date", "max"),
    ).reset_index().sort_values("total_value", ascending=False)

    ticker_summary["total_value"] = ticker_summary["total_value"].apply(fmt_money)
    ticker_summary["avg_score"] = ticker_summary["avg_score"].round(1)
    ticker_summary.columns = ["Ticker", "Signals", "Total Value", "Avg Score",
                              "Max Score", "Last Date"]
    st.dataframe(ticker_summary, use_container_width=True, hide_index=True, height=500)


with tab4:
    st.markdown('<div class="bb-section">Grouped by insider</div>',
                unsafe_allow_html=True)

    insider_summary = df.groupby("insider").agg(
        tickers=("ticker", lambda x: ", ".join(sorted(set(x)))),
        signals=("insider", "count"),
        total_value=("value", "sum"),
        avg_score=("score", "mean"),
        last_date=("date", "max"),
    ).reset_index().sort_values("total_value", ascending=False)

    insider_summary["total_value"] = insider_summary["total_value"].apply(fmt_money)
    insider_summary["avg_score"] = insider_summary["avg_score"].round(1)
    insider_summary.columns = ["Insider", "Tickers", "Signals", "Total Value",
                               "Avg Score", "Last Date"]
    st.dataframe(insider_summary, use_container_width=True, hide_index=True, height=600)


with tab5:
    col1, col2 = st.columns(2)

    with col1:
        st.markdown('<div class="bb-section">Score distribution</div>',
                    unsafe_allow_html=True)

        bins = [0, 20, 40, 50, 60, 70, 80, 90, 101]
        labels = ["0-19", "20-39", "40-49", "50-59", "60-69", "70-79", "80-89", "90-100"]
        df["score_bin"] = pd.cut(df["score"], bins=bins, labels=labels, right=False)
        score_dist = df["score_bin"].value_counts().reindex(labels).fillna(0)

        fig = go.Figure(data=[go.Bar(
            x=score_dist.index,
            y=score_dist.values,
            marker_color=["#666", "#666", "#ff6600", "#ff6600",
                          "#ff6600", "#4CAF50", "#4CAF50", "#4CAF50"],
            text=score_dist.values.astype(int),
            textposition="outside",
            textfont=dict(color="#e6e6e6", size=11),
        )])
        fig.update_layout(
            height=350, showlegend=False,
            paper_bgcolor="#000000", plot_bgcolor="#0a0a0a",
            font=dict(color="#e6e6e6", size=10, family="Consolas"),
            xaxis_title="Score range", yaxis_title="Count",
        )
        fig.update_xaxes(gridcolor="#222")
        fig.update_yaxes(gridcolor="#222")
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

    with col2:
        st.markdown('<div class="bb-section">Role breakdown</div>',
                    unsafe_allow_html=True)

        def role_group(r):
            r = str(r).lower()
            if "ceo" in r: return "CEO"
            if "cfo" in r: return "CFO"
            if "chair" in r: return "Chairman"
            if "director" in r: return "Director"
            if "10%" in r: return "10% Owner"
            if "officer" in r: return "Officer"
            return "Other"

        role_counts = df["role"].apply(role_group).value_counts()

        fig = go.Figure(data=[go.Pie(
            labels=role_counts.index,
            values=role_counts.values,
            hole=0.5,
            marker=dict(colors=["#ff6600", "#4CAF50", "#58a6ff", "#FFD700",
                                "#FF3B30", "#a371f7", "#666"]),
            textinfo="label+percent",
            textfont=dict(color="#e6e6e6", size=11),
        )])
        fig.update_layout(
            height=350,
            paper_bgcolor="#000000",
            font=dict(color="#e6e6e6", size=10, family="Consolas"),
            showlegend=False,
        )
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})