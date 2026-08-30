"""Bounded, deterministic chatbot-path load harness.

The default transport is an in-process simulator: no Qt objects, workers,
providers, sockets, or persistence are started.  Production adapters can be
injected for opt-in smoke/soak runs.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
import math
import threading
import time
from typing import Callable, Iterable

from src.observability import (
    record_cache_hit,
    record_llm_fallback,
    record_request_cancellation,
    record_visible_latency,
    record_llm_request,
    update_provider_health,
    update_request_in_flight,
    update_request_queue_depth,
)


PATHS = ("user", "autonomous", "refill", "mcp")


@dataclass(frozen=True)
class LoadCase:
    path: str
    duration_ms: int
    success: bool = True
    cancelled: bool = False
    provider: str = "simulated"
    cache_hit: bool = False


@dataclass(frozen=True)
class LoadSummary:
    total: int
    completed: int
    failed: int
    cancelled: int
    throughput_per_second: float
    latency_ms: dict[str, float]


def _percentile(values: list[float], fraction: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, math.ceil(len(ordered) * fraction) - 1))
    return ordered[index]


def default_cases(iterations: int = 4) -> list[LoadCase]:
    """Return repeatable coverage for every interactive path."""
    if iterations < 1:
        raise ValueError("iterations must be >= 1")
    cases: list[LoadCase] = []
    for i in range(iterations):
        cases.extend((
            LoadCase("user", 20 + i),
            LoadCase("autonomous", 30 + i),
            LoadCase("refill", 40 + i, cache_hit=(i % 2 == 0)),
            LoadCase("mcp", 10 + i, success=(i != iterations - 1)),
        ))
    cases.append(LoadCase("user", 5, cancelled=True))
    return cases


def run_load_test(
    cases: Iterable[LoadCase] | None = None,
    *,
    concurrency: int = 4,
    transport: Callable[[LoadCase], LoadCase] | None = None,
) -> LoadSummary:
    """Run bounded cases with an injectable, side-effect-free transport."""
    if concurrency < 1 or concurrency > 32:
        raise ValueError("concurrency must be between 1 and 32")
    work = list(default_cases() if cases is None else cases)
    if not work:
        return LoadSummary(0, 0, 0, 0, 0.0, {})
    if any(case.path not in PATHS for case in work):
        raise ValueError(f"path must be one of {PATHS}")
    transport = transport or (lambda case: case)
    update_request_queue_depth("load", len(work))
    in_flight = 0
    counter_lock = threading.Lock()

    def execute(case: LoadCase) -> LoadCase:
        nonlocal in_flight
        with counter_lock:
            in_flight += 1
            current = in_flight
        update_request_in_flight(current)
        update_request_queue_depth("load", max(0, len(work) - current))
        try:
            result = transport(case)
            if result.cache_hit:
                record_cache_hit(result.path)
            if result.cancelled:
                record_request_cancellation(result.path)
            record_llm_request(result.path, result.duration_ms / 1000, result.success)
            record_visible_latency(
                result.duration_ms / 1000, result.path, result.provider,
            )
            update_provider_health(result.provider, result.success)
            if not result.success:
                record_llm_fallback(result.provider, "load_test_failure")
            return result
        finally:
            with counter_lock:
                in_flight -= 1
                current = in_flight
            update_request_in_flight(current)

    started = time.monotonic()
    with ThreadPoolExecutor(max_workers=concurrency) as pool:
        results = list(pool.map(execute, work))
    elapsed_seconds = max(0.0, time.monotonic() - started)
    successful = sum(result.success and not result.cancelled for result in results)
    cancelled = sum(result.cancelled for result in results)
    durations = [float(result.duration_ms) for result in results]
    latency = {
        "p50": _percentile(durations, 0.50),
        "p95": _percentile(durations, 0.95),
        "p99": _percentile(durations, 0.99),
    }
    return LoadSummary(
        total=len(results),
        completed=successful,
        failed=len(results) - successful - cancelled,
        cancelled=cancelled,
        throughput_per_second=(len(results) / elapsed_seconds) if elapsed_seconds else 0.0,
        latency_ms=latency,
    )
