from __future__ import annotations

from app.ablation import run_ablation
from app.config import PROJECT_ROOT
from app.evaluation import load_dataset
from app.service import RAGService


def test_ablation_isolates_retrieval_threshold_and_rewrite_effects(
    service: RAGService,
) -> None:
    report = run_ablation(
        service.settings,
        load_dataset(service.settings.evaluation_dataset),
        load_dataset(
            PROJECT_ROOT / "data" / "evaluation" / "graph_dataset.jsonl"
        ),
        k=4,
    )
    runs = {(run.component, run.variant): run for run in report.runs}

    vector = runs[("retrieval", "vector_only")]
    hybrid = runs[("retrieval", "hybrid_no_rerank")]
    reranked = runs[("retrieval", "hybrid_with_rerank")]
    assert hybrid.answer_keyword_recall >= vector.answer_keyword_recall
    assert reranked.mrr is not None
    assert hybrid.mrr is not None
    assert reranked.mrr >= hybrid.mrr

    permissive = runs[("evidence_threshold", "permissive_0_12")]
    baseline = runs[("evidence_threshold", "baseline_0_18")]
    strict = runs[("evidence_threshold", "strict_0_24")]
    assert baseline.decision_accuracy > permissive.decision_accuracy
    assert baseline.decision_accuracy > strict.decision_accuracy

    no_rewrite = runs[("query_rewrite", "max_rewrites_0")]
    one_rewrite = runs[("query_rewrite", "max_rewrites_1")]
    two_rewrites = runs[("query_rewrite", "max_rewrites_2")]
    assert one_rewrite.decision_accuracy > no_rewrite.decision_accuracy
    assert one_rewrite.source_hit_rate > no_rewrite.source_hit_rate
    assert one_rewrite.recovered_case_ids
    assert two_rewrites.decision_accuracy == one_rewrite.decision_accuracy
    assert two_rewrites.average_attempts > one_rewrite.average_attempts

    assert len(report.comparisons) == 6
