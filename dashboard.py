"""
Food Health & Spending Dashboard
Run with:  streamlit run dashboard.py
"""

import subprocess, sys
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st
from pathlib import Path
from food_categories import CATEGORIES, health_label

# ── Config ────────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Food Health & Spending Dashboard",
    page_icon="🥗",
    layout="wide",
)

# ── Password gate ─────────────────────────────────────────────────────────────
def _check_password():
    pwd = st.secrets.get("APP_PASSWORD", "")
    if not pwd:
        return True  # no password set — local dev mode
    if st.session_state.get("authenticated"):
        return True
    st.title("🥗 Food Dashboard")
    entered = st.text_input("Password", type="password")
    if st.button("Sign in"):
        if entered == pwd:
            st.session_state["authenticated"] = True
            st.rerun()
        else:
            st.error("Incorrect password")
    st.stop()

_check_password()

DATA_DIR  = Path(__file__).parent / "data"
ITEMS_CSV    = DATA_DIR / "items.csv"
RECEIPTS_CSV = DATA_DIR / "receipts.csv"

CAT_COLORS = {name: d["color"] for name, d in CATEGORIES.items()}
CAT_COLORS["Sonstiges"] = "#90A4AE"

SCORE_COLORS = {
    "Very Healthy":  "#2E7D32",
    "Healthy":       "#558B2F",
    "Moderate":      "#F57F17",
    "Unhealthy":     "#E65100",
    "Non-Food":      "#546E7A",
    "Unknown":       "#9E9E9E",
}


def score_to_label(score: int) -> str:
    if score >= 8:  return "Very Healthy"
    if score >= 6:  return "Healthy"
    if score >= 4:  return "Moderate"
    if score >= 2:  return "Unhealthy"
    if score == 0:  return "Non-Food"
    return "Unknown"


# ── Load data ─────────────────────────────────────────────────────────────────
@st.cache_data(ttl=3600)   # Re-reads CSV at most once per hour
def load_data():
    if not ITEMS_CSV.exists() or not RECEIPTS_CSV.exists():
        return None, None
    # Pass file modification time so cache invalidates when CSV changes
    _ = ITEMS_CSV.stat().st_mtime
    items    = pd.read_csv(ITEMS_CSV,    parse_dates=["date"])
    receipts = pd.read_csv(RECEIPTS_CSV, parse_dates=["date"])
    items["health_label"] = items["health_score"].apply(score_to_label)
    items["month"]  = items["date"].dt.to_period("M").astype(str)
    items["week"]   = items["date"].dt.to_period("W").apply(lambda p: p.start_time)
    receipts["month"] = receipts["date"].dt.to_period("M").astype(str)
    return items, receipts


items, receipts = load_data()

# ── Header ────────────────────────────────────────────────────────────────────
st.title("🥗 Food Health & Spending Dashboard")
stores_in_data = sorted(items["store"].unique().tolist()) if items is not None else []
st.caption("Receipts · " + " & ".join(stores_in_data) + " · Mainz-Kostheim")

if items is None:
    st.error(
        "No data found. Run `python extract_receipts.py` first to process your receipts."
    )
    st.stop()

# ── Sidebar filters ───────────────────────────────────────────────────────────
with st.sidebar:
    st.header("Filters")

    stores = ["All"] + sorted(items["store"].unique().tolist())
    sel_store = st.selectbox("Store", stores)

    months = sorted(items["month"].unique().tolist())
    sel_months = st.multiselect("Month(s)", months, default=months)

    st.divider()
    st.markdown("**Health Score Legend**")
    for label, color in SCORE_COLORS.items():
        st.markdown(f"<span style='color:{color}'>■</span> {label}", unsafe_allow_html=True)
    st.divider()
    if ITEMS_CSV.exists():
        import datetime
        mtime = ITEMS_CSV.stat().st_mtime
        updated = datetime.datetime.fromtimestamp(mtime).strftime("%d %b %Y %H:%M")
        st.caption(f"Data last updated: {updated}")
    if st.button("Reload data"):
        st.cache_data.clear()
        st.rerun()

    st.divider()
    IS_CLOUD = not (Path(__file__).parent / "credentials.json").exists()
    if IS_CLOUD:
        st.caption("🌐 Cloud mode — data updates automatically via weekly sync.")
    else:
        st.markdown("**Sync & Update**")
    if not IS_CLOUD and st.button("🔄 Pull from Google Drive + Refresh", use_container_width=True):
        status = st.empty()
        log_lines = []

        def _run(script, label):
            status.info(f"⏳ {label}…")
            result = subprocess.run(
                [sys.executable, "-X", "utf8", str(Path(__file__).parent / script)],
                capture_output=True, text=True, encoding="utf-8", errors="replace",
            )
            out = (result.stdout + result.stderr).strip()
            log_lines.append(f"**{label}**\n```\n{out}\n```")
            return result.returncode == 0

        ok_sync    = _run("sync_from_drive.py", "Syncing Google Drive")
        ok_extract = _run("extract_receipts.py", "Extracting receipts")

        st.cache_data.clear()
        status.empty()

        if ok_sync and ok_extract:
            st.success("✅ Done! Data refreshed.")
        else:
            st.warning("⚠️ Finished with errors — see log below.")

        with st.expander("📋 Run log", expanded=not (ok_sync and ok_extract)):
            for block in log_lines:
                st.markdown(block)

