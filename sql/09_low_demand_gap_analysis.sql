-- Low demand gap analysis — maintenance and refurbishment windows
-- Nithin Arisetty
--
-- The flip side of peak planning is knowing when you *can* take a venue offline
-- or run at reduced capacity for maintenance. This uses a gaps-and-islands pattern
-- to find consecutive stretches of below-baseline weeks.
--
-- Gaps-and-islands: the classic ROW_NUMBER trick.
-- Sort all below-baseline weeks, then compare their sequential row number
-- against their actual week number. When a consecutive run breaks, the difference
-- changes — that's how you identify separate islands.

WITH below_baseline AS (
    SELECT
        region,
        iso_year,
        week_number,
        week_start,
        week_end,
        demand_index,
        ROW_NUMBER() OVER (
            PARTITION BY region, iso_year
            ORDER BY week_number
        ) AS rn
    FROM demand_index
    WHERE demand_index < 1.0   -- below baseline
),

island_groups AS (
    SELECT
        region,
        iso_year,
        week_number,
        week_start,
        week_end,
        demand_index,
        -- the gap-detection: if weeks are consecutive, (week_number - rn) is constant
        week_number - rn AS island_id
    FROM below_baseline
),

gap_windows AS (
    SELECT
        region,
        iso_year,
        island_id,
        MIN(week_start)     AS window_start,
        MAX(week_end)       AS window_end,
        COUNT(*)            AS consecutive_weeks,
        ROUND(AVG(demand_index), 3) AS avg_demand_in_window,
        ROUND(MIN(demand_index), 3) AS min_demand_in_window
    FROM island_groups
    GROUP BY region, iso_year, island_id
),

ranked_gaps AS (
    SELECT
        region,
        iso_year,
        window_start,
        window_end,
        consecutive_weeks,
        avg_demand_in_window,
        min_demand_in_window,
        RANK() OVER (
            PARTITION BY region, iso_year
            ORDER BY consecutive_weeks DESC
        ) AS gap_rank  -- longest gaps first
    FROM gap_windows
    WHERE consecutive_weeks >= 2  -- only meaningful windows
)

SELECT
    region,
    iso_year,
    gap_rank,
    window_start,
    window_end,
    consecutive_weeks,
    avg_demand_in_window,
    CASE
        WHEN consecutive_weeks >= 6 THEN 'Major refurb window — 6+ quiet weeks'
        WHEN consecutive_weeks >= 3 THEN 'Good maintenance window — 3-5 weeks'
        ELSE 'Short quiet window — minor works only'
    END AS maintenance_suitability
FROM ranked_gaps
WHERE gap_rank <= 3  -- top 3 quiet windows per region per year
ORDER BY region, iso_year, gap_rank;
