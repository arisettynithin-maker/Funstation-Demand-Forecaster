"""
Funstation Demand Forecaster — Streamlit App
Nithin Arisetty, 2024

4-page app for visualising UK school holiday demand patterns across Funstation
venue regions. Built to demonstrate what a finance analyst with a data engineering
background can put together for a leisure/FEC operator.

Data is loaded from the processed CSVs in data/processed/. If they don't exist
yet, the app runs the pipeline first (takes ~30s on first load).
"""

import os
import sys
import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from io import StringIO
import io

# make sure we can import from the data/ directory
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(ROOT, "data", "processed")
sys.path.insert(0, os.path.join(ROOT, "data"))

st.set_page_config(
    page_title="Funstation Demand Forecaster",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="expanded",
)

FUNSTATION_ORANGE = "#FF6B35"
DARK_BG = "#1A1A2E"
MID_BG = "#16213E"

ALL_REGIONS = [
    "England - North",
    "England - Midlands",
    "England - South",
    "England - London",
    "Wales",
    "Scotland",
    "Northern Ireland",
]


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

@st.cache_data(ttl=3600)
def load_demand_index() -> pd.DataFrame:
    path = os.path.join(DATA_DIR, "demand_index.csv")
    if not os.path.exists(path):
        with st.spinner("First run — building demand index (this takes ~30s)..."):
            from build_demand_index import build_full_demand_index
            os.makedirs(DATA_DIR, exist_ok=True)
            df = build_full_demand_index()
            df.to_csv(path, index=False)
            return df
    df = pd.read_csv(path, parse_dates=["week_start", "week_end"])
    return df


@st.cache_data(ttl=3600)
def load_bank_holidays() -> pd.DataFrame:
    path = os.path.join(DATA_DIR, "bank_holidays.csv")
    if not os.path.exists(path):
        from fetch_bank_holidays import fetch_bank_holidays
        bh_df = fetch_bank_holidays()
        bh_df.to_csv(path, index=False)
        return bh_df
    return pd.read_csv(path, parse_dates=["date"])


@st.cache_data(ttl=3600)
def load_term_dates() -> pd.DataFrame:
    path = os.path.join(DATA_DIR, "term_dates.csv")
    if not os.path.exists(path):
        from fetch_term_dates import build_all_term_dates
        hols_df = build_all_term_dates()
        hols_df.to_csv(path, index=False)
        return hols_df
    return pd.read_csv(path, parse_dates=["start_date", "end_date"])


def apply_filters(df: pd.DataFrame, regions: list, year: int, holiday_filter: str) -> pd.DataFrame:
    filtered = df[df["region"].isin(regions) & (df["iso_year"] == year)].copy()
    if holiday_filter == "School Holidays Only":
        filtered = filtered[filtered["is_school_holiday"] == True]
    elif holiday_filter == "Bank Holidays Only":
        filtered = filtered[filtered["is_bank_holiday_week"] == True]
    return filtered


def df_to_csv_bytes(df: pd.DataFrame) -> bytes:
    return df.to_csv(index=False).encode("utf-8")


# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------

def render_sidebar():
    with st.sidebar:
        st.markdown(
            f"<h2 style='color:{FUNSTATION_ORANGE}'>🎯 Funstation Demand Forecaster</h2>",
            unsafe_allow_html=True,
        )
        st.markdown("---")
        st.subheader("Filters")

        selected_regions = st.multiselect(
            "Venue Regions",
            options=ALL_REGIONS,
            default=ALL_REGIONS,
            help="Filter by Funstation venue region",
        )
        if not selected_regions:
            selected_regions = ALL_REGIONS

        selected_year = st.selectbox("Year", options=[2025, 2026], index=0)

        holiday_filter = st.radio(
            "Holiday Type",
            options=["All", "School Holidays Only", "Bank Holidays Only"],
            index=0,
        )

        st.markdown("---")
        st.markdown(
            "<small style='color:#888'>Built by Nithin Arisetty<br>"
            "Senior BI Analyst | Amazon UK → FEC</small>",
            unsafe_allow_html=True,
        )

    return selected_regions, selected_year, holiday_filter


# ---------------------------------------------------------------------------
# Page 1: National Demand Overview
# ---------------------------------------------------------------------------

