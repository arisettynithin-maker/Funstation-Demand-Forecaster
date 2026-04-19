-- Year-on-year peak week comparison: 2025 vs 2026
-- Nithin Arisetty
--
-- Easter moves. So does the May bank holiday date. These shifts can move
-- the revenue calendar by 1-3 weeks, which matters for things like:
--   - when to run paid social campaigns
--   - when to schedule maintenance downtime
--   - annual budget phasing (Q1/Q2 split)
--
-- CTEs to isolate each year, then join on rank position to compare.

WITH peaks_2025 AS (
    SELECT
        region,
        week_start,
        week_number,
        demand_index,
        is_school_holiday,
        is_bank_holiday_week,
        DENSE_RANK() OVER (
            PARTITION BY region
            ORDER BY demand_index DESC
        ) AS rank_2025
    FROM demand_index
    WHERE iso_year = 2025
),

peaks_2026 AS (
    SELECT
        region,
        week_start,
        week_number,
        demand_index,
        is_school_holiday,
        is_bank_holiday_week,
        DENSE_RANK() OVER (
            PARTITION BY region
            ORDER BY demand_index DESC
        ) AS rank_2026
    FROM demand_index
    WHERE iso_year = 2026
),

top_peaks_25 AS (SELECT * FROM peaks_2025 WHERE rank_2025 <= 5),
top_peaks_26 AS (SELECT * FROM peaks_2026 WHERE rank_2026 <= 5),

comparison AS (
    SELECT
        COALESCE(p25.region, p26.region)        AS region,
        COALESCE(p25.rank_2025, p26.rank_2026)  AS peak_rank,
        p25.week_start                          AS peak_week_2025,
        p25.week_number                         AS week_num_2025,
        ROUND(p25.demand_index, 2)              AS demand_2025,
        p26.week_start                          AS peak_week_2026,
        p26.week_number                         AS week_num_2026,
        ROUND(p26.demand_index, 2)              AS demand_2026,
        -- week shift: positive means 2026 peak is later in the year
        p26.week_number - p25.week_number       AS week_shift
    FROM top_peaks_25 p25
    FULL OUTER JOIN top_peaks_26 p26
        ON  p25.region     = p26.region
        AND p25.rank_2025  = p26.rank_2026
)

SELECT
    region,
    peak_rank,
    peak_week_2025,
    demand_2025,
    peak_week_2026,
    demand_2026,
    week_shift,
    CASE
        WHEN ABS(week_shift) >= 2 THEN 'Significant calendar shift — re-phase budget'
        WHEN ABS(week_shift) = 1  THEN 'Minor shift — review campaign timing'
        ELSE 'Stable — same week both years'
    END AS planning_implication
FROM comparison
ORDER BY region, peak_rank;
