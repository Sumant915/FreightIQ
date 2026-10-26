import csv
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path

import psycopg

from db_config import get_database_url

DB_URL = get_database_url()
CSV_PATH = Path("data/brent_daily.csv")
SOURCE_NAME = "Brent Crude Oil Spot Price - Europe"
SOURCE_URL = "https://www.eia.gov/dnav/pet/hist/RBRTED.htm"
PROVENANCE_NOTES = (
    "Observations were loaded from the bundled local CSV mirror. The EIA URL "
    "identifies the underlying series, but this ingestion did not fetch the "
    "observations directly from the EIA API or verify the mirror's lineage."
)


def main():
    if not CSV_PATH.exists():
        raise SystemExit(f"Missing file: {CSV_PATH}")

    observations = []
    with CSV_PATH.open("r", encoding="utf-8-sig", newline="") as csv_file:
        reader = csv.DictReader(csv_file)
        if not {"Date", "Price"}.issubset(reader.fieldnames or []):
            raise SystemExit("CSV must contain Date and Price columns.")

        for row in reader:
            try:
                observed_on = date.fromisoformat(row["Date"].strip())
                value = Decimal(row["Price"].strip())
            except (ValueError, InvalidOperation, AttributeError):
                continue

            if (
                date(2021, 1, 1) <= observed_on <= date(2025, 12, 31)
                and value.is_finite()
                and value > 0
            ):
                observations.append((observed_on, value))

    if not observations:
        raise SystemExit("No valid 2021-2025 rows found.")

    with psycopg.connect(DB_URL) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO data_sources (
                    source_name, publisher, source_url, dataset_type, units,
                    frequency, coverage_start, coverage_end, provenance_notes
                )
                VALUES (
                    %s, 'U.S. Energy Information Administration', %s, 'observed',
                    'USD per barrel', 'daily', %s, %s, %s
                )
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
                (
                    SOURCE_NAME,
                    SOURCE_URL,
                    min(item[0] for item in observations),
                    max(item[0] for item in observations),
                    PROVENANCE_NOTES,
                ),
            )
            source_id = cursor.fetchone()[0]
            cursor.executemany(
                """
                INSERT INTO market_observations (
                    observed_at, source_id, indicator_code, value, unit,
                    frequency, data_type, source_record_ref, notes
                )
                VALUES (
                    %s, %s, 'BRENT', %s, 'USD/barrel',
                    'daily', 'observed', 'bundled Brent CSV mirror', %s
                )
                ON CONFLICT (observed_at, source_id, indicator_code) DO NOTHING
                """,
                [
                    (
                        f"{observed_on.isoformat()} 00:00:00+00",
                        source_id,
                        value,
                        PROVENANCE_NOTES,
                    )
                    for observed_on, value in observations
                ],
            )
            inserted_count = cursor.rowcount
            cursor.execute(
                """
                SELECT count(*), min(observed_at)::date, max(observed_at)::date
                FROM market_observations
                WHERE source_id = %s AND indicator_code = 'BRENT'
                """,
                (source_id,),
            )
            total_count, first_date, last_date = cursor.fetchone()

    print(f"Valid CSV observations: {len(observations)}")
    print(f"New observations inserted: {inserted_count}")
    print(
        f"Database BRENT observations: {total_count}; "
        f"coverage: {first_date} to {last_date}"
    )
    print("Source caveat: observations came from the bundled CSV mirror, not a direct EIA API fetch.")


if __name__ == "__main__":
    main()
