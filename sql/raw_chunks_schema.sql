CREATE TABLE raw_chunks (
    id BIGINT IDENTITY(1,1),
    doc_key VARCHAR(500),
    chunk_index INT,
    chunk_text VARCHAR(65535),
    created_at TIMESTAMP DEFAULT GETDATE()
);
