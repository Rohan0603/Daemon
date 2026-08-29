"""Small, thread-safe helpers for safe, useful logging context."""
import contextvars
import logging
import re
import uuid
from collections import OrderedDict
from contextlib import contextmanager
from time import monotonic as _monotonic
from typing import Any, Iterator

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


@contextmanager
def correlation_scope(cid: str | None = None) -> Iterator[str]:
    """Temporarily bind a correlation ID and restore the previous one."""
    value = cid or uuid.uuid4().hex[:12]
    token = _correlation_id.set(value)
    try:
        yield value
    finally:
        _correlation_id.reset(token)


correlation_id_scope = correlation_scope
correlation_context = correlation_scope


_SENSITIVE_KEY = re.compile(
    r"(?:pass(?:word|code)?|secret|token|api[_-]?key|auth|cookie|credential|"
    r"private[_-]?key|id[_-]?token|refresh[_-]?token)",
    re.IGNORECASE,
)
_SENSITIVE_VALUE = re.compile(
    r"(?i)\b(?:bearer|basic)\s+[A-Za-z0-9._~+/=-]+|"
    r"\b(?:password|secret|api[_-]?key|access[_-]?token|refresh[_-]?token)"
    r"\s*[:=]\s*[^\s,;]+"
)


def redact_sensitive(
    value: Any,
    *,
    key: str | None = None,
    max_length: int = 512,
) -> Any:
    """Return a bounded, log-safe representation of ``value``.

    Sensitive mapping fields are replaced before truncation. Other strings have
    common bearer/token assignments masked, then are capped to ``max_length``.
    """
    if key and _SENSITIVE_KEY.search(key):
        return "[REDACTED]"
    if isinstance(value, dict):
        return {
            str(k): redact_sensitive(v, key=str(k), max_length=max_length)
            for k, v in value.items()
        }
    if isinstance(value, (list, tuple, set)):
        items = [redact_sensitive(item, max_length=max_length) for item in value]
        return type(value)(items) if not isinstance(value, tuple) else tuple(items)
    if isinstance(value, bytes):
        value = value.decode("utf-8", errors="replace")
    if isinstance(value, str):
        safe = _SENSITIVE_VALUE.sub("[REDACTED]", value)
        if len(safe) > max_length:
            return safe[:max_length] + "…"
        return safe
    return value


safe_log_value = redact_sensitive
sanitize_log_value = redact_sensitive


class RepeatedEventFilter(logging.Filter):
    """Suppress repeated records while retaining a bounded key cache."""

    def __init__(
        self,
        *,
        max_repeats: int = 5,
        interval_seconds: float = 30.0,
        max_keys: int = 1024,
    ) -> None:
        super().__init__()
        self.max_repeats = max(1, max_repeats)
        self.interval_seconds = max(0.0, interval_seconds)
        self.max_keys = max(1, max_keys)
        self._events: OrderedDict[tuple[str, int, str], tuple[float, int]] = OrderedDict()

    def filter(self, record: logging.LogRecord) -> bool:
        now = _monotonic()
        key = (record.name, record.levelno, redact_sensitive(record.getMessage(), max_length=512))
        previous = self._events.get(key)
        elapsed = now - previous[0] if previous is not None else None
        if previous is None or not isinstance(elapsed, (int, float)) or elapsed >= self.interval_seconds:
            count = 1
        else:
            count = previous[1] + 1
        self._events[key] = (now, count)
        self._events.move_to_end(key)
        while len(self._events) > self.max_keys:
            self._events.popitem(last=False)
        return count <= self.max_repeats


class SafeLogFilter(logging.Filter):
    """Redact and bound rendered message text before handlers emit it."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = redact_sensitive(record.getMessage())
        record.args = ()
        return True


RateLimitFilter = RepeatedEventFilter


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
