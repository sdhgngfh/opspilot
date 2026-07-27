from __future__ import annotations

from langchain_core.documents import Document

from app.retrieval import BM25Index, reciprocal_rank_fusion, tokenize


def _document(content: str, chunk_id: str) -> Document:
    return Document(page_content=content, metadata={"chunk_id": chunk_id})


def test_tokenizer_preserves_identifiers_and_chinese_ngrams() -> None:
    tokens = tokenize("AUTH-403-DATA 表示数据权限错误")

    assert "w:auth-403-data" in tokens
    assert "b:数据" in tokens
    assert "t:权限错" in tokens


def test_bm25_prefers_exact_error_code() -> None:
    index = BM25Index(
        [
            _document("普通的销售订单权限说明", "general"),
            _document("错误码 AUTH-403-DATA 表示没有数据范围权限", "exact"),
        ]
    )

    results = index.scores("AUTH-403-DATA 怎么处理")

    assert results[0].document.metadata["chunk_id"] == "exact"
    assert results[0].score > results[1].score


def test_rrf_rewards_documents_present_in_both_rankings() -> None:
    scores = reciprocal_rank_fusion(
        [["vector-only", "both"], ["both", "keyword-only"]],
        weights=[0.5, 0.5],
        rrf_k=60,
    )

    assert scores["both"] > scores["vector-only"]
    assert scores["both"] > scores["keyword-only"]
