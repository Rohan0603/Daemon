"""Tests for IDE visual rendering — teal tint and blinking cursor overlay."""

import pytest
from unittest.mock import MagicMock, patch
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QPainter, QColor
import sys

# Ensure QApplication exists for Qt types
_app = QApplication.instance() or QApplication(sys.argv)

from src.ui.pet_renderer import RenderContext, PetRenderer
from src.pet_fsm import PetState


def _make_ctx(**kwargs) -> RenderContext:
    defaults = dict(
        state=PetState.IDLE,
        pet_x=100,
        pet_y=100,
        anim_tick=0,
        hyper_color_index=0,
        fall_velocity=0.0,
        wander_direction=1,
        bubble_text="",
        drag_velocity_x=0.0,
        scale=1.0,
    )
    defaults.update(kwargs)
    return RenderContext(**defaults)


def test_render_context_has_ide_mode_field():
    ctx = _make_ctx(ide_mode=False)
    assert ctx.ide_mode is False


def test_render_context_ide_mode_default_false():
    ctx = _make_ctx()
    assert ctx.ide_mode is False


def test_body_color_is_teal_in_ide_mode():
    renderer = PetRenderer()
    ctx = _make_ctx(ide_mode=True)
    color = renderer._body_color(ctx)
    # Dark turquoise: #00CED1 = RGB(0, 206, 209)
    assert color.red() == 0
    assert color.green() == 206
    assert color.blue() == 209


def test_body_color_is_not_teal_normally():
    renderer = PetRenderer()
    ctx = _make_ctx(ide_mode=False)
    color = renderer._body_color(ctx)
    # Normal color should NOT be teal
    assert not (color.red() == 0 and color.green() == 206 and color.blue() == 209)


def test_draw_ide_cursor_collects_no_error_in_visible_phase():
    """Verify _draw_ide_cursor doesn't crash during the visible blink phase."""
    renderer = PetRenderer()
    ctx = _make_ctx(ide_mode=True, anim_tick=0)
    painter = MagicMock(spec=QPainter)
    try:
        renderer._draw_ide_cursor(painter, ctx)
    except Exception as e:
        pytest.fail(f"_draw_ide_cursor raised an exception: {e}")


def test_draw_ide_cursor_silent_in_hidden_phase():
    """Verify _draw_ide_cursor returns early during the hidden blink phase."""
    renderer = PetRenderer()
    ctx = _make_ctx(ide_mode=True, anim_tick=15)  # half_cycle=15, so 15//15 % 2 == 1 → hidden
    painter = MagicMock(spec=QPainter)
    renderer._draw_ide_cursor(painter, ctx)
    # No save/restore calls means it returned early
    assert painter.save.call_count == 0


def test_draw_ide_cursor_returns_early_when_not_ide_mode():
    renderer = PetRenderer()
    ctx = _make_ctx(ide_mode=False)
    painter = MagicMock(spec=QPainter)
    # Should not crash even though there's no IDE mode
    try:
        renderer._draw_ide_cursor(painter, ctx)
    except Exception as e:
        pytest.fail(f"raised: {e}")
