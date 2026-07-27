from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.evaluation import load_dataset
from app.generator import GeneratedAnswer, ModelUsage, extract_model_usage
from app.model_evaluation import PricingSnapshot, evaluate_online_model
from app.service import RAGService


class FakeUsageGenerator:
    def generate_with_usage(self, question, hits) -> GeneratedAnswer:
        del question
        return GeneratedAnswer(
            answer="\n".join(hit.document.page_content for hit in hits),
            model_latency_ms=25.0,
            usage=ModelUsage(
                input_tokens=100,
                output_tokens=20,
                total_tokens=120,
                cached_input_tokens=10,
                reasoning_tokens=5,
            ),
        )


class MissingUsageGenerator:
    def generate_with_usage(self, question, hits) -> GeneratedAnswer:
        del question, hits
        return GeneratedAnswer(
            answer="未返回用量",
            model_latency_ms=25.0,
            usage=None,
        )


def test_extract_model_usage_supports_langchain_metadata() -> None:
    response = SimpleNamespace(
        usage_metadata={
            "input_tokens": 120,
            "output_tokens": 30,
            "total_tokens": 150,
            "input_token_details": {"cache_read": 20},
            "output_token_details": {"reasoning": 7},
        }
    )

    usage = extract_model_usage(response)

    assert usage == ModelUsage(
        input_tokens=120,
        output_tokens=30,
        total_tokens=150,
        cached_input_tokens=20,
        reasoning_tokens=7,
    )


def test_extract_model_usage_supports_openai_compatible_metadata() -> None:
    response = SimpleNamespace(
        usage_metadata=None,
        response_metadata={
            "token_usage": {
                "prompt_tokens": 80,
                "completion_tokens": 20,
                "prompt_tokens_details": {"cached_tokens": 8},
                "completion_tokens_details": {"reasoning_tokens": 4},
            }
        },
    )

    usage = extract_model_usage(response)

    assert usage == ModelUsage(
        input_tokens=80,
        output_tokens=20,
        total_tokens=100,
        cached_input_tokens=8,
        reasoning_tokens=4,
    )


def test_online_model_evaluation_records_quality_latency_tokens_and_cost(
    service: RAGService,
) -> None:
    all_cases = load_dataset(service.settings.evaluation_dataset)
    selected_ids = {"perm-01", "perm-02", "unknown-01"}
    cases = [case for case in all_cases if case.id in selected_ids]
    pricing = PricingSnapshot(
        input_usd_per_million_tokens=1.0,
        output_usd_per_million_tokens=2.0,
        cached_input_usd_per_million_tokens=0.5,
        as_of="2026-07-26",
        source="test fixture",
    )

    summary = evaluate_online_model(
        service,
        FakeUsageGenerator(),
        cases,
        pricing=pricing,
        model="test-model",
        provider="test-provider",
        k=4,
    )

    assert summary.cases == 3
    assert summary.answerable_cases == 2
    assert summary.model_calls == 2
    assert summary.source_hit_rate == 1.0
    assert summary.decision_accuracy == 1.0
    assert summary.total_input_tokens == 200
    assert summary.total_output_tokens == 40
    assert summary.total_tokens == 240
    assert summary.total_cached_input_tokens == 20
    assert summary.total_reasoning_tokens == 10
    assert summary.total_cost_usd == pytest.approx(0.00027)
    assert summary.average_cost_per_request_usd == pytest.approx(0.00009)
    assert summary.average_cost_per_model_call_usd == pytest.approx(0.000135)
    assert set(summary.breakdowns) == {"question_type", "difficulty"}


def test_online_model_evaluation_rejects_missing_usage(
    service: RAGService,
) -> None:
    case = load_dataset(service.settings.evaluation_dataset)[0]
    pricing = PricingSnapshot(
        input_usd_per_million_tokens=1.0,
        output_usd_per_million_tokens=2.0,
        as_of="2026-07-26",
        source="test fixture",
    )

    with pytest.raises(RuntimeError, match="Token 用量"):
        evaluate_online_model(
            service,
            MissingUsageGenerator(),
            [case],
            pricing=pricing,
            model="test-model",
            provider="test-provider",
            k=4,
        )
