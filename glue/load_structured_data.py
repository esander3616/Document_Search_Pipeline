import sys, csv, json, io
import boto3
import pg8000.native
from awsglue.utils import getResolvedOptions

args = getResolvedOptions(sys.argv, ['bucket', 'redshift_host', 'redshift_password'])
BUCKET = args['bucket']

s3 = boto3.client('s3')
conn = pg8000.native.Connection(
    user="admin", password=args['redshift_password'],
    host=args['redshift_host'], port=5439, database="dev"
)

obj = s3.get_object(Bucket=BUCKET, Key='csv-json/customers/customers.csv')
reader = csv.DictReader(io.StringIO(obj['Body'].read().decode('utf-8')))
count = 0
for row in reader:
    conn.run(
        """INSERT INTO customers (customer_id, email, segment, region, signup_date,
           monthly_spend, status, cancelled_date)
           VALUES (:cid, :email, :seg, :reg, :signup, :spend, :status, :cancelled)""",
        cid=row['customer_id'], email=row['email'], seg=row['segment'], reg=row['region'],
        signup=row['signup_date'], spend=float(row['monthly_spend']), status=row['status'],
        cancelled=row['cancelled_date'] if row['cancelled_date'] else None
    )
    count += 1
print(f"Loaded {count} customer rows")

obj = s3.get_object(Bucket=BUCKET, Key='csv-json/usage/product_usage.json')
records = json.loads(obj['Body'].read())
for r in records:
    conn.run(
        """INSERT INTO usage_events (user_id, feature_used, usage_count, session_date, device_type)
           VALUES (:uid, :feat, :cnt, :sess, :dev)""",
        uid=r['user_id'], feat=r['feature_used'], cnt=r['usage_count'],
        sess=r['session_date'], dev=r['device_type']
    )
print(f"Loaded {len(records)} usage records")

conn.close()