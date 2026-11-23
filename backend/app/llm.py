from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from . import config

SYSTEM_PROMPT = (
    "You are an assistant for question-answering tasks. "
    "Use the provided image context (pages of financial PDFs) to answer the question. "
    "If you don't know the answer, say that you don't know. "
    "Answer in detail, based ONLY on the provided context."
)


class GeminiRAG:
    def __init__(self):
        self.llm = ChatOpenAI(
            model=config.LLM_MODEL,
            temperature=0.2,
            api_key=config.EURI_GEMINI_API_KEY,
            base_url=config.GEMINI_API_BASE_URL,
        )

    def answer(self, question: str, images_b64: list[str]) -> str:
        content = [{"type": "text", "text": question}]
        content += [
            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b}"}}
            for b in images_b64
        ]
        reply = self.llm.invoke([SystemMessage(content=SYSTEM_PROMPT), HumanMessage(content=content)])
        return reply.content