def page_overview(demand_df: pd.DataFrame, regions: list, year: int, holiday_filter: str):
    st.title("National Demand Overview")
    st.markdown(
        "Weekly demand index across all regions, combining school holiday periods, "
        "bank holidays, and BRC footfall trend data."
    )

    filtered = apply_filters(demand_df, regions, year, holiday_filter)

    if filtered.empty:
        st.warning("No data for current filters.")
        return

    # --- Metric cards ---
    peak_row = filtered.loc[filtered["demand_index"].idxmax()]
    avg_uplift = filtered["demand_index"].mean()
    weeks_above_threshold = (filtered["demand_index"] >= 1.5).sum()
    highest_region = filtered.groupby("region")["demand_index"].mean().idxmax()

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric(
            "Peak Week",
            peak_row["week_start"].strftime("%d %b %Y") if hasattr(peak_row["week_start"], "strftime") else str(peak_row["week_start"])[:10],
            f"Week {int(peak_row['week_number'])}",
        )
    with col2:
        st.metric("Highest Demand Region", highest_region)
    with col3:
        st.metric("Avg Demand Index", f"{avg_uplift:.2f}x", "vs 1.0 baseline")
    with col4:
        st.metric("Weeks Above 1.5x", f"{weeks_above_threshold}", "staffing trigger weeks")

    st.markdown("---")

    # --- Heatmap ---
    st.subheader("Demand Index Heatmap — Week × Region")
    heatmap_df = filtered.pivot_table(
        index="region", columns="week_number", values="demand_index", aggfunc="mean"
    ).fillna(0)

    fig_hm = go.Figure(
        data=go.Heatmap(
            z=heatmap_df.values,
            x=[f"W{c}" for c in heatmap_df.columns],
            y=heatmap_df.index.tolist(),
            colorscale=[
                [0, MID_BG],
                [0.3, "#1E4D8C"],
                [0.6, "#FF8C00"],
                [1.0, FUNSTATION_ORANGE],
            ],
            zmin=0.8,
            zmax=3.0,
            colorbar=dict(title="Demand Index"),
        )
    )
    fig_hm.update_layout(
        paper_bgcolor=DARK_BG,
        plot_bgcolor=DARK_BG,
        font_color="#EAEAEA",
        height=380,
        margin=dict(l=20, r=20, t=30, b=20),
        xaxis=dict(tickfont=dict(size=9)),
    )
    st.plotly_chart(fig_hm, use_container_width=True)
    st.caption(
        "Orange = peak demand weeks. Gaps in Scotland around week 27–33 reflect their earlier "
        "summer holiday window vs England's later July–August peak. These mismatches are operationally "
        "important — you can't run a single national staffing plan."
    )

    st.markdown("---")

    # --- National top 10 bar chart ---
    st.subheader("Top 10 Peak Weeks (National Average)")
    top10 = (
        filtered.groupby(["week_number", "week_start"])["demand_index"]
        .mean()
        .reset_index()
        .nlargest(10, "demand_index")
        .sort_values("demand_index", ascending=True)
    )
    top10["label"] = top10["week_start"].apply(
        lambda x: x.strftime("%d %b") if hasattr(x, "strftime") else str(x)[:10]
    )

    fig_bar = go.Figure(
        go.Bar(
            x=top10["demand_index"],
            y=top10["label"],
            orientation="h",
            marker_color=FUNSTATION_ORANGE,
            text=[f"{v:.2f}x" for v in top10["demand_index"]],
            textposition="outside",
        )
    )
    fig_bar.add_vline(x=1.5, line_dash="dash", line_color="#888", annotation_text="1.5x threshold")
    fig_bar.update_layout(
        paper_bgcolor=DARK_BG,
        plot_bgcolor=DARK_BG,
        font_color="#EAEAEA",
        height=380,
        xaxis_title="Average Demand Index",
        yaxis_title="",
        margin=dict(l=20, r=60, t=20, b=20),
    )
    st.plotly_chart(fig_bar, use_container_width=True)
    st.caption("Averaged across all selected regions. Summer and Easter dominate nationally, but the exact week varies by region.")

    st.markdown("---")
    st.download_button(
        "⬇ Download Filtered Data (CSV)",
        data=df_to_csv_bytes(filtered),
        file_name=f"demand_overview_{year}.csv",
        mime="text/csv",
    )


# ---------------------------------------------------------------------------
# Page 2: Region Deep-Dive
# ---------------------------------------------------------------------------

