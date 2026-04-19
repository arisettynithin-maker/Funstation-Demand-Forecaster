-- Holiday overlap across regions — when can you run a national campaign?
-- Nithin Arisetty
--
-- If Scotland and England have Easter at different times, a single national
-- "Easter campaign" wastes budget on whichever region is already back at school.
-- This query finds weeks where multiple regions share school holidays —
-- those are the windows for coordinated national marketing spend.
--
-- Self-join on the demand index: both regions in the same week, both flagged as holiday

WITH holiday_weeks AS (
    SELECT
        iso_year,
        week_number,
        week_start,
        region,
        demand_index
    FROM demand_index
    WHERE is_school_holiday = TRUE
),

region_pairs AS (
    SELECT
        a.iso_year,
        a.week_number,
        a.week_start,
        a.region            AS region_a,
        b.region            AS region_b,
        a.demand_index      AS demand_a,
        b.demand_index      AS demand_b,
        (a.demand_index + b.demand_index) / 2.0 AS avg_demand
    FROM holiday_weeks a
    JOIN holiday_weeks b
        ON  a.iso_year     = b.iso_year
        AND a.week_number  = b.week_number
        AND a.region       < b.region   -- avoid duplicates (A-B and B-A)
),

overlap_summary AS (
    SELECT
        region_a,
        region_b,
        iso_year,
        COUNT(*)            AS overlapping_holiday_weeks,
        ROUND(AVG(avg_demand), 2) AS avg_combined_demand,
        MIN(week_start)     AS first_overlap_week,
        MAX(week_start)     AS last_overlap_week
    FROM region_pairs
    GROUP BY region_a, region_b, iso_year
)

SELECT
    region_a,
    region_b,
    iso_year,
    overlapping_holiday_weeks,
    avg_combined_demand,
    first_overlap_week,
    last_overlap_week,
    -- flag region pairs with good overlap — these support joint campaigns
    CASE
        WHEN overlapping_holiday_weeks >= 8 THEN 'Strong overlap — good for joint campaign'
        WHEN overlapping_holiday_weeks >= 4 THEN 'Moderate overlap'
        ELSE 'Low overlap — campaign timing needs splitting'
    END AS campaign_suitability
FROM overlap_summary
ORDER BY iso_year, overlapping_holiday_weeks DESC;
