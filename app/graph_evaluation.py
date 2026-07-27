from __future__ import annotations

import json
from pathlib import Path

from app.graph import RAGGraphWorkflow
from app.models import (
    EvaluationCase,
    GraphComparisonCaseResult,
    GraphEvaluationSummary,
)
from app.service import RAGService


def _keyword_recall(answer: str, keywords: list[str]) -> float | None:
    if not keywords:
        return None
    lowered = answer.lower()
    return sum(keyword.lower() in lowered for keyword in keywords) / len(keywords)


def evaluate_graph(
    service: RAGService,
    workflow: RAGGraphWorkflow,
    cases: list[EvaluationCase],
) -> GraphEvaluationSummary:
    results: list[GraphComparisonCaseResult] = []
    answerable_results: list[GraphComparisonCaseResult] = []

    for case in cases:
        base = service.ask(case.question)
        graph = workflow.ask(
            question=case.question,
            thread_id=f"evaluation-{case.id}",
        )
        expected_sources = set(case.expected_sources)
        base_sources = {citation.source for citation in base.citations}
        graph_sources = {citation.source for citation in graph.citations}
        base_keyword_recall = _keyword_recall(base.answer, case.answer_keywords)
        graph_keyword_recall = _keyword_recall(graph.answer, case.answer_keywords)
        result = GraphComparisonCaseResult(
            id=case.id,
            question=case.question,
            answerable=case.answerable,
            base_grounded=base.grounded,
            graph_grounded=graph.grounded,
            base_source_hit=bool(expected_sources & base_sources),
            graph_source_hit=bool(expected_sources & graph_sources),
            base_keyword_recall=(
                round(base_keyword_recall, 6)
                if base_keyword_recall is not None
                else None
            ),
            graph_keyword_recall=(
                round(graph_keyword_recall, 6)
                if graph_keyword_recall is not None
                else None
            ),
            rewrite_count=graph.rewrite_count,
            attempts=len(graph.attempts),
            recovered_after_rewrite=(
                case.answerable and graph.rewrite_count > 0 and graph.grounded
            ),
            base_latency_ms=base.latency_ms,
            graph_latency_ms=graph.latency_ms,
        )
        results.append(result)
        if case.answerable:
            answerable_results.append(result)

    base_keywords = [
        result.base_keyword_recall
        for result in answerable_results
        if result.base_keyword_recall is not None
    ]
    graph_keywords = [
        result.graph_keyword_recall
        for result in answerable_results
        if result.graph_keyword_recall is not None
    ]
    retry_candidates = [
        result
        for result in answerable_results
        if result.rewrite_count > 0
    ]
    return GraphEvaluationSummary(
        cases=len(results),
        base_decision_accuracy=round(
            sum(result.base_grounded == result.answerable for result in results)
            / len(results),
            6,
        ),
        graph_decision_accuracy=round(
            sum(result.graph_grounded == result.answerable for result in results)
            / len(results),
            6,
        ),
        base_source_hit_rate=round(
            sum(result.base_source_hit for result in answerable_results)
            / len(answerable_results),
            6,
        ),
        graph_source_hit_rate=round(
            sum(result.graph_source_hit for result in answerable_results)
            / len(answerable_results),
            6,
        ),
        base_answer_keyword_recall=round(
            sum(base_keywords) / len(base_keywords) if base_keywords else 0.0,
            6,
        ),
        graph_answer_keyword_recall=round(
            sum(graph_keywords) / len(graph_keywords) if graph_keywords else 0.0,
            6,
        ),
        rewrite_rate=round(
            sum(result.rewrite_count > 0 for result in results) / len(results),
            6,
        ),
        retry_recovery_rate=round(
            (
                sum(result.recovered_after_rewrite for result in retry_candidates)
                / len(retry_candidates)
            )
            if retry_candidates
            else 0.0,
            6,
        ),
        average_attempts=round(
            sum(result.attempts for result in results) / len(results),
            3,
        ),
        base_average_latency_ms=round(
            sum(result.base_latency_ms for result in results) / len(results),
            3,
        ),
        graph_average_latency_ms=round(
            sum(result.graph_latency_ms for result in results) / len(results),
            3,
        ),
        results=results,
    )


def save_graph_summary(summary: GraphEvaluationSummary, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(summary.model_dump(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
