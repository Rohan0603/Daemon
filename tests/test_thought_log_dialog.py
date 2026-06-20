import pytest
from unittest.mock import patch, MagicMock


def test_dialog_creates_with_correct_title(app):
    from src.thought_log_dialog import ThoughtLogDialog
    dialog = ThoughtLogDialog()
    assert "Brain Scan" in dialog.windowTitle()
    assert "Internal Monologue" in dialog.windowTitle()


def test_dialog_shows_no_thoughts_message_when_no_log(app, tmp_path):
    from src.thought_log_dialog import ThoughtLogDialog
    log_path = tmp_path / "nonexistent" / ".daemon_thoughts.log"
    with patch("src.thought_log_dialog.THOUGHTS_LOG_PATH", log_path):
        dialog = ThoughtLogDialog()
        dialog._update_log()
        assert "No thoughts" in dialog._text_edit.toPlainText()


def test_dialog_displays_log_content(app, tmp_path):
    from src.thought_log_dialog import ThoughtLogDialog
    log_path = tmp_path / ".daemon_thoughts.log"
    log_path.write_text("[2026-06-11 10:00:00] [idle] Thought: I am a teapot\n", encoding="utf-8")
    with patch("src.thought_log_dialog.THOUGHTS_LOG_PATH", log_path):
        dialog = ThoughtLogDialog()
        dialog._update_log()
        assert "I am a teapot" in dialog._text_edit.toPlainText()


def test_dialog_auto_scrolls_to_bottom(app, tmp_path):
    from src.thought_log_dialog import ThoughtLogDialog
    log_path = tmp_path / ".daemon_thoughts.log"
    log_path.write_text("line1\nline2\nline3\n", encoding="utf-8")
    with patch("src.thought_log_dialog.THOUGHTS_LOG_PATH", log_path):
        dialog = ThoughtLogDialog()
        dialog._update_log()
        scrollbar = dialog._text_edit.verticalScrollBar()
        assert scrollbar.value() == scrollbar.maximum()


def test_dialog_update_timer_active(app):
    from src.thought_log_dialog import ThoughtLogDialog
    dialog = ThoughtLogDialog()
    assert dialog._update_timer.isActive()
    assert dialog._update_timer.interval() == 1000
