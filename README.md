# Funstation Demand Forecaster

![Python](https://img.shields.io/badge/Python-3.11-3776AB?style=flat&logo=python&logoColor=white)
![Streamlit](https://img.shields.io/badge/Streamlit-1.32-FF4B4B?style=flat&logo=streamlit&logoColor=white)
![Pandas](https://img.shields.io/badge/Pandas-2.2-150458?style=flat&logo=pandas&logoColor=white)
![Plotly](https://img.shields.io/badge/Plotly-5.20-3F4F75?style=flat&logo=plotly&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-green?style=flat)

> A regional demand forecasting tool for UK family entertainment centres — combining school holiday calendars, bank holidays, and BRC footfall data into a weekly demand index across all Funstation venue regions.

**Live demo → [Streamlit URL — add after deployment]**

---

## The problem

Funstation operates 14+ venues across England, Scotland, and Northern Ireland. Their revenue is almost entirely driven by school holidays, half-terms, and bank holiday weekends — but each region runs on a different term date calendar.

Scotland's summer holiday starts in late June. England's starts in late July. Northern Ireland's October half-term doesn't always align with England's. If you're planning staffing, pricing, or marketing spend from a national average, you're getting the timing wrong for most of your venues.

I built this after reading Funstation's annual reports and noticing there was no systematic way to view demand peaks regionally rather than nationally. The finance function almost certainly knows this problem exists — this is what a solution looks like.

---

## Approach

```
School term dates (gov.uk / mygov.scot / nidirect)
        +
UK bank holidays (gov.uk JSON API)
        +
BRC-Sensormatic footfall index (monthly YoY %)
        ↓
Weekly demand multiplier per region
  — school holiday week:  2.0× baseline
  — bank holiday week:    1.5× baseline
  — footfall modifier:    continuous ±% adjustment
        ↓
Streamlit dashboard + SQL analysis layer
```

Overlapping factors take the max rather than the product — a bank holiday inside summer holidays doesn't double demand, families are already out. The index is capped at 3.5× to prevent outliers from breaking visualisations.

---

## Key findings

- **Summer dominates but Scotland peaks 3–4 weeks earlier than England** — a national "summer push" campaign launched in late July misses Edinburgh's peak entirely
- **October half-term is the highest-value standalone peak** — the one week outside summer where families actively seek out leisure venues, easy to under-staff because it's not as psychologically obvious as summer
- **Standalone bank holidays (May, August) drive 40–60% uplift vs baseline** for most regions — bigger than most ops teams account for
- **Scotland has the highest demand variance** in the estate — long summer + genuinely quiet autumn means the biggest swings, needs a proper flex staffing model rather than a fixed rota

---

## Project structure

```
funstation-demand-forecaster/
│
├── data/
│   ├── fetch_term_dates.py       # scrapes school holidays — England, Scotland, NI, Wales
│   ├── fetch_bank_holidays.py    # gov.uk bank holidays JSON API
│   ├── fetch_footfall.py         # BRC-Sensormatic footfall index loader
│   ├── build_demand_index.py     # combines all sources → weekly demand multiplier
│   └── processed/                # generated CSVs (gitignored)
│
├── notebooks/
│   └── demand_analysis.ipynb     # methodology walkthrough + visualisations
│
├── sql/
│   ├── 01_peak_weeks_by_region.sql          # DENSE_RANK — top weeks per region
│   ├── 02_holiday_overlap_analysis.sql      # self-join — national campaign windows
│   ├── 03_bank_holiday_uplift_cohort.sql    # cohort analysis — embedded vs standalone BHs
│   ├── 04_footfall_trend_vs_holiday.sql     # LAG — MoM footfall vs holiday intensity
│   ├── 05_rolling_demand_moving_average.sql # ROWS BETWEEN window frame
│   ├── 06_yoy_peak_comparison.sql           # CTE — 2025 vs 2026 calendar shift
│   ├── 07_venue_region_mapping.sql          # multi-table join — venue → region → holidays
│   ├── 08_staffing_trigger_flags.sql        # CASE WHEN threshold logic
│   ├── 09_low_demand_gap_analysis.sql       # gaps-and-islands — maintenance windows
│   ├── 10_regional_sensitivity_ranking.sql  # STDDEV window — demand variance ranking
│   └── README_sql.md                        # index of all queries + concepts demonstrated
│
├── app/
│   └── streamlit_app.py          # 4-page Streamlit dashboard
│
├── .streamlit/
│   └── config.toml               # dark theme — Funstation orange (#FF6B35)
│
├── docs/
│   └── deployment.md             # Streamlit Cloud deployment steps
│
└── requirements.txt
```

---

## App pages

| Page | What it shows |
|------|--------------|
| **National Overview** | Demand heatmap (week × region), metric cards, top 10 peak weeks bar chart |
| **Region Deep-Dive** | Weekly demand line chart with 1.0× and 1.5× threshold markers, top 10 peak weeks table |
| **Holiday Calendar** | Gantt-style holiday timeline, side-by-side region comparison, overlap analysis |
| **Staffing Simulator** | Input baseline staff + hourly wage → outputs additional headcount and weekly labour cost per peak week, CSV export |

All pages support sidebar filters: region multiselect, year (2025/2026), holiday type.

---

## SQL coverage

The 10 SQL files in `sql/` demonstrate:

`DENSE_RANK` · `LAG` · `STDDEV` · `PERCENTILE_CONT` · `AVG() OVER (ROWS BETWEEN)` · gaps-and-islands · cohort analysis · self-join · `FULL OUTER JOIN` · CTEs · YoY comparison

Written as analyst notes, not just query dumps — each file explains the business question and why the approach was chosen.

---

## How to run

```bash
# Install dependencies
pip install -r requirements.txt

# Option 1: let the app build data on first load (auto, ~30s)
streamlit run app/streamlit_app.py

# Option 2: pre-build the data manually
cd data && python build_demand_index.py
cd .. && streamlit run app/streamlit_app.py
```

Requires Python 3.10+. No API keys needed — all data sources are public.

---

## Data sources

| Source | Data | Method |
|--------|------|--------|
| [gov.uk](https://www.gov.uk/school-term-holiday-dates) | England & Wales school term dates | BeautifulSoup scrape |
| [mygov.scot](https://www.mygov.scot/school-holidays) | Scotland school term dates | BeautifulSoup scrape |
| [nidirect.gov.uk](https://www.nidirect.gov.uk/articles/school-term-holiday-dates) | Northern Ireland term dates | BeautifulSoup scrape |
| [gov.uk API](https://www.gov.uk/bank-holidays.json) | UK bank holidays (all nations) | JSON API |
| [BRC-Sensormatic](https://brc.org.uk/retail-insight-analytics/footfall-and-sales-reports/) | Monthly footfall YoY % by destination type | Published press release figures |

---

## TODO

- Add actual Funstation venue coordinates to map venues spatially against their regional calendars (would need scraping their site)
- Wire up live BRC footfall updates when new monthly data publishes — currently using hardcoded figures from 2024–25 press releases
- Validate demand index against actual visitor count data if it becomes available

---

*Nithin Arisetty — Senior BI Analyst, formerly Amazon UK*  
*Built as a portfolio project demonstrating applied demand forecasting for the UK FEC sector*
