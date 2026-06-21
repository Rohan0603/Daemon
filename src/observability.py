"""Observability Stack — Structured logging, metrics, and tracing for Daemon.

Provides:
- Structured JSON logging via structlog
- Prometheus metrics exposition (/metrics endpoint)
- OpenTelemetry distributed tracing
- Integration with existing logging setup
"""
from __future__ import annotations
import logging
import os
import sys
import time
from contextlib import contextmanager
from functools import wraps
from typing import Any, Callable, Dict, Optional, TypeVar

# Optional dependencies - gracefully degrade if not installed
try:
    import structlog
    _STRUCTLOG_AVAILABLE = True
except ImportError:
    _STRUCTLOG_AVAILABLE = False

try:
    from prometheus_client import Counter, Gauge, Histogram, generate_latest, CollectorRegistry, CONTENT_TYPE_LATEST
    from prometheus_client.core import REGISTRY
    _PROMETHEUS_AVAILABLE = True
except ImportError:
    _PROMETHEUS_AVAILABLE = False

try:
    from opentelemetry import trace
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
    from opentelemetry.instrumentation.requests import RequestsInstrumentor
    _OTEL_AVAILABLE = True
except ImportError:
    _OTEL_AVAILABLE = False

logger = logging.getLogger(__name__)

# Type variable for decorators
F = TypeVar('F', bound=Callable[..., Any])

# Global state
_metrics_registry: Optional["CollectorRegistry"] = None
_tracer = None
_observability_initialized = False


# =============================================================================
# Structured Logging (structlog)
# =============================================================================

def setup_structured_logging(
    level: int = logging.INFO,
    json_output: bool = True,
    add_timestamp: bool = True,
) -> None:
    """Configure structlog for structured JSON logging.

    Call this early in main() before other logging setup.
    """
    if not _STRUCTLOG_AVAILABLE:
        logger.warning("structlog not available, falling back to stdlib logging")
        return

    processors = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    if add_timestamp:
        processors.append(structlog.processors.TimeStamper(fmt="iso"))

    if json_output:
        processors.append(structlog.processors.JSONRenderer())
    else:
        processors.append(structlog.dev.ConsoleRenderer())

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(level),
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # Also configure stdlib logging to use structlog
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=level,
    )


def get_structured_logger(name: str) -> Any:
    """Get a structlog logger instance."""
    if _STRUCTLOG_AVAILABLE:
        return structlog.get_logger(name)
    return logging.getLogger(name)


# =============================================================================
# Prometheus Metrics
# =============================================================================

class DaemonMetrics:
    """Prometheus metrics for Daemon observability."""

    def __init__(self, registry: Optional["CollectorRegistry"] = None):
        self._registry = registry or CollectorRegistry()

        # System metrics
        self.uptime_seconds = Gauge(
            "daemon_uptime_seconds",
            "Daemon uptime in seconds",
            registry=self._registry,
        )

        # FSM metrics
        self.fsm_state = Gauge(
            "daemon_fsm_state",
            "Current FSM state (1=active, 0=inactive)",
            ["state"],
            registry=self._registry,
        )
        self.fsm_transitions_total = Counter(
            "daemon_fsm_transitions_total",
            "Total FSM state transitions",
            ["from_state", "to_state"],
            registry=self._registry,
        )

        # Emotion metrics
        self.current_emotion = Gauge(
            "daemon_current_emotion",
            "Current emotion (1=active, 0=inactive)",
            ["emotion"],
            registry=self._registry,
        )
        self.emotion_shifts_total = Counter(
            "daemon_emotion_shifts_total",
            "Total emotion shifts",
            ["from_emotion", "to_emotion"],
            registry=self._registry,
        )

        # LLM metrics
        self.llm_requests_total = Counter(
            "daemon_llm_requests_total",
            "Total LLM requests",
            ["type", "status"],  # type: user/autonomous/refill, status: success/error/timeout
            registry=self._registry,
        )
        self.llm_request_duration_seconds = Histogram(
            "daemon_llm_request_duration_seconds",
            "LLM request duration in seconds",
            ["type"],
            registry=self._registry,
        )
        self.llm_tokens_total = Counter(
            "daemon_llm_tokens_total",
            "Total LLM tokens (prompt + completion)",
            ["type"],
            registry=self._registry,
        )

        # MCP metrics
        self.mcp_tool_calls_total = Counter(
            "daemon_mcp_tool_calls_total",
            "Total MCP tool calls",
            ["tool", "status"],  # status: allowed/blocked/error
            registry=self._registry,
        )
        self.mcp_tool_duration_seconds = Histogram(
            "daemon_mcp_tool_duration_seconds",
            "MCP tool execution duration",
            ["tool"],
            registry=self._registry,
        )

        # Memory metrics
        self.memory_facts_total = Gauge(
            "daemon_memory_facts_total",
            "Total memory facts stored",
            registry=self._registry,
        )
        self.memory_sync_total = Counter(
            "daemon_memory_sync_total",
            "Total memory sync operations",
            ["direction", "status"],  # direction: to_local/from_local, status: success/failed
            registry=self._registry,
        )

        # Autonomous behavior metrics
        self.autonomous_triggers_total = Counter(
            "daemon_autonomous_triggers_total",
            "Total autonomous behavior triggers",
            ["mode", "status"],  # mode: chat/joke/boredom/refill, status: fired/blocked
            registry=self._registry,
        )
        self.thought_pool_size = Gauge(
            "daemon_thought_pool_size",
            "Current thought pool size",
            ["type"],  # typing_reaction, observation, intel_roast, idle_thought
            registry=self._registry,
        )

        # APM metrics
        self.current_apm = Gauge(
            "daemon_current_apm",
            "Current actions per minute",
            registry=self._registry,
        )

        # Health metrics
        self.health_check_status = Gauge(
            "daemon_health_check_status",
            "Health check status (1=healthy, 0=unhealthy)",
            ["component"],  # component: opencode, mcp
            registry=self._registry,
        )

    def get_registry(self) -> "CollectorRegistry":
        return self._registry

    def metrics_endpoint(self) -> bytes:
        """Generate Prometheus metrics output for /metrics endpoint."""
        return generate_latest(self._registry)


