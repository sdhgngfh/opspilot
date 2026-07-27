from __future__ import annotations

from app.service import REFUSAL, RAGService


def test_answer_contains_citation(service: RAGService) -> None:
    response = service.ask("如何让销售人员只能查看本部门销售订单？")

    assert response.grounded is True
    assert response.citations
    assert response.citations[0].source == "u9c_permissions.md"
    assert response.citations[0].retrieval_details["bm25"] > 0
    assert "[1]" in response.answer


def test_unknown_question_is_refused(service: RAGService) -> None:
    response = service.ask("公司食堂今天的午餐菜单是什么？")

    assert response.grounded is False
    assert response.answer == REFUSAL
    assert response.citations == []


def test_index_is_reused(service: RAGService) -> None:
    first = service.ensure_ready()
    second = service.ensure_ready()

    assert first.rebuilt is False
    assert second.rebuilt is False
    assert first.corpus_fingerprint == second.corpus_fingerprint


def test_exact_error_code_uses_hybrid_signals(service: RAGService) -> None:
    hits = service.retrieve("AUTH-403-DATA 表示什么？", top_k=4)

    assert hits[0].document.metadata["source"] == "integration_error_codes.md"
    assert hits[0].vector_score > 0
    assert hits[0].bm25_score == 1.0
    assert hits[0].rerank_score > 0
