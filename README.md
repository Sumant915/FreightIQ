# FreightIQ Sprint 1

FreightIQ Sprint 1 is a local PostgreSQL/TimescaleDB starter for exploring bulk-freight scenarios, candidate trade lanes, and provenance-aware market and coal-trade data. It is a development project, not a production deployment or a source of navigational advice.

## Current scope and data integrity

- The project contains 14,608 **synthetic** freight scenario observations covering 2021-01-01 through 2025-12-31. Their freight rates and embedded BDI/BPI proxy values are not historical market observations.
- Ten trade lanes and ten sea-distance records are present. All lane distances remain **derived**, not navigationally or AIS verified.
- `market_observations` contains the Brent series only (1,263 observations) from the bundled CSV mirror. The EIA URL identifies the underlying series; the CSV was not fetched directly from the EIA API during ingestion.
- `coal_trade_volumes` contains 300 Australia-origin India import rows for 2021-2025. The data are monthly and retained at the source's apparent million-tonne scale; the source file does not explicitly state a unit definition.
- A 2026 trade file uses partner `World`; it is not Australia-specific and is kept only as a separate reference.
- The Top-10 country file includes Australia but has no verified reporting year or publisher metadata, so it is an unverified reference, not a 2021-2025 time series.
- No destination-port-level coal volumes are inferred from national totals.

See [SPRINT1_COMPLETION_REPORT.md](SPRINT1_COMPLETION_REPORT.md) for the detailed inventory, validation evidence, source caveats, and outstanding work.

## Project structure

```text
data/       Raw source datasets and separately generated cleaned CSV outputs
scripts/    Idempotent ingestion scripts, DB configuration helper, validation
sql/        PostgreSQL/TimescaleDB schema and validation queries
docker-compose.yml
requirements.txt
.env.example
SPRINT1_COMPLETION_REPORT.md
```

The database itself is local and is not included in Git. Teammates populate a new local database using Docker Compose, the schema, the scripts, and the checked-in datasets.

## Prerequisites

- Windows 10/11 with PowerShell (commands below), or macOS/Linux with Docker Compose and Python.
- Docker Desktop with Compose v2 (or Docker Engine + Compose).
- Python 3.10 or newer.
- Git.

## Clone and configure locally

```powershell
git clone https://github.com/Sumant915/FreightIQ.git
Set-Location FreightIQ
Copy-Item .env.example .env
```

Edit `.env` locally. Set `POSTGRES_PASSWORD` to a unique local password and use the same password in `DATABASE_URL`. Use an alphanumeric password to avoid URL-encoding issues. `.env` is ignored by Git and must never be committed.

Create the Python environment:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

The scripts load `DATABASE_URL` from `.env`; alternatively, set it in the current PowerShell process:

```powershell
$env:DATABASE_URL = "postgresql://freightiq:YOUR_LOCAL_PASSWORD@localhost:5432/freightiq"
```

## Start and initialize the database

From the project root, after configuring `.env`:

```powershell
docker compose up -d
docker compose ps
```

Wait for the `timescaledb` service to report `healthy`. On an **empty** Docker volume, Compose runs `sql/001_schema.sql` automatically. Existing volumes are not recreated or migrated by this step; do not use `docker compose down -v` unless you intentionally want to delete your local database.

Database records are not in the Git repository. The first startup initializes schema tables; ingestion scripts then populate data from the included CSVs.

## Ingest data

Run from the project root in this order:

```powershell
python scripts/ingest_route_config.py --input data/route_configuration.csv
python scripts/ingest_freight_csv.py --input data/FreightIQ_Freight_Forecasting_2021_2025_Reviewed.csv
python scripts/ingest_brent_market.py
python scripts/ingest_coal_trade_volumes.py
```

These scripts use upserts/conflict handling so they can be rerun. Route distances loaded from the configuration remain derived. The coal script creates the separate `coal_trade_volumes` table with `CREATE TABLE IF NOT EXISTS`; it does not drop or recreate existing tables. The Brent importer registers its source dynamically and preserves the local CSV-mirror caveat.

