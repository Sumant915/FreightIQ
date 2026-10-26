import os
import psycopg
from db_config import get_database_url
DB_URL = get_database_url()
checks=[
('freight_row_count',"SELECT count(*) FROM freight_observations"),
('duplicate_date_record_ids',"SELECT count(*) FROM (SELECT assessment_date,record_id FROM freight_observations GROUP BY 1,2 HAVING count(*)>1) x"),
('nonpositive_rates',"SELECT count(*) FROM freight_observations WHERE freight_rate_usd_per_tonne<=0 OR freight_rate_usd_per_tonne IS NULL"),
('rows_missing_port_names',"SELECT count(*) FROM freight_observations WHERE origin_port IS NULL OR destination_port IS NULL OR btrim(origin_port)='' OR btrim(destination_port)=''"),
('required_destination_ports_present',"SELECT count(DISTINCT destination_port) FROM freight_observations WHERE destination_port IN ('Paradip','Visakhapatnam','Haldia')"),
('candidate_lanes_count',"SELECT count(*) FROM trade_lanes"),
('approved_observed_index_rows',"SELECT count(*) FROM market_observations WHERE indicator_code IN ('BDI','BCI','BPI') AND data_type='observed'"),
]
with psycopg.connect(DB_URL) as conn:
 with conn.cursor() as cur:
  for name,sql in checks:
   cur.execute(sql); value=cur.fetchone()[0]
   if name=='duplicate_date_record_ids': status='PASS' if value==0 else 'FAIL'
   elif name=='nonpositive_rates': status='PASS' if value==0 else 'FAIL'
   elif name=='required_destination_ports_present': status='PASS' if value==3 else 'FAIL'
   elif name=='approved_observed_index_rows': status='BLOCKED' if value==0 else 'DATA_PRESENT_VERIFY_PROVENANCE'
   else: status='INFO'
   print(f'{name}: {value} [{status}]')
  cur.execute("SELECT destination_port,count(*) FROM freight_observations GROUP BY destination_port ORDER BY destination_port")
  print('Rows by destination:')
  for row in cur.fetchall(): print(f'  {row[0]}: {row[1]}')
  cur.execute("SELECT min(assessment_date),max(assessment_date),count(DISTINCT assessment_date) FROM freight_observations")
  print('Freight date coverage:',cur.fetchone())
