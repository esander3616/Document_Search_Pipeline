CREATE TABLE raw_chunks (
    id BIGINT IDENTITY(1,1),
    doc_key VARCHAR(500),
    chunk_index INT,
    chunk_text VARCHAR(65535),
    created_at TIMESTAMP DEFAULT GETDATE()
);

CREATE TABLE customers (
    customer_id VARCHAR(50),
    email VARCHAR(255),
    segment VARCHAR(50),
    region VARCHAR(50),
    signup_date DATE,
    monthly_spend DECIMAL(10,2),
    status VARCHAR(20),
    cancelled_date DATE
);

CREATE TABLE usage_events (
    user_id VARCHAR(50),
    feature_used VARCHAR(100),
    usage_count INT,
    session_date DATE,
    device_type VARCHAR(50)
);