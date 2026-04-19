"""
UK bank holidays from the official gov.uk JSON API
Nithin Arisetty, 2024

Clean, official, and free. Covers England/Wales, Scotland, Northern Ireland separately
which is exactly what we need — bank holidays differ by nation and that affects
venue demand differently across the Funstation estate.
"""

import requests
import pandas as pd
import os

API_URL = "https://www.gov.uk/bank-holidays.json"

DIVISION_TO_REGION = {
    "england-and-wales": "England/Wales",
    "scotland": "Scotland",
    "northern-ireland": "Northern Ireland",
}


def fetch_bank_holidays() -> pd.DataFrame:
    print("Fetching bank holidays from gov.uk API...")
    r = requests.get(API_URL, timeout=15)
    r.raise_for_status()
    data = r.json()

    rows = []
    for division, info in data.items():
        region_label = DIVISION_TO_REGION.get(division, division)
        for event in info.get("events", []):
            rows.append({
                "region": region_label,
                "holiday_name": event["title"],
                "date": pd.to_datetime(event["date"]),
                "notes": event.get("notes", ""),
                "bunting": event.get("bunting", False),
            })

    bh_df = pd.DataFrame(rows)
    bh_df["year"] = bh_df["date"].dt.year
    # only 2025 and 2026 for this analysis
    bh_df = bh_df[bh_df["year"].isin([2025, 2026])].reset_index(drop=True)
    bh_df["week_number"] = bh_df["date"].dt.isocalendar().week.astype(int)
    bh_df["iso_year"] = bh_df["date"].dt.isocalendar().year.astype(int)

    print(f"  Got {len(bh_df)} bank holidays across {bh_df['region'].nunique()} regions")
    return bh_df


if __name__ == "__main__":
    out_dir = os.path.join(os.path.dirname(__file__), "processed")
    os.makedirs(out_dir, exist_ok=True)
    bh_df = fetch_bank_holidays()
    out_path = os.path.join(out_dir, "bank_holidays.csv")
    bh_df.to_csv(out_path, index=False)
    print(f"Saved to {out_path}")
    print(bh_df.to_string())
