-- Footfall trend direction vs holiday calendar intensity
-- Nithin Arisetty
--
-- Does a positive BRC footfall trend amplify holiday peaks, or are they
-- independent? If positive footfall months *and* school holidays coincide,
-- those are the highest-value weeks of the year — worth knowing for
-- pricing decisions as much as staffing.
--
-- LAG to get MoM footfall change; then compare against average holiday
-- intensity (fraction of weeks that are school holiday weeks) in that month.

WITH monthly_footfall AS (
    SELECT
        year,
        month_num,
        destination_type,
        footfall_yoy_pct,
        footfall_modifier,
        LAG(footfall_yoy_pct) OVER (
            PARTITION BY destination_type
            ORDER BY year, month_num
        ) AS prev_month_yoy_pct,
        footfall_yoy_pct - LAG(footfall_yoy_pct) OVER (
            PARTITION BY destination_type
            ORDER BY year, month_num
        ) AS mom_change_ppt  -- percentage point change month-on-month
    FROM footfall_index
    WHERE destination_type = 'shopping_centre'
),

weekly_holiday_density AS (
    -- what fraction of weeks in each month are school holiday weeks?
    SELECT
        iso_year                              AS year,
        EXTRACT(MONTH FROM week_start)        AS month_num,
        COUNT(*)                              AS total_weeks,
        SUM(CASE WHEN is_school_holiday THEN 1 ELSE 0 END) AS holiday_weeks,
        ROUND(
            SUM(CASE WHEN is_school_holiday THEN 1.0 ELSE 0.0 END) / COUNT(*),
            3
        ) AS holiday_density
    FROM demand_index
    GROUP BY iso_year, EXTRACT(MONTH FROM week_start)
),

combined AS (
    SELECT
        f.year,
        f.month_num,
        f.footfall_yoy_pct,
        f.prev_month_yoy_pct,
        f.mom_change_ppt,
        f.footfall_modifier,
        d.holiday_density,
        d.holiday_weeks,
        d.total_weeks
    FROM monthly_footfall f
    LEFT JOIN weekly_holiday_density d
        ON f.year = d.year AND f.month_num = d.month_num
    WHERE f.mom_change_ppt IS NOT NULL
)

SELECT
    year,
    month_num,
    ROUND(footfall_yoy_pct, 1)      AS footfall_yoy_pct,
    ROUND(mom_change_ppt, 2)        AS mom_change_ppt,
    ROUND(footfall_modifier, 3)     AS footfall_modifier,
    holiday_density,
    -- quadrant classification for the scatter analysis
    CASE
        WHEN footfall_modifier > 1.0 AND holiday_density > 0.5 THEN 'Peak × Positive — highest revenue potential'
        WHEN footfall_modifier > 1.0 AND holiday_density <= 0.5 THEN 'Positive footfall, low holidays'
        WHEN footfall_modifier <= 1.0 AND holiday_density > 0.5 THEN 'Holiday peak, muted footfall market'
        ELSE 'Low demand — maintenance / promo window'
    END AS demand_quadrant
FROM combined
ORDER BY year, month_num;
