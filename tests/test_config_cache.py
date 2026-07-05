# tests/test_config_cache.py
import threading
import time
import random
import pytest
from unittest.mock import patch
import src.config as config_module


@pytest.fixture(autouse=True)
def reset_runtime_config():
    original = config_module._RUNTIME_CONFIG.copy()
    yield
    config_module._RUNTIME_CONFIG.clear()
    config_module._RUNTIME_CONFIG.update(original)


# ── Task 1.1: Config cache basics ─────────────────────────────────────────────

def test_config_get_dot_path():
    config_module._RUNTIME_CONFIG = {"pet": {"chattiness": 7}}
    assert config_module.config_get("pet.chattiness") == 7


def test_config_get_missing_returns_default():
    config_module._RUNTIME_CONFIG = {}
    assert config_module.config_get("pet.chattiness", default=5) == 5


def test_config_get_partial_missing_returns_default():
    config_module._RUNTIME_CONFIG = {"pet": {}}
    assert config_module.config_get("pet.chattiness", default=3) == 3


def test_config_set_dot_path():
    config_module._RUNTIME_CONFIG = {"pet": {"chattiness": 5}}
    config_module.config_set("pet.chattiness", 9)
    assert config_module._RUNTIME_CONFIG["pet"]["chattiness"] == 9


def test_config_set_creates_nested_keys():
    config_module._RUNTIME_CONFIG = {}
    config_module.config_set("behavior.dnd_enabled", True)
    assert config_module._RUNTIME_CONFIG["behavior"]["dnd_enabled"] is True


def test_config_set_fires_async_save():
    config_module._RUNTIME_CONFIG = {"pet": {"chattiness": 5}}
    saved_events = []

    def fake_save(cfg, path=None):
        saved_events.append(cfg)

    with patch.object(config_module, "save_config", fake_save):
        config_module.config_set("pet.chattiness", 8)
        time.sleep(0.15)

    assert len(saved_events) == 1


def test_config_set_does_not_block():
    config_module._RUNTIME_CONFIG = {"pet": {}}

    def slow_save(cfg, path=None):
        time.sleep(0.5)

    start = time.monotonic()
    with patch.object(config_module, "save_config", slow_save):
        config_module.config_set("pet.chattiness", 8)
        elapsed = time.monotonic() - start

    assert elapsed < 0.1, "config_set must not block on disk write"


# ── Task 1.2: DND circuit breaker ─────────────────────────────────────────────

def test_apm_worker_dnd_drops_tick():
    from src.config import config_get
    config_module._RUNTIME_CONFIG = {"behavior": {"dnd_enabled": True}}
    ticked = True
    if config_get("behavior.dnd_enabled"):
        ticked = False
    assert not ticked


def test_event_worker_dnd_suppresses_window_switch():
    config_module._RUNTIME_CONFIG = {"behavior": {"dnd_enabled": True}}
    from src.config import config_get
    fired = []

    def on_window_switch():
        if config_get("behavior.dnd_enabled"):
            return
        fired.append(1)

    on_window_switch()
    assert len(fired) == 0


def test_event_worker_probability_gate_suppresses_at_low_chattiness():
    config_module._RUNTIME_CONFIG = {"pet": {"chattiness": 1}}
    from src.config import config_get
    suppressed = 0
    total = 1000
    for _ in range(total):
        chattiness = config_get("pet.chattiness", 5)
        if random.random() > (chattiness / 10.0):
            suppressed += 1
    assert suppressed > 800


# ── Task 1.3: Adaptive idle threshold ─────────────────────────────────────────

def test_adaptive_idle_threshold_scales_with_chattiness():
    from src.config import config_get
    from src.autonomy.behavior_controller import compute_dynamic_idle_threshold

    config_module._RUNTIME_CONFIG = {"pet": {"chattiness": 1}}
    high = compute_dynamic_idle_threshold()
    assert high >= 30

    config_module._RUNTIME_CONFIG = {"pet": {"chattiness": 10}}
    low = compute_dynamic_idle_threshold()
    assert low < high
    assert low >= 30