# Global metrics instance
_metrics: Optional[DaemonMetrics] = None


def init_metrics(registry: Optional["CollectorRegistry"] = None) -> DaemonMetrics:
    """Initialize global metrics instance."""
    global _metrics
    _metrics = DaemonMetrics(registry)
    return _metrics


def get_metrics() -> Optional[DaemonMetrics]:
    return _metrics


# =============================================================================
# OpenTelemetry Tracing
# =============================================================================

def init_tracing(
    service_name: str = "daemon",
    otlp_endpoint: Optional[str] = None,
) -> Optional[Any]:
    """Initialize OpenTelemetry tracing.

    Args:
        service_name: Service name for traces
        otlp_endpoint: OTLP HTTP endpoint (e.g., "http://localhost:4318/v1/traces")

    Returns:
        Tracer instance or None if OpenTelemetry not available
    """
    global _tracer, _observability_initialized

    if not _OTEL_AVAILABLE:
        logger.warning("OpenTelemetry not available, tracing disabled")
        return None

    # Set up tracer provider
    provider = TracerProvider()
    trace.set_tracer_provider(provider)

    # Add OTLP exporter if endpoint provided (else no export)
    if otlp_endpoint:
        try:
            exporter = OTLPSpanExporter(endpoint=otlp_endpoint)
            processor = BatchSpanProcessor(exporter)
            provider.add_span_processor(processor)
            logger.info("OpenTelemetry OTLP exporter configured: %s", otlp_endpoint)
        except Exception as e:
            logger.warning("Failed to configure OTLP exporter: %s", e)

    # Auto-instrument requests library
    try:
        RequestsInstrumentor().instrument()
    except Exception as e:
        logger.warning("Failed to instrument requests: %s", e)

    _tracer = trace.get_tracer(service_name)
    _observability_initialized = True
    logger.info("OpenTelemetry tracing initialized for %s", service_name)
    return _tracer


def get_tracer() -> Optional[Any]:
    return _tracer


@contextmanager
def trace_span(name: str, attributes: Optional[Dict[str, Any]] = None):
    """Context manager for creating traced spans."""
    if _tracer is None:
        yield None
        return

    with _tracer.start_as_current_span(name) as span:
        if attributes:
            for k, v in attributes.items():
                span.set_attribute(k, str(v))
        yield span


def trace_function(name: Optional[str] = None, attributes: Optional[Dict[str, Any]] = None):
    """Decorator for tracing function calls."""
    def decorator(func: F) -> F:
        span_name = name or f"{func.__module__}.{func.__qualname__}"

        @wraps(func)
        def wrapper(*args, **kwargs):
            with trace_span(span_name, attributes) as span:
                try:
                    result = func(*args, **kwargs)
                    if span:
                        span.set_attribute("function.result", "success")
                    return result
                except Exception as e:
                    if span:
                        span.set_attribute("function.result", "error")
                        span.set_attribute("function.error", str(e))
                    raise

        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            with trace_span(span_name, attributes) as span:
                try:
                    result = await func(*args, **kwargs)
                    if span:
                        span.set_attribute("function.result", "success")
                    return result
                except Exception as e:
                    if span:
                        span.set_attribute("function.result", "error")
                        span.set_attribute("function.error", str(e))
                    raise

        import inspect
        if inspect.iscoroutinefunction(func):
            return async_wrapper  # type: ignore
        return wrapper  # type: ignore

    return decorator


# =============================================================================
# Convenience & Integration
# =============================================================================

