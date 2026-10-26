import argparse, csv, json, os, sys
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path
import psycopg
from psycopg.types.json import Jsonb
from db_config import get_database_url

DB_URL = get_database_url()

def dec(v):
    if v is None or str(v).strip() == '': return None
    try: return Decimal(str(v))
    except InvalidOperation: return None

def main():
    ap=argparse.ArgumentParser(description='Idempotently ingest synthetic FreightIQ CSV into PostgreSQL/TimescaleDB.')
    ap.add_argument('--input', required=True, help='Path to FreightIQ CSV')
    args=ap.parse_args(); path=Path(args.input)
    if not path.exists(): raise SystemExit(f'Input file not found: {path}')
    with path.open(newline='', encoding='utf-8-sig') as f:
        reader=csv.DictReader(f); rows=list(reader)
    required={'record_id','assessment_date','origin_country','origin_port','destination_country','destination_port','route_id','commodity','vessel_class','freight_rate_usd_per_tonne'}
    missing=required-set(reader.fieldnames or [])
    if missing: raise SystemExit(f'Missing required columns: {sorted(missing)}')
    with psycopg.connect(DB_URL) as conn:
      with conn.cursor() as cur:
        cur.execute("""INSERT INTO data_sources(source_name,publisher,source_url,dataset_type,units,frequency,coverage_start,coverage_end,provenance_notes)
          VALUES (%s,%s,%s,'synthetic','USD/DMT','daily',%s,%s,%s)
          ON CONFLICT (source_name,dataset_type) DO UPDATE SET provenance_notes=EXCLUDED.provenance_notes
          RETURNING source_id""", (path.name,'FreightIQ team',None,
             min(date.fromisoformat(r['assessment_date']) for r in rows),
             max(date.fromisoformat(r['assessment_date']) for r in rows),
             'Synthetic freight-rate dataset. BDI/BPI columns in this file are synthetic proxies, not observed Baltic Exchange history.'))
        source_id=cur.fetchone()[0]
        cur.execute("INSERT INTO ingestion_runs(source_id,file_name,status,rows_read,rows_attempted) VALUES (%s,%s,'running',%s,%s) RETURNING ingestion_run_id",(source_id,path.name,len(rows),len(rows)))
        run_id=cur.fetchone()[0]
        for r in rows:
          origin=r['origin_port'].strip(); dest=r['destination_port'].strip()
          for pname,country in [(origin,r['origin_country'].strip()),(dest,r['destination_country'].strip())]:
            cur.execute("""INSERT INTO ports(port_name,country,coordinate_status,notes)
              VALUES (%s,%s,'unknown','Imported as a port name from the synthetic dataset; coordinates/physical limits require source verification.')
              ON CONFLICT (port_name,country) DO NOTHING""",(pname,country))
          cur.execute('SELECT port_id FROM ports WHERE port_name=%s AND country=%s',(origin,r['origin_country'].strip())); origin_id=cur.fetchone()[0]
          cur.execute('SELECT port_id FROM ports WHERE port_name=%s AND country=%s',(dest,r['destination_country'].strip())); dest_id=cur.fetchone()[0]
          cur.execute("""INSERT INTO trade_lanes(route_id,origin_port_id,destination_port_id,commodity,vessel_class,feasibility_status,direct_fixture_evidence,source_id,notes)
            VALUES (%s,%s,%s,%s,%s,'candidate_synthetic_scenario',FALSE,%s,'Candidate scenario from synthetic data; not proof of an executed fixture.')
            ON CONFLICT (route_id) DO NOTHING""",(r['route_id'],origin_id,dest_id,r['commodity'],r['vessel_class'],source_id))
          cur.execute('SELECT lane_id FROM trade_lanes WHERE route_id=%s',(r['route_id'],)); lane_id=cur.fetchone()[0]
          rate=dec(r.get('freight_rate_usd_per_tonne'))
          if rate is None or rate <= 0: raise ValueError(f"Invalid freight rate for record_id={r['record_id']}")
          cur.execute("""INSERT INTO freight_observations(assessment_date,record_id,source_id,lane_id,route_id,origin_port,destination_port,commodity,vessel_class,freight_rate_usd_per_tonne,rate_unit,route_distance_nm,bdi_proxy_value,bpi_proxy_value,target_data_type,index_data_type,extreme_flag,source_reference,assumptions_notes,raw_payload)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'synthetic',%s,%s,%s,%s,%s)
            ON CONFLICT (assessment_date,record_id) DO UPDATE SET
              source_id=EXCLUDED.source_id,lane_id=EXCLUDED.lane_id,route_id=EXCLUDED.route_id,origin_port=EXCLUDED.origin_port,destination_port=EXCLUDED.destination_port,
              commodity=EXCLUDED.commodity,vessel_class=EXCLUDED.vessel_class,freight_rate_usd_per_tonne=EXCLUDED.freight_rate_usd_per_tonne,rate_unit=EXCLUDED.rate_unit,
              route_distance_nm=EXCLUDED.route_distance_nm,bdi_proxy_value=EXCLUDED.bdi_proxy_value,bpi_proxy_value=EXCLUDED.bpi_proxy_value,
              target_data_type=EXCLUDED.target_data_type,index_data_type=EXCLUDED.index_data_type,extreme_flag=EXCLUDED.extreme_flag,
              source_reference=EXCLUDED.source_reference,assumptions_notes=EXCLUDED.assumptions_notes,raw_payload=EXCLUDED.raw_payload,imported_at=now()""",
            (date.fromisoformat(r['assessment_date']),r['record_id'],source_id,lane_id,r['route_id'],origin,dest,r['commodity'],r['vessel_class'],rate,
             r.get('rate_unit'),dec(r.get('route_distance_nm')),dec(r.get('bdi_value')),dec(r.get('bpi_value')),
             'synthetic_proxy_not_historical_observation',str(r.get('extreme_flag','')).lower() in ('true','1','yes'),r.get('source_reference'),r.get('assumptions_notes'),Jsonb(r)))
        cur.execute("UPDATE ingestion_runs SET status='success',finished_at=now() WHERE ingestion_run_id=%s",(run_id,))
        cur.execute('SELECT count(*) FROM freight_observations'); total=cur.fetchone()[0]
        cur.execute('SELECT count(*) FROM ports'); ports=cur.fetchone()[0]
        cur.execute('SELECT count(*) FROM trade_lanes'); lanes=cur.fetchone()[0]
      conn.commit()
    print(f'Import finished. Rows read/attempted: {len(rows)}; database freight rows: {total}; ports: {ports}; lanes: {lanes}.')
    print('Safe to rerun: conflicts update the same (assessment_date, record_id) instead of inserting duplicates.')

if __name__=='__main__':
 try: main()
 except Exception as e:
  print(f'ERROR: {e}',file=sys.stderr); raise
