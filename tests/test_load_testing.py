from __future__ import annotations

from app.load_testing import (
    LoadSample,
    SLOThresholds,
    percentile,
    summarize_load,
)


def test_percentile_uses_nearest_rank() -> None:
    assert percentile([1, 2, 3, 4, 5], 0.95) == 5
    assert percentile([], 0.95) == 0


def test_load_summary_passes_configured_slo() -> None:
    samples = [LoadSample(status_code=200, latency_ms=float(value)) for value in range(1, 101)]
    summary = summarize_load(
        samples,
        wall_time_seconds=2.0,
        thresholds=SLOThresholds(
            availability_target=0.995,
            p95_latency_ms=100,
            min_requests=20,
        ),
    )

    assert summary.availability == 1.0
    assert summary.throughput_rps == 50.0
    assert summary.p95_latency_ms == 95
    assert summary.slo_passed is True


def test_load_summary_reports_availability_latency_and_sample_failures() -> None:
    samples = [
        LoadSample(status_code=200, latency_ms=6000),
        LoadSample(status_code=500, latency_ms=2),
        LoadSample(status_code=0, latency_ms=1, error="ConnectError"),
    ]
    summary = summarize_load(
        samples,
        wall_time_seconds=1.0,
        thresholds=SLOThresholds(
            availability_target=0.995,
            p95_latency_ms=5000,
            min_requests=20,
        ),
    )

    assert summary.slo_passed is False
    assert len(summary.slo_failures) == 3
    assert summary.status_counts == {
        "200": 1,
        "500": 1,
        "transport_error": 1,
    }
    assert summary.error_counts == {"ConnectError": 1}
