-- Staffing trigger flags — weeks where demand exceeds 1.5x baseline
-- Nithin Arisetty
--
-- 1.5x was chosen as the trigger threshold because:
--   a) it's the point where a standard rota can't absorb the extra volume
--      without service degrading (based on typical FEC capacity assumptions)
--   b) it's above every bank holiday standalone week, so we're only flagging
--      genuinely elevated periods, not every Monday in May
--
-- These flags are what the Staffing Simulator page in the app uses.
-- A week flagged here should trigger a staffing conversation 4-6 weeks prior.

WITH baseline_by_region AS (
    -- Use median rather than mean — mean gets skewed by the summer peak
    SELECT
        region,
        iso_year,
        PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY demand_index) AS median_demand,
        AVG(demand_index)                                          AS mean_demand,
        STDDEV(demand_index)                                       AS stddev_demand
    FROM demand_index
    GROUP BY region, iso_year
),

flagged_weeks AS (
    SELECT
        d.region,
        d.iso_year,
        d.week_number,
        d.week_start,
        d.week_end,
        ROUND(d.demand_index, 2)        AS demand_index,
        ROUND(b.median_demand, 2)       AS median_baseline,
        ROUND(d.demand_index / NULLIF(b.median_demand, 0), 2) AS uplift_vs_median,
        d.is_school_holiday,
        d.is_bank_holiday_week,
        CASE
            WHEN d.demand_index >= b.median_demand * 2.0 THEN 'CRITICAL — 2x+ baseline, full surge plan'
            WHEN d.demand_index >= b.median_demand * 1.5 THEN 'STAFF UP — 1.5x+ baseline trigger'
            WHEN d.demand_index >= b.median_demand * 1.2 THEN 'MONITOR — approaching threshold'
            ELSE 'Normal'
        END AS staffing_flag,
        -- how many weeks notice do we have from today (hardcoded for demo)
        -- TODO: replace with CURRENT_DATE in live environment
        DATEDIFF('week', DATE '2025-01-01', d.week_start) AS weeks_until
    FROM demand_index d
    JOIN baseline_by_region b
        ON d.region = b.region AND d.iso_year = b.iso_year
)

SELECT
    region,
    iso_year,
    week_start,
    week_end,
    week_number,
    demand_index,
    median_baseline,
    uplift_vs_median,
    staffing_flag,
    is_school_holiday,
    is_bank_holiday_week
FROM flagged_weeks
WHERE staffing_flag != 'Normal'
ORDER BY region, iso_year, week_start;