def page_region_deepdive(demand_df: pd.DataFrame, regions: list, year: int, holiday_filter: str):
    st.title("Region Deep-Dive")
    st.markdown("Weekly demand index by region with threshold markers and top peak weeks.")

    filtered = apply_filters(demand_df, regions, year, holiday_filter)
    if filtered.empty:
        st.warning("No data for current filters.")
        return

    # --- Line chart ---
    st.subheader("Weekly Demand Index by Region")
    fig_line = go.Figure()
    for region in filtered["region"].unique():
        r_df = filtered[filtered["region"] == region].sort_values("week_start")
        fig_line.add_trace(
            go.Scatter(
                x=r_df["week_start"],
                y=r_df["demand_index"],
                mode="lines",
                name=region,
                line=dict(width=2),
                hovertemplate="%{y:.2f}x<br>%{x|%d %b}<extra>" + region + "</extra>",
            )
        )

    # threshold lines
    fig_line.add_hline(y=1.0, line_dash="dot", line_color="#555", annotation_text="1.0x baseline")
    fig_line.add_hline(y=1.5, line_dash="dash", line_color=FUNSTATION_ORANGE, annotation_text="1.5x staff trigger")

    fig_line.update_layout(
        paper_bgcolor=DARK_BG,
        plot_bgcolor=DARK_BG,
        font_color="#EAEAEA",
        height=420,
        yaxis_title="Demand Index",
        xaxis_title="",
        legend=dict(bgcolor=MID_BG, bordercolor="#333"),
        margin=dict(l=20, r=20, t=30, b=20),
        hovermode="x unified",
    )
    st.plotly_chart(fig_line, use_container_width=True)
    st.caption(
        "The dashed orange line at 1.5x is the staffing trigger threshold. "
        "Weeks above it need additional staff regardless of which region's calendar drives it."
    )

    st.markdown("---")

    # --- Top 10 peak weeks table ---
    st.subheader("Top 10 Peak Weeks per Region")
    top_weeks = (
        filtered.sort_values("demand_index", ascending=False)
        .groupby("region")
        .head(10)
        .sort_values(["region", "demand_index"], ascending=[True, False])
    )
    display_cols = ["region", "week_start", "week_end", "demand_index", "is_school_holiday", "is_bank_holiday_week"]
    top_display = top_weeks[display_cols].copy()
    top_display.columns = ["Region", "Week Start", "Week End", "Demand Index", "School Hols", "Bank Hol Week"]
    top_display["Demand Index"] = top_display["Demand Index"].round(2)
    top_display["Week Start"] = pd.to_datetime(top_display["Week Start"]).dt.strftime("%d %b %Y")
    top_display["Week End"] = pd.to_datetime(top_display["Week End"]).dt.strftime("%d %b %Y")
    st.dataframe(top_display, use_container_width=True, hide_index=True)

    st.download_button(
        "⬇ Download Region Data (CSV)",
        data=df_to_csv_bytes(top_weeks),
        file_name=f"region_deepdive_{year}.csv",
        mime="text/csv",
    )


# ---------------------------------------------------------------------------
# Page 3: Holiday Calendar View
# ---------------------------------------------------------------------------

