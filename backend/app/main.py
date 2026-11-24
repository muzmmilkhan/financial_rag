import shutil
from contextlib import asynccontextmanager
from pathlib import Path

import boto3
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from . import config
from .embedder import GeminiEmbedder
from .ingestion import start_background_ingestion
from .llm import GeminiRAG
from .schemas import QueryRequest, QueryResponse, UploadResponse
from .vector_store import VectorStore

clients: dict = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        clients["embedder"] = GeminiEmbedder()
        clients["store"] = VectorStore()
        clients["llm"] = GeminiRAG()
        if not config.SQS_QUEUE_URL:  # local mode: watch data/ folder; AWS mode: worker container ingests
            start_background_ingestion(clients["embedder"], clients["store"])
        print("Backend ready.")
    except Exception as e:
        print(f"Startup error: {e}")
    yield


app = FastAPI(title="Financial RAG API", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


@app.get("/health")
def health():
    ready = len(clients) == 3
    return {"status": "healthy" if ready else "degraded", "details": {k: True for k in clients}}


@app.post("/query", response_model=QueryResponse)
def query(req: QueryRequest):
    if len(clients) < 3:
        raise HTTPException(503, "Backend not initialised. Check GEMINI_API_KEY and Qdrant.")
    try:
        vector = clients["embedder"].embed_text(req.question)
        images = clients["store"].search(vector, req.limit)
        if not images:
            return QueryResponse(
                question=req.question,
                answer="No documents have been indexed yet. Add PDFs and wait for ingestion.",
                pages_retrieved=0,
            )
        answer = clients["llm"].answer(req.question, images)
    except Exception as e:
        raise HTTPException(500, f"Query failed: {e}")
    return QueryResponse(question=req.question, answer=answer, pages_retrieved=len(images), images=images)


@app.post("/upload", response_model=UploadResponse)
def upload(file: UploadFile = File(...)):
    name = Path(file.filename or "").name
    if not name.lower().endswith(".pdf"):
        raise HTTPException(400, "Only PDF files are supported.")
    if config.S3_BUCKET_NAME:
        try:
            boto3.client("s3", region_name=config.AWS_REGION).upload_fileobj(
                file.file, config.S3_BUCKET_NAME, name, ExtraArgs={"ContentType": "application/pdf"}
            )
        except Exception as e:
            raise HTTPException(500, f"S3 upload failed: {e}")
        return UploadResponse(
            status="success", filename=name,
            message=f"Uploaded {name} to s3://{config.S3_BUCKET_NAME}. The worker will ingest it shortly.",
        )
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(config.DATA_DIR / name, "wb") as out:
        shutil.copyfileobj(file.file, out)
    return UploadResponse(
        status="success", filename=name, message=f"Saved {name}. Ingestion has started automatically."
    )
