import os
from pathlib import Path

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
COLLECTION_NAME = os.getenv("COLLECTION_NAME", "financial_documents")
DATA_DIR = Path(os.getenv("DATA_DIR", "./data"))
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "gemini-embedding-2")
LLM_MODEL = os.getenv("LLM_MODEL", "euri-vision")
SCAN_INTERVAL_SECONDS = int(os.getenv("SCAN_INTERVAL_SECONDS", "5"))
GEMINI_API_BASE_URL = os.getenv("GEMINI_API_BASE_URL", "https://api.euron.one/api/v1/euri")
EURI_GEMINI_API_KEY = os.getenv("EURI_GEMINI_API_KEY", "")
# AWS mode: set S3_BUCKET_NAME (uploads go to S3) and SQS_QUEUE_URL (worker ingests from the queue)
AWS_REGION = os.getenv("AWS_REGION", "eu-north-1")
S3_BUCKET_NAME = os.getenv("S3_BUCKET_NAME", "")
SQS_QUEUE_URL = os.getenv("SQS_QUEUE_URL", "")
