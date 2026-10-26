import csv
import os
import sys
from decimal import Decimal, InvalidOperation
from pathlib import Path

import psycopg
from db_config import get_database_url

DB_URL = get_database_url()

RAW_CSV = Path("data/india_coal_imports_data.csv")
CLEAN_CSV = Path("data/india_australia_coal_imports_2021_2025_clean.csv")
TOP10_RAW_CSV = Path("data/Top-10-Countries-wise-Coal-Import.csv")
TOP10_CLEAN_CSV = Path("data/Top-10-Countries-wise-Coal-Import_cleaned.csv")
WORLD_2026_RAW_CSV = Path("data/TradeData_10_23_2026_16_1_45.csv")
WORLD_2026_CLEAN_CSV = Path("data/TradeData_10_23_2026_16_1_45_cleaned.csv")

SELECTED_CODES = [
    "27011100",
    "27011200",
    "27011910",
    "27011920",
    "27011990",
]


def as_decimal(value):
    if value is None:
        return None
    value = str(value).strip()
    if value in {"", "-", "N/A", "NA", "NULL"}:
        return None
    try:
        dec = Decimal(value)
    except InvalidOperation:
        return None
    return dec if dec.is_finite() else None


def parse_yyyy_mm(raw_value):
    value = (raw_value or "").strip()
    if len(value) != 6 or not value.isdigit():
        return None
    year = int(value[:4])
    month = int(value[4:6])
    if year < 2021 or year > 2025:
        return None
    if month < 1 or month > 12:
        return None
    return year, month


def safe_insert_source(cur, source_name, source_url, dataset_type, provenance_notes, units=None, frequency=None, coverage_start=None, coverage_end=None):
    cur.execute(
        """
        INSERT INTO data_sources (
            source_name, source_url, dataset_type, units, frequency, coverage_start, coverage_end, provenance_notes
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (source_name, dataset_type)
        DO UPDATE SET
            source_url = EXCLUDED.source_url,
            units = EXCLUDED.units,
            frequency = EXCLUDED.frequency,
            coverage_start = EXCLUDED.coverage_start,
            coverage_end = EXCLUDED.coverage_end,
            provenance_notes = EXCLUDED.provenance_notes
        RETURNING source_id
        """,
        (source_name, source_url, dataset_type, units, frequency, coverage_start, coverage_end, provenance_notes),
    )
    return cur.fetchone()[0]


