from pathlib import Path
from typing import Final

STORAGE_DIR = Path(__file__).parent.parent / 'data'
STORAGE_DIR.mkdir(exist_ok=True)

CONFIG_PATH = STORAGE_DIR / 'daemon_config.json'
MAX_RESPONSE_CHARS = 4000
BUBBLE_QUEUE_TTL_SECS = 25
HISTORY_MAX_ENTRIES = 200
DEBUG: bool = False
FIRESTORE_SYNC_INTERVAL_SEC = 300
BUBBLE_MAX_CHARS = 400

# Bubble + typewriter config (overridden at runtime by daemon_config.json)
BUBBLE_MS_PER_CHAR = 50
BUBBLE_MIN_DURATION_MS = 2000
BUBBLE_MAX_DURATION_MS = 30000
DIALOGUE_MAX_LENGTH = 150
TYPEWRITER_TICK_MS = 30
TYPEWRITER_CHARS_PER_TICK = 8

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

# ── Action Layer ─────────────────────────────────────────────────────────────
ACTION_STACK_MAX              = 5
ACTION_FLOAT_DURATION_MS      = 2000
ACTION_JUMP_DURATION_MS       = 800
ACTION_GROW_DURATION_MS       = 1200
ACTION_SHRINK_DURATION_MS     = 1200
ACTION_PULSE_DURATION_MS      = 600
ACTION_GLITCH_DURATION_MS     = 1500
ACTION_RAINBOW_DURATION_MS    = 2000
ACTION_FLIP_DURATION_MS       = 400
ACTION_TELEPORT_DURATION_MS   = 1100
ACTION_WAVE_DURATION_MS       = 1500
ACTION_WOBBLE_DURATION_MS     = 1000
ACTION_DASH_DURATION_MS       = 500
ACTION_MELT_DURATION_MS       = 1500
ACTION_INFLATE_DURATION_MS    = 1500
ACTION_NOD_DURATION_MS        = 800
ACTION_HEADSHAKE_DURATION_MS  = 800
ACTION_TREMBLE_DURATION_MS    = 1000
ACTION_STRUT_DURATION_MS      = 2000
ACTION_FLAIL_DURATION_MS      = 1200
ACTION_VANISH_DURATION_MS     = 1300
# Migrated from FSM
ACTION_SHAKE_DURATION_MS      = 500
ACTION_BOUNCE_DURATION_MS     = 600
ACTION_SPIN_DURATION_MS       = 1500
ACTION_LOOK_AWAY_DURATION_MS  = 4000

# Timing constants (config-driven fallback)
BEHAVIOR_TICK_MS = 1000
FSM_TICK_MS = 33

