from __future__ import annotations

import hashlib
import math
import re
from collections import Counter

from langchain_core.embeddings import Embeddings

from app.config import Settings

_LATIN_OR_NUMBER = re.compile(r"[a-zA-Z]+(?:[-_][a-zA-Z0-9]+)*|\d+(?:\.\d+)?")
_CJK_RUN = re.compile(r"[\u3400-\u9fff]+")


class LocalHashEmbeddings(Embeddings):
    """Deterministic embeddings for local development and repeatable CI.

    Character n-grams make the baseline usable for Chinese without downloading a
    model. This is intentionally a test adapter, not a substitute for a semantic
    embedding model in production.
    """

    def __init__(self, dimensions: int = 1536) -> None:
        self.dimensions = dimensions

    @staticmethod
    def _tokens(text: str) -> list[str]:
        lowered = text.lower()
        tokens = [f"w:{item}" for item in _LATIN_OR_NUMBER.findall(lowered)]
        for run in _CJK_RUN.findall(lowered):
            tokens.extend(f"c:{char}" for char in run)
            tokens.extend(f"b:{run[i:i + 2]}" for i in range(max(0, len(run) - 1)))
            tokens.extend(f"t:{run[i:i + 3]}" for i in range(max(0, len(run) - 2)))
        return tokens

    def _embed(self, text: str) -> list[float]:
        counts = Counter(self._tokens(text))
        vector = [0.0] * self.dimensions
        for token, count in counts.items():
            digest = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
            index = int.from_bytes(digest, "big") % self.dimensions
            vector[index] += 1.0 + math.log(count)
        norm = math.sqrt(sum(value * value for value in vector))
        if norm:
            return [value / norm for value in vector]
        return vector

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._embed(text) for text in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._embed(text)


def build_embeddings(settings: Settings) -> Embeddings:
    if settings.embedding_provider == "local":
        return LocalHashEmbeddings()

    from langchain_openai import OpenAIEmbeddings

    return OpenAIEmbeddings(
        model=settings.embedding_model,
        api_key=settings.openai_api_key,
        base_url=settings.openai_base_url,
    )


def embedding_signature(settings: Settings) -> str:
    if settings.embedding_provider == "local":
        return "local-hash-v1-1536"
    base = settings.openai_base_url or "default"
    return f"openai:{base}:{settings.embedding_model}"

