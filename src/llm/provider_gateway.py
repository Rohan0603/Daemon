"""Shared provider policy for OpenCode and Ollama.

Workers remain responsible for transport and Qt signals.  This module owns
provider-neutral request/result/error shapes and retry, health, and fallback
decisions so callers do not need provider-specific policy branches.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import random
import time
from typing import Any, Callable


class Provider(str, Enum):
    OPENCODE = "opencode"
    OLLAMA = "ollama"


@dataclass(frozen=True)
class ProviderRequest:
    prompt: str
    provider: str = Provider.OPENCODE.value
    autonomous: bool = False
    deadline: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def remaining(self, now: float | None = None) -> float | None:
        if self.deadline is None:
            return None
        return max(0.0, self.deadline - (time.monotonic() if now is None else now))


@dataclass(frozen=True)
class ProviderResult:
    provider: str
    items: list[dict[str, Any]]
    raw: Any = None
    elapsed: float = 0.0


@dataclass(frozen=True)
class ProviderError:
    provider: str
    code: str
    message: str = ""
    retryable: bool = False
    elapsed: float = 0.0


class Health(str, Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    OPEN = "open"


@dataclass
class _Circuit:
    failures: int = 0
    opened_at: float | None = None


@dataclass(frozen=True)
class FallbackDecision:
    should_fallback: bool
    provider: str | None = None
    reason: str = ""


class ProviderGateway:
    """Provider-neutral policy facade.

    ``invoke`` is deliberately injected: Qt workers can keep their existing
    asynchronous lifecycle while synchronous callers/tests can use ``execute``.
    """

    def __init__(
        self,
        *,
        preferred: str = Provider.OPENCODE.value,
        fallback: str = Provider.OPENCODE.value,
        failure_threshold: int = 3,
        cooldown_seconds: float = 30.0,
        max_retries: int = 2,
        base_retry_seconds: float = 0.25,
        jitter: Callable[[], float] | None = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.preferred = preferred
        self.fallback = fallback
        self.failure_threshold = max(1, failure_threshold)
        self.cooldown_seconds = max(0.0, cooldown_seconds)
        self.max_retries = max(0, max_retries)
        self.base_retry_seconds = max(0.0, base_retry_seconds)
        self._jitter = jitter or random.random
        self._clock = clock
        self._circuits: dict[str, _Circuit] = {}

    def request(self, prompt: str, *, provider: str | None = None,
                autonomous: bool = False, timeout: float | None = None,
                metadata: dict[str, Any] | None = None) -> ProviderRequest:
        deadline = None if timeout is None else self._clock() + max(0.0, timeout)
        return ProviderRequest(
            prompt=prompt,
            provider=provider or self.preferred,
            autonomous=autonomous,
            deadline=deadline,
            metadata=dict(metadata or {}),
        )

    def health(self, provider: str) -> Health:
        circuit = self._circuits.get(provider)
        if circuit is None or circuit.failures == 0:
            return Health.HEALTHY
        if circuit.opened_at is not None:
            if self._clock() - circuit.opened_at >= self.cooldown_seconds:
                return Health.DEGRADED
            return Health.OPEN
        return Health.DEGRADED

    def can_attempt(self, provider: str) -> bool:
        return self.health(provider) != Health.OPEN

    def record_success(self, provider: str) -> None:
        self._circuits[provider] = _Circuit()

    def record_failure(self, error: ProviderError) -> None:
        circuit = self._circuits.setdefault(error.provider, _Circuit())
        circuit.failures += 1
        if circuit.failures >= self.failure_threshold:
            circuit.opened_at = self._clock()

    def fallback_decision(self, request: ProviderRequest,
                          error: ProviderError) -> FallbackDecision:
        target = self.fallback
        if (target != request.provider and target and self.can_attempt(target)
                and error.code in {"timeout", "parse_failed", "unavailable", "connection"}):
            return FallbackDecision(True, target, f"{request.provider}:{error.code}")
        return FallbackDecision(False, None, f"{request.provider}:{error.code}")

    def retry_delays(self, request: ProviderRequest) -> list[float]:
        delays: list[float] = []
        for attempt in range(self.max_retries):
            delay = self.base_retry_seconds * (2 ** attempt) * (0.5 + self._jitter())
            remaining = request.remaining(self._clock())
            if remaining is not None and delay >= remaining:
                break
            delays.append(delay)
        return delays

    def normalize_result(self, request: ProviderRequest, items: Any,
                         *, raw: Any = None, elapsed: float = 0.0) -> ProviderResult:
        normalized = items if isinstance(items, list) else [items]
        normalized = [item for item in normalized if isinstance(item, dict)]
        self.record_success(request.provider)
        return ProviderResult(request.provider, normalized, raw=raw, elapsed=elapsed)

    def normalize_error(self, request: ProviderRequest, code: str,
                        message: str = "", *, retryable: bool = False,
                        elapsed: float = 0.0) -> ProviderError:
        error = ProviderError(request.provider, code, message, retryable, elapsed)
        self.record_failure(error)
        return error

    def execute(self, request: ProviderRequest,
                invoke: Callable[[ProviderRequest], Any]) -> ProviderResult:
        """Run an injected provider call with bounded retries and deadline."""
        started = self._clock()
        delays = self.retry_delays(request)
        attempts = len(delays) + 1
        last_error: ProviderError | None = None
        for attempt in range(attempts):
            if attempt == 0 and not self.can_attempt(request.provider):
                raise RuntimeError(f"provider circuit open: {request.provider}")
            try:
                value = invoke(request)
                return self.normalize_result(
                    request, value, raw=value, elapsed=self._clock() - started
                )
            except Exception as exc:
                last_error = self.normalize_error(
                    request, type(exc).__name__, str(exc),
                    retryable=attempt < len(delays), elapsed=self._clock() - started
                )
                if attempt >= len(delays):
                    break
                time.sleep(delays[attempt])
                if request.remaining(self._clock()) == 0:
                    break
        raise RuntimeError(last_error.message if last_error else "provider failed")