def init_observability(
    service_name: str = "daemon",
    log_level: int = logging.INFO,
    json_logs: bool = True,
    enable_metrics: bool = True,
    enable_tracing: bool = False,
    otlp_endpoint: Optional[str] = None,
) -> Dict[str, Any]:
    """Initialize all observability components.

    Returns dict with initialized components.
    """
    results = {}

    # 1. Structured logging
    if _STRUCTLOG_AVAILABLE:
        setup_structured_logging(level=log_level, json_output=json_logs)
        results["structured_logging"] = True
    else:
        results["structured_logging"] = False
        logger.warning("structlog not installed, skipping structured logging")

    # 2. Metrics
    if enable_metrics and _PROMETHEUS_AVAILABLE:
        metrics = init_metrics()
        results["metrics"] = metrics
    else:
        results["metrics"] = None
        if not _PROMETHEUS_AVAILABLE:
            logger.warning("prometheus-client not installed, skipping metrics")

    # 3. Tracing
    if enable_tracing and _OTEL_AVAILABLE:
        tracer = init_tracing(service_name, otlp_endpoint)
        results["tracing"] = tracer
    else:
        results["tracing"] = None
        if not _OTEL_AVAILABLE:
            logger.warning("opentelemetry not installed, skipping tracing")

    return results


def record_llm_request(
    request_type: str,
    duration_seconds: float,
    success: bool,
    tokens: int = 0,
) -> None:
    """Record LLM request metrics."""
    if _metrics:
        status = "success" if success else "error"
        _metrics.llm_requests_total.labels(type=request_type, status=status).inc()
        _metrics.llm_request_duration_seconds.labels(type=request_type).observe(duration_seconds)
        if tokens:
            _metrics.llm_tokens_total.labels(type=request_type).inc(tokens)


def record_mcp_tool_call(
    tool_name: str,
    duration_seconds: float,
    allowed: bool,
) -> None:
    """Record MCP tool call metrics."""
    if _metrics:
        status = "allowed" if allowed else "blocked"
        _metrics.mcp_tool_calls_total.labels(tool=tool_name, status=status).inc()
        _metrics.mcp_tool_duration_seconds.labels(tool=tool_name).observe(duration_seconds)


def record_fsm_transition(from_state: str, to_state: str) -> None:
    """Record FSM transition metrics."""
    if _metrics:
        _metrics.fsm_transitions_total.labels(from_state=from_state, to_state=to_state).inc()
        # Update current state gauges
        for state in ["IDLE", "SLEEP", "PERIMETER", "CHASE", "HYPER", "THINKING", "AUTONOMOUS_THINKING",
                       "CELEBRATE", "DEVASTATED", "DRAGGED", "FALLING", "SHAKING", "BOUNCING", "SPINNING", "LOOK_AWAY"]:
            _metrics.fsm_state.labels(state=state).set(1 if state == to_state else 0)


def record_emotion_shift(from_emotion: str, to_emotion: str) -> None:
    """Record emotion shift metrics."""
    if _metrics:
        _metrics.emotion_shifts_total.labels(from_emotion=from_emotion, to_emotion=to_emotion).inc()
        for emotion in ["MIRTH", "ANGER", "FEAR", "DISGUST", "PATHOS", "DEVOTION", "HEROISM", "WONDER", "TRANQUILITY"]:
            _metrics.current_emotion.labels(emotion=emotion).set(1 if emotion == to_emotion else 0)


def record_autonomous_trigger(mode: str, fired: bool) -> None:
    """Record autonomous trigger metrics."""
    if _metrics:
        status = "fired" if fired else "blocked"
        _metrics.autonomous_triggers_total.labels(mode=mode, status=status).inc()


def update_uptime(start_time: float) -> None:
    """Update uptime metric."""
    if _metrics:
        _metrics.uptime_seconds.set(time.time() - start_time)


def update_apm(apm: int) -> None:
    """Update current APM metric."""
    if _metrics:
        _metrics.current_apm.set(apm)


def update_health_check(component: str, healthy: bool) -> None:
    """Update health check metric."""
    if _metrics:
        _metrics.health_check_status.labels(component=component).set(1 if healthy else 0)


def update_memory_facts(count: int) -> None:
    """Update memory facts count."""
    if _metrics:
        _metrics.memory_facts_total.set(count)


def update_thought_pool_size(pool_type: str, size: int) -> None:
    """Update thought pool size."""
    if _metrics:
        _metrics.thought_pool_size.labels(type=pool_type).set(size)


# =============================================================================
# Metrics Endpoint (for Prometheus scraping)
# =============================================================================

async def metrics_handler(request: Any) -> Any:
    """ASGI handler for /metrics endpoint (for use with FastAPI/Starlette).

    If using a different framework, call `_metrics.metrics_endpoint()` directly.
    """
    if _metrics:
        from aiohttp import web
        return web.Response(
            body=_metrics.metrics_endpoint(),
            content_type=CONTENT_TYPE_LATEST,
        )
    from aiohttp import web
    return web.Response(status=503, text="Metrics not initialized")


def get_metrics_output() -> bytes:
    """Get metrics output for Prometheus scraping (sync version)."""
    if _metrics:
        return _metrics.metrics_endpoint()
    return b"# Metrics not initialized\n"