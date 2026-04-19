"""
School term date scraper — England, Scotland, Northern Ireland
Nithin Arisetty, 2024

Scrapes gov.uk / mygov.scot / nidirect and normalises into one clean DataFrame.
The regional split matters a lot for Funstation — Edinburgh and Northampton
don't share the same half-term calendar, which means you can't just look at
national averages for demand planning.
"""

import requests
from bs4 import BeautifulSoup
import pandas as pd
from datetime import datetime
import re
import os

HEADERS = {"User-Agent": "Mozilla/5.0 (research/data-collection)"}

ENGLAND_REGIONS = {
    "England - North": "north-east-england",
    "England - Midlands": "east-midlands",
    "England - South": "south-east-england",
    "England - London": "london",
    "Wales": "wales",
}


def fetch_england_wales_terms(region_label: str, slug: str) -> pd.DataFrame:
    """
    GOV.UK term date pages have a fairly consistent structure but the HTML
    varies a bit year to year. Using lxml parser for speed.
    """
    url = f"https://www.gov.uk/school-term-holiday-dates/{slug}"
    rows = []
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "lxml")
        # The dates are in definition lists or tables depending on the page version
        tables = soup.find_all("table")
        for table in tables:
            headers_row = table.find("thead")
            caption = table.find("caption")
            holiday_context = caption.get_text(strip=True) if caption else "Unknown"
            for row in table.find_all("tr"):
                cells = row.find_all(["td", "th"])
                if len(cells) >= 2:
                    name_text = cells[0].get_text(strip=True)
                    date_text = cells[1].get_text(strip=True) if len(cells) > 1 else ""
                    if not name_text or name_text.lower() in ["holiday", "term dates"]:
                        continue
                    parsed = _parse_date_range(date_text)
                    if parsed:
                        rows.append({
                            "region": region_label,
                            "holiday_name": name_text,
                            "start_date": parsed[0],
                            "end_date": parsed[1],
                            "holiday_type": _classify_holiday(name_text),
                        })
    except Exception as e:
        print(f"  [warn] England/Wales fetch failed for {region_label}: {e}")
        # fall back to hardcoded 2025/2026 data so the app still runs
        rows = _england_fallback(region_label)
    return pd.DataFrame(rows)


def fetch_scotland_terms() -> pd.DataFrame:
    """
    Scotland is totally separate — mygov.scot has a different URL and page layout.
    # scotland dates are in a different format, needed manual fix on first run
    """
    url = "https://www.mygov.scot/school-holidays"
    rows = []
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "lxml")
        tables = soup.find_all("table")
        for table in tables:
            for row in table.find_all("tr"):
                cells = row.find_all(["td", "th"])
                if len(cells) >= 2:
                    name_text = cells[0].get_text(strip=True)
                    date_text = cells[-1].get_text(strip=True)
                    if not name_text or name_text.lower() == "holiday":
                        continue
                    parsed = _parse_date_range(date_text)
                    if parsed:
                        rows.append({
                            "region": "Scotland",
                            "holiday_name": name_text,
                            "start_date": parsed[0],
                            "end_date": parsed[1],
                            "holiday_type": _classify_holiday(name_text),
                        })
    except Exception as e:
        print(f"  [warn] Scotland fetch failed: {e}")
        rows = _scotland_fallback()
    return pd.DataFrame(rows)


def fetch_northern_ireland_terms() -> pd.DataFrame:
    url = "https://www.nidirect.gov.uk/articles/school-term-holiday-dates"
    rows = []
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "lxml")
        tables = soup.find_all("table")
        for table in tables:
            for row in table.find_all("tr"):
                cells = row.find_all(["td", "th"])
                if len(cells) >= 2:
                    name_text = cells[0].get_text(strip=True)
                    date_text = cells[1].get_text(strip=True)
                    parsed = _parse_date_range(date_text)
                    if parsed and name_text:
                        rows.append({
                            "region": "Northern Ireland",
                            "holiday_name": name_text,
                            "start_date": parsed[0],
                            "end_date": parsed[1],
                            "holiday_type": _classify_holiday(name_text),
                        })
    except Exception as e:
        print(f"  [warn] Northern Ireland fetch failed: {e}")
        rows = _northern_ireland_fallback()
    return pd.DataFrame(rows)