def page_holiday_calendar(demand_df: pd.DataFrame, term_dates_df: pd.DataFrame, regions: list, year: int):
    st.title("Holiday Calendar View")
    st.markdown("School holiday periods by region, colour-coded by type. Compare two regions side-by-side.")

    col_a, col_b = st.columns(2)
    with col_a:
        region_left = st.selectbox("Left Region", options=regions, index=0)
    with col_b:
        right_idx = min(1, len(regions) - 1)
        region_right = st.selectbox("Right Region", options=regions, index=right_idx)

    COLOR_MAP = {
        "main_holiday": "#FF6B35",
        "half_term": "#4ECDC4",
        "bank_holiday": "#FFE66D",
    }

    def render_calendar(region_name: str):
        region_hols = term_dates_df[
            (term_dates_df["region"] == region_name)
            & (pd.to_datetime(term_dates_df["start_date"]).dt.year.isin([year, year - 1]))
        ].copy()
        # filter to the target year approximately
        region_hols = region_hols[
            (pd.to_datetime(region_hols["end_date"]) >= pd.Timestamp(f"{year}-01-01"))
            & (pd.to_datetime(region_hols["start_date"]) <= pd.Timestamp(f"{year}-12-31"))
        ]
        st.markdown(f"**{region_name}** — {year}")
        if region_hols.empty:
            st.info("No holiday data for this region/year.")
            return pd.DataFrame()

        fig = go.Figure()
        for _, row in region_hols.iterrows():
            color = COLOR_MAP.get(row["holiday_type"], "#888")
            fig.add_trace(
                go.Bar(
                    x=[(pd.Timestamp(row["end_date"]) - pd.Timestamp(row["start_date"])).days + 1],
                    y=[row["holiday_type"]],
                    base=[pd.Timestamp(row["start_date"]).timestamp() * 1000],
                    orientation="h",
                    marker_color=color,
                    name=row["holiday_name"],
                    hovertemplate=f"<b>{row['holiday_name']}</b><br>{row['start_date']} → {row['end_date']}<extra></extra>",
                    showlegend=False,
                )
            )

        # x-axis as dates
        start_ts = pd.Timestamp(f"{year}-01-01").timestamp() * 1000
        end_ts = pd.Timestamp(f"{year}-12-31").timestamp() * 1000
        fig.update_layout(
            barmode="overlay",
            paper_bgcolor=DARK_BG,
            plot_bgcolor=DARK_BG,
            font_color="#EAEAEA",
            height=250,
            xaxis=dict(
                range=[start_ts, end_ts],
                tickformat="%b",
                type="date",
            ),
            yaxis=dict(categoryorder="total ascending"),
            margin=dict(l=10, r=10, t=10, b=30),
        )
        # convert base back to dates for plotly
        fig2 = px.timeline(
            region_hols,
            x_start="start_date",
            x_end="end_date",
            y="holiday_type",
            color="holiday_type",
            hover_name="holiday_name",
            color_discrete_map=COLOR_MAP,
            range_x=[f"{year}-01-01", f"{year}-12-31"],
        )
        fig2.update_layout(
            paper_bgcolor=DARK_BG,
            plot_bgcolor=DARK_BG,
            font_color="#EAEAEA",
            height=250,
            showlegend=True,
            legend=dict(bgcolor=MID_BG, font=dict(size=10)),
            margin=dict(l=10, r=10, t=10, b=30),
            xaxis_title="",
            yaxis_title="",
        )
        st.plotly_chart(fig2, use_container_width=True)
        return region_hols

    col1, col2 = st.columns(2)
    with col1:
        left_hols = render_calendar(region_left)
    with col2:
        right_hols = render_calendar(region_right)

    st.markdown("---")
    st.subheader("Overlap Analysis")
    if not left_hols.empty and not right_hols.empty:
        # find weeks where both regions are on holiday
        left_weeks = set()
        right_weeks = set()
        for _, row in left_hols.iterrows():
            dates = pd.date_range(row["start_date"], row["end_date"])
            left_weeks.update([d.isocalendar()[:2] for d in dates])
        for _, row in right_hols.iterrows():
            dates = pd.date_range(row["start_date"], row["end_date"])
            right_weeks.update([d.isocalendar()[:2] for d in dates])

        overlap = left_weeks & right_weeks
        only_left = left_weeks - right_weeks
        only_right = right_weeks - left_weeks

        oc1, oc2, oc3 = st.columns(3)
        oc1.metric("Shared Holiday Weeks", len(overlap), "both regions on hols")
        oc2.metric(f"Only {region_left[:15]}", len(only_left), "weeks")
        oc3.metric(f"Only {region_right[:15]}", len(only_right), "weeks")
        st.caption(
            f"Shared weeks are the best windows for joint campaigns targeting both regions. "
            f"{len(overlap)} weeks out of a possible ~52 share holiday status."
        )

    combined = pd.concat([left_hols, right_hols], ignore_index=True) if not left_hols.empty and not right_hols.empty else pd.DataFrame()
    if not combined.empty:
        st.download_button(
            "⬇ Download Calendar Data (CSV)",
            data=df_to_csv_bytes(combined),
            file_name=f"holiday_calendar_{region_left}_{region_right}_{year}.csv",
            mime="text/csv",
        )


# ---------------------------------------------------------------------------
# Page 4: Staffing Simulator
# ---------------------------------------------------------------------------

