import pytest

from src.llm.provider_gateway import (
    Health, ProviderError, ProviderGateway, ProviderResult,
)


def test_request_has_bounded_deadline_and_normalized_result():
    gateway = ProviderGateway()
    request = gateway.request("hello", provider="ollama", timeout=2)
    assert request.prompt == "hello"
    assert request.remaining() <= 2
    result = gateway.normalize_result(request, {"dialogue": "hi"})
    assert isinstance(result, ProviderResult)
    assert result.provider == "ollama"
    assert result.items == [{"dialogue": "hi"}]


def test_circuit_opens_then_recovers_after_cooldown():
    now = [0.0]
    gateway = ProviderGateway(
        failure_threshold=2, cooldown_seconds=10, clock=lambda: now[0]
    )
    request = gateway.request("x", provider="ollama")
    error = ProviderError("ollama", "unavailable", retryable=True)
    gateway.record_failure(error)
    assert gateway.health("ollama") == Health.DEGRADED
    gateway.record_failure(error)
    assert not gateway.can_attempt("ollama")
    now[0] = 10
    assert gateway.can_attempt("ollama")


def test_fallback_decision_is_explicit():
    gateway = ProviderGateway(preferred="ollama", fallback="opencode")
    request = gateway.request("x", provider="ollama")
    decision = gateway.fallback_decision(
        request, ProviderError("ollama", "parse_failed")
    )
    assert decision.should_fallback is True
    assert decision.provider == "opencode"
    assert decision.reason == "ollama:parse_failed"


def test_execute_retries_with_jitter_and_returns_typed_result():
    gateway = ProviderGateway(
        max_retries=2, base_retry_seconds=0, jitter=lambda: 0
    )
    calls = []

    def invoke(request):
        calls.append(request.provider)
        if len(calls) < 2:
            raise ValueError("temporary")
        return [{"dialogue": "ok"}]

    result = gateway.execute(gateway.request("x"), invoke)
    assert result.items == [{"dialogue": "ok"}]
    assert len(calls) == 2
