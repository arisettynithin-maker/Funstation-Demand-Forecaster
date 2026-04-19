# SQL Analysis Files

Each file addresses a specific business question relevant to Funstation's demand planning function.

| File | Business Question | SQL Concepts |
|------|------------------|--------------|
| `01_peak_weeks_by_region.sql` | Which 10 weeks drive highest demand per region? | `DENSE_RANK()` window function, `CASE WHEN` labelling |
| `02_holiday_overlap_analysis.sql` | When do multiple regions share school holidays? (national campaign windows) | Self-join, aggregation, `GROUP BY` with `MIN/MAX` |
| `03_bank_holiday_uplift_cohort.sql` | Do standalone bank holidays drive more uplift than those embedded in school hols? | Cohort analysis, `PERCENTILE_CONT`, baseline join, percentage uplift calc |
| `04_footfall_trend_vs_holiday_intensity.sql` | Does positive BRC footfall trend amplify holiday peaks? | `LAG()` window function, MoM change, quadrant classification |
| `05_rolling_demand_moving_average.sql` | What does the smoothed 4-week demand curve look like? | `AVG() OVER` with `ROWS BETWEEN` window frame, 8-week comparison |
| `06_yoy_peak_comparison.sql` | Have peak weeks shifted between 2025 and 2026 (Easter shift, etc.)? | CTEs, `FULL OUTER JOIN`, `DENSE_RANK`, week-shift calculation |
| `07_venue_region_mapping_analysis.sql` | How many peak weeks does each Funstation venue face? | Multi-source `UNION ALL`, venue-to-region join, ops complexity classification |
| `08_staffing_trigger_flags.sql` | Which weeks trigger the "staff up" threshold (1.5x baseline)? | `PERCENTILE_CONT` for median baseline, threshold-based `CASE WHEN`, uplift ratios |
| `09_low_demand_gap_analysis.sql` | Where are the longest quiet windows for maintenance? | Gaps-and-islands (`ROW_NUMBER` trick), `RANK()`, consecutive week grouping |
| `10_regional_sensitivity_ranking.sql` | Which regions have the most volatile demand profile? | `STDDEV()` window function, coefficient of variation, `RANK()` |

## Notes

These queries are written against the `demand_index` and `footfall_index` tables which the Python pipeline in `data/` generates and saves as CSVs. In a real warehouse setup (Redshift, BigQuery, Snowflake) you'd load those CSVs into staging tables and run these directly.

The SQL flavour is mostly ANSI-compatible with a few PostgreSQL-isms (`PERCENTILE_CONT`, `DATEDIFF`). Minor adjustments needed for BigQuery or Spark SQL.
