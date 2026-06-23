"""Tests for ClickThroughManager — float coords, shutdown guard."""
import pytest
from unittest.mock import MagicMock, patch


def test_get_click_geometry_with_float_coords():
    """_get_click_geometry must not crash when _pet_x/_pet_y are floats."""
    from src.pet_window import PetWindow
    from PyQt6.QtCore import QRect, QPoint
    import sys
    # Create minimal QApplication if needed
    from PyQt6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication(sys.argv)
    
    # Use proper init with mocked dependencies
    with patch("src.ui.pet_window.ClickThroughManager"), \
         patch("PyQt6.QtWidgets.QSystemTrayIcon"), \
         patch("src.ui.pet_window.APMWorker"), \
         patch("src.ui.pet_window.MCPServer"), \
         patch("src.ui.pet_window.BehaviorController"):
        win = PetWindow(opencode_enabled=False)
        win._pet_x = 123.7   # floats from physics engine
        win._pet_y = 456.2
        win._scale = 1.0
        win._pet_scale = 1.0
        win._bubble_text = ""
        # Must not raise TypeError
        rect = win._get_click_geometry()
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