`data/india_australia_coal_imports_2021_2025_clean.csv`, `data/Top-10-Countries-wise-Coal-Import_cleaned.csv`, and `data/TradeData_10_23_2026_16_1_45_cleaned.csv` are generated cleaned outputs; the corresponding raw inputs remain unchanged. World-total and unverified annual references are deliberately not imported as Australia-specific monthly observations.

## Validate

```powershell
python scripts/validate_db.py
```

To run the SQL checks in PowerShell:

```powershell
Get-Content .\sql\validation_queries.sql | docker exec -i freightiq-timescaledb psql -U freightiq -d freightiq -v ON_ERROR_STOP=1
```

Expected baseline for the current populated database:

- `freight_row_count`: 14,608; duplicate date/record keys: 0; nonpositive rates: 0.
- Three required destination ports and ten candidate lanes.
- Ten lane-distance records, all with status `derived`.
- 300 coal rows with no duplicate keys.
- 1,263 BRENT observations; approved observed BDI/BCI/BPI rows remain 0 and are reported as `BLOCKED`.

Exact recent command output and database counts are in the completion report. Row counts on a brand-new database may be lower until all ingestion commands have completed.

## Dataset inventory and provenance

| Dataset | Period / rows | Classification and intended use | Unit / provenance caveat |
|---|---:|---|---|
| `FreightIQ_Freight_Forecasting_2021_2025_Reviewed.csv` | 2021-2025; 14,608 DB rows | Synthetic freight scenarios only | USD/DMT; BDI/BPI fields are synthetic proxies |
| `route_configuration.csv` | 10 candidate routes | Derived route configuration | Nautical-mile distances are proxies; not navigation/AIS verified |
| `india_coal_imports_data.csv` → cleaned Australia subset | 2021-2025; 300 selected rows | Australia-origin India monthly trade observations | Apparent million tonnes; raw source does not explicitly define units |
| `TradeData_10_23_2026_16_1_45.csv` | 2026 Jan-Jul; 7 rows | Out-of-period World-total reference | kg, HS 2701; World partner is not Australia |
| `TradeData_10_23_2026_16_2_5.csv` | 2026 reference; 12 rows | World-total reference only | kg, HS 2701; not Australia-specific |
| `Top-10-Countries-wise-Coal-Import.csv` | 10 countries | Unverified country reference | MT columns; reporting year and publisher unknown; Australia included |
| `Import-of-Coal-and-Coke-last-ten-years-2.pdf` and annual reference CSV | FY 2015-16 to FY 2024-25; 10 annual rows | National India aggregate reference | MT; not Australia- or port-specific |
| `Month-wise-Coal-and-Coal-Products-Import.csv` | 12 rows | Quality-check reference | Unit/source metadata incomplete; suspicious 2024-25 zero values retained |
| `brent_daily.csv` | 2021-2025; 1,263 market rows | BRENT market input | USD/barrel; local CSV mirror associated with EIA history page, not direct API fetch |

The Comtrade-like CSVs do not embed a definitive publisher URL. `https://comtradeplus.un.org/` is recorded for the previously processed Australian-origin source, but exact query/export provenance should be captured if those files are regenerated.

## Limitations and remaining work

- Source-backed Australian thermal coal and coking coal price observations are not present.
- Verified BDI, BCI, BPI, and VLSFO historical observations are not present. Synthetic freight proxies are not substitutes.
- Independent navigational or AIS verification of the ten sea distances is outstanding.
- Verify the coal source's exact unit definition and persist query/export provenance.
- Confirm reporting year and publisher for the Top-10 country dataset before using it as annual data.
- Current coal HS selection avoids known overlapping subcodes but does not infer coking/non-coking quality where the source does not identify it.
- Berth constraints and route feasibility still require source review for any operational decisions.

## Team Git workflow

1. Start from the latest `main`: `git switch main` then `git pull --ff-only`.
2. Create a focused branch, for example `git switch -c docs/data-provenance`.
3. Avoid parallel edits to the same schema, importer, or report without coordinating with the team. Assign ownership or agree on one integration branch for shared files.
4. Make small commits with descriptive messages. Do not stage `.env`, `.venv`, database dumps, or generated local caches.
5. Push the feature branch and open a pull request to `main`. Review the diff, run validation, and resolve conflicts before merging.
6. Never force-push shared branches or commit credentials. Keep local passwords in ignored `.env` files.
