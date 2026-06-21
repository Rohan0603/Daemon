import time
import pytest
from src.action_layer import ActionLayer, ActiveAction


def test_trigger_adds_to_stack():
    layer = ActionLayer()
    layer.trigger("float", 2000)
    assert len(layer.get_active()) == 1
    assert layer.get_active()[0].name == "float"


def test_tick_removes_expired_action():
    layer = ActionLayer()
    layer.trigger("shake", 500)
    layer.tick(600)
    assert len(layer.get_active()) == 0


def test_tick_keeps_unexpired_action():
    layer = ActionLayer()
    layer.trigger("grow", 1200)
    layer.tick(400)
    assert len(layer.get_active()) == 1


def test_multiple_actions_stack():
    layer = ActionLayer()
    layer.trigger("float", 2000)
    layer.trigger("rainbow", 2000)
    assert len(layer.get_active()) == 2


def test_stack_cap_evicts_oldest():
    from src.constants import ACTION_STACK_MAX
    layer = ActionLayer()
    names = [f"action_{i}" for i in range(ACTION_STACK_MAX + 1)]
    for i, n in enumerate(names):
        layer.trigger(n, 9999)
    active_names = [a.name for a in layer.get_active()]
    assert len(active_names) == ACTION_STACK_MAX
    assert names[0] not in active_names   # oldest evicted


def test_clear_empties_stack():
    layer = ActionLayer()
    layer.trigger("float", 2000)
    layer.trigger("rainbow", 2000)
    layer.clear()
    assert len(layer.get_active()) == 0


def test_get_active_returns_snapshot():
    layer = ActionLayer()
    layer.trigger("nod", 800)
    snapshot = layer.get_active()
    layer.clear()
    assert len(snapshot) == 1  # snapshot is independent


def test_params_stored_on_action():
    layer = ActionLayer()
    layer.trigger("teleport", 1100, params={"target_x": 100, "target_y": 200})
    assert layer.get_active()[0].params["target_x"] == 100


def test_elapsed_ms_advances_with_tick():
    layer = ActionLayer()
    layer.trigger("grow", 1200)
    layer.tick(300)
    assert layer.get_active()[0].elapsed_ms == pytest.approx(300, abs=1)
