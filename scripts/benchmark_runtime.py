"""Measure deterministic runtime-path latency and Python allocations.

This benchmark does not start Qt, providers, sockets, workers, or persistence.
Use ``benchmark_model_routing.py`` separately for live provider measurements.
"""
from __future__ import annotations

import argparse
import json
import sys
import statistics
import time
import tracemalloc
from dataclasses import asdict
from pathlib import Path

# Keep ``py scripts/benchmark_runtime.py`` usable as documented on Windows.
if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.load_harness import LoadCase, run_load_test


def _percentile(values: list[float], fraction: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(len(ordered) - 1, round((len(ordered) - 1) * fraction))
    return ordered[index]


def run_baseline(iterations: int = 4, concurrency: int = 1) -> dict[str, object]:
    """Run repeatable fast-path cases and return JSON-serializable metrics."""
    cases = [
        LoadCase("user", 1),
        LoadCase("autonomous", 1),
        LoadCase("refill", 1, cache_hit=True),
        LoadCase("mcp", 1),
    ] * iterations
    tracemalloc.start()
    started = time.perf_counter()
    summary = run_load_test(cases, concurrency=concurrency)
    elapsed_ms = (time.perf_counter() - started) * 1000
    _, peak_bytes = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    durations = [case.duration_ms for case in cases]
    return {
        "iterations": iterations,
        "concurrency": concurrency,
        "elapsed_ms": round(elapsed_ms, 3),
        "peak_python_allocations_mb": round(peak_bytes / 1024 / 1024, 3),
        "load_summary": asdict(summary),
        "case_duration_ms": {
            "mean": statistics.fmean(durations),
            "p50": _percentile(durations, 0.50),
            "p95": _percentile(durations, 0.95),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--iterations", type=int, default=4)
    parser.add_argument("--concurrency", type=int, default=1)
    args = parser.parse_args()
    if args.iterations < 1:
        parser.error("--iterations must be >= 1")
    if args.concurrency < 1 or args.concurrency > 32:
        parser.error("--concurrency must be between 1 and 32")
    print(json.dumps(run_baseline(args.iterations, args.concurrency), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())