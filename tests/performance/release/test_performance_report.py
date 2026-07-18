"""Unit tests for the schema-versioned release performance report helpers."""

from __future__ import annotations

from tests.performance.release.run_performance import metric_report, percentile


def test_percentile_uses_interpolated_rank() -> None:
    assert percentile([1, 2, 3, 4], 0.5) == 2.5
    assert percentile([1, 2, 3, 4], 0.95) == 3.85


def test_metric_report_contains_percentiles_and_budget_status() -> None:
    report = metric_report(
        "api.load.read",
        [10, 20, 30, 40],
        {"p50Ms": 25, "p95Ms": 50, "p99Ms": 60},
    )

    assert report["p50Ms"] == 25
    assert report["p95Ms"] == 38.5
    assert report["p99Ms"] == 39.7
    assert report["status"] == "passed"
