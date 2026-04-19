-- 4-week rolling average demand index by region
-- Nithin Arisetty
--
-- The raw weekly index is spiky — a single half-term week surrounded by
-- low-demand weeks can look like an anomaly. The 4-week MA smooths that out
-- and gives the ops team a cleaner view of whether they're heading into a
-- high-demand period or coming out of one.
--
-- ROWS BETWEEN 3 PRECEDING AND CURRENT ROW = current week + 3 prior weeks
-- Ordered by week_start not week_number to handle year-boundary correctly

SELECT
    region,
    iso_year,
    week_number,
    week_start,
    ROUND(demand_index, 3)          AS demand_index,
    ROUND(
        AVG(demand_index) OVER (
            PARTITION BY region
            ORDER BY week_start
            ROWS BETWEEN 3 PRECEDING AND CURRENT ROW
        ),
        3
    )                               AS rolling_4wk_avg,
    ROUND(
        AVG(demand_index) OVER (
            PARTITION BY region
            ORDER BY week_start
            ROWS BETWEEN 7 PRECEDING AND CURRENT ROW
        ),
        3
    )                               AS rolling_8wk_avg,
    -- direction signal: is the 4-week trend rising or falling?
    CASE
        WHEN AVG(demand_index) OVER (
                PARTITION BY region ORDER BY week_start
                ROWS BETWEEN 3 PRECEDING AND CURRENT ROW
             ) >
             AVG(demand_index) OVER (
                PARTITION BY region ORDER BY week_start
                ROWS BETWEEN 7 PRECEDING AND 4 PRECEDING
             )
        THEN 'Rising'
        ELSE 'Falling / Flat'
    END                             AS trend_direction,
    is_school_holiday,
    is_bank_holiday_week
FROM demand_index
ORDER BY region, week_start;
