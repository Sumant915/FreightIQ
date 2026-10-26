
import argparse
import csv
import os
import sys
from pathlib import Path
from decimal import Decimal

import psycopg
from db_config import get_database_url

DB_URL = get_database_url()

def val(value):
    if value is None or str(value).strip() == "":
        return None
    return str(value).strip()


def dec(value):
    cleaned = val(value)
    return None if cleaned is None else Decimal(cleaned)


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Load candidate routes and derived distance proxies "
            "from route_configuration.csv"
        )
    )
    parser.add_argument("--input", required=True)
    args = parser.parse_args()

    path = Path(args.input)

    if not path.exists():
        raise SystemExit(f"Input file not found: {path}")

    with path.open(newline="", encoding="utf-8-sig") as file:
        rows = list(csv.DictReader(file))

    if not rows:
        raise SystemExit("Input CSV contains no data rows.")

    required = {
        "route_id",
        "origin_country",
        "origin_port",
        "destination_country",
        "destination_port",
        "commodity",
        "vessel_class",
        "route_distance_nm",
        "distance_method",
    }

    missing = required - set(rows[0].keys())
    if missing:
        raise SystemExit(f"Missing required columns: {sorted(missing)}")

    processed = 0
    proxy_inserted = 0
    proxy_skipped_invalid = 0
    proxy_skipped_conflict = 0

    with psycopg.connect(DB_URL) as conn:
        with conn.cursor() as cur:

            # Register the CSV source.
            cur.execute(
                """
                INSERT INTO data_sources (
                    source_name,
                    publisher,
                    dataset_type,
                    units,
                    frequency,
                    provenance_notes
                )
                VALUES (
                    %s,
                    'FreightIQ team',
                    'mixed',
                    'nautical miles',
                    'route-level',
                    %s
                )
                ON CONFLICT (source_name, dataset_type)
                DO UPDATE SET
                    provenance_notes = EXCLUDED.provenance_notes
                RETURNING source_id
                """,
                (
                    path.name,
                    (
                        "Candidate route scenarios and approximate derived "
                        "distances. Coordinates and distance allowances require "
                        "review; direct fixture evidence was not established."
                    ),
                ),
            )
            source_id = cur.fetchone()[0]

            for row in rows:
                origin = row["origin_port"].strip()
                destination = row["destination_port"].strip()
                origin_country = row["origin_country"].strip()
                destination_country = row["destination_country"].strip()

                origin_lat = dec(row.get("origin_latitude_assumed"))
                origin_lon = dec(row.get("origin_longitude_assumed"))
                destination_lat = dec(row.get("destination_latitude_assumed"))
                destination_lon = dec(row.get("destination_longitude_assumed"))

                # Insert ports without replacing existing non-null coordinates.
                for name, country, latitude, longitude in [
                    (origin, origin_country, origin_lat, origin_lon),
                    (
                        destination,
                        destination_country,
                        destination_lat,
                        destination_lon,
                    ),
                ]:
                    cur.execute(
                        """
                        INSERT INTO ports (
                            port_name,
                            country,
                            latitude,
                            longitude,
                            coordinate_status,
                            source_id,
                            notes
                        )
                        VALUES (
                            %s, %s, %s, %s,
                            'approximate_assumed',
                            %s,
                            'Coordinates from route configuration; not for navigation.'
                        )
                        ON CONFLICT (port_name, country)
                        DO UPDATE SET
                            latitude = COALESCE(
                                ports.latitude, EXCLUDED.latitude
                            ),
                            longitude = COALESCE(
                                ports.longitude, EXCLUDED.longitude
                            )
                        """,
                        (
                            name,
                            country,
                            latitude,
                            longitude,
                            source_id,
                        ),
                    )

                cur.execute(
                    """
                    SELECT port_id
                    FROM ports
                    WHERE port_name = %s AND country = %s
                    """,
                    (origin, origin_country),
                )
                origin_id = cur.fetchone()[0]

                cur.execute(
                    """
                    SELECT port_id
                    FROM ports
                    WHERE port_name = %s AND country = %s
                    """,
                    (destination, destination_country),
                )
                destination_id = cur.fetchone()[0]

                notes = "; ".join(
                    filter(
                        None,
                        [
                            val(row.get("route_evidence_and_limitations")),
                            val(row.get("destination_port_constraint")),
                            val(row.get("absolute_freight_scale_status")),
                        ],
                    )
                )

                # Upsert the candidate trade lane.
                cur.execute(
                    """
                    INSERT INTO trade_lanes (
                        route_id,
                        origin_port_id,
                        destination_port_id,
                        commodity,
                        vessel_class,
                        feasibility_status,
                        direct_fixture_evidence,
                        source_id,
                        notes
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, FALSE, %s, %s)
                    ON CONFLICT (route_id)
                    DO UPDATE SET
                        origin_port_id = EXCLUDED.origin_port_id,
                        destination_port_id = EXCLUDED.destination_port_id,
                        commodity = EXCLUDED.commodity,
                        vessel_class = EXCLUDED.vessel_class,
                        feasibility_status = EXCLUDED.feasibility_status,
                        source_id = EXCLUDED.source_id,
                        notes = EXCLUDED.notes
                    """,
                    (
                        row["route_id"],
                        origin_id,
                        destination_id,
                        row["commodity"],
                        row["vessel_class"],
                        val(row.get("feasibility_status"))
                        or "candidate_scenario",
                        source_id,
                        notes,
                    ),
                )

                cur.execute(
                    """
                    SELECT lane_id
                    FROM trade_lanes
                    WHERE route_id = %s
                    """,
                    (row["route_id"],),
                )
                lane_id = cur.fetchone()[0]

                distance = dec(row["route_distance_nm"])

                if distance is None or distance <= 0:
                    proxy_skipped_invalid += 1
                    processed += 1
                    continue

                distance_method = (
                    val(row.get("distance_method"))
                    or "CSV-derived proxy; method unspecified"
                )
                coordinate_status = (
                    val(row.get("coordinate_source_status")) or ""
                )

                cur.execute(
                    """
                    INSERT INTO lane_distances (
                        lane_id,
                        distance_nm,
                        method,
                        distance_status,
                        source_id,
                        notes
                    )
                    VALUES (%s, %s, %s, 'derived', %s, %s)
                    ON CONFLICT (lane_id, distance_nm, method)
                    DO NOTHING
                    """,
                    (
                        lane_id,
                        distance,
                        distance_method,
                        source_id,
                        (
                            "CSV proxy only; not a navigational or "
                            "AIS-verified sailing distance. "
                            + coordinate_status
                        ),
                    ),
                )

                if cur.rowcount == 1:
                    proxy_inserted += 1
                else:
                    proxy_skipped_conflict += 1

                processed += 1

            cur.execute("SELECT COUNT(*) FROM trade_lanes")
            lane_count = cur.fetchone()[0]

        conn.commit()

    print(f"Route config processed: {processed} rows")
    print(f"Candidate lanes currently in DB: {lane_count}")
    print(f"CSV proxy distances inserted: {proxy_inserted}")
    print(f"Proxies skipped (duplicate key): {proxy_skipped_conflict}")
    print(f"Invalid/missing distances skipped: {proxy_skipped_invalid}")
    print("Done. Existing distance records were not deleted or overwritten.")


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(f"ERROR: {error}", file=sys.stderr)
        raise
