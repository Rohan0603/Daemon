from scripts.benchmark_runtime import run_baseline


def test_run_baseline_reports_all_runtime_paths():
    result = run_baseline(iterations=1)

    assert result["iterations"] == 1
    assert result["load_summary"]["total"] == 4
    assert result["load_summary"]["completed"] == 4
    assert result["load_summary"]["cancelled"] == 0
    assert result["case_duration_ms"]["p95"] == 1
    assert result["peak_python_allocations_mb"] >= 0