# ── Apply filters ─────────────────────────────────────────────────────────────
df = items.copy()
if sel_store != "All":
    df = df[df["store"] == sel_store]
if sel_months:
    df = df[df["month"].isin(sel_months)]

df_receipts = receipts.copy()
if sel_store != "All":
    df_receipts = df_receipts[df_receipts["store"] == sel_store]
if sel_months:
    df_receipts = df_receipts[df_receipts["month"].isin(sel_months)]

# Food items only (exclude Non-Food from health metrics)
food_df = df[df["health_score"] > 0]

# ── KPI row ───────────────────────────────────────────────────────────────────
col1, col2, col3, col4, col5 = st.columns(5)

total_spend   = df_receipts["total"].sum()
avg_per_shop  = df_receipts["total"].mean()
num_trips     = len(df_receipts)
avg_score     = food_df["health_score"].mean() if len(food_df) else 0
healthy_pct   = (
    len(food_df[food_df["health_score"] >= 6]) / len(food_df) * 100
    if len(food_df) else 0
)

col1.metric("Total Spending", f"€{total_spend:.2f}")
col2.metric("Avg. per Trip", f"€{avg_per_shop:.2f}")
col3.metric("Shopping Trips", num_trips)
col4.metric("Avg. Health Score", f"{avg_score:.1f} / 10")
col5.metric("Healthy Items %", f"{healthy_pct:.0f}%")

st.divider()

# ── Row 1: Health gauge + Health breakdown ────────────────────────────────────
row1_l, row1_r = st.columns([1, 2])

with row1_l:
    st.subheader("Overall Health Score")
    fig_gauge = go.Figure(go.Indicator(
        mode="gauge+number+delta",
        value=avg_score,
        delta={"reference": 5, "increasing": {"color": "#2E7D32"}},
        gauge={
            "axis": {"range": [0, 10], "tickwidth": 1},
            "bar": {"color": "#2E7D32" if avg_score >= 6 else
                             "#F57F17" if avg_score >= 4 else "#E65100"},
            "steps": [
                {"range": [0, 2],  "color": "#FFEBEE"},
                {"range": [2, 4],  "color": "#FFF3E0"},
                {"range": [4, 6],  "color": "#FFFDE7"},
                {"range": [6, 8],  "color": "#F1F8E9"},
                {"range": [8, 10], "color": "#E8F5E9"},
            ],
            "threshold": {"line": {"color": "black", "width": 2}, "value": 6},
        },
        title={"text": "out of 10"},
    ))
    fig_gauge.update_layout(height=280, margin=dict(t=30, b=0, l=20, r=20))
    st.plotly_chart(fig_gauge, use_container_width=True)

with row1_r:
    st.subheader("Spending by Health Category")
    hl_spend = (
        food_df.groupby("health_label")["price"]
        .sum()
        .reset_index()
        .rename(columns={"price": "spend", "health_label": "category"})
    )
    order = ["Very Healthy", "Healthy", "Moderate", "Unhealthy"]
    hl_spend["category"] = pd.Categorical(hl_spend["category"], categories=order, ordered=True)
    hl_spend = hl_spend.sort_values("category")
    fig_hl = px.bar(
        hl_spend, x="category", y="spend",
        color="category",
        color_discrete_map=SCORE_COLORS,
        text_auto=".2f",
        labels={"spend": "€ Spent", "category": ""},
    )
    fig_hl.update_layout(height=280, showlegend=False, margin=dict(t=10, b=0))
    fig_hl.update_traces(textposition="outside")
    st.plotly_chart(fig_hl, use_container_width=True)

# ── Row 2: Monthly spending ───────────────────────────────────────────────────
st.subheader("Monthly Grocery Spending")

monthly = (
    df_receipts.groupby(["month", "store"])["total"]
    .sum()
    .reset_index()
)
monthly_total = (
    df_receipts.groupby("month")["total"]
    .sum()
    .reset_index()
    .rename(columns={"total": "total_spend"})
)

