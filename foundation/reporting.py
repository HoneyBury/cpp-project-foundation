from __future__ import annotations

import statistics
from pathlib import Path
from typing import Any

from .common import FoundationError, load_json


def _number(document: dict[str, Any], key: str) -> float:
    value = document.get(key)
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise FoundationError(f"operations summary requires numeric {key}")
    return float(value)


def _integer(document: dict[str, Any], key: str) -> int:
    value = _number(document, key)
    if not value.is_integer():
        raise FoundationError(f"operations summary requires integer {key}")
    return int(value)


def _measurements(document: dict[str, Any], key: str, field: str) -> list[float]:
    values = document.get(key)
    if not isinstance(values, list) or not values:
        raise FoundationError(f"operations summary requires non-empty {key}")
    measurements = []
    for item in values:
        if not isinstance(item, dict):
            raise FoundationError(f"operations summary contains invalid {key}")
        measurements.append(_number(item, field))
    return measurements


def render_operations_report(
    soak_path: Path,
    performance_path: Path,
    output: Path,
    *,
    append: bool = False,
) -> dict[str, Any]:
    soak = load_json(soak_path)
    performance = load_json(performance_path)
    if soak.get("schema_version") != 1 or performance.get("schema_version") != 1:
        raise FoundationError("operations summary schema_version must be 1")

    latencies = _measurements(soak, "samples", "latency_ms")
    operations = _measurements(performance, "results", "ops_per_second")
    p99_values = _measurements(performance, "results", "p99_ms")
    sample_count = _integer(soak, "sample_count")
    repetitions = _integer(performance, "repetitions")
    if sample_count != len(latencies):
        raise FoundationError("soak sample_count does not match samples")
    if repetitions != len(operations):
        raise FoundationError("performance repetitions does not match results")

    gates = performance.get("gates")
    if not isinstance(gates, dict):
        raise FoundationError("operations summary requires performance gates")
    minimum_ops = _number(gates, "minimum_ops_per_second")
    maximum_p99 = _number(gates, "maximum_p99_ms")
    failures = _integer(soak, "failures")
    samples = soak["samples"]
    observed_failures = sum(
        not isinstance(item, dict) or item.get("success") is not True
        for item in samples
    )
    if failures != observed_failures:
        raise FoundationError("soak failures does not match samples")
    overall_pass = (
        soak.get("overall_pass") is True and performance.get("overall_pass") is True
    )
    metrics = {
        "duration_target_seconds": _number(soak, "duration_target_seconds"),
        "duration_elapsed_seconds": _number(soak, "duration_elapsed_seconds"),
        "sample_count": sample_count,
        "failures": failures,
        "minimum_latency_ms": min(latencies),
        "average_latency_ms": statistics.fmean(latencies),
        "maximum_latency_ms": max(latencies),
        "minimum_ops_per_second": min(operations),
        "median_ops_per_second": statistics.median(operations),
        "maximum_ops_per_second": max(operations),
        "maximum_p99_ms": max(p99_values),
        "gate_minimum_ops_per_second": minimum_ops,
        "gate_maximum_p99_ms": maximum_p99,
    }
    status = "PASS" if overall_pass else "FAIL"
    markdown = "\n".join(
        (
            "## C++ Foundation Operations",
            "",
            f"**Result: {status}**",
            "",
            "| Metric | Result | Gate |",
            "| --- | ---: | ---: |",
            (
                "| Stability duration | "
                f"{metrics['duration_elapsed_seconds']:.3f} s | "
                f">= {metrics['duration_target_seconds']:.3f} s |"
            ),
            f"| Samples | {sample_count} ({failures} failures) | 0 failures |",
            (
                "| Check latency min / avg / max | "
                f"{metrics['minimum_latency_ms']:.3f} / "
                f"{metrics['average_latency_ms']:.3f} / "
                f"{metrics['maximum_latency_ms']:.3f} ms | informational |"
            ),
            (
                "| Throughput min / median / max | "
                f"{metrics['minimum_ops_per_second']:,.3f} / "
                f"{metrics['median_ops_per_second']:,.3f} / "
                f"{metrics['maximum_ops_per_second']:,.3f} ops/s | "
                f">= {minimum_ops:,.3f} ops/s |"
            ),
            (
                f"| Maximum benchmark P99 | {metrics['maximum_p99_ms']:.3f} ms | "
                f"<= {maximum_p99:.3f} ms |"
            ),
            "",
        )
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    mode = "a" if append else "w"
    with output.open(mode, encoding="utf-8") as stream:
        stream.write(markdown)
    return {
        "schema_version": 1,
        "overall_pass": overall_pass,
        "output": str(output),
        "metrics": metrics,
    }
