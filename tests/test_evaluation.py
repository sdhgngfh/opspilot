from __future__ import annotations

import pytest

from app.config import PROJECT_ROOT
from app.evaluation import evaluate, load_dataset
from app.graph import RAGGraphWorkflow
from app.graph_evaluation import evaluate_graph
from app.service import RAGService
from app.ticket_evaluation import evaluate_ticket_workflow


def test_baseline_retrieval_metrics(service: RAGService) -> None:
    cases = load_dataset(service.settings.evaluation_dataset)
    summary = evaluate(service, cases, k=4)

    assert summary.cases == 36
    assert summary.retrieval_strategy == "hybrid_rerank"
    assert summary.hit_rate_at_k >= 0.875
    assert summary.mrr >= 0.75
    assert summary.abstention_accuracy >= 0.8
    assert {item.value for item in summary.breakdowns["question_type"]} == {
        "error_code",
        "out_of_scope",
        "policy",
        "procedure",
        "troubleshooting",
    }
    assert {item.value for item in summary.breakdowns["difficulty"]} == {
        "easy",
        "medium",
        "hard",
    }
    hard_slice = next(
        item for item in summary.breakdowns["difficulty"] if item.value == "hard"
    )
    assert hard_slice.cases >= 12
    assert hard_slice.hit_rate_at_k >= 0.8
    assert hard_slice.abstention_accuracy >= 0.8


def test_dataset_rejects_duplicate_case_ids(tmp_path) -> None:
    dataset = tmp_path / "duplicates.jsonl"
    row = (
        '{"id":"duplicate","question":"如何排查登录故障？",'
        '"answerable":true,"question_type":"troubleshooting",'
        '"difficulty":"easy","expected_sources":["source.md"],'
        '"answer_keywords":["登录"]}\n'
    )
    dataset.write_text(row + row, encoding="utf-8")

    with pytest.raises(ValueError, match="重复 id"):
        load_dataset(dataset)


def test_graph_retry_evaluation(
    service: RAGService,
    workflow: RAGGraphWorkflow,
) -> None:
    cases = load_dataset(
        PROJECT_ROOT / "data" / "evaluation" / "graph_dataset.jsonl"
    )
    summary = evaluate_graph(service, workflow, cases)

    assert summary.cases == 10
    assert summary.graph_decision_accuracy >= summary.base_decision_accuracy
    assert summary.graph_source_hit_rate >= summary.base_source_hit_rate
    assert summary.retry_recovery_rate >= 0.6


def test_ticket_workflow_evaluation_covers_all_control_paths(
    service: RAGService,
) -> None:
    summary = evaluate_ticket_workflow(
        service.settings,
        PROJECT_ROOT / "data" / "evaluation" / "ticket_dataset.jsonl",
    )

    assert summary["cases"] == 3
    assert summary["approval_barrier_rate"] == 1.0
    assert summary["decision_accuracy"] == 1.0
    assert summary["edit_accuracy"] == 1.0
    assert summary["submission_idempotency_rate"] == 1.0
