-- Bank holiday uplift: embedded vs standalone
-- Nithin Arisetty
--
-- A bank holiday in the middle of summer holidays is different from a random
-- May Day Monday. Families are already out and about in the former case — the
-- BH just keeps them out longer. In the standalone case the BH is the reason
-- they're going out at all, so the uplift effect is larger and more operationally
-- important (you might not have staffed up for it).
--
-- Cohort: "embedded" = BH week is also a school holiday week
--         "standalone" = BH week is NOT a school holiday

WITH bh_weeks AS (
    SELECT
        region,
        iso_year,
        week_number,
        week_start,
        demand_index,
        is_school_holiday,
        CASE
            WHEN is_school_holiday THEN 'embedded'
            ELSE 'standalone'
        END AS bh_cohort
    FROM demand_index
    WHERE is_bank_holiday_week = TRUE
),

baseline AS (
    -- typical non-holiday week demand per region and year, for comparison
    SELECT
        region,
        iso_year,
        AVG(demand_index) AS avg_baseline_demand
    FROM demand_index
    WHERE is_school_holiday = FALSE
      AND is_bank_holiday_week = FALSE
    GROUP BY region, iso_year
),

cohort_stats AS (
    SELECT
        bh.region,
        bh.iso_year,
        bh.bh_cohort,
        COUNT(*)                    AS bh_week_count,
        ROUND(AVG(bh.demand_index), 3) AS avg_demand,
        ROUND(b.avg_baseline_demand, 3) AS baseline_demand,
        ROUND(AVG(bh.demand_index) - b.avg_baseline_demand, 3) AS absolute_uplift,
        ROUND(
            (AVG(bh.demand_index) - b.avg_baseline_demand) / NULLIF(b.avg_baseline_demand, 0) * 100,
            1
        ) AS pct_uplift_vs_baseline
    FROM bh_weeks bh
    JOIN baseline b
        ON bh.region   = b.region
        AND bh.iso_year = b.iso_year
    GROUP BY bh.region, bh.iso_year, bh.bh_cohort, b.avg_baseline_demand
)

SELECT
    region,
    iso_year,
    bh_cohort,
    bh_week_count,
    avg_demand,
    baseline_demand,
    absolute_uplift,
    pct_uplift_vs_baseline,
    -- the insight: standalone BHs should be staffed up more proactively
    CASE
        WHEN bh_cohort = 'standalone' AND pct_uplift_vs_baseline > 40
            THEN 'HIGH PRIORITY — standalone BH, big uplift, needs staff plan'
        WHEN bh_cohort = 'standalone'
            THEN 'Moderate — standalone BH, manageable uplift'
        ELSE 'Embedded in holiday — already in peak staffing mode'
    END AS ops_recommendation
FROM cohort_stats
ORDER BY region, iso_year, bh_cohort;
