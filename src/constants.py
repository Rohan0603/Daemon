from pathlib import Path
from typing import Final

STORAGE_DIR = Path(__file__).parent.parent / 'data'
STORAGE_DIR.mkdir(exist_ok=True)

CONFIG_PATH = STORAGE_DIR / 'daemon_config.json'
MAX_RESPONSE_CHARS = 4000
DEBUG: bool = False

SETTINGS_SCALE_MIN: float = 0.5
SETTINGS_SCALE_MAX: float = 2.0
SETTINGS_OPACITY_MIN: float = 0.3
SETTINGS_OPACITY_MAX: float = 1.0
SETTINGS_SPEED_MIN: float = 0.5
SETTINGS_SPEED_MAX: float = 2.0
CHATTINESS_DEFAULT = 1.0
CHATTINESS_MIN = 0.5
CHATTINESS_MAX = 3.0

STRUCTURED_SCHEMA = {'type': 'array', 'items': {'type': 'object',
    'properties': {'type': {'type': 'string', 'enum': ['typing_reaction',
    'observation', 'intel_roast', 'idle_thought']}, 'thought': {'type':
    'string', 'maxLength': 200}, 'dialogue': {'type': 'string', 'maxLength':
    150}, 'priority': {'type': 'integer', 'minimum': 1, 'maximum': 5},
    'context_hash': {'type': 'string'}, 'brain_update': {'type': 'object',
    'description': 'Optional dict to update user memory facts.',
    'additionalProperties': {'type': 'array', 'items': {'type': 'string'}}}
    }, 'required': ['thought', 'dialogue', 'type'], 'additionalProperties':
    False}, 'minItems': 1, 'maxItems': 5}

def __getattr__(name):
    from src.config import load_config, flatten_config
    cfg = load_config()
    flat = flatten_config(cfg)
    if name in flat:
        # Also set it on the module so we don't load_config() repeatedly for the same key
        val = flat[name]
        globals()[name] = val
        return val
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
