-- Peak weeks by region — ranked within each region
-- Nithin Arisetty
--
-- The business question: which 10 weeks of the year should each venue be
-- treating as "battle stations"? Not just nationally — Edinburgh's peak weeks
-- genuinely differ from Northampton's because Scotland's term dates shift by
-- 2-4 weeks in summer and October break.
--
-- DENSE_RANK so tied demand scores don't skip ranks (you'd lose weeks if you used RANK)

WITH ranked_weeks AS (
    SELECT
        region,
        iso_year,
        week_number,
        week_start,
        week_end,
        demand_index,
        is_school_holiday,
        is_bank_holiday_week,
        DENSE_RANK() OVER (
            PARTITION BY region, iso_year
            ORDER BY demand_index DESC
        ) AS demand_rank
    FROM demand_index
),

peak_10 AS (
    SELECT *
    FROM ranked_weeks
    WHERE demand_rank <= 10
)

SELECT
    region,
    iso_year,
    demand_rank,
    week_start,
    week_end,
    ROUND(demand_index, 2)          AS demand_index,
    is_school_holiday,
    is_bank_holiday_week,
    -- practical label for the ops team
    CASE
        WHEN is_school_holiday AND is_bank_holiday_week THEN 'School + Bank Holiday'
        WHEN is_school_holiday                          THEN 'School Holiday'
        WHEN is_bank_holiday_week                       THEN 'Bank Holiday Only'
        ELSE 'High Footfall Period'
    END                             AS peak_type
FROM peak_10
ORDER BY region, iso_year, demand_rank;
