"""Tests for TypingBuffer.

TypingBuffer captures global keystrokes via pynput and maintains
a rolling buffer of the most recent typing.
"""
import sys
import pytest
from collections import deque
from pynput.keyboard import Key, KeyCode
from PyQt6.QtWidgets import QApplication


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance() or QApplication(sys.argv)
    return app


def _make_buffer():
    from src.typing_buffer import TypingBuffer
    return TypingBuffer()


class TestTypingBuffer:

    def test_constructor_creates_deque_with_maxlen_500(self, qapp):
        buf = _make_buffer()
        assert isinstance(buf._buffer, deque)
        assert buf._buffer.maxlen == 500

    def test_printable_char_appends_and_emits_signal(self, qapp):
        buf = _make_buffer()
        emitted = []
        buf.text_updated.connect(lambda: emitted.append(None))
        buf._on_press(KeyCode.from_char('a'))
        buf._on_press(KeyCode.from_char('b'))
        buf._on_press(KeyCode.from_char('c'))
        assert list(buf._buffer) == ['a', 'b', 'c']
        assert len(emitted) == 3

    def test_backspace_pops_last_char_and_emits_signal(self, qapp):
        buf = _make_buffer()
        buf._buffer.append('a')
        buf._buffer.append('b')
        emitted = []
        buf.text_updated.connect(lambda: emitted.append(None))
        buf._on_press(Key.backspace)
        assert list(buf._buffer) == ['a']
        assert len(emitted) == 1

    def test_backspace_on_empty_does_not_error(self, qapp):
        buf = _make_buffer()
        buf._on_press(Key.backspace)
        assert list(buf._buffer) == []

    def test_enter_appends_newline_and_emits_signal(self, qapp):
        buf = _make_buffer()
        emitted = []
        buf.text_updated.connect(lambda: emitted.append(None))
        buf._on_press(KeyCode.from_char('a'))
        buf._on_press(Key.enter)
        buf._on_press(KeyCode.from_char('b'))
        assert list(buf._buffer) == ['a', '\n', 'b']
        assert len(emitted) == 3

    def test_tab_appends_tab_character_and_emits_signal(self, qapp):
        buf = _make_buffer()
        emitted = []
        buf.text_updated.connect(lambda: emitted.append(None))
        buf._on_press(Key.tab)
        assert list(buf._buffer) == ['\t']
        assert len(emitted) == 1

    def test_space_appends_space_and_emits_signal(self, qapp):
        buf = _make_buffer()
        emitted = []
        buf.text_updated.connect(lambda: emitted.append(None))
        buf._on_press(KeyCode.from_char('a'))
        buf._on_press(Key.space)
        buf._on_press(KeyCode.from_char('b'))
        assert list(buf._buffer) == ['a', ' ', 'b']
        assert len(emitted) == 3

    def test_modifier_keys_ignored_and_no_signal(self, qapp):
        buf = _make_buffer()
        emitted = []
        buf.text_updated.connect(lambda: emitted.append(None))
        for key in (Key.ctrl, Key.alt, Key.shift, Key.cmd):
            buf._on_press(key)
        assert list(buf._buffer) == []
        assert len(emitted) == 0

    def test_caps_lock_ignored_and_no_signal(self, qapp):
        buf = _make_buffer()
        emitted = []
        buf.text_updated.connect(lambda: emitted.append(None))
        buf._on_press(Key.caps_lock)
        assert list(buf._buffer) == []
        assert len(emitted) == 0

    def test_other_special_keys_ignored_and_no_signal(self, qapp):
        buf = _make_buffer()
        emitted = []
        buf.text_updated.connect(lambda: emitted.append(None))
        for key in (Key.esc, Key.f1, Key.up, Key.page_up, Key.home):
            buf._on_press(key)
        assert list(buf._buffer) == []
        assert len(emitted) == 0

    def test_get_context_returns_formatted_text(self, qapp):
        buf = _make_buffer()
        buf._on_press(KeyCode.from_char('h'))
        buf._on_press(KeyCode.from_char('i'))
        result = buf.get_context()
        assert result == "Recent Typing:\n  > hi"

    def test_get_context_returns_empty_string(self, qapp):
        buf = _make_buffer()
        result = buf.get_context()
        assert result == ""

    def test_buffer_caps_at_500(self, qapp):
        buf = _make_buffer()
        for _ in range(510):
            buf._on_press(KeyCode.from_char('x'))
        assert len(buf._buffer) == 500

    def test_get_context_truncates(self, qapp):
        buf = _make_buffer()
        for _ in range(100):
            buf._on_press(KeyCode.from_char('x'))
        ctx = buf.get_context(max_chars=10)
        assert ctx.count("x") == 10
        assert "Recent Typing:" in ctx
