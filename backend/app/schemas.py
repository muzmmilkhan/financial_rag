from pydantic import BaseModel, Field


class QueryRequest(BaseModel):
    question: str = Field(..., min_length=1)
    limit: int = Field(default=3, ge=1, le=10, description="Max pages to retrieve")


class QueryResponse(BaseModel):
    question: str
    answer: str
    pages_retrieved: int
    images: list[str] = []


class UploadResponse(BaseModel):
    status: str
    filename: str
    message: str
