import uuid

from qdrant_client import QdrantClient
from qdrant_client.http.models import Distance, PointStruct, VectorParams

from . import config


class VectorStore:
    def __init__(self):
        self.client = QdrantClient(url=config.QDRANT_URL)
        self.name = config.COLLECTION_NAME

    def ensure_collection(self, size: int):
        if self.client.collection_exists(self.name):
            vectors = self.client.get_collection(self.name).config.params.vectors
            if getattr(vectors, "size", size) == size:
                return
            self.client.delete_collection(self.name)
        self.client.create_collection(
            self.name, vectors_config=VectorParams(size=size, distance=Distance.COSINE)
        )

    def add_page(self, vector: list[float], image_b64: str, source: str, page: int):
        self.client.upsert(
            self.name,
            points=[
                PointStruct(
                    id=str(uuid.uuid4()),
                    vector=vector,
                    payload={"image_base64": image_b64, "source": source, "page": page},
                )
            ],
        )

    def search(self, vector: list[float], limit: int) -> list[str]:
        if not self.client.collection_exists(self.name):
            return []
        hits = self.client.query_points(self.name, query=vector, limit=limit).points
        return [h.payload["image_base64"] for h in hits if h.payload and "image_base64" in h.payload]
