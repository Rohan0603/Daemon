import pytest
from PyQt6.QtCore import QObject, QThread
from src.fsm_bridge import FSMActionBridge


def test_constructor():
    bridge = FSMActionBridge()
    assert isinstance(bridge, QObject)
    assert bridge._last_action is None


def test_emit_request_sends_action(qtbot):
    bridge = FSMActionBridge()
    received = []

    def slot(action, tx, ty):
        received.append((action, tx, ty))

    bridge.request.connect(slot)
    bridge.emit_request("shake")
    assert len(received) == 1
    assert received[0] == ("shake", None, None)


def test_emit_request_with_coords(qtbot):
    bridge = FSMActionBridge()
    received = []

    def slot(action, tx, ty):
        received.append((action, tx, ty))

    bridge.request.connect(slot)
    bridge.emit_request("chase", target_x=500, target_y=300)
    assert len(received) == 1
    assert received[0] == ("chase", 500, 300)


def test_emit_request_from_background_thread(qtbot):
    """Signal must be delivered on main thread via QueuedConnection."""
    bridge = FSMActionBridge()
    main_thread_id = int(QThread.currentThread().currentThreadId())
    received = []

    def check_thread(action, tx, ty):
        received.append(int(QThread.currentThread().currentThreadId()))

    bridge.request.connect(check_thread)
    bridge.emit_request("spin")
    assert len(received) == 1
    assert received[0] == main_thread_id


def test_noop_when_bridge_not_connected():
    """emit_request should not crash when nothing is connected."""
    bridge = FSMActionBridge()
    bridge.emit_request("idle")  # should not raise


def test_emit_toast(qtbot):
    bridge = FSMActionBridge()
    received = []

    def slot(title, message):
        received.append((title, message))

    bridge.toast_request.connect(slot)
    bridge.emit_toast("System Alert", "Your APM is 0")
    assert len(received) == 1
    assert received[0] == ("System Alert", "Your APM is 0")
