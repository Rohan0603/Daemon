"""Run the deterministic chatbot-path load harness.

This is intentionally offline by default.  It is safe to run in CI and does
not create QApplication, QThread, provider, MCP, or persistence resources.
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.load_harness import default_cases, run_load_test


def main() -> int:
    parser = argparse.ArgumentParser(description="Bounded offline chatbot load test")
    parser.add_argument("--iterations", type=int, default=4)
    parser.add_argument("--concurrency", type=int, default=4)
    args = parser.parse_args()
    summary = run_load_test(
        default_cases(args.iterations), concurrency=args.concurrency,
    )
    print(json.dumps({
        "total": summary.total,
        "completed": summary.completed,
        "failed": summary.failed,
        "cancelled": summary.cancelled,
        "throughput_per_second": round(summary.throughput_per_second, 2),
        "latency_ms": summary.latency_ms,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
