import boto3, json
import pg8000.native
from opensearchpy import OpenSearch, RequestsHttpConnection
from requests_aws4auth import AWS4Auth
from sentence_transformers import SentenceTransformer

REDSHIFT_HOST = "capstone-redshift.cnsdmrdqgxxb.us-east-1.redshift.amazonaws.com"
REDSHIFT_PASSWORD = "YourTestPass123!"
OPENSEARCH_HOST = "search-capstone-search-ladsv6jj5rjdm353pf3s35t3t4.us-east-1.es.amazonaws.com"

bedrock = boto3.client("bedrock-runtime", region_name="us-east-1")
account_id = boto3.client("sts").get_caller_identity()["Account"]
MODEL_ID = f"arn:aws:bedrock:us-east-1:{account_id}:inference-profile/us.anthropic.claude-sonnet-4-6"

_st_model = None
def get_st_model():
    global _st_model
    if _st_model is None:
        _st_model = SentenceTransformer('all-MiniLM-L6-v2')
    return _st_model

def invoke_claude(prompt: str, max_tokens: int = 500) -> dict:
    body = {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": max_tokens,
        "messages": [{"role": "user", "content": prompt}]
    }
    response = bedrock.invoke_model(modelId=MODEL_ID, body=json.dumps(body))
    result = json.loads(response["body"].read())
    return {"text": result["content"][0]["text"],
            "input_tokens": result["usage"]["input_tokens"],
            "output_tokens": result["usage"]["output_tokens"]}

BLOCKED_KEYWORDS = ["DROP", "DELETE", "UPDATE", "INSERT", "ALTER", "TRUNCATE", "GRANT", "REVOKE"]
def validate_sql(query: str) -> dict:
    query_upper = query.upper().strip()
    for keyword in BLOCKED_KEYWORDS:
        if f" {keyword} " in f" {query_upper} " or query_upper.startswith(keyword):
            return {"valid": False, "reason": f"Blocked: {keyword} not permitted"}
    if not query_upper.startswith("SELECT"):
        return {"valid": False, "reason": "Only SELECT queries are permitted"}
    return {"valid": True, "reason": "OK"}

SCHEMA_CONTEXT = """
Table: customers
  customer_id VARCHAR, email VARCHAR, segment VARCHAR (Enterprise/Mid-Market/SMB/Self-Serve),
  region VARCHAR, signup_date DATE, monthly_spend DECIMAL, status VARCHAR (active/cancelled),
  cancelled_date DATE

Table: usage_events
  user_id VARCHAR, feature_used VARCHAR, usage_count INT, session_date DATE, device_type VARCHAR
"""

def generate_sql(question: str) -> str:
    prompt = f"""You are a SQL generator for Amazon Redshift. Output ONLY a single valid SELECT
statement, no markdown, no explanation, no semicolon-separated multiple statements.

Schema:
{SCHEMA_CONTEXT}

Question: {question}

SQL:"""
    result = invoke_claude(prompt, max_tokens=300)
    sql = result["text"].strip().strip("`").replace("sql\n", "").strip()
    return sql

def execute_sql(query: str):
    conn = pg8000.native.Connection(user="admin", password=REDSHIFT_PASSWORD,
                                     host=REDSHIFT_HOST, port=5439, database="dev")
    rows = conn.run(query)
    columns = [c["name"] for c in conn.columns] if conn.columns else []
    conn.close()
    return [dict(zip(columns, row)) for row in rows]

def get_opensearch_client():
    region = 'us-east-1'
    credentials = boto3.Session().get_credentials()
    awsauth = AWS4Auth(credentials.access_key, credentials.secret_key, region, 'es',
                        session_token=credentials.token)
    return OpenSearch(hosts=[{'host': OPENSEARCH_HOST, 'port': 443}], http_auth=awsauth,
                       use_ssl=True, verify_certs=True, connection_class=RequestsHttpConnection)

def retrieve_chunks(question: str, k: int = 3):
    model = get_st_model()
    vector = model.encode(question).tolist()
    client = get_opensearch_client()
    body = {"size": k, "query": {"knn": {"embedding": {"vector": vector, "k": k}}}}
    result = client.search(index="document-chunks", body=body)
    return [{"text": h["_source"]["text"], "doc_key": h["_source"]["doc_key"]}
            for h in result["hits"]["hits"]]

def classify_query(question: str) -> str:
    prompt = f"""Classify this question into exactly one category:
"redshift" (needs structured/numerical warehouse data), "opensearch" (needs document/policy
content), or "both" (needs combining warehouse data with document content).

Question: {question}

Respond with ONLY one word: redshift, opensearch, or both."""
    result = invoke_claude(prompt, max_tokens=10)
    category = result["text"].strip().lower()
    return category if category in ("redshift", "opensearch", "both") else "both"

def answer_redshift(question: str) -> dict:
    sql = generate_sql(question)
    check = validate_sql(sql)
    if not check["valid"]:
        return {"answer": f"Query blocked: {check['reason']}", "sql": sql}
    rows = execute_sql(sql)
    prompt = f"Question: {question}\n\nSQL used: {sql}\n\nResults: {rows}\n\nAnswer in plain English."
    result = invoke_claude(prompt)
    return {"answer": result["text"], "sql": sql, "rows": rows}

def answer_opensearch(question: str) -> dict:
    chunks = retrieve_chunks(question)
    context = "\n\n".join(f"[Source: {c['doc_key']}] {c['text']}" for c in chunks)
    prompt = f"""Answer using ONLY the context below. Cite the source document(s) by name.

Context:
{context}

Question: {question}"""
    result = invoke_claude(prompt)
    return {"answer": result["text"], "sources": [c["doc_key"] for c in chunks]}

def answer_both(question: str) -> dict:
    sql = generate_sql(question)
    check = validate_sql(sql)
    sql_rows = execute_sql(sql) if check["valid"] else f"(blocked: {check['reason']})"
    chunks = retrieve_chunks(question)
    context = "\n\n".join(f"[Source: {c['doc_key']}] {c['text']}" for c in chunks)
    prompt = f"""Answer by combining BOTH sources into ONE unified answer. Explicitly cite both
the data warehouse numbers and the document content by name. Do not answer twice separately.

Data warehouse results (SQL: {sql}):
{sql_rows}

Document excerpts:
{context}

Question: {question}"""
    result = invoke_claude(prompt, max_tokens=800)
    return {"answer": result["text"], "sql": sql, "sources": [c["doc_key"] for c in chunks]}

def answer_question(question: str) -> dict:
    category = classify_query(question)
    print(f"[routed to: {category}]")
    if category == "redshift":
        return answer_redshift(question)
    elif category == "opensearch":
        return answer_opensearch(question)
    return answer_both(question)

if __name__ == "__main__":
    tests = [
        "How many customers are in each segment?",
        "What does our retention strategy say about churn targets?",
    ]
    for q in tests:
        print(f"\nQ: {q}")
        result = answer_question(q)
        print(result["answer"])