def ensure_coal_trade_table(cur):
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS coal_trade_volumes (
            month_start DATE NOT NULL,
            origin_country TEXT NOT NULL,
            destination_country TEXT NOT NULL,
            hs_code TEXT NOT NULL,
            commodity_group TEXT NOT NULL,
            quantity_value NUMERIC(18,6) NOT NULL,
            unit TEXT NOT NULL DEFAULT 'million_tonnes',
            source_id BIGINT NOT NULL REFERENCES data_sources(source_id),
            source_record_ref TEXT,
            value_status TEXT NOT NULL DEFAULT 'reported' CHECK (value_status IN ('reported','suspected_missing','zero_reported')),
            notes TEXT,
            PRIMARY KEY (month_start, origin_country, destination_country, hs_code, source_id)
        )
        """
    )


def write_reference_top10_csv(path):
    if not TOP10_RAW_CSV.exists():
        return
    with TOP10_RAW_CSV.open('r', encoding='utf-8-sig', newline='') as fh:
        rows = list(csv.DictReader(fh))
    with path.open('w', newline='', encoding='utf-8') as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=[
                'country',
                'reporting_year',
                'reporting_period',
                'coking_coal_mt',
                'non_coking_coal_mt',
                'total_coal_mt',
                'source_name',
                'source_url',
                'period_status',
                'classification',
                'notes',
            ],
        )
        writer.writeheader()
        for row in rows:
            country = (row.get('Country') or '').strip()
            writer.writerow({
                'country': country,
                'reporting_year': '',
                'reporting_period': 'unknown',
                'coking_coal_mt': row.get('Coking_Coal_MT', ''),
                'non_coking_coal_mt': row.get('Non_Coking_Coal_MT', ''),
                'total_coal_mt': row.get('Total_Coal_MT', ''),
                'source_name': 'Top-10 Countries-wise Coal Import dataset',
                'source_url': 'unknown',
                'period_status': 'unverified_reference',
                'classification': 'annual_country_reference',
                'notes': 'Reporting year and source URL were not embedded in the file, so the period is preserved as an unverified annual country reference rather than a validated 2021-2025 time series.',
            })
    print(f"Saved cleaned reference CSV to {path} ({len(rows)} rows).")


def write_reference_world_2026_csv(path):
    if not WORLD_2026_RAW_CSV.exists():
        return
    with WORLD_2026_RAW_CSV.open('r', encoding='utf-8-sig', newline='') as fh:
        rows = list(csv.DictReader(fh))
    filtered = []
    for row in rows:
        if row.get('partnerDesc') != 'World':
            continue
        if row.get('flowDesc') != 'Import':
            continue
        if row.get('cmdCode') != '2701':
            continue
        filtered.append({
            'month': row.get('refMonth', '').strip(),
            'period': row.get('period', '').strip(),
            'reporter_country': row.get('reporterDesc', '').strip(),
            'partner_country': row.get('partnerDesc', '').strip(),
            'commodity_code': row.get('cmdCode', '').strip(),
            'commodity_desc': row.get('cmdDesc', '').strip(),
            'quantity_kg': row.get('qty', '').strip(),
            'quantity_unit': row.get('qtyUnitAbbr', '').strip(),
            'value_usd': row.get('primaryValue', '').strip(),
            'source_name': 'UN Comtrade India coal import world totals (2026 monthly reference)',
            'source_url': 'unknown',
            'period_status': 'out_of_model_period_reference',
            'classification': 'world_total_reference',
            'notes': 'World aggregate imports are not Australia-specific and must not be treated as Australian origin volumes. These observations are retained only as a separate 2026 reference dataset.',
        })
    with path.open('w', newline='', encoding='utf-8') as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=[
                'month',
                'period',
                'reporter_country',
                'partner_country',
                'commodity_code',
                'commodity_desc',
                'quantity_kg',
                'quantity_unit',
                'value_usd',
                'source_name',
                'source_url',
                'period_status',
                'classification',
                'notes',
            ],
        )
        writer.writeheader()
        for row in filtered:
            writer.writerow(row)
    print(f"Saved cleaned 2026 reference CSV to {path} ({len(filtered)} rows).")


def main():
    if not RAW_CSV.exists():
        raise SystemExit(f"Missing required raw coal import CSV: {RAW_CSV}")

    with RAW_CSV.open("r", encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        rows = list(reader)

    if not rows:
        raise SystemExit("Raw coal import CSV contains no rows.")

    prepared = []
    for row in rows:
        parsed = parse_yyyy_mm(row.get("YYYYMM"))
        if parsed is None:
            continue
        year, month = parsed
        month_start = f"{year:04d}-{month:02d}-01"
        for code in SELECTED_CODES:
            raw_value = row.get(f"AUS.{code}")
            quantity_value = as_decimal(raw_value)
            if quantity_value is None:
                continue
            prepared.append(
                {
                    "month_start": month_start,
                    "year": year,
                    "month": month,
                    "origin_country": "Australia",
                    "destination_country": "India",
                    "hs_code": code,
                    "hs_group": "coal",
                    "quantity_value": quantity_value,
                    "unit": "million_tonnes",
                    "source_name": "India monthly import dataset (Australia origin)",
                    "source_url": "https://comtradeplus.un.org/",
                    "source_record_ref": f"AUS.{code}",
                    "notes": (
                        "Australia-origin monthly import values from the source matrix were retained in their native scale, which appears to be million tonnes. "
                        "Only non-overlapping direct coal HS categories were retained; 27011210 and 27011290 were excluded to avoid double-counting with aggregate 27011200."
                    ),
                }
            )

    if not prepared:
        raise SystemExit("No usable Australia-origin coal import rows were found for 2021-2025.")

    source_name = "India monthly import dataset (Australia origin, cleaned 2021-2025)"
    source_url = "https://comtradeplus.un.org/"
    source_note = (
        "Cleaned Australia-origin monthly coal import subset for 2021-2025 extracted from the broader India import matrix. "
        "Only direct coal HS codes in the 2701 family were retained, excluding overlapping subcodes and coal products to avoid double counting. "
        "The source values appear to be in million tonnes and were preserved in their native unit rather than converted without a documented conversion factor."
    )

    with psycopg.connect(DB_URL) as conn:
        with conn.cursor() as cur:
            ensure_coal_trade_table(cur)
            source_id = safe_insert_source(
                cur, source_name, source_url, "mixed", source_note,
                units="million tonnes", frequency="monthly",
                coverage_start="2021-01-01", coverage_end="2025-12-01",
            )
            for item in prepared:
                value_status = "reported"
                if item["quantity_value"] == 0:
                    value_status = "zero_reported"
                cur.execute(
                    """
                    INSERT INTO coal_trade_volumes (
                        month_start, origin_country, destination_country, hs_code, commodity_group,
                        quantity_value, unit, source_id, source_record_ref, value_status, notes
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (month_start, origin_country, destination_country, hs_code, source_id)
                    DO UPDATE SET
                        commodity_group = EXCLUDED.commodity_group,
                        quantity_value = EXCLUDED.quantity_value,
                        unit = EXCLUDED.unit,
                        source_record_ref = EXCLUDED.source_record_ref,
                        value_status = EXCLUDED.value_status,
                        notes = EXCLUDED.notes
                    """,
                    (
                        item["month_start"],
                        item["origin_country"],
                        item["destination_country"],
                        item["hs_code"],
                        item["hs_group"],
                        item["quantity_value"],
                        item["unit"],
                        source_id,
                        item["source_record_ref"],
                        value_status,
                        item["notes"],
                    ),
                )
            safe_insert_source(
                cur,
                "Top-10 Countries-wise Coal Import dataset",
                "unknown",
                "unknown",
                "Source URL and reporting year were not embedded in the file; the data is retained as an unverified annual country-reference dataset only.",
                units="million tonnes",
                frequency="annual",
            )
            safe_insert_source(
                cur,
                "UN Comtrade India coal import world totals (2026 monthly reference)",
                "unknown",
                "mixed",
                "World aggregate records do not identify Australia as the origin and are retained only as a separate out-of-period reference dataset.",
                units="kg",
                frequency="monthly",
                coverage_start="2026-01-01",
                coverage_end="2026-07-01",
            )
            conn.commit()

    with CLEAN_CSV.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=[
                "month_start",
                "origin_country",
                "destination_country",
                "hs_code",
                "commodity_group",
                "quantity_value",
                "unit",
                "source_name",
                "source_url",
                "source_record_ref",
                "value_status",
                "notes",
            ],
        )
        writer.writeheader()
        for item in prepared:
            writer.writerow(
                {
                    "month_start": item["month_start"],
                    "origin_country": item["origin_country"],
                    "destination_country": item["destination_country"],
                    "hs_code": item["hs_code"],
                    "commodity_group": item["hs_group"],
                    "quantity_value": str(item["quantity_value"]),
                    "unit": item["unit"],
                    "source_name": item["source_name"],
                    "source_url": item["source_url"],
                    "source_record_ref": item["source_record_ref"],
                    "value_status": "reported" if item["quantity_value"] != 0 else "zero_reported",
                    "notes": item["notes"],
                }
            )

    write_reference_top10_csv(TOP10_CLEAN_CSV)
    write_reference_world_2026_csv(WORLD_2026_CLEAN_CSV)

    print(f"Prepared {len(prepared)} Australia-origin coal import rows from {RAW_CSV}.")
    print(f"Saved cleaned CSV to {CLEAN_CSV}.")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise
