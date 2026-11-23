import random
import time

from google import genai

from . import config


class GeminiEmbedder:
    def __init__(self):
        if not config.GEMINI_API_KEY:
            raise ValueError("GEMINI_API_KEY is not set. Add it to the .env file.")
        self.client = genai.Client(api_key=config.GEMINI_API_KEY)

    def _embed(self, content, retries=6) -> list[float]:
        for attempt in range(retries):
            try:
                result = self.client.models.embed_content(model=config.EMBEDDING_MODEL, contents=content)
                return result.embeddings[0].values
            except Exception as e:
                rate_limited = "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e)
                if not rate_limited or attempt == retries - 1:
                    raise
                wait = 4 * (2**attempt) + random.uniform(1, 3)
                print(f"Rate limited, retrying in {wait:.0f}s...")
                time.sleep(wait)

    def embed_image(self, image) -> list[float]:
        return self._embed(image)

    def embed_text(self, text: str) -> list[float]:
        return self._embed(text)
