import boto3, json

s3 = boto3.client('s3')
textract = boto3.client('textract')
glue = boto3.client('glue')

def chunk_text(text, words_per_chunk=750):
    words = text.split()
    return [" ".join(words[i:i + words_per_chunk]) for i in range(0, len(words), words_per_chunk)]

def lambda_handler(event, context):
    record = event['Records'][0]
    bucket = record['s3']['bucket']['name']
    key = record['s3']['object']['key']

    response = textract.detect_document_text(
        Document={'S3Object': {'Bucket': bucket, 'Name': key}}
    )
    lines = [b['Text'] for b in response['Blocks'] if b['BlockType'] == 'LINE']
    full_text = "\n".join(lines)
    chunks = chunk_text(full_text)

    chunk_key = key.replace('pdf/', 'chunks/').rsplit('.', 1)[0] + '.json'
    s3.put_object(Bucket=bucket, Key=chunk_key, Body=json.dumps(chunks))

    glue.start_job_run(JobName='embed-chunks', Arguments={'--input_key': chunk_key})

    return {'statusCode': 200, 'body': json.dumps({'chunks': len(chunks), 'output_key': chunk_key})}