fig_monthly = make_subplots(specs=[[{"secondary_y": False}]])
colors_store = {"HIT": "#1565C0", "Lidl": "#E53935", "Restaurant": "#7B1FA2"}

for store in monthly["store"].unique():
    sd = monthly[monthly["store"] == store]
    fig_monthly.add_trace(go.Bar(
        x=sd["month"], y=sd["total"],
        name=store,
        marker_color=colors_store.get(store, "#607D8B"),
        text=[f"€{v:.0f}" for v in sd["total"]],
        textposition="inside",
    ))

# Add total line
fig_monthly.add_trace(go.Scatter(
    x=monthly_total["month"],
    y=monthly_total["total_spend"],
    mode="lines+markers+text",
    name="Total",
    line=dict(color="#333", width=2, dash="dot"),
    text=[f"€{v:.0f}" for v in monthly_total["total_spend"]],
    textposition="top center",
))

fig_monthly.update_layout(
    barmode="stack",
    height=340,
    legend=dict(orientation="h", y=1.05),
    margin=dict(t=30, b=0),
    yaxis_title="€",
    xaxis_title="Month",
)
st.plotly_chart(fig_monthly, use_container_width=True)

# ── Row 3: Category breakdown (pie) + Weekly health trend ────────────────────
row3_l, row3_r = st.columns(2)

with row3_l:
    st.subheader("Spending by Food Category")
    cat_spend = (
        food_df.groupby("category")["price"]
        .sum()
        .reset_index()
        .sort_values("price", ascending=False)
    )
    fig_pie = px.pie(
        cat_spend, values="price", names="category",
        color="category",
        color_discrete_map=CAT_COLORS,
        hole=0.4,
    )
    fig_pie.update_traces(textposition="inside", textinfo="percent+label")
    fig_pie.update_layout(height=380, showlegend=False, margin=dict(t=20, b=0))
    st.plotly_chart(fig_pie, use_container_width=True)

with row3_r:
    st.subheader("Weekly Health Score Trend")
    weekly = (
        food_df.groupby("week")["health_score"]
        .mean()
        .reset_index()
        .rename(columns={"health_score": "avg_score"})
    )
    fig_trend = px.line(
        weekly, x="week", y="avg_score",
        markers=True,
        labels={"week": "", "avg_score": "Avg. Health Score"},
        color_discrete_sequence=["#2E7D32"],
    )
    fig_trend.add_hline(y=6, line_dash="dash", line_color="#F57F17",
                        annotation_text="Healthy threshold (6)")
    fig_trend.update_layout(
        height=380, margin=dict(t=20, b=0),
        yaxis=dict(range=[0, 10]),
    )
    st.plotly_chart(fig_trend, use_container_width=True)

# ── Row 4: Store comparison ───────────────────────────────────────────────────
st.subheader("Store Comparison — " + " vs ".join(stores_in_data))

col_s1, col_s2 = st.columns(2)

with col_s1:
    store_summary = (
        df.groupby("store")
        .agg(
            total_spend=("price", "sum"),
            avg_health=("health_score", lambda x: x[x > 0].mean()),
            items=("name", "count"),
        )
        .reset_index()
    )
    fig_stores = px.bar(
        store_summary, x="store", y="total_spend",
        color="store", color_discrete_map=colors_store,
        text_auto=".2f",
        labels={"total_spend": "Total € Spent", "store": ""},
        title="Total Spending per Store",
    )
    fig_stores.update_layout(height=300, showlegend=False, margin=dict(t=40, b=0))
    st.plotly_chart(fig_stores, use_container_width=True)

with col_s2:
    store_health = (
        food_df.groupby("store")["health_score"]
        .mean()
        .reset_index()
        .rename(columns={"health_score": "avg_score"})
    )
    fig_sh = px.bar(
        store_health, x="store", y="avg_score",
        color="store", color_discrete_map=colors_store,
        text_auto=".1f",
        labels={"avg_score": "Avg. Health Score", "store": ""},
        title="Avg. Health Score per Store",
    )
    fig_sh.add_hline(y=6, line_dash="dash", line_color="#F57F17")
    fig_sh.update_layout(height=300, showlegend=False, margin=dict(t=40, b=0),
                         yaxis=dict(range=[0, 10]))
    st.plotly_chart(fig_sh, use_container_width=True)

