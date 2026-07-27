from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import pytest
from langchain_core.documents import Document

from app.embeddings import build_embeddings
from app.index import KnowledgeIndex
from app.reranking import CrossEncoderReranker


class FakeCrossEncoder:
    def predict(
        self,
        pairs: list[tuple[str, str]],
        *,
        batch_size: int,
        show_progress_bar: bool,
    ) -> list[float]:
        assert batch_size == 8
        assert show_progress_bar is False
        assert pairs[0][0] == "数据权限"
        return [2.0, -2.0]


class FixedReranker:
    @property
    def name(self) -> str:
        return "fixed-test-reranker"

    def score(self, query: str, documents: Sequence[Document]) -> list[float]:
        del query
        return [0.9 if index == 0 else 0.1 for index, _ in enumerate(documents)]


def test_cross_encoder_scores_are_normalized_without_loading_model(
    settings: Any,
) -> None:
    reranker = CrossEncoderReranker(settings)
    reranker._model = FakeCrossEncoder()

    scores = reranker.score(
        "数据权限",
        [
            Document(page_content="部门数据权限"),
            Document(page_content="公司午餐菜单"),
        ],
    )

    assert scores[0] == pytest.approx(0.880797, rel=1e-5)
    assert scores[1] == pytest.approx(0.119203, rel=1e-5)
    assert scores[0] > scores[1]


def test_cross_encoder_empty_candidates_do_not_load_model(settings: Any) -> None:
    reranker = CrossEncoderReranker(settings)

    assert reranker.score("问题", []) == []
    assert reranker._model is None


def test_knowledge_index_blends_cross_encoder_with_local_score(settings: Any) -> None:
    index = KnowledgeIndex(
        settings,
        build_embeddings(settings),
        reranker=FixedReranker(),
    )
    index.ensure_ready()

    hits = index.search(
        "AUTH-403-DATA 表示什么？",
        k=4,
        strategy="hybrid_rerank",
    )

    assert hits[0].model_rerank_score == 0.9
    assert hits[0].score == pytest.approx(
        settings.cross_encoder_weight * 0.9
        + (1 - settings.cross_encoder_weight) * hits[0].rerank_score
    )
