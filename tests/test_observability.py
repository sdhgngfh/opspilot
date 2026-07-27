from __future__ import annotations

from fastapi.testclient import TestClient
from prometheus_client import CollectorRegistry

import app.api as api_module
from app.api import app
from app.observability import (
    NoopMetrics,
    PrometheusMetrics,
    configure_observability,
    metrics_for,
    otel_enabled,
    tracing_enabled,
)


def test_langsmith_configuration_is_opt_in(settings, monkeypatch) -> None:
    monkeypatch.delenv("LANGSMITH_TRACING", raising=False)
    monkeypatch.delenv("LANGSMITH_API_KEY", raising=False)
    monkeypatch.delenv("LANGSMITH_PROJECT", raising=False)

    configure_observability(settings)

    assert "LANGSMITH_TRACING" not in __import__("os").environ
    assert tracing_enabled(settings) is False


def test_langsmith_configuration_sets_runtime_environment(settings, monkeypatch) -> None:
    monkeypatch.delenv("LANGSMITH_TRACING", raising=False)
    traced = settings.model_copy(
        update={
            "langsmith_tracing": True,
            "langsmith_api_key": "test-key",
            "langsmith_project": "opspilot-tests",
        }
    )

    configure_observability(traced)

    assert __import__("os").environ["LANGSMITH_TRACING"] == "true"
    assert __import__("os").environ["LANGSMITH_PROJECT"] == "opspilot-tests"
    assert tracing_enabled(traced) is True


def test_metrics_are_opt_in(settings) -> None:
    recorder = metrics_for(settings)

    assert isinstance(recorder, NoopMetrics)
    assert recorder.enabled is False


def test_prometheus_metrics_use_bounded_labels_without_business_content() -> None:
    recorder = PrometheusMetrics(CollectorRegistry())
    recorder.request_started("post")
    recorder.observe_http(
        method="post",
        route="/v1/graph/threads/{thread_id}",
        status_code=200,
        latency_seconds=0.025,
    )
    recorder.request_finished("post")
    recorder.observe_rag(
        workflow="graph",
        grounded=False,
        latency_seconds=0.05,
        rewrite_count=2,
    )
    recorder.observe_ticket(action="approve", status="submitted")
    recorder.observe_rate_limit_rejection()
    recorder.observe_readiness(False)

    payload, content_type = recorder.render()
    text = payload.decode("utf-8")

    assert "text/plain" in content_type
    assert 'route="/v1/graph/threads/{thread_id}"' in text
    assert 'status_class="2xx"' in text
    assert 'outcome="refused"' in text
    assert 'action="approve"' in text
    assert "opspilot_readiness_status 0.0" in text
    assert "thread-actual-value" not in text
    assert "user question" not in text


def test_otel_configuration_is_explicit(settings) -> None:
    assert otel_enabled(settings) is False


def test_metrics_endpoint_is_opt_in_and_emits_http_metrics(
    settings,
    monkeypatch,
) -> None:
    dependency = api_module.get_settings
    disabled = TestClient(app).get("/metrics")
    assert disabled.status_code == 404

    enabled = settings.model_copy(update={"metrics_enabled": True})
    recorder = PrometheusMetrics(CollectorRegistry())
    app.dependency_overrides[dependency] = lambda: enabled
    monkeypatch.setattr(api_module, "get_settings", lambda: enabled)
    monkeypatch.setattr(api_module, "metrics_for", lambda runtime: recorder)
    try:
        client = TestClient(app)
        assert client.get("/health/live").status_code == 200
        response = client.get("/metrics")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/plain")
    assert 'route="/health/live"' in response.text
    assert 'status_class="2xx"' in response.text
