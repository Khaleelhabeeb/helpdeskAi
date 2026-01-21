import os
import boto3
from botocore.exceptions import ClientError
from botocore.config import Config
from typing import Optional, BinaryIO
from dotenv import load_dotenv
import json
from datetime import datetime

load_dotenv()

# AWS S3 Configuration
AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")
AWS_S3_BUCKET = os.getenv("AWS_S3_BUCKET")
AWS_S3_REGION = os.getenv("AWS_S3_REGION", "us-east-1")

# Configure retry strategy with exponential backoff
retry_config = Config(
    retries={
        'max_attempts': 5,  # Retry up to 5 times
        'mode': 'adaptive'  # Adaptive retry mode for better performance
    },
    connect_timeout=10,
    read_timeout=30
)

# Initialize S3 client with retry configuration
s3_client = boto3.client(
    's3',
    aws_access_key_id=AWS_ACCESS_KEY_ID,
    aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
    region_name=AWS_S3_REGION,
    config=retry_config
)


def get_s3_key(user_id: int, agent_id: str, kb_id: str, file_type: str, extension: str = "txt") -> str:
    # Generate S3 key: user_{user_id}/agent_{agent_id}/kb_{kb_id}_{file_type}.{extension}
    return f"user_{user_id}/agent_{agent_id}/kb_{kb_id}_{file_type}.{extension}"


def upload_file_to_s3(file_content: bytes, s3_key: str, content_type: str = "text/plain") -> bool:
    # Upload file content to S3
    try:
        s3_client.put_object(
            Bucket=AWS_S3_BUCKET,
            Key=s3_key,
            Body=file_content,
            ContentType=content_type
        )
        return True
    except ClientError as e:
        print(f"S3 upload error: {e}")
        return False


def upload_text_to_s3(text: str, s3_key: str) -> bool:
    # Upload text content to S3 as UTF-8 encoded file
    try:
        s3_client.put_object(
            Bucket=AWS_S3_BUCKET,
            Key=s3_key,
            Body=text.encode('utf-8'),
            ContentType='text/plain; charset=utf-8'
        )
        return True
    except ClientError as e:
        print(f"S3 text upload error: {e}")
        return False


def upload_json_to_s3(data: dict, s3_key: str) -> bool:
    # Upload JSON data to S3
    try:
        json_content = json.dumps(data, indent=2, default=str)
        s3_client.put_object(
            Bucket=AWS_S3_BUCKET,
            Key=s3_key,
            Body=json_content.encode('utf-8'),
            ContentType='application/json'
        )
        return True
    except ClientError as e:
        print(f"S3 JSON upload error: {e}")
        return False


def download_from_s3(s3_key: str) -> Optional[bytes]:
    # Download file content from S3
    try:
        response = s3_client.get_object(Bucket=AWS_S3_BUCKET, Key=s3_key)
        return response['Body'].read()
    except ClientError as e:
        print(f"S3 download error: {e}")
        return None


def download_text_from_s3(s3_key: str) -> Optional[str]:
    # Download text content from S3 as UTF-8 string
    content = download_from_s3(s3_key)
    if content:
        try:
            return content.decode('utf-8')
        except UnicodeDecodeError:
            return content.decode('utf-8', errors='ignore')
    return None


def delete_from_s3(s3_key: str) -> bool:
    # Delete a file from S3
    try:
        s3_client.delete_object(Bucket=AWS_S3_BUCKET, Key=s3_key)
        return True
    except ClientError as e:
        print(f"S3 delete error: {e}")
        return False


def delete_kb_files(user_id: int, agent_id: str, kb_id: str) -> bool:
    # Delete all files associated with a knowledge base
    prefix = f"user_{user_id}/agent_{agent_id}/kb_{kb_id}_"
    
    try:
        # List all objects with the prefix
        response = s3_client.list_objects_v2(Bucket=AWS_S3_BUCKET, Prefix=prefix)
        
        if 'Contents' not in response:
            return True
        
        # Delete all matching files
        objects_to_delete = [{'Key': obj['Key']} for obj in response['Contents']]
        
        if objects_to_delete:
            s3_client.delete_objects(
                Bucket=AWS_S3_BUCKET,
                Delete={'Objects': objects_to_delete}
            )
        
        return True
    except ClientError as e:
        print(f"S3 bulk delete error: {e}")
        return False


def get_presigned_url(s3_key: str, expiration: int = 3600) -> Optional[str]:
    # Generate a presigned URL for downloading a file (expires in 1 hour by default)
    try:
        url = s3_client.generate_presigned_url(
            'get_object',
            Params={'Bucket': AWS_S3_BUCKET, 'Key': s3_key},
            ExpiresIn=expiration
        )
        return url
    except ClientError as e:
        print(f"S3 presigned URL error: {e}")
        return None


def get_file_size(s3_key: str) -> Optional[int]:
    # Get the size of a file in S3 in bytes
    try:
        response = s3_client.head_object(Bucket=AWS_S3_BUCKET, Key=s3_key)
        return response['ContentLength']
    except ClientError as e:
        print(f"S3 head object error: {e}")
        return None
