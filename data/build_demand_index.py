"""
Demand index builder — the main analytical engine
Nithin Arisetty, 2024

Combines term dates + bank holidays + BRC footfall into a weekly demand multiplier
for each region. The output is what drives both the Jupyter analysis and the
Streamlit app.

Weights:
  - School holiday week: 2.0x baseline
  - Bank holiday in week: 1.5x baseline
  - Footfall trend: continuous modifier (e.g. +5% footfall = 1.05x)
  Overlapping factors stack multiplicatively up to a cap.

I landed on these weights after comparing against Funstation's own stated
peak periods in their annual reports and LinkedIn posts about "record summer".
The 2x for school holidays is the dominant driver — everything else is modulation.
"""

import pandas as pd
import numpy as np
import os
import sys

# allow running from any directory
sys.path.insert(0, os.path.dirname(__file__))
from fetch_term_dates import build_all_term_dates
from fetch_bank_holidays import fetch_bank_holidays
from fetch_footfall import load_footfall_data

SCHOOL_HOLIDAY_WEIGHT = 2.0
BANK_HOLIDAY_WEIGHT = 1.5
MAX_DEMAND_INDEX = 3.5  # cap so outliers don't break the heatmap

# map our granular regions to the two BH calendars we have
REGION_TO_BH_CALENDAR = {
    "England - North": "England/Wales",
    "England - Midlands": "England/Wales",
    "England - South": "England/Wales",
    "England - London": "England/Wales",
    "Wales": "England/Wales",
    "Scotland": "Scotland",
    "Northern Ireland": "Northern Ireland",
}


def build_weekly_spine(years=(2025, 2026)) -> pd.DataFrame:
    """
    Generate a row per ISO week per region — this is the scaffold everything joins onto.
    ISO weeks are slightly awkward at year boundaries but they're standard.
    """
    all_regions = list(REGION_TO_BH_CALENDAR.keys())
    rows = []
    for year in years:
        # ISO year can have 52 or 53 weeks
        n_weeks = pd.Timestamp(f"{year}-12-28").isocalendar().week
        for week in range(1, int(n_weeks) + 1):
            week_start = _iso_to_date(year, week, 1)
            week_end = _iso_to_date(year, week, 7)
            for region in all_regions:
                rows.append({
                    "iso_year": year,
                    "week_number": week,
                    "week_start": week_start,
                    "week_end": week_end,
                    "region": region,
                })
    df = pd.DataFrame(rows)
    df["week_start"] = pd.to_datetime(df["week_start"])
    df["week_end"] = pd.to_datetime(df["week_end"])
    return df


def _iso_to_date(year: int, week: int, day: int) -> pd.Timestamp:
    """Convert ISO year/week/day to a date. day=1 is Monday."""
    return pd.Timestamp.fromisocalendar(year, week, day)


def flag_school_holidays(spine: pd.DataFrame, hols_df: pd.DataFrame) -> pd.DataFrame:
    """
    Mark each week as school holiday if it overlaps with any holiday period
    for that region. An overlap is defined as week_start <= end_date AND week_end >= start_date.
    Not the most elegant join but it's correct.
    """
    spine = spine.copy()
    spine["is_school_holiday"] = False

    for _, hol in hols_df.iterrows():
        if hol["holiday_type"] == "bank_holiday":
            continue
        mask = (
            (spine["region"] == hol["region"])
            & (spine["week_start"] <= hol["end_date"])
            & (spine["week_end"] >= hol["start_date"])
        )
        spine.loc[mask, "is_school_holiday"] = True

    return spine


def flag_bank_holidays(spine: pd.DataFrame, bh_df: pd.DataFrame) -> pd.DataFrame:
    """
    Similarly flag weeks containing at least one bank holiday.
    Map our regions to the three BH calendars first.
    """
    spine = spine.copy()
    spine["bh_calendar"] = spine["region"].map(REGION_TO_BH_CALENDAR)
    spine["is_bank_holiday_week"] = False
    spine["bank_holiday_count"] = 0

    for _, bh in bh_df.iterrows():
        mask = (
            (spine["bh_calendar"] == bh["region"])
            & (spine["week_start"] <= bh["date"])
            & (spine["week_end"] >= bh["date"])
        )
        spine.loc[mask, "is_bank_holiday_week"] = True
        spine.loc[mask, "bank_holiday_count"] += 1

    return spine


