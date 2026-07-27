from __future__ import annotations

import math
from collections.abc import Sequence
from typing import Protocol

from langchain_core.documents import Document

from app.config import Settings


class Reranker(Protocol):
    """Score already-retrieved query/document pairs on a normalized [0, 1] scale."""

    @property
    def name(self) -> str: ...

    def score(self, query: str, documents: Sequence[Document]) -> list[float]: ...


class CrossEncoderReranker:
    """Lazy Sentence Transformers Cross-Encoder adapter.

    The optional dependency and model are loaded only when the provider is enabled,
    so the default local/CI path remains fast and network-independent.
    """

    def __init__(self, settings: Settings) -> None:
        self.model_name = settings.cross_encoder_model
        self.device = settings.cross_encoder_device
        self.batch_size = settings.cross_encoder_batch_size
        self._model: object | None = None

    @property
    def name(self) -> str:
        return self.model_name

    def _load(self) -> object:
        if self._model is not None:
            return self._model
        try:
            from sentence_transformers import CrossEncoder
        except ImportError as exc:
            raise RuntimeError(
                "启用 Cross-Encoder 需要安装可选依赖："
                "uv sync --extra reranker"
            ) from exc
        self._model = CrossEncoder(self.model_name, device=self.device)
        return self._model

    @staticmethod
    def _sigmoid(value: float) -> float:
        if value >= 0:
            return 1.0 / (1.0 + math.exp(-value))
        exp_value = math.exp(value)
        return exp_value / (1.0 + exp_value)

    def score(self, query: str, documents: Sequence[Document]) -> list[float]:
        if not documents:
            return []
        model = self._load()
        pairs = [(query, document.page_content) for document in documents]
        raw_scores = model.predict(  # type: ignore[attr-defined]
            pairs,
            batch_size=self.batch_size,
            show_progress_bar=False,
        )
        return [self._sigmoid(float(score)) for score in raw_scores]


def build_reranker(settings: Settings) -> Reranker | None:
    if settings.reranker_provider == "cross_encoder":
        return CrossEncoderReranker(settings)
    return None
