"""Tests for ClickThroughManager — float coords, shutdown guard."""
import pytest
from unittest.mock import MagicMock, patch


def test_get_click_geometry_with_float_coords(safe_pet_window):
    """_get_click_geometry must not crash when _pet_x/_pet_y are floats."""
    from PyQt6.QtCore import QRect

    safe_pet_window._pet_x = 123.7   # floats from physics engine
    safe_pet_window._pet_y = 456.2
    safe_pet_window._scale = 1.0
    safe_pet_window._pet_scale = 1.0
    safe_pet_window._bubble_text = ""
    # Must not raise TypeError
    rect = safe_pet_window._get_click_geometry()
    assert isinstance(rect, QRect)


def test_poll_exits_immediately_after_stop():
    """_poll must return without toggling after stop() is called."""
    from src.click_through import ClickThroughManager

    get_geom = MagicMock(return_value=None)
    mgr = ClickThroughManager.__new__(ClickThroughManager)
    mgr._hwnd = 0
    mgr._get_geometry = get_geom
    mgr._transparent = False
    mgr._last_toggle_time = 0.0
    mgr._prev_cursor_over = None
    mgr._stopped = False
    mgr._timer = MagicMock()

    mgr.stop()
    assert mgr._stopped is True

    # _poll after stop must not call get_geometry
    get_geom.reset_mock()
    mgr._poll()
    get_geom.assert_not_called()
