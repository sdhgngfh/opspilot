from __future__ import annotations

import time

from app.config import Settings
from app.embeddings import build_embeddings
from app.generator import AnswerGenerator, build_generator
from app.index import KnowledgeIndex, RetrievalHit
from app.models import AskResponse, Citation, IngestResponse
from app.retrieval import RetrievalStrategy

REFUSAL = "当前知识库中没有足够证据回答这个问题。请补充相关文档或换一种问法。"


class RAGService:
    def __init__(
        self,
        settings: Settings,
        *,
        index: KnowledgeIndex | None = None,
        generator: AnswerGenerator | None = None,
    ) -> None:
        self.settings = settings
        embeddings = build_embeddings(settings)
        self.index = index or KnowledgeIndex(settings, embeddings)
        self.generator = generator or build_generator(settings)

    def ensure_ready(self) -> IngestResponse:
        manifest = self.index.ensure_ready()
        return IngestResponse(**manifest)

    def reindex(self) -> IngestResponse:
        return IngestResponse(**self.index.rebuild())

    def retrieve(self, question: str, top_k: int | None = None, *, strategy: RetrievalStrategy | None = None) -> list[RetrievalHit]:
        k = top_k or self.settings.top_k
        active_strategy = strategy or self.settings.retrieval_strategy
        return self.index.search(question, k=k, strategy=active_strategy)

    def select_evidence(self, raw_hits: list[RetrievalHit], *, strategy: RetrievalStrategy | None = None) -> list[RetrievalHit]:
        active_strategy = strategy or self.settings.retrieval_strategy
        return [
            hit for hit in raw_hits
            if hit.score >= self.settings.min_relevance_score
            and (active_strategy == "vector" or hit.vector_score >= self.settings.min_relevance_score
                 or (hit.bm25_score >= self.settings.min_bm25_score and hit.lexical_score >= self.settings.min_lexical_coverage))
        ]

    def evidence_score(self, raw_hits: list[RetrievalHit]) -> float:
        if not raw_hits:
            return 0.0
        top = raw_hits[0]
        return max(0.0, min(0.65 * top.score + 0.35 * max(top.vector_score, top.bm25_score * top.lexical_score), 1.0))

    @staticmethod
    def evidence_reason(raw_hits: list[RetrievalHit], selected_hits: list[RetrievalHit]) -> str:
        if not raw_hits:
            return "检索器未返回候选证据"
        top = raw_hits[0]
        if selected_hits:
            return f"证据通过双信号门控：综合分={top.score:.3f}，向量分={top.vector_score:.3f}，BM25={top.bm25_score:.3f}"
        return f"候选证据未通过双信号门控：综合分={top.score:.3f}"

    @staticmethod
    def build_citations(hits: list[RetrievalHit]) -> list[Citation]:
        return [
            Citation(
                rank=rank, source=str(hit.document.metadata["source"]),
                title=str(hit.document.metadata.get("title", hit.document.metadata["source"])),
                chunk_id=str(hit.document.metadata["chunk_id"]),
                score=round(hit.score, 6),
                excerpt=hit.document.page_content[:240].strip(),
            )
            for rank, hit in enumerate(hits, start=1)
        ]

    def ask(self, question: str, top_k: int | None = None) -> AskResponse:
        started = time.perf_counter()
        raw_hits = self.retrieve(question, top_k)
        hits = self.select_evidence(raw_hits)
        if not hits:
            return AskResponse(question=question, answer=REFUSAL, grounded=False, citations=[], latency_ms=round((time.perf_counter() - started) * 1000, 3))
        answer = self.generator.generate(question, hits)
        return AskResponse(question=question, answer=answer, grounded=True, citations=self.build_citations(hits), latency_ms=round((time.perf_counter() - started) * 1000, 3))
