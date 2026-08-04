from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from langchain_core.vectorstores import InMemoryVectorStore

from app.config import Settings
from app.embeddings import embedding_signature
from app.loaders import corpus_fingerprint, load_source_documents, split_documents
from app.reranking import Reranker, build_reranker
from app.retrieval import (
    BM25Index,
    RetrievalStrategy,
    local_rerank_score,
    reciprocal_rank_fusion,
)


@dataclass(frozen=True)
class RetrievalHit:
    document: Document
    score: float
    vector_score: float = 0.0
    bm25_score: float = 0.0
    rrf_score: float = 0.0
    lexical_score: float = 0.0
    rerank_score: float = 0.0
    model_rerank_score: float = 0.0


class KnowledgeIndex:
    def __init__(
        self,
        settings: Settings,
        embeddings: Embeddings,
        *,
        reranker: Reranker | None = None,
    ) -> None:
        self.settings = settings
        self.embeddings = embeddings
        self.vector_store: InMemoryVectorStore | None = None
        self.bm25_index: BM25Index | None = None
        self.reranker = reranker or build_reranker(settings)
        self._manifest: dict[str, object] | None = None

    @property
    def manifest_path(self) -> Path:
        return self.settings.index_path.with_suffix(".manifest.json")

    def _is_ready(self) -> bool:
        return self.vector_store is not None and self.bm25_index is not None

    def _expected_manifest(self) -> dict[str, object]:
        return {
            "corpus_fingerprint": corpus_fingerprint(
                self.settings.knowledge_dir, self.settings
            ),
            "embedding_signature": embedding_signature(self.settings),
            "chunk_size": self.settings.chunk_size,
            "chunk_overlap": self.settings.chunk_overlap,
        }

    def ensure_ready(self) -> dict[str, object]:
        expected = self._expected_manifest()
        source_documents = load_source_documents(self.settings.knowledge_dir, self.settings)
        chunks = split_documents(source_documents, self.settings)
        if self.settings.index_path.exists() and self.manifest_path.exists():
            actual = json.loads(self.manifest_path.read_text(encoding="utf-8"))
            comparable = {key: actual.get(key) for key in expected}
            if comparable == expected and actual.get("chunks") == len(chunks):
                self.vector_store = InMemoryVectorStore.load(
                    str(self.settings.index_path), self.embeddings
                )
                self.bm25_index = BM25Index(chunks)
                self._manifest = actual
                return {**actual, "rebuilt": False}
        return self.rebuild()

    def rebuild(self) -> dict[str, object]:
        source_documents = load_source_documents(self.settings.knowledge_dir, self.settings)
        if not source_documents:
            raise ValueError(f"知识库目录中没有可索引文档: {self.settings.knowledge_dir}")
        chunks = split_documents(source_documents, self.settings)
        self.vector_store = InMemoryVectorStore(self.embeddings)
        self.vector_store.add_documents(
            chunks,
            ids=[str(chunk.metadata["chunk_id"]) for chunk in chunks],
        )
        self.bm25_index = BM25Index(chunks)

        self.settings.index_path.parent.mkdir(parents=True, exist_ok=True)
        self.vector_store.dump(str(self.settings.index_path))
        manifest = {
            **self._expected_manifest(),
            "documents": len(source_documents),
            "chunks": len(chunks),
        }
        self.manifest_path.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        self._manifest = manifest
        return {**manifest, "rebuilt": True}

    def _vector_search(
        self,
        query: str,
        k: int,
    ) -> list[RetrievalHit]:
        assert self.vector_store is not None
        query_vector = self.embeddings.embed_query(query)
        if sum(value * value for value in query_vector) <= 1e-12:
            return []
        fetch_k = (
            len(self.bm25_index.documents)
            if self.bm25_index is not None
            else k
        )
        hits = [
            RetrievalHit(
                document=document,
                score=float(score),
                vector_score=max(0.0, min(float(score), 1.0)),
            )
            for document, score in self.vector_store.similarity_search_with_score(
                query, k=fetch_k
            )
        ]
        return hits[:k]

    def search(
        self,
        query: str,
        k: int,
        *,
        strategy: RetrievalStrategy | None = None,
    ) -> list[RetrievalHit]:
        if not self._is_ready():
            self.ensure_ready()
        assert self.bm25_index is not None
        strategy = strategy or self.settings.retrieval_strategy
        if strategy == "vector":
            return self._vector_search(query, k)

        candidate_k = max(k, self.settings.candidate_k)
        vector_hits = self._vector_search(query, candidate_k)
        all_bm25_items = [
            item
            for item in self.bm25_index.scores(query)
        ]
        bm25_items = all_bm25_items[:candidate_k]
        maximum_bm25 = all_bm25_items[0].score if all_bm25_items else 0.0
        bm25_scores = {
            str(item.document.metadata["chunk_id"]): (
                item.score / maximum_bm25 if maximum_bm25 > 0 else 0.0
            )
            for item in all_bm25_items
        }
        vector_by_id = {
            str(hit.document.metadata["chunk_id"]): hit for hit in vector_hits
        }
        document_by_id = {
            str(hit.document.metadata["chunk_id"]): hit.document for hit in vector_hits
        }
        document_by_id.update(
            {
                str(item.document.metadata["chunk_id"]): item.document
                for item in bm25_items
            }
        )
        vector_ids = list(vector_by_id)
        bm25_ids = [
            str(item.document.metadata["chunk_id"]) for item in bm25_items
        ]
        rrf_scores = reciprocal_rank_fusion(
            [vector_ids, bm25_ids],
            weights=[self.settings.vector_weight, self.settings.bm25_weight],
            rrf_k=self.settings.rrf_k,
        )

        hits: list[RetrievalHit] = []
        for chunk_id, document in document_by_id.items():
            vector_score = vector_by_id.get(
                chunk_id, RetrievalHit(document=document, score=0.0)
            ).vector_score
            bm25_score = bm25_scores.get(chunk_id, 0.0)
            rrf_score = rrf_scores.get(chunk_id, 0.0)
            lexical_score = self.bm25_index.query_coverage(query, document)
            hybrid_score = (
                self.settings.vector_weight * vector_score
                + self.settings.bm25_weight * bm25_score
            )
            rerank_score = local_rerank_score(
                vector_score=vector_score,
                bm25_score=bm25_score,
                query_coverage=lexical_score,
                rrf_score=rrf_score,
            )
            hits.append(
                RetrievalHit(
                    document=document,
                    score=rerank_score if strategy == "hybrid_rerank" else hybrid_score,
                    vector_score=vector_score,
                    bm25_score=bm25_score,
                    rrf_score=rrf_score,
                    lexical_score=lexical_score,
                    rerank_score=rerank_score,
                )
            )
        if strategy == "hybrid":
            hits.sort(
                key=lambda item: (item.rrf_score, item.score),
                reverse=True,
            )
        else:
            if self.reranker is not None:
                model_scores = self.reranker.score(
                    query,
                    [hit.document for hit in hits],
                )
                if len(model_scores) != len(hits):
                    raise ValueError("Cross-Encoder 返回的分数数量与候选文档数量不一致")
                cross_encoder_weight = self.settings.cross_encoder_weight
                hits = [
                    RetrievalHit(
                        document=hit.document,
                        score=(
                            cross_encoder_weight * model_score
                            + (1 - cross_encoder_weight) * hit.rerank_score
                        ),
                        vector_score=hit.vector_score,
                        bm25_score=hit.bm25_score,
                        rrf_score=hit.rrf_score,
                        lexical_score=hit.lexical_score,
                        rerank_score=hit.rerank_score,
                        model_rerank_score=model_score,
                    )
                    for hit, model_score in zip(hits, model_scores, strict=True)
                ]
                hits.sort(key=lambda item: item.score, reverse=True)
            else:
                hits.sort(key=lambda item: item.rerank_score, reverse=True)
        return hits[:k]
