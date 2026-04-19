-- Venue to region mapping and holiday exposure
-- Nithin Arisetty
--
-- Funstation has 14+ venues across England, Scotland, and Northern Ireland.
-- Each venue operates under the term date calendar of its local education authority.
-- This query maps venues to their regional calendar and summarises their
-- annual holiday exposure — i.e. how many peak weeks does each venue face?
-- More peaks = more revenue opportunity but also more operational complexity.
--
-- In a real implementation this would join to a venues table in the Funstation DB.
-- Here I'm using a static mapping based on publicly listed venue locations.

-- Venue reference table (would normally be a proper dim_venues table)
WITH venues AS (
    SELECT 'Edinburgh' AS venue_name, 'Scotland' AS region, 'EH' AS postcode_area
    UNION ALL SELECT 'Glasgow', 'Scotland', 'G'
    UNION ALL SELECT 'Aberdeen', 'Scotland', 'AB'
    UNION ALL SELECT 'Belfast', 'Northern Ireland', 'BT'
    UNION ALL SELECT 'Northampton', 'England - Midlands', 'NN'
    UNION ALL SELECT 'Leicester', 'England - Midlands', 'LE'
    UNION ALL SELECT 'Birmingham', 'England - Midlands', 'B'
    UNION ALL SELECT 'Manchester', 'England - North', 'M'
    UNION ALL SELECT 'Leeds', 'England - North', 'LS'
    UNION ALL SELECT 'Newcastle', 'England - North', 'NE'
    UNION ALL SELECT 'London Lakeside', 'England - South', 'RM'
    UNION ALL SELECT 'Guildford', 'England - South', 'GU'
    UNION ALL SELECT 'Bristol', 'Wales', 'BS'   -- actually England but close to Wales calendar
    UNION ALL SELECT 'Cardiff', 'Wales', 'CF'
),

venue_demand AS (
    SELECT
        v.venue_name,
        v.region,
        v.postcode_area,
        d.iso_year,
        COUNT(*)                    AS total_weeks,
        SUM(CASE WHEN d.is_school_holiday THEN 1 ELSE 0 END) AS school_holiday_weeks,
        SUM(CASE WHEN d.is_peak_week THEN 1 ELSE 0 END)      AS peak_weeks,
        ROUND(AVG(d.demand_index), 2)                         AS avg_demand_index,
        ROUND(MAX(d.demand_index), 2)                         AS max_demand_index,
        SUM(CASE WHEN d.demand_index >= 2.5 THEN 1 ELSE 0 END) AS ultra_peak_weeks
    FROM venues v
    JOIN demand_index d ON v.region = d.region
    GROUP BY v.venue_name, v.region, v.postcode_area, d.iso_year
)

SELECT
    venue_name,
    region,
    iso_year,
    school_holiday_weeks,
    peak_weeks,
    ultra_peak_weeks,
    avg_demand_index,
    max_demand_index,
    -- venues with more ultra peaks need more robust staffing contingency plans
    ROUND(peak_weeks * 1.0 / total_weeks * 100, 1) AS pct_peak_weeks,
    CASE
        WHEN ultra_peak_weeks >= 6 THEN 'High complexity — needs dedicated ops plan'
        WHEN ultra_peak_weeks >= 3 THEN 'Medium complexity'
        ELSE 'Standard planning sufficient'
    END AS staffing_complexity
FROM venue_demand
ORDER BY iso_year, pct_peak_weeks DESC;
