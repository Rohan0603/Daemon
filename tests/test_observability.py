"""Tests for observability module."""
import pytest
import time
from unittest.mock import MagicMock, patch
import src.observability as obs


# Test without dependencies first
def test_observability_import_without_deps():
    """Test that observability module can be imported without optional deps."""
    # This tests graceful degradation
    import importlib
    import sys

    # Mock missing dependencies
    for mod in ['structlog', 'prometheus_client', 'opentelemetry']:
        sys.modules[mod] = None

    # Re-import should work
    import importlib
    import src.observability
    importlib.reload(src.observability)

    # Functions should exist
    assert hasattr(src.observability, 'init_observability')
    assert hasattr(src.observability, 'get_metrics')
    assert hasattr(src.observability, 'get_tracer')
    assert hasattr(src.observability, 'trace_span')
    assert hasattr(src.observability, 'trace_function')


def test_init_observability_without_deps():
    """Test init_observability returns False for missing components."""
    with patch.object(obs, '_STRUCTLOG_AVAILABLE', False):
        with patch.object(obs, '_PROMETHEUS_AVAILABLE', False):
            with patch.object(obs, '_OTEL_AVAILABLE', False):
                import importlib
                import src.observability
                importlib.reload(src.observability)

                result = src.observability.init_observability()
                assert result["structured_logging"] is False
                assert result["metrics"] is None
                assert result["tracing"] is None


def test_metrics_recording_functions_noop_when_none():
    """Test that recording functions are no-ops when metrics is None."""
    import src.observability

    # Should not raise
    src.observability.record_llm_request("test", 1.0, True, 100)
    src.observability.record_mcp_tool_call("read_file", 0.5, True)
    src.observability.record_fsm_transition("IDLE", "THINKING")
    src.observability.record_emotion_shift("MIRTH", "ANGER")
    src.observability.record_autonomous_trigger("chat", True)
    src.observability.update_uptime(time.time() - 100)
    src.observability.update_apm(50)
    src.observability.update_health_check("opencode", True)
    src.observability.update_memory_facts(10)
    src.observability.update_thought_pool_size("typing_reaction", 5)


def test_trace_span_context_manager():
    """Test trace_span context manager works without OpenTelemetry."""
    import src.observability

    with src.observability.trace_span("test_span", {"key": "value"}) as span:
        assert span is None


def test_trace_function_decorator():
    """Test trace_function decorator works without OpenTelemetry."""
    import src.observability

    @src.observability.trace_function("test_func", {"attr": "value"})
    def test_func(x: int) -> int:
        return x * 2

    result = test_func(5)
    assert result == 10


def test_get_metrics_output():
    """Test get_metrics_output returns bytes."""
    import src.observability

    output = src.observability.get_metrics_output()
    assert isinstance(output, bytes)
    # Should contain "not initialized" when metrics is None
    assert b"not initialized" in output or b"Metrics not initialized" in output


def test_reliability_metrics_cover_dashboard_signals():
    registry = obs.CollectorRegistry()
    obs.init_metrics(registry)
    obs.record_llm_request("user", 0.1, True, 12)
    obs.record_visible_latency(0.05, "user", "test")
    obs.update_request_in_flight(2)
    obs.update_request_queue_depth("load", 3)
    obs.update_provider_health("test", False)
    obs.record_cache_hit("refill")
    obs.record_request_cancellation("user")
    output = obs.get_metrics_output().decode()
    for metric in (
        "daemon_request_throughput_total",
        "daemon_request_visible_latency_seconds",
        "daemon_request_in_flight",
        "daemon_request_queue_depth",
        "daemon_provider_health",
        "daemon_cache_hits_total",
        "daemon_request_cancellations_total",
    ):
        assert metric in output


def test_request_timing_records_typed_e2e_phases():
    timing = obs.RequestTiming("cid-test")
    timing.mark("queue")
    timing.marks["provider"] = 0.25
    assert timing.correlation_id == "cid-test"
    assert timing.duration("provider") == 0.25
    assert timing.duration("missing") == 0.0


def test_e2e_metrics_expose_phase_and_fallback_labels():
    if not obs._PROMETHEUS_AVAILABLE:
        pytest.skip("prometheus-client unavailable")
    metrics = obs.init_metrics()
    timing = obs.RequestTiming("cid-test")
    timing.marks["first_visible"] = 0.125
    obs.record_request_phase(timing, "first_visible", "user", "opencode")
    obs.record_llm_fallback("opencode", "parse_failed")
    output = metrics.metrics_endpoint().decode()
    assert 'daemon_e2e_phase_seconds_count{phase="first_visible",provider="opencode",request_type="user"}' in output
    assert 'daemon_llm_fallback_total{provider="opencode",reason="parse_failed"}' in output


# Test with mocked prometheus
def test_metrics_class_with_prometheus():
    """Test DaemonMetrics class with mocked prometheus."""
    # Skip this test since it requires complex module-level patching
    pytest.skip("Requires module-level import patching, tested via integration")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])