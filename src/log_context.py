"""Correlation ID context for distributed tracing across log lines."""
import contextvars
import logging
import uuid

_correlation_id: contextvars.ContextVar[str] = contextvars.ContextVar(
    "correlation_id", default=""
)


def get_correlation_id() -> str:
    return _correlation_id.get()


def set_correlation_id(cid: str | None = None) -> str:
    """Set a correlation ID. Generates one if not provided."""
    if not cid:
        cid = uuid.uuid4().hex[:12]
    _correlation_id.set(cid)
    return cid


def reset_correlation_id() -> None:
    _correlation_id.set("")


class CorrelationIdFilter(logging.Filter):
    """Logging filter that adds correlation_id to every log record."""

    def filter(self, record: logging.LogRecord) -> bool:
        cid = get_correlation_id()
        record.correlation_id = cid if cid else "-"
        return True


class CorrelationIdDefault(logging.Formatter):
    """Formatter that injects correlation_id from contextvar into log records."""

    def format(self, record: logging.LogRecord) -> str:
        cid = get_correlation_id()
        record.correlation_id = cid if cid else "-"
        return logging.Formatter.format(self, record)

