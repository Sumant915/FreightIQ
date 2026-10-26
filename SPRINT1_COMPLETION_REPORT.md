# FreightIQ Sprint 1 completion report

## Workspace status
The project was continued in-place without dropping or recreating the existing database tables. The synthetic freight dataset and the 10 derived lane-distance records were preserved as required. The coal reference data was integrated as raw plus cleaned reference outputs without fabricating missing source-backed market observations.

## Data inventory and source review

### 1) data/india_coal_imports_data.csv
- Purpose: Raw monthly India import matrix used as the primary Australian-origin coal source.
- Row count: 247 data rows.
- Period: Monthly values across the matrix; the 2021-2025 subset was retained.
- Unit: Native source scale appears to be million tonnes; retained without conversion.
- Origin: Explicit Australia-origin columns (`AUS.*`) were used; World totals were not used to infer Australia-specific volumes.
- Classification: source-reported observations with mixed/incomplete provenance; used to create the cleaned Australia-origin subset.
- Use: 2021-2025 Australia-origin monthly reference series. The origin and monthly records are explicit in the matrix; the exact publication/export lineage and unit definition remain to be confirmed.
- Source URL: `https://comtradeplus.un.org/` (inferred from the file structure and prior project metadata; not directly embedded in the raw file).

### 2) data/Month-wise-Coal-and-Coal-Products-Import.csv
- Purpose: Monthly India coal import reference file with suspicious zero values in the 2024-25 series.
- Row count: 12 rows.
- Period: Monthly reference values with the 2024-25 series containing zero values for October, November, and December.
- Unit: Native source unit was not explicitly converted; preserved as a reference file.
- Classification: reference dataset with a documented data-quality caveat.
- Use: Quality check and provenance note only; not used as a validated 2021-2025 Australia-specific series.
- Source URL: Not embedded in the file.
- Result: Zero values were kept as reported and explicitly documented as suspicious rather than overwritten.

### 3) data/TradeData_10_23_2026_16_2_5.csv
- Purpose: Prior world-total monthly India coal import reference.
- Row count: 12 rows.
- Period: 2026 monthly world totals.
- Unit: kilograms (`qtyUnitAbbr = kg`).
- Partner definition: `partnerDesc = World`; not Australia-specific.
- Commodity: `cmdCode = 2701`, coal category.
- Classification: out-of-period reference; not part of the 2021-2025 model dataset.
- Use: Separate world-total reference only; never used to infer Australian origin import volumes.
- Source URL: Not embedded in the file; likely Comtrade/Comtrade+ based on column structure, but source URL could not be verified from the file.

### 4) data/TradeData_10_23_2026_16_1_45.csv
- Purpose: New 2026 World-total monthly import reference.
- Row count: 7 rows.
- Period: 2026 monthly imports, July coverage; `refMonth` values 1 through 7.
- Unit: kilograms (`qtyUnitAbbr = kg`).
- Partner definition: `partnerDesc = World`; not Australia-specific.
- Commodity code: `cmdCode = 2701`, `Coal; briquettes, ovoids and similar solid fuels manufactured from coal`.
- Classification: out-of-model-period reference dataset.
- Use: Kept separate from the 2021-2025 Australian coal series; not used as Australian-origin data.
- Source URL: Not embedded in the file; source was not confirmed beyond the Comtrade-like field structure.

### 5) data/Top-10-Countries-wise-Coal-Import.csv
- Purpose: New country ranking reference file.
- Row count: 10 rows.
- Period: Reporting year not embedded in the file; no reliable year/period metadata was present.
- Unit: million tonnes (MT) as written in the columns.
- Country review: Australia is included (`Australia, 24.584, 8.451, 33.035`).
- Classification: unverified annual country reference.
- Use: retained as a reference dataset only; not treated as a validated 2021-2025 time series.
- Source URL: not discoverable from the file and not embedded in the metadata.
- Important caveat: The file includes coking, non-coking, and total categories distinctly, and total coal was not added to component values in the cleaned reference output; the file was preserved as an unverified reference, not as a validated monthly or annual model dataset.

### 6) data/Import-of-Coal-and-Coke-last-ten-years-2.pdf
- Purpose: National India annual coal import report used to validate the broader scale and reference totals.
- Period: FY 2015-16 through FY 2024-25.
- Unit: million tonnes.
- Classification: annual national reference, not Australia-specific.
- Use: Reference for national India coal import totals only.
- Source URL: Local file in the project data folder; no stable public URL was embedded in the PDF.

### 7) data/india_australia_coal_imports_2021_2025_clean.csv
- Purpose: Cleaned Australia-origin monthly coal import series for 2021-2025.
- Row count: 300 rows.
- Period: 2021-01-01 through 2025-12-01.
- Unit: million tonnes.
- Classification: observed / source-backed for the Australian-origin subset.
- Use: Approved for the project model dataset.
- Source integrity: direct coal HS codes (27011100, 27011200, 27011910, 27011920, 27011990) retained; overlapping subcategories were excluded to avoid double-counting.

### 8) data/india_coal_imports_reference_annual_fy_2015_2025.csv
- Purpose: Cleaned annual India FY reference totals.
- Row count: 10 rows.
- Period: FY 2015-16 through FY 2024-25.
- Unit: million tonnes.
- Classification: annual national reference only.
- Use: Not Australia-specific and not monthly.

### 9) data/Top-10-Countries-wise-Coal-Import_cleaned.csv
- Purpose: Cleaned export of the unverified country-ranking file.
- Row count: 10 rows.
- Period status: `unverified_reference`.
- Use: Reference only.

### 10) data/TradeData_10_23_2026_16_1_45_cleaned.csv
- Purpose: Cleaned 2026 world-total monthly reference file.
- Row count: 7 rows.
- Period: 2026 monthly values.
- Unit: kilograms.
- Classification: world-total reference, out-of-model-period.
- Use: Reference only; not interpreted as Australian-origin volumes.

## Database state and actual counts
- `freight_observations`: 14,608 rows
- `trade_lanes`: 10 rows
- `lane_distances`: 10 rows
- `market_observations`: 1,263 rows (BRENT only)
- `coal_trade_volumes`: 300 rows
- `data_sources`: includes the new coal-source references and the preserved existing sources

Verified database checks:
- `coal_trade_volumes` duplicate key count: 0
- `market_observations` duplicate key count: 0
- `lane_distances` status counts: `derived` = 10
- `approved_observed_index_rows`: 0
- `trade_lanes`: 10
- All 10 lane distances remain `derived`, not upgraded

## Actual validation command outputs
Command run:
`python scripts/validate_db.py` (DATABASE_URL loaded from ignored local `.env`)

Output:
- `freight_row_count: 14608 [INFO]`
- `duplicate_date_record_ids: 0 [PASS]`
- `nonpositive_rates: 0 [PASS]`
- `rows_missing_port_names: 0 [INFO]`
- `required_destination_ports_present: 3 [PASS]`
- `candidate_lanes_count: 10 [INFO]`
- `approved_observed_index_rows: 0 [BLOCKED]`
- `Rows by destination: Haldia: 3652, Paradip: 5478, Visakhapatnam: 5478`
- `Freight date coverage: (2021-01-01, 2025-12-31, 1826)`

Command run:
`python scripts/ingest_coal_trade_volumes.py` (DATABASE_URL loaded from ignored local `.env`)

Output:
- `Saved cleaned reference CSV to data\Top-10-Countries-wise-Coal-Import_cleaned.csv (10 rows).`
- `Saved cleaned 2026 reference CSV to data\TradeData_10_23_2026_16_1_45_cleaned.csv (7 rows).`
- `Prepared 300 Australia-origin coal import rows from data\india_coal_imports_data.csv.`
- `Saved cleaned CSV to data\india_australia_coal_imports_2021_2025_clean.csv.`

## Remaining blockers
The following items remain unresolved because actual source-backed observations were not available in this workspace and were not fabricated:
- Australian thermal coal price series
- Australian coking coal price series
- BDI, BCI, BPI, and VLSFO observations
- Independent navigational/AIS verification of sea distances

## Verified facts vs unresolved metadata
Verified facts:
- 14,608 synthetic freight observations remain intact.
- 10 trade lanes remain present.
- 10 lane distances remain `derived`.
- The cleaned Australia-origin coal subset is 300 rows for 2021-2025 monthly data.
- The world-total 2026 coal import files were preserved separately and not treated as Australia-specific.
- The Top-10 country file was preserved as an unverified reference because no reporting period/source metadata was embedded in the file.
- The Brent source metadata caveat was preserved.

Unresolved or unknown metadata:
- Exact original publisher and URL for the Top-10 country file.
- Exact source URL for the 2026 Comtrade-like world file.
- Verified Australian price series for thermal and coking coal.
- Verified BDI/BCI/BPI/VLSFO observations.
- Independent distance verification beyond the existing derived route assumptions.

## Outcome
The requested remaining coal-import integration work is complete for the available data sources. Existing freight and derived-distance records were preserved. New, clearly labelled reference datasets were added and documented without claiming unsupported values. The project remains validly blocked only by the missing market and distance evidence noted above.

## Team handoff and repository preparation
- The local database is not part of Git; teammates initialize a local TimescaleDB volume and repopulate it from the tracked SQL and datasets.
- `.env.example` contains placeholders only. `.env`, Python environments, caches, logs, database dumps, and local database files are excluded by `.gitignore`.
- Database scripts now require `DATABASE_URL` from `.env` or the process environment; no connection password is embedded in the scripts or Compose configuration.
- The Brent importer uses a dynamic source ID and idempotent conflict handling. Its provenance note explicitly states that observations are loaded from the bundled CSV mirror and were not fetched directly from the EIA API.
- The GitHub target was found to contain an existing `main` commit with a `LICENSE` file. That history and file must be preserved during integration; no force-push is appropriate.
- Python compilation passed: `python -m compileall -q scripts`.
- Compose parsing passed: `docker compose config -q` with a validation-only environment variable; no container was started or recreated.
- The idempotent Brent import read 1,263 valid CSV observations, inserted 0 new rows, and confirmed 1,263 database BRENT rows with coverage 2021-01-04 through 2025-12-31. It printed the CSV-mirror caveat.
- The idempotent coal import regenerated the 10-row Top-10 reference CSV, the 7-row 2026 World reference CSV, and the 300-row Australian-origin cleaned CSV.
- A second `scripts/validate_db.py` run passed with: 14,608 freight rows; 0 duplicate freight keys; 0 nonpositive rates; 0 missing port names; 3 required destination ports; 10 candidate lanes; and 0 approved observed BDI/BCI/BPI rows (`BLOCKED`).
- Final SQL checks returned: 14,608 freight rows; 10 lanes; 10 distances, all `derived`; 1,263 market rows (BRENT/observed); 300 coal rows (Australia to India, `million_tonnes`, 2021-01 through 2025-12); 0 coal duplicate keys; 0 market duplicate keys; and 0 orphan coal or market source IDs.