def _parse_date_range(text: str):
    """Try a few common UK date formats. Hacky but works for gov.uk pages."""
    text = text.strip()
    # "Monday 21 July to Friday 1 September 2025"
    patterns = [
        r"(\d{1,2}\s+\w+\s+\d{4})\s+(?:to|-)\s+(\d{1,2}\s+\w+\s+\d{4})",
        r"(\w+\s+\d{1,2}\s+\w+)\s+(?:to|-)\s+(\w+\s+\d{1,2}\s+\w+\s+\d{4})",
        r"(\d{1,2}/\d{1,2}/\d{4})\s*[-–]\s*(\d{1,2}/\d{1,2}/\d{4})",
    ]
    for pat in patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            try:
                s = pd.to_datetime(m.group(1), dayfirst=True)
                e = pd.to_datetime(m.group(2), dayfirst=True)
                return s, e
            except Exception:
                continue
    # single date
    try:
        d = pd.to_datetime(text, dayfirst=True)
        return d, d
    except Exception:
        return None


def _classify_holiday(name: str) -> str:
    name_lower = name.lower()
    if "half" in name_lower:
        return "half_term"
    elif any(w in name_lower for w in ["christmas", "easter", "summer", "spring"]):
        return "main_holiday"
    elif "bank" in name_lower:
        return "bank_holiday"
    else:
        return "main_holiday"


# ---------------------------------------------------------------------------
# Fallback data — 2025 and 2026 term dates hardcoded so the app works offline
# Based on published gov.uk / LA calendars
# ---------------------------------------------------------------------------

def _england_fallback(region: str) -> list:
    # Generic England dates — LA variation is small enough this is fine for demo
    return [
        {"region": region, "holiday_name": "Easter 2025", "start_date": pd.Timestamp("2025-04-11"), "end_date": pd.Timestamp("2025-04-25"), "holiday_type": "main_holiday"},
        {"region": region, "holiday_name": "May Half Term 2025", "start_date": pd.Timestamp("2025-05-26"), "end_date": pd.Timestamp("2025-05-30"), "holiday_type": "half_term"},
        {"region": region, "holiday_name": "Summer 2025", "start_date": pd.Timestamp("2025-07-22"), "end_date": pd.Timestamp("2025-09-02"), "holiday_type": "main_holiday"},
        {"region": region, "holiday_name": "October Half Term 2025", "start_date": pd.Timestamp("2025-10-27"), "end_date": pd.Timestamp("2025-10-31"), "holiday_type": "half_term"},
        {"region": region, "holiday_name": "Christmas 2025", "start_date": pd.Timestamp("2025-12-22"), "end_date": pd.Timestamp("2026-01-02"), "holiday_type": "main_holiday"},
        {"region": region, "holiday_name": "Feb Half Term 2026", "start_date": pd.Timestamp("2026-02-16"), "end_date": pd.Timestamp("2026-02-20"), "holiday_type": "half_term"},
        {"region": region, "holiday_name": "Easter 2026", "start_date": pd.Timestamp("2026-04-02"), "end_date": pd.Timestamp("2026-04-17"), "holiday_type": "main_holiday"},
        {"region": region, "holiday_name": "May Half Term 2026", "start_date": pd.Timestamp("2026-05-25"), "end_date": pd.Timestamp("2026-05-29"), "holiday_type": "half_term"},
        {"region": region, "holiday_name": "Summer 2026", "start_date": pd.Timestamp("2026-07-21"), "end_date": pd.Timestamp("2026-09-01"), "holiday_type": "main_holiday"},
        {"region": region, "holiday_name": "October Half Term 2026", "start_date": pd.Timestamp("2026-10-26"), "end_date": pd.Timestamp("2026-10-30"), "holiday_type": "half_term"},
    ]