# ── Restaurant vs Grocery spending ───────────────────────────────────────────
if "Restaurant" in df["store"].values:
    st.subheader("Restaurant vs Grocery Spending")
    df_receipts_rg = df_receipts.copy()
    df_receipts_rg["type"] = df_receipts_rg["store"].apply(
        lambda s: "Restaurant" if s == "Restaurant" else "Grocery"
    )
    rg_monthly = (
        df_receipts_rg.groupby(["month", "type"])["total"]
        .sum().reset_index()
    )
    fig_rg = px.bar(
        rg_monthly, x="month", y="total", color="type",
        barmode="group",
        color_discrete_map={"Grocery": "#1565C0", "Restaurant": "#7B1FA2"},
        text_auto=".0f",
        labels={"total": "€ Spent", "month": "Month", "type": ""},
    )
    fig_rg.update_layout(height=300, margin=dict(t=10, b=0))
    st.plotly_chart(fig_rg, use_container_width=True)

# ── Row 5: Healthy vs Unhealthy ratio over months ─────────────────────────────
st.subheader("Healthy vs. Unhealthy Spending Over Time")

food_monthly = food_df.copy()
food_monthly["is_healthy"] = food_monthly["health_score"] >= 6
monthly_split = (
    food_monthly.groupby(["month", "is_healthy"])["price"]
    .sum()
    .reset_index()
)
monthly_split["label"] = monthly_split["is_healthy"].map({True: "Healthy (≥6)", False: "Unhealthy (<6)"})

fig_split = px.bar(
    monthly_split, x="month", y="price",
    color="label",
    barmode="stack",
    color_discrete_map={"Healthy (≥6)": "#2E7D32", "Unhealthy (<6)": "#E65100"},
    text_auto=".0f",
    labels={"price": "€ Spent", "month": "Month", "label": ""},
)
fig_split.update_layout(height=320, margin=dict(t=10, b=0))
st.plotly_chart(fig_split, use_container_width=True)

# ── Row 6: Top purchased items ────────────────────────────────────────────────
st.subheader("Most Purchased Items")

col_t1, col_t2 = st.columns(2)

with col_t1:
    st.markdown("**By Total Spend (€)**")
    top_spend = (
        food_df.groupby(["name", "category", "health_score"])["price"]
        .sum()
        .reset_index()
        .sort_values("price", ascending=False)
        .head(15)
    )
    top_spend["health_label"] = top_spend["health_score"].apply(score_to_label)
    fig_top = px.bar(
        top_spend, x="price", y="name",
        orientation="h",
        color="health_label",
        color_discrete_map=SCORE_COLORS,
        text_auto=".2f",
        labels={"price": "€ Total", "name": ""},
    )
    fig_top.update_layout(height=420, showlegend=False, margin=dict(t=10, b=0),
                          yaxis={"categoryorder": "total ascending"})
    st.plotly_chart(fig_top, use_container_width=True)

with col_t2:
    st.markdown("**By Frequency (# times bought)**")
    top_freq = (
        food_df.groupby(["name", "category", "health_score"])
        .size()
        .reset_index(name="count")
        .sort_values("count", ascending=False)
        .head(15)
    )
    top_freq["health_label"] = top_freq["health_score"].apply(score_to_label)
    fig_freq = px.bar(
        top_freq, x="count", y="name",
        orientation="h",
        color="health_label",
        color_discrete_map=SCORE_COLORS,
        text_auto="d",
        labels={"count": "# Purchases", "name": ""},
    )
    fig_freq.update_layout(height=420, showlegend=False, margin=dict(t=10, b=0),
                           yaxis={"categoryorder": "total ascending"})
    st.plotly_chart(fig_freq, use_container_width=True)

# ── Row 7: Raw data explorer ──────────────────────────────────────────────────
with st.expander("🔍 Browse all items"):
    show_df = df[["date", "store", "name", "category", "health_score",
                  "health_label", "price", "quantity"]].copy()
    show_df["date"] = show_df["date"].dt.strftime("%Y-%m-%d")
    show_df = show_df.sort_values("date", ascending=False)
    st.dataframe(show_df, use_container_width=True, height=400)

with st.expander("📋 Monthly summary table"):
    monthly_summary = (
        df_receipts.groupby("month")
        .agg(trips=("receipt_id", "count"), total=("total", "sum"), avg_trip=("total", "mean"))
        .reset_index()
    )
    monthly_summary["total"] = monthly_summary["total"].map("€{:.2f}".format)
    monthly_summary["avg_trip"] = monthly_summary["avg_trip"].map("€{:.2f}".format)
    monthly_summary.columns = ["Month", "Trips", "Total Spend", "Avg/Trip"]
    st.dataframe(monthly_summary, use_container_width=True)

st.divider()
if receipts is not None and len(receipts):
    date_range = f"{receipts['date'].min().strftime('%b %Y')} – {receipts['date'].max().strftime('%b %Y')}"
else:
    date_range = "–"
st.caption(f"Built with Streamlit · Data from {' & '.join(stores_in_data)} · {date_range}")
