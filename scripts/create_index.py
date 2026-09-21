import os
import boto3
from opensearchpy import OpenSearch, RequestsHttpConnection
from requests_aws4auth import AWS4Auth

OPENSEARCH_HOST = os.environ.get("OPENSEARCH_HOST")
if not OPENSEARCH_HOST:
    raise SystemExit("Set OPENSEARCH_HOST to your domain endpoint first.")

region = 'us-east-1'
credentials = boto3.Session().get_credentials()
awsauth = AWS4Auth(credentials.access_key, credentials.secret_key, region, 'es',
                    session_token=credentials.token)
client = OpenSearch(hosts=[{'host': OPENSEARCH_HOST, 'port': 443}], http_auth=awsauth,
                     use_ssl=True, verify_certs=True, connection_class=RequestsHttpConnection)

index_body = {
    "settings": {"index.knn": True},
    "mappings": {"properties": {
        "text": {"type": "text"}, "embedding": {"type": "knn_vector", "dimension": 384},
        "doc_key": {"type": "keyword"}, "chunk_index": {"type": "integer"}
    }}
}
client.indices.create(index="document-chunks", body=index_body)
print("Index created")
