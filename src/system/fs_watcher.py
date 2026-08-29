"""Debounced workspace file watching for code-context cache invalidation."""
from __future__ import annotations

import logging
import threading
from pathlib import Path
from collections.abc import Callable, Iterable
from typing import Any

logger = logging.getLogger(__name__)

_DEFAULT_EXTENSIONS = frozenset({
    ".c", ".cpp", ".cs", ".go", ".java", ".js", ".jsx", ".py", ".rs",
    ".ts", ".tsx", ".vue",
})
_DEFAULT_IGNORED_DIRS = frozenset({
    ".git", ".hg", ".mypy_cache", ".pytest_cache", ".venv", "__pycache__",
    "node_modules", "venv",
})


class WorkspaceFileWatcher:
    """Watch workspace source files and coalesce save bursts into callbacks.

    The watcher owns the watchdog observer and all debounce timers. Consumers
    receive normalized absolute paths only after the debounce interval elapses.
    """

    def __init__(
        self,
        workspace: str | Path,
        on_changed: Callable[[Path], Any],
        *,
        debounce_ms: int = 500,
        extensions: Iterable[str] = _DEFAULT_EXTENSIONS,
        ignored_dirs: Iterable[str] = _DEFAULT_IGNORED_DIRS,
        observer_factory: Callable[[], Any] | None = None,
        timer_factory: Callable[..., threading.Timer] = threading.Timer,
    ) -> None:
        if not callable(on_changed):
            raise TypeError("on_changed must be callable")
        if debounce_ms < 0:
            raise ValueError("debounce_ms must be non-negative")
        root = Path(workspace).expanduser().resolve()
        if not root.exists():
            raise ValueError(f"Workspace does not exist: {root}")
        if not root.is_dir():
            raise ValueError(f"Workspace is not a directory: {root}")

        normalized_extensions = {
            ext.casefold() if ext.startswith(".") else f".{ext.casefold()}"
            for ext in extensions
        }
        self.workspace = root
        self.on_changed = on_changed
        self.debounce_seconds = debounce_ms / 1000
        self.extensions = frozenset(normalized_extensions)
        self.ignored_dirs = frozenset(str(name).casefold() for name in ignored_dirs)
        self._observer_factory = observer_factory
        self._timer_factory = timer_factory
        self._observer: Any | None = None
        self._timers: dict[Path, threading.Timer] = {}
        self._lock = threading.RLock()
        self._running = False

    @property
    def running(self) -> bool:
        return self._running

    def start(self) -> None:
        """Start recursive workspace observation."""
        with self._lock:
            if self._running:
                return
            observer = self._create_observer()
            observer.schedule(self._handler(), str(self.workspace), recursive=True)
            observer.start()
            self._observer = observer
            self._running = True

    def stop(self, *, flush: bool = False) -> None:
        """Stop observation and cancel pending timers, optionally flushing them."""
        with self._lock:
            observer = self._observer
            self._observer = None
            self._running = False
            timers = list(self._timers.items())
            self._timers.clear()
        for _, timer in timers:
            timer.cancel()
        if flush:
            for path, _ in timers:
                self._deliver(path)
        if observer is not None:
            observer.stop()
            observer.join()

    def handle_path(self, path: str | Path) -> None:
        """Queue a path for debounced delivery; safe for watchdog callbacks."""
        normalized = Path(path).expanduser().resolve()
        if not self._is_relevant(normalized):
            return
        with self._lock:
            old_timer = self._timers.pop(normalized, None)
            if old_timer is not None:
                old_timer.cancel()
            timer = self._timer_factory(
                self.debounce_seconds, self._deliver, args=(normalized,)
            )
            self._timers[normalized] = timer
            timer.daemon = True
            timer.start()

    def _deliver(self, path: Path) -> None:
        with self._lock:
            self._timers.pop(path, None)
            if not self._is_relevant(path):
                return
        try:
            self.on_changed(path)
        except Exception:
            logger.exception("Workspace change callback failed for %s", path)

    def _is_relevant(self, path: Path) -> bool:
        try:
            relative = path.relative_to(self.workspace)
        except ValueError:
            return False
        if not path.is_file() or path.suffix.casefold() not in self.extensions:
            return False
        return not any(part.casefold() in self.ignored_dirs for part in relative.parts)

    def _create_observer(self) -> Any:
        if self._observer_factory is not None:
            return self._observer_factory()
        try:
            from watchdog.observers import Observer
        except ImportError as exc:
            raise RuntimeError(
                "watchdog is required for WorkspaceFileWatcher"
            ) from exc
        return Observer()

    def _handler(self) -> Any:
        from watchdog.events import FileSystemEventHandler

        watcher = self

        class Handler(FileSystemEventHandler):
            def on_created(self, event: Any) -> None:
                if not event.is_directory:
                    watcher.handle_path(event.src_path)

            def on_modified(self, event: Any) -> None:
                if not event.is_directory:
                    watcher.handle_path(event.src_path)

            def on_moved(self, event: Any) -> None:
                if not event.is_directory:
                    watcher.handle_path(event.dest_path)

        return Handler()
