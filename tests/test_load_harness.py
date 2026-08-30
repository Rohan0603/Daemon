from src.load_harness import LoadCase, default_cases, run_load_test


def test_default_cases_cover_paths_and_cancellation():
    cases = default_cases(3)
    assert {case.path for case in cases} == {"user", "autonomous", "refill", "mcp"}
    assert sum(case.cancelled for case in cases) == 1


def test_load_harness_is_bounded_repeatable_and_reports_percentiles():
    cases = [
        LoadCase("user", 10),
        LoadCase("autonomous", 20),
        LoadCase("refill", 30, cache_hit=True),
        LoadCase("mcp", 40, success=False),
        LoadCase("user", 50, cancelled=True),
    ]
    first = run_load_test(cases, concurrency=2)
    second = run_load_test(cases, concurrency=2)
    assert first.total == second.total == 5
    assert first.completed == second.completed == 3
    assert first.failed == second.failed == 1
    assert first.cancelled == second.cancelled == 1
    assert first.latency_ms == {"p50": 30.0, "p95": 50.0, "p99": 50.0}
    assert first.throughput_per_second > 0


def test_load_harness_rejects_unbounded_inputs():
    try:
        run_load_test([], concurrency=33)
    except ValueError as exc:
        assert "between 1 and 32" in str(exc)
    else:
        raise AssertionError("expected concurrency bound")
