CREATE EXTENSION IF NOT EXISTS timescaledb;

CREATE TABLE IF NOT EXISTS data_sources (
  source_id BIGSERIAL PRIMARY KEY,
  source_name TEXT NOT NULL,
  publisher TEXT,
  source_url TEXT,
  dataset_type TEXT NOT NULL CHECK (dataset_type IN ('observed','derived','synthetic','assumed','mixed','unknown')),
  units TEXT,
  frequency TEXT,
  coverage_start DATE,
  coverage_end DATE,
  license_notes TEXT,
  provenance_notes TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (source_name, dataset_type)
);

CREATE TABLE IF NOT EXISTS ports (
  port_id BIGSERIAL PRIMARY KEY,
  port_name TEXT NOT NULL,
  country TEXT NOT NULL,
  port_code TEXT,
  latitude NUMERIC(9,6),
  longitude NUMERIC(9,6),
  coordinate_status TEXT NOT NULL DEFAULT 'unknown',
  source_id BIGINT REFERENCES data_sources(source_id),
  notes TEXT,
  UNIQUE (port_name, country)
);

CREATE TABLE IF NOT EXISTS berths (
  berth_id BIGSERIAL PRIMARY KEY,
  port_id BIGINT NOT NULL REFERENCES ports(port_id),
  berth_name TEXT NOT NULL,
  cargo_type TEXT,
  max_draft_m NUMERIC(6,2),
  max_loa_m NUMERIC(7,2),
  max_dwt_tonnes INTEGER,
  restriction_notes TEXT,
  source_id BIGINT REFERENCES data_sources(source_id),
  effective_from DATE,
  effective_to DATE,
  verification_status TEXT NOT NULL DEFAULT 'awaiting_verification'
    CHECK (verification_status IN ('verified','partially_verified','assumed','awaiting_verification')),
  UNIQUE (port_id, berth_name, effective_from)
);

CREATE TABLE IF NOT EXISTS trade_lanes (
  lane_id BIGSERIAL PRIMARY KEY,
  route_id TEXT NOT NULL UNIQUE,
  origin_port_id BIGINT NOT NULL REFERENCES ports(port_id),
  destination_port_id BIGINT NOT NULL REFERENCES ports(port_id),
  commodity TEXT NOT NULL,
  vessel_class TEXT NOT NULL,
  feasibility_status TEXT NOT NULL DEFAULT 'candidate_scenario',
  direct_fixture_evidence BOOLEAN NOT NULL DEFAULT FALSE,
  source_id BIGINT REFERENCES data_sources(source_id),
  notes TEXT
);

CREATE TABLE IF NOT EXISTS lane_distances (
  distance_id BIGSERIAL PRIMARY KEY,
  lane_id BIGINT NOT NULL REFERENCES trade_lanes(lane_id),
  distance_nm NUMERIC(10,2) NOT NULL CHECK (distance_nm > 0),
  method TEXT NOT NULL,
  distance_status TEXT NOT NULL CHECK (distance_status IN ('observed','derived','assumed','synthetic')),
  source_id BIGINT REFERENCES data_sources(source_id),
  valid_from DATE,
  notes TEXT,
  UNIQUE (lane_id, distance_nm, method)
);

CREATE TABLE IF NOT EXISTS ingestion_runs (
  ingestion_run_id BIGSERIAL PRIMARY KEY,
  source_id BIGINT REFERENCES data_sources(source_id),
  file_name TEXT NOT NULL,
  started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  finished_at TIMESTAMPTZ,
  status TEXT NOT NULL DEFAULT 'running' CHECK (status IN ('running','success','failed')),
  rows_read INTEGER NOT NULL DEFAULT 0,
  rows_attempted INTEGER NOT NULL DEFAULT 0,
  error_message TEXT
);

CREATE TABLE IF NOT EXISTS market_observations (
  observed_at TIMESTAMPTZ NOT NULL,
  source_id BIGINT NOT NULL REFERENCES data_sources(source_id),
  indicator_code TEXT NOT NULL CHECK (indicator_code IN ('BDI','BCI','BPI','VLSFO','BRENT','AU_THERMAL_COAL','AU_COKING_COAL')),
  value NUMERIC(18,6) NOT NULL,
  unit TEXT NOT NULL,
  frequency TEXT NOT NULL,
  data_type TEXT NOT NULL CHECK (data_type IN ('observed','derived','synthetic','assumed')),
  source_record_ref TEXT,
  notes TEXT,
  PRIMARY KEY (observed_at, source_id, indicator_code)
);
SELECT create_hypertable('market_observations', 'observed_at', if_not_exists => TRUE);

CREATE TABLE IF NOT EXISTS freight_observations (
  assessment_date DATE NOT NULL,
  record_id TEXT NOT NULL,
  source_id BIGINT NOT NULL REFERENCES data_sources(source_id),
  lane_id BIGINT REFERENCES trade_lanes(lane_id),
  route_id TEXT NOT NULL,
  origin_port TEXT NOT NULL,
  destination_port TEXT NOT NULL,
  commodity TEXT NOT NULL,
  vessel_class TEXT NOT NULL,
  freight_rate_usd_per_tonne NUMERIC(18,6) NOT NULL CHECK (freight_rate_usd_per_tonne > 0),
  rate_unit TEXT,
  route_distance_nm NUMERIC(10,2),
  bdi_proxy_value NUMERIC(18,6),
  bpi_proxy_value NUMERIC(18,6),
  target_data_type TEXT NOT NULL DEFAULT 'synthetic' CHECK (target_data_type IN ('observed','derived','synthetic','assumed')),
  index_data_type TEXT NOT NULL DEFAULT 'unknown',
  extreme_flag BOOLEAN,
  source_reference TEXT,
  assumptions_notes TEXT,
  raw_payload JSONB NOT NULL,
  imported_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (assessment_date, record_id)
);
SELECT create_hypertable('freight_observations', 'assessment_date', if_not_exists => TRUE);

CREATE TABLE IF NOT EXISTS validation_results (
  validation_id BIGSERIAL PRIMARY KEY,
  validation_run_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  check_name TEXT NOT NULL,
  status TEXT NOT NULL CHECK (status IN ('passed','failed','blocked','warning')),
  observed_value TEXT,
  expected_value TEXT,
  evidence TEXT
);

CREATE INDEX IF NOT EXISTS idx_freight_route_date ON freight_observations(route_id, assessment_date DESC);
CREATE INDEX IF NOT EXISTS idx_market_indicator_date ON market_observations(indicator_code, observed_at DESC);
CREATE INDEX IF NOT EXISTS idx_lanes_destination ON trade_lanes(destination_port_id);
