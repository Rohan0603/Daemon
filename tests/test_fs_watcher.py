import threading
import time
from pathlib import Path

import pytest

from src.system.fs_watcher import WorkspaceFileWatcher


class FakeObserver:
    def __init__(self):
        self.scheduled = []
        self.started = False
        self.stopped = False
        self.joined = False

    def schedule(self, handler, path, recursive):
        self.scheduled.append((handler, path, recursive))

    def start(self):
        self.started = True

    def stop(self):
        self.stopped = True

    def join(self):
        self.joined = True


def test_watcher_coalesces_source_changes(tmp_path):
    source = tmp_path / "main.py"
    source.write_text("print(1)", encoding="utf-8")
    changed = []
    watcher = WorkspaceFileWatcher(
        tmp_path,
        changed.append,
        debounce_ms=20,
        observer_factory=FakeObserver,
    )

    watcher.handle_path(source)
    watcher.handle_path(source)
    time.sleep(0.08)

    assert changed == [source.resolve()]


def test_watcher_filters_extensions_and_ignored_directories(tmp_path):
    source = tmp_path / "main.py"
    source.write_text("", encoding="utf-8")
    text_file = tmp_path / "notes.txt"
    text_file.write_text("", encoding="utf-8")
    ignored = tmp_path / ".git" / "config.py"
    ignored.parent.mkdir()
    ignored.write_text("", encoding="utf-8")
    changed = []
    watcher = WorkspaceFileWatcher(tmp_path, changed.append, debounce_ms=0)

    watcher.handle_path(source)
    watcher.handle_path(text_file)
    watcher.handle_path(ignored)
    time.sleep(0.03)

    assert changed == [source.resolve()]


def test_watcher_handles_created_modified_and_moved_events(tmp_path):
    source = tmp_path / "new.py"
    source.write_text("", encoding="utf-8")
    changed = []
    observer = FakeObserver()
    watcher = WorkspaceFileWatcher(
        tmp_path,
        changed.append,
        debounce_ms=20,
        observer_factory=lambda: observer,
    )
    watcher.start()
    handler = observer.scheduled[0][0]

    class Event:
        is_directory = False
        src_path = str(source)
        dest_path = str(source)

    handler.on_created(Event())
    handler.on_modified(Event())
    handler.on_moved(Event())
    time.sleep(0.08)
    watcher.stop()

    assert changed == [source.resolve()]
    assert observer.started and observer.stopped and observer.joined
    assert observer.scheduled[0][1:] == (str(tmp_path.resolve()), True)


def test_watcher_validates_workspace_and_callback(tmp_path):
    with pytest.raises(ValueError, match="does not exist"):
        WorkspaceFileWatcher(tmp_path / "missing", lambda _: None)
    with pytest.raises(TypeError, match="callable"):
        WorkspaceFileWatcher(tmp_path, None)
    with pytest.raises(ValueError, match="debounce_ms"):
        WorkspaceFileWatcher(tmp_path, lambda _: None, debounce_ms=-1)
