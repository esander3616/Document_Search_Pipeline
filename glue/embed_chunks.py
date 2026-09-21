import os
os.environ["HF_HOME"] = "/tmp/hf_home"
os.environ["TRANSFORMERS_CACHE"] = "/tmp/transformers_cache"
os.environ["SENTENCE_TRANSFORMERS_HOME"] = "/tmp/st_home"

import sys, json, boto3
from awsglue.utils import getResolvedOptions
from sentence_transformers import SentenceTransformer
import pg8000.native
from opensearchpy import OpenSearch, RequestsHttpConnection
from requests_aws4auth import AWS4Auth

args = getResolvedOptions(sys.argv, [
    'input_key', 'bucket', 'redshift_host', 'redshift_password', 'opensearch_host'
])

BUCKET = args['bucket']
REDSHIFT_HOST = args['redshift_host']
REDSHIFT_PASSWORD = args['redshift_password']
OPENSEARCH_HOST = args['opensearch_host']

s3 = boto3.client('s3')
obj = s3.get_object(Bucket=BUCKET, Key=args['input_key'])
chunks = json.loads(obj['Body'].read())
doc_key = args['input_key']

model = SentenceTransformer('all-MiniLM-L6-v2')
embeddings = model.encode(chunks)

conn = pg8000.native.Connection(user="admin", password=REDSHIFT_PASSWORD,
                                 host=REDSHIFT_HOST, port=5439, database="dev")
for i, chunk in enumerate(chunks):
    conn.run(
        "INSERT INTO raw_chunks (doc_key, chunk_index, chunk_text) VALUES (:doc_key, :idx, :text)",
        doc_key=doc_key, idx=i, text=chunk
    )
conn.close()

region = 'us-east-1'
credentials = boto3.Session().get_credentials()
awsauth = AWS4Auth(credentials.access_key, credentials.secret_key, region, 'es',
                    session_token=credentials.token)
client = OpenSearch(
    hosts=[{'host': OPENSEARCH_HOST, 'port': 443}],
    http_auth=awsauth, use_ssl=True, verify_certs=True,
    connection_class=RequestsHttpConnection
)
for i, (chunk, emb) in enumerate(zip(chunks, embeddings)):
    client.index(index="document-chunks", body={
        "text": chunk, "embedding": emb.tolist(), "doc_key": doc_key, "chunk_index": i
    })

print(f"Wrote {len(chunks)} chunks to Redshift and OpenSearch")
