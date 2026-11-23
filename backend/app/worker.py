"""AWS ingestion worker: S3 upload -> SQS event -> download PDF -> embed -> Qdrant."""
import json
import os
import signal
import tempfile
import time
import urllib.parse
from pathlib import Path

import boto3

from . import config
from .embedder import GeminiEmbedder
from .ingestion import ingest_pdf
from .vector_store import VectorStore

running = True


def _stop(*_):
    global running
    running = False


def handle_message(body: str, s3, embedder, store) -> bool:
    """Return True when the message can be deleted from the queue."""
    try:
        data = json.loads(body)
    except ValueError:
        return True
    ok = True
    for record in data.get("Records", []):
        if not record.get("eventName", "").startswith("ObjectCreated:"):
            continue
        bucket = record["s3"]["bucket"]["name"]
        key = urllib.parse.unquote_plus(record["s3"]["object"]["key"])
        if not key.lower().endswith(".pdf"):
            continue
        fd, tmp = tempfile.mkstemp(suffix=".pdf")
        os.close(fd)
        try:
            s3.download_file(bucket, key, tmp)
            ingest_pdf(Path(tmp), embedder, store, source=key)
        except Exception as e:
            print(f"Failed to ingest s3://{bucket}/{key}: {e}")
            ok = False
        finally:
            os.remove(tmp)
    return ok


def main():
    if not config.SQS_QUEUE_URL:
        raise SystemExit("SQS_QUEUE_URL is not set.")
    signal.signal(signal.SIGTERM, _stop)
    signal.signal(signal.SIGINT, _stop)
    sqs = boto3.client("sqs", region_name=config.AWS_REGION)
    s3 = boto3.client("s3", region_name=config.AWS_REGION)
    embedder, store = GeminiEmbedder(), VectorStore()
    print(f"Worker listening on {config.SQS_QUEUE_URL}")
    while running:
        try:
            resp = sqs.receive_message(
                QueueUrl=config.SQS_QUEUE_URL, MaxNumberOfMessages=1, WaitTimeSeconds=20, VisibilityTimeout=900
            )
            for msg in resp.get("Messages", []):
                if handle_message(msg["Body"], s3, embedder, store):
                    sqs.delete_message(QueueUrl=config.SQS_QUEUE_URL, ReceiptHandle=msg["ReceiptHandle"])
        except Exception as e:
            print(f"Worker error: {e}")
            time.sleep(5)


if __name__ == "__main__":
    main()
