"""Provider-neutral LLM request lifecycle coordination."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass(frozen=True)
class LLMRequest:
    """Minimal request shape shared by user, autonomous, and refill callers."""

    prompt: str
    autonomous: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)


class LLMOrchestrator:
    """Own worker lifecycle while leaving rendering and policy to the UI."""

    def __init__(self, worker_factory: Callable[[LLMRequest], Any]) -> None:
        self._worker_factory = worker_factory
        self._worker: Any | None = None

    @property
    def active(self) -> bool:
        worker = self._worker
        return worker is not None and bool(worker.isRunning())

    @property
    def worker(self) -> Any | None:
        return self._worker

    def submit(
        self,
        request: LLMRequest,
        *,
        preempt: bool = False,
        response_ready: Callable[[list[dict]], None] | None = None,
        error_occurred: Callable[[str], None] | None = None,
        partial_response: Callable[[str], None] | None = None,
        session_created: Callable[[str], None] | None = None,
        brain_update_ready: Callable[[dict], None] | None = None,
    ) -> Any | None:
        """Start request, optionally aborting current worker for user input."""
        if self.active:
            if not preempt:
                return None
            self.cancel()
        worker = self._worker_factory(request)
        self._connect(worker, "response_ready", response_ready)
        self._connect(worker, "error_occurred", error_occurred)
        self._connect(worker, "partial_response", partial_response)
        self._connect(worker, "session_created", session_created)
        self._connect(worker, "brain_update_ready", brain_update_ready)
        worker.start()
        self._worker = worker
        return worker

    def cancel(self) -> None:
        """Request cancellation without blocking the UI thread."""
        worker = self._worker
        if worker is None:
            return
        abort = getattr(worker, "abort", None)
        if callable(abort):
            abort()
        quit_worker = getattr(worker, "quit", None)
        if callable(quit_worker):
            quit_worker()
        self._worker = None

    def clear(self, worker: Any) -> None:
        """Forget completed worker when its response/error has been handled."""
        if self._worker is worker:
            self._worker = None

    @staticmethod
    def _connect(worker: Any, signal_name: str, callback: Callable | None) -> None:
        if callback is None:
            return
        signal = getattr(worker, signal_name, None)
        if signal is not None:
            signal.connect(callback)