def _scotland_fallback() -> list:
    # Scotland has genuinely different dates — earlier summer, different Oct break
    return [
        {"region": "Scotland", "holiday_name": "Spring Break 2025", "start_date": pd.Timestamp("2025-04-07"), "end_date": pd.Timestamp("2025-04-18"), "holiday_type": "main_holiday"},
        {"region": "Scotland", "holiday_name": "May Day 2025", "start_date": pd.Timestamp("2025-05-05"), "end_date": pd.Timestamp("2025-05-05"), "holiday_type": "bank_holiday"},
        {"region": "Scotland", "holiday_name": "Summer 2025", "start_date": pd.Timestamp("2025-06-27"), "end_date": pd.Timestamp("2025-08-18"), "holiday_type": "main_holiday"},
        {"region": "Scotland", "holiday_name": "October Break 2025", "start_date": pd.Timestamp("2025-10-13"), "end_date": pd.Timestamp("2025-10-24"), "holiday_type": "half_term"},
        {"region": "Scotland", "holiday_name": "Christmas 2025", "start_date": pd.Timestamp("2025-12-22"), "end_date": pd.Timestamp("2026-01-05"), "holiday_type": "main_holiday"},
        {"region": "Scotland", "holiday_name": "Feb Break 2026", "start_date": pd.Timestamp("2026-02-09"), "end_date": pd.Timestamp("2026-02-13"), "holiday_type": "half_term"},
        {"region": "Scotland", "holiday_name": "Spring Break 2026", "start_date": pd.Timestamp("2026-04-06"), "end_date": pd.Timestamp("2026-04-17"), "holiday_type": "main_holiday"},
        {"region": "Scotland", "holiday_name": "Summer 2026", "start_date": pd.Timestamp("2026-06-26"), "end_date": pd.Timestamp("2026-08-17"), "holiday_type": "main_holiday"},
        {"region": "Scotland", "holiday_name": "October Break 2026", "start_date": pd.Timestamp("2026-10-12"), "end_date": pd.Timestamp("2026-10-23"), "holiday_type": "half_term"},
    ]


def _northern_ireland_fallback() -> list:
    return [
        {"region": "Northern Ireland", "holiday_name": "Easter 2025", "start_date": pd.Timestamp("2025-04-14"), "end_date": pd.Timestamp("2025-04-25"), "holiday_type": "main_holiday"},
        {"region": "Northern Ireland", "holiday_name": "May Half Term 2025", "start_date": pd.Timestamp("2025-05-26"), "end_date": pd.Timestamp("2025-05-30"), "holiday_type": "half_term"},
        {"region": "Northern Ireland", "holiday_name": "Summer 2025", "start_date": pd.Timestamp("2025-07-01"), "end_date": pd.Timestamp("2025-08-29"), "holiday_type": "main_holiday"},
        {"region": "Northern Ireland", "holiday_name": "October Half Term 2025", "start_date": pd.Timestamp("2025-10-27"), "end_date": pd.Timestamp("2025-10-31"), "holiday_type": "half_term"},
        {"region": "Northern Ireland", "holiday_name": "Christmas 2025", "start_date": pd.Timestamp("2025-12-22"), "end_date": pd.Timestamp("2026-01-02"), "holiday_type": "main_holiday"},
        {"region": "Northern Ireland", "holiday_name": "Easter 2026", "start_date": pd.Timestamp("2026-04-02"), "end_date": pd.Timestamp("2026-04-17"), "holiday_type": "main_holiday"},
        {"region": "Northern Ireland", "holiday_name": "Summer 2026", "start_date": pd.Timestamp("2026-07-01"), "end_date": pd.Timestamp("2026-08-28"), "holiday_type": "main_holiday"},
    ]


def build_all_term_dates() -> pd.DataFrame:
    print("Fetching term dates...")
    frames = []
    for label, slug in ENGLAND_REGIONS.items():
        print(f"  {label}...")
        frames.append(fetch_england_wales_terms(label, slug))
    print("  Scotland...")
    frames.append(fetch_scotland_terms())
    print("  Northern Ireland...")
    frames.append(fetch_northern_ireland_terms())

    df = pd.concat(frames, ignore_index=True)
    df = df.dropna(subset=["start_date", "end_date"])
    df["start_date"] = pd.to_datetime(df["start_date"])
    df["end_date"] = pd.to_datetime(df["end_date"])
    df = df.drop_duplicates(subset=["region", "holiday_name", "start_date"])
    df = df.sort_values(["region", "start_date"]).reset_index(drop=True)
    print(f"  Done — {len(df)} holiday periods across {df['region'].nunique()} regions")
    return df


if __name__ == "__main__":
    out_dir = os.path.join(os.path.dirname(__file__), "processed")
    os.makedirs(out_dir, exist_ok=True)
    hols_df = build_all_term_dates()
    out_path = os.path.join(out_dir, "term_dates.csv")
    hols_df.to_csv(out_path, index=False)
    print(f"Saved to {out_path}")
    print(hols_df.head(10).to_string())