def page_staffing_simulator(demand_df: pd.DataFrame, regions: list, year: int):
    st.title("Staffing Simulator")
    st.markdown(
        "Model the additional headcount and labour cost for peak weeks. "
        "Adjust the inputs below to match your venue profile."
    )

    col1, col2, col3 = st.columns(3)
    with col1:
        baseline_staff = st.number_input(
            "Baseline Staff per Venue",
            min_value=5,
            max_value=200,
            value=25,
            step=1,
            help="Typical staff on a normal trading week",
        )
    with col2:
        hourly_wage = st.number_input(
            "Average Hourly Wage (£)",
            min_value=8.0,
            max_value=30.0,
            value=12.50,
            step=0.25,
        )
    with col3:
        hours_per_week = st.number_input(
            "Hours per Staff Member per Week",
            min_value=10,
            max_value=60,
            value=35,
            step=1,
        )

    st.markdown("---")

    filtered = demand_df[demand_df["region"].isin(regions) & (demand_df["iso_year"] == year)].copy()
    filtered = filtered[filtered["is_peak_week"] == True].copy()

    if filtered.empty:
        st.info("No peak weeks for selected regions and year.")
        return

    filtered["additional_staff_needed"] = np.ceil(
        baseline_staff * (filtered["demand_index"] - 1.0)
    ).astype(int)
    filtered["additional_staff_needed"] = filtered["additional_staff_needed"].clip(lower=0)
    filtered["additional_weekly_labour_cost"] = (
        filtered["additional_staff_needed"] * hourly_wage * hours_per_week
    ).round(2)
    filtered["total_staff_needed"] = baseline_staff + filtered["additional_staff_needed"]

    # summary cards
    sc1, sc2, sc3 = st.columns(3)
    sc1.metric("Total Peak Weeks", len(filtered))
    sc2.metric(
        "Max Additional Staff (single week)",
        int(filtered["additional_staff_needed"].max()),
    )
    sc3.metric(
        "Total Est. Additional Labour Cost",
        f"£{filtered['additional_weekly_labour_cost'].sum():,.0f}",
        "across all selected peak weeks",
    )

    st.markdown("---")
    st.subheader("Peak Week Staffing Plan")

    display = filtered[[
        "region", "week_start", "week_end", "demand_index",
        "additional_staff_needed", "total_staff_needed", "additional_weekly_labour_cost"
    ]].copy()
    display.columns = [
        "Region", "Week Start", "Week End", "Demand Index",
        "Additional Staff", "Total Staff", "Additional Cost (£)"
    ]
    display["Week Start"] = pd.to_datetime(display["Week Start"]).dt.strftime("%d %b %Y")
    display["Week End"] = pd.to_datetime(display["Week End"]).dt.strftime("%d %b %Y")
    display["Demand Index"] = display["Demand Index"].round(2)

    st.dataframe(display, use_container_width=True, hide_index=True)

    st.markdown("---")

    # cost bar chart by region
    cost_by_region = (
        filtered.groupby("region")["additional_weekly_labour_cost"]
        .sum()
        .reset_index()
        .sort_values("additional_weekly_labour_cost", ascending=True)
    )
    fig_cost = go.Figure(
        go.Bar(
            x=cost_by_region["additional_weekly_labour_cost"],
            y=cost_by_region["region"],
            orientation="h",
            marker_color=FUNSTATION_ORANGE,
            text=[f"£{v:,.0f}" for v in cost_by_region["additional_weekly_labour_cost"]],
            textposition="outside",
        )
    )
    fig_cost.update_layout(
        paper_bgcolor=DARK_BG,
        plot_bgcolor=DARK_BG,
        font_color="#EAEAEA",
        height=300,
        title="Additional Peak Labour Cost by Region",
        xaxis_title="Total Additional Labour Cost (£)",
        margin=dict(l=20, r=80, t=40, b=20),
    )
    st.plotly_chart(fig_cost, use_container_width=True)
    st.caption(
        "Based on demand_index - 1.0 = fraction of extra staff needed above baseline. "
        "Costs are indicative — doesn't include NI contributions, agency premiums, or management overhead."
    )

    st.markdown("---")
    st.download_button(
        "⬇ Download Staffing Plan (CSV)",
        data=df_to_csv_bytes(filtered),
        file_name=f"staffing_plan_{year}.csv",
        mime="text/csv",
        help="Download the full staffing plan as a CSV for sharing with venue managers",
    )


# ---------------------------------------------------------------------------
# Main app
# ---------------------------------------------------------------------------

def main():
    demand_df = load_demand_index()
    term_dates_df = load_term_dates()

    regions, year, holiday_filter = render_sidebar()

    page = st.sidebar.radio(
        "Page",
        ["National Overview", "Region Deep-Dive", "Holiday Calendar", "Staffing Simulator"],
        index=0,
    )

    if page == "National Overview":
        page_overview(demand_df, regions, year, holiday_filter)
    elif page == "Region Deep-Dive":
        page_region_deepdive(demand_df, regions, year, holiday_filter)
    elif page == "Holiday Calendar":
        page_holiday_calendar(demand_df, term_dates_df, regions, year)
    elif page == "Staffing Simulator":
        page_staffing_simulator(demand_df, regions, year)


if __name__ == "__main__":
    main()