def attach_footfall(spine: pd.DataFrame, footfall_df: pd.DataFrame) -> pd.DataFrame:
    """
    Join monthly footfall modifier to each week by year + month.
    Use shopping_centre as the most relevant destination type for Funstation venues.
    TODO: could weight by venue-level destination type if we had that data
    """
    spine = spine.copy()
    spine["month_num"] = spine["week_start"].dt.month
    spine["year_for_join"] = spine["week_start"].dt.year

    sc_footfall = footfall_df[footfall_df["destination_type"] == "shopping_centre"][
        ["year", "month_num", "footfall_modifier"]
    ].drop_duplicates()

    spine = spine.merge(
        sc_footfall,
        left_on=["year_for_join", "month_num"],
        right_on=["year", "month_num"],
        how="left",
    )
    # fill any missing months with neutral modifier
    spine["footfall_modifier"] = spine["footfall_modifier"].fillna(1.0)
    return spine


def calculate_demand_index(spine: pd.DataFrame) -> pd.DataFrame:
    """
    The actual index formula. Multiplicative so that a bank holiday *during*
    school holidays compounds rather than just adding.
    """
    df = spine.copy()

    base = pd.Series(np.ones(len(df)), index=df.index)

    holiday_factor = df["is_school_holiday"].map({True: SCHOOL_HOLIDAY_WEIGHT, False: 1.0})
    bh_factor = df["is_bank_holiday_week"].map({True: BANK_HOLIDAY_WEIGHT, False: 1.0})

    # when both school holiday and BH overlap, use the max rather than multiply
    # (multiplying would give 3.0 which overstates — a BH within summer hols
    # doesn't double the demand, families are already there)
    combined_holiday = np.maximum(holiday_factor, bh_factor)

    df["demand_index"] = np.minimum(
        combined_holiday * df["footfall_modifier"],
        MAX_DEMAND_INDEX
    )
    df["demand_index"] = df["demand_index"].round(4)
    df["is_peak_week"] = df["demand_index"] >= 1.5

    return df


def build_full_demand_index() -> pd.DataFrame:
    print("Building demand index...")
    print("  Loading term dates...")
    hols_df = build_all_term_dates()
    print("  Loading bank holidays...")
    bh_df = fetch_bank_holidays()
    print("  Loading footfall data...")
    footfall_df = load_footfall_data()

    print("  Building weekly spine...")
    spine = build_weekly_spine(years=(2025, 2026))
    print(f"  Spine: {len(spine)} rows ({spine['region'].nunique()} regions × ~104 weeks)")

    spine = flag_school_holidays(spine, hols_df)
    spine = flag_bank_holidays(spine, bh_df)
    spine = attach_footfall(spine, footfall_df)
    demand_df = calculate_demand_index(spine)

    cols = [
        "iso_year", "week_number", "week_start", "week_end", "region",
        "is_school_holiday", "is_bank_holiday_week", "bank_holiday_count",
        "footfall_modifier", "demand_index", "is_peak_week",
    ]
    demand_df = demand_df[cols].sort_values(["region", "iso_year", "week_number"]).reset_index(drop=True)
    print(f"  Done. Peak weeks: {demand_df['is_peak_week'].sum()} / {len(demand_df)}")
    return demand_df


if __name__ == "__main__":
    out_dir = os.path.join(os.path.dirname(__file__), "processed")
    os.makedirs(out_dir, exist_ok=True)

    demand_df = build_full_demand_index()
    out_path = os.path.join(out_dir, "demand_index.csv")
    demand_df.to_csv(out_path, index=False)
    print(f"\nSaved to {out_path}")

    # quick sanity check
    top10 = (
        demand_df.groupby("region")
        .apply(lambda x: x.nlargest(3, "demand_index")[["week_start", "demand_index"]])
        .reset_index(level=1, drop=True)
    )
    print("\nTop 3 weeks per region:")
    print(top10.to_string())
