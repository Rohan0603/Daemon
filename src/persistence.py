from __future__ import annotations
import json
import logging
import os
from pathlib import Path
from src.constants import STATE_PATH

logger = logging.getLogger(__name__)

_DEFAULTS = {"mood": 0, "interactions": 0, "runtime_seconds": 0, "skill_greeted": False, "first_run_done": False}
_DEFAULT_PATH = STATE_PATH


def save_state(state: dict, path: str = _DEFAULT_PATH) -> None:
    try:
        tmp = path + ".tmp"
        if os.path.exists(path):
            try:
                os.replace(path, path + ".bak")
            except OSError:
                pass
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(state, f)
        os.replace(tmp, path)
    except Exception as e:
        logger.warning("Failed to save state to %s: %s", path, e)


def load_state(path: str = _DEFAULT_PATH) -> dict:
    if not os.path.exists(path):
        logger.debug("State file not found at %s, using defaults", path)
        return dict(_DEFAULTS)
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        result = dict(_DEFAULTS)
        result.update({k: data[k] for k in _DEFAULTS if k in data})
        return result
    except Exception as e:
        logger.warning("Failed to load state from %s: %s", path, e)
        return dict(_DEFAULTS)
