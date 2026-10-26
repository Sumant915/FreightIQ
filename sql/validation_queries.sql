-- 1) Row count and date coverage
SELECT count(*) AS rows, min(assessment_date) AS first_date, max(assessment_date) AS last_date,
       count(DISTINCT assessment_date) AS distinct_dates FROM freight_observations;

-- 2) Duplicate check (must return zero rows)
SELECT assessment_date, record_id, count(*)
FROM freight_observations GROUP BY assessment_date, record_id HAVING count(*) > 1;

-- 3) Required destination ports (must show all three)
SELECT destination_port, count(*)
FROM freight_observations
WHERE destination_port IN ('Paradip','Visakhapatnam','Haldia')
GROUP BY destination_port ORDER BY destination_port;

-- 4) Synthetic proxy provenance; do not report these as observed index values
SELECT target_data_type, index_data_type, count(*)
FROM freight_observations GROUP BY 1,2 ORDER BY 1,2;

-- 5) Approved observed market index coverage. Initially may be zero; report BLOCKED, not fabricated.
SELECT indicator_code, data_type, min(observed_at), max(observed_at), count(*)
FROM market_observations WHERE indicator_code IN ('BDI','BCI','BPI')
GROUP BY indicator_code, data_type ORDER BY indicator_code, data_type;

-- 6) Weekly gaps for observed indices after ingestion. This generates a weekly calendar
-- and lists missing weeks only for indices that have at least one observed record.
WITH observed_codes AS (
  SELECT DISTINCT indicator_code FROM market_observations
  WHERE data_type='observed' AND indicator_code IN ('BDI','BCI','BPI')
), bounds AS (
  SELECT indicator_code, date_trunc('week', min(observed_at)) AS first_week,
         date_trunc('week', max(observed_at)) AS last_week
  FROM market_observations WHERE data_type='observed' AND indicator_code IN ('BDI','BCI','BPI')
  GROUP BY indicator_code
), calendar AS (
  SELECT b.indicator_code, g.week_start
  FROM bounds b CROSS JOIN LATERAL generate_series(b.first_week,b.last_week,interval '1 week') g(week_start)
)
SELECT c.indicator_code, c.week_start::date AS missing_week
FROM calendar c
LEFT JOIN market_observations m ON m.indicator_code=c.indicator_code AND m.data_type='observed'
 AND date_trunc('week',m.observed_at)=c.week_start
WHERE m.observed_at IS NULL ORDER BY c.indicator_code,c.week_start;

-- 7) Berth verification status; empty table means port physical limits still need evidence.
SELECT p.port_name,b.berth_name,b.max_draft_m,b.max_loa_m,b.verification_status,b.restriction_notes
FROM ports p LEFT JOIN berths b USING(port_id)
WHERE p.port_name IN ('Paradip','Visakhapatnam','Haldia') ORDER BY p.port_name,b.berth_name;
