from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass
from typing import Literal

from langchain_core.documents import Document

RetrievalStrategy = Literal["vector", "hybrid", "hybrid_rerank"]

_LATIN_OR_NUMBER = re.compile(r"[a-zA-Z]+(?:[-_.][a-zA-Z0-9]+)*|\d+(?:\.\d+)?")
_CJK_RUN = re.compile(r"[\u3400-\u9fff]+")


def tokenize(text: str) -> list[str]:
    """Tokenize English, identifiers and Chinese without external dictionaries."""
    lowered = text.lower()
    tokens = [f"w:{item}" for item in _LATIN_OR_NUMBER.findall(lowered)]
    for run in _CJK_RUN.findall(lowered):
        if len(run) == 1:
            tokens.append(f"c:{run}")
        tokens.extend(f"b:{run[index:index + 2]}" for index in range(len(run) - 1))
        tokens.extend(f"t:{run[index:index + 3]}" for index in range(len(run) - 2))
    return tokens


@dataclass(frozen=True)
class ScoredDocument:
    document: Document
    score: float


class BM25Index:
    """Small in-process BM25 index used for deterministic demos and CI."""

    def __init__(
        self,
        documents: list[Document],
        *,
        k1: float = 1.5,
        b: float = 0.75,
    ) -> None:
        if not documents:
            raise ValueError("BM25 索引至少需要一个文档分块")
        self.documents = documents
        self.k1 = k1
        self.b = b
        self._tokens = [tokenize(document.page_content) for document in documents]
        self._term_frequencies = [Counter(tokens) for tokens in self._tokens]
        self._lengths = [len(tokens) for tokens in self._tokens]
        self._average_length = sum(self._lengths) / len(self._lengths)
        document_frequency: Counter[str] = Counter()
        for tokens in self._tokens:
            document_frequency.update(set(tokens))
        count = len(documents)
        self._idf = {
            term: math.log(1 + (count - frequency + 0.5) / (frequency + 0.5))
            for term, frequency in document_frequency.items()
        }
        self._unknown_idf = math.log(1 + (count + 0.5) / 0.5)

    def _score(self, query_tokens: list[str], index: int) -> float:
        frequencies = self._term_frequencies[index]
        length = self._lengths[index]
        normalizer = self.k1 * (
            1 - self.b + self.b * length / max(self._average_length, 1.0)
        )
        score = 0.0
        for term in set(query_tokens):
            frequency = frequencies.get(term, 0)
            if not frequency:
                continue
            score += self._idf.get(term, self._unknown_idf) * (
                frequency * (self.k1 + 1) / (frequency + normalizer)
            )
        return score

    def scores(self, query: str) -> list[ScoredDocument]:
        query_tokens = tokenize(query)
        raw = [
            ScoredDocument(document=document, score=self._score(query_tokens, index))
            for index, document in enumerate(self.documents)
        ]
        return sorted(raw, key=lambda item: item.score, reverse=True)

    def normalized_scores(self, query: str) -> dict[str, float]:
        scored = self.scores(query)
        maximum = scored[0].score if scored else 0.0
        if maximum <= 0:
            return {
                str(item.document.metadata["chunk_id"]): 0.0
                for item in scored
            }
        return {
            str(item.document.metadata["chunk_id"]): item.score / maximum
            for item in scored
        }

    def query_coverage(self, query: str, document: Document) -> float:
        query_terms = set(tokenize(query))
        if not query_terms:
            return 0.0
        document_terms = set(tokenize(document.page_content))
        numerator = sum(
            self._idf.get(term, self._unknown_idf)
            for term in query_terms & document_terms
        )
        denominator = sum(
            self._idf.get(term, self._unknown_idf) for term in query_terms
        )
        return numerator / denominator if denominator else 0.0


def reciprocal_rank_fusion(
    ranked_ids: list[list[str]],
    *,
    weights: list[float],
    rrf_k: int,
) -> dict[str, float]:
    if len(ranked_ids) != len(weights):
        raise ValueError("排名列表数量必须与权重数量一致")
    scores: dict[str, float] = {}
    for ranking, weight in zip(ranked_ids, weights, strict=True):
        for rank, document_id in enumerate(ranking, start=1):
            scores[document_id] = scores.get(document_id, 0.0) + weight / (
                rrf_k + rank
            )
    theoretical_max = sum(weights) / (rrf_k + 1)
    if theoretical_max:
        return {
            document_id: score / theoretical_max
            for document_id, score in scores.items()
        }
    return scores


def local_rerank_score(
    *,
    vector_score: float,
    bm25_score: float,
    query_coverage: float,
    rrf_score: float,
) -> float:
    """Calibrated, explainable second-stage score; all inputs are in [0, 1]."""
    score = (
        0.40 * max(0.0, min(vector_score, 1.0))
        + 0.30 * max(0.0, min(bm25_score, 1.0))
        + 0.20 * max(0.0, min(query_coverage, 1.0))
        + 0.10 * max(0.0, min(rrf_score, 1.0))
    )
    return max(0.0, min(score, 1.0))
