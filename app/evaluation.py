from __future__ import annotations

import json
import math
from pathlib import Path

from app.models import (
    CaseResult,
    EvaluationCase,
    EvaluationSlice,
    EvaluationSummary,
)
from app.service import RAGService


def load_dataset(path: Path) -> list[EvaluationCase]:
    cases: list[EvaluationCase] = []
    case_ids: set[str] = set()
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if line.strip():
                try:
                    case = EvaluationCase.model_validate_json(line)
                except ValueError as exc:
                    raise ValueError(f"评测集第 {line_number} 行格式错误") from exc
                if case.id in case_ids:
                    raise ValueError(f"评测集存在重复 id：{case.id}")
                case_ids.add(case.id)
                cases.append(case)
    if not cases:
        raise ValueError("评测集为空")
    return cases


def _percentile(values: list[float], percentile: float) -> float:
    ordered = sorted(values)
    index = max(0, math.ceil(percentile * len(ordered)) - 1)
    return ordered[index]


def _build_slice(
    dimension: str,
    value: str,
    results: list[CaseResult],
) -> EvaluationSlice:
    answerable_results = [result for result in results if result.answerable]
    keyword_values = [
        result.keyword_recall
        for result in answerable_results
        if result.keyword_recall is not None
    ]
    latencies = [result.latency_ms for result in results]
    answerable_count = len(answerable_results)
    return EvaluationSlice(
        dimension=dimension,
        value=value,
        cases=len(results),
        answerable_cases=answerable_count,
        hit_rate_at_k=round(
            (
                sum(item.reciprocal_rank > 0 for item in answerable_results)
                / answerable_count
            )
            if answerable_count
            else 0.0,
            6,
        ),
        recall_at_k=round(
            (
                sum(item.recall_at_k for item in answerable_results)
                / answerable_count
            )
            if answerable_count
            else 0.0,
            6,
        ),
        mrr=round(
            (
                sum(item.reciprocal_rank for item in answerable_results)
                / answerable_count
            )
            if answerable_count
            else 0.0,
            6,
        ),
        answer_keyword_recall=round(
            sum(keyword_values) / len(keyword_values) if keyword_values else 0.0,
            6,
        ),
        abstention_accuracy=round(
            sum(item.grounded == item.answerable for item in results) / len(results),
            6,
        ),
        average_latency_ms=round(sum(latencies) / len(latencies), 3),
        p95_latency_ms=round(_percentile(latencies, 0.95), 3),
    )


def _build_breakdowns(
    results: list[CaseResult],
) -> dict[str, list[EvaluationSlice]]:
    breakdowns: dict[str, list[EvaluationSlice]] = {}
    for dimension in ("question_type", "difficulty"):
        values = sorted({str(getattr(result, dimension)) for result in results})
        breakdowns[dimension] = [
            _build_slice(
                dimension,
                value,
                [
                    result
                    for result in results
                    if str(getattr(result, dimension)) == value
                ],
            )
            for value in values
        ]
    return breakdowns


def evaluate(
    service: RAGService,
    cases: list[EvaluationCase],
    *,
    k: int,
) -> EvaluationSummary:
    results: list[CaseResult] = []
    answerable_results: list[CaseResult] = []

    for case in cases:
        raw_hits = service.retrieve(case.question, top_k=k)
        response = service.ask(case.question, top_k=k)
        retrieved_sources = [
            str(hit.document.metadata["source"]) for hit in raw_hits
        ]
        expected = set(case.expected_sources)
        matching_ranks = [
            rank
            for rank, source in enumerate(retrieved_sources, start=1)
            if source in expected
        ]
        reciprocal_rank = 1 / min(matching_ranks) if matching_ranks else 0.0
        recall_at_k = len(expected & set(retrieved_sources)) / len(expected) if expected else 0.0

        if case.answerable and case.answer_keywords:
            keyword_recall = sum(
                keyword.lower() in response.answer.lower()
                for keyword in case.answer_keywords
            ) / len(case.answer_keywords)
        else:
            keyword_recall = None

        result = CaseResult(
            id=case.id,
            question=case.question,
            answerable=case.answerable,
            question_type=case.question_type,
            difficulty=case.difficulty,
            grounded=response.grounded,
            retrieved_sources=retrieved_sources,
            reciprocal_rank=round(reciprocal_rank, 6),
            recall_at_k=round(recall_at_k, 6),
            keyword_recall=round(keyword_recall, 6)
            if keyword_recall is not None
            else None,
            latency_ms=response.latency_ms,
        )
        results.append(result)
        if case.answerable:
            answerable_results.append(result)

    hit_rate = sum(item.reciprocal_rank > 0 for item in answerable_results) / len(
        answerable_results
    )
    latencies = [item.latency_ms for item in results]
    keyword_values = [
        item.keyword_recall for item in answerable_results if item.keyword_recall is not None
    ]
    return EvaluationSummary(
        retrieval_strategy=service.settings.retrieval_strategy,
        cases=len(results),
        k=k,
        hit_rate_at_k=round(hit_rate, 6),
        recall_at_k=round(
            sum(item.recall_at_k for item in answerable_results) / len(answerable_results),
            6,
        ),
        mrr=round(
            sum(item.reciprocal_rank for item in answerable_results)
            / len(answerable_results),
            6,
        ),
        answer_keyword_recall=round(
            sum(keyword_values) / len(keyword_values) if keyword_values else 0.0,
            6,
        ),
        abstention_accuracy=round(
            sum(item.grounded == item.answerable for item in results) / len(results),
            6,
        ),
        average_latency_ms=round(sum(latencies) / len(latencies), 3),
        p95_latency_ms=round(_percentile(latencies, 0.95), 3),
        breakdowns=_build_breakdowns(results),
        results=results,
    )


def save_summary(summary: EvaluationSummary, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(summary.model_dump(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
