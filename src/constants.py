# src/constants.py
from pathlib import Path
from typing import Final

STORAGE_DIR = Path(__file__).parent.parent / "data"
STORAGE_DIR.mkdir(exist_ok=True)

# --- Daemon Configuration ---
APM_HYPER_THRESHOLD        = 150
APM_WINDOW_SECONDS         = 60
SPEECH_BUBBLE_DURATION_MS  = 8000
OPENCODE_TIMEOUT_SECONDS   = 90
OPENCODE_SCRIPT_PATH       = str(Path(__file__).parent.parent / "opencode-query.ps1")
OPENCODE_SERVER_URL        = "http://127.0.0.1:4096"
OPENCODE_API_MODEL_PROVIDER = "opencode-go"
OPENCODE_API_MODEL_ID       = "deepseek-v4-flash"
OPENCODE_API_TIMEOUT_SEC    = 180
WANDER_SPEED_PX            = 2
HYPER_SPEED_MULTIPLIER     = 3.0
GRAVITY_ACCELERATION       = 0.5
GROUND_PADDING_PX          = 0
CHASE_ENTER_RADIUS_PX      = 120
CHASE_EXIT_RADIUS_PX       = 250
SLEEP_IDLE_SECONDS         = 300
BOREDOM_TIMEOUT_SEC        = 30
AUTONOMOUS_QUERY_INTERVAL_SEC = 20
ACTIVE_CHAT_INTERVAL_SEC   = 25
JOKE_INTERVAL_SEC          = 60
AUTONOMOUS_COOLDOWN_SEC    = 45   # minimum gap between ANY autonomous queries

# --- Behavioral Settings (Phase 37) ---
BEHAVIOR_TICK_MS = 1000              # Master Tick interval (default 1 second)
CHATTINESS_DEFAULT = 1.0             # Default chattiness multiplier
CHATTINESS_MIN = 0.5                 # Slider minimum (quiet)
CHATTINESS_MAX = 3.0                 # Slider maximum (hyperactive)

WRITE_COALESCE_FLUSH_SEC   = 8      # batched local-storage flush interval
SHAKE_DURATION_MS          = 2000
BOUNCE_DURATION_MS         = 3000
SPIN_DURATION_MS           = 1500
LOOK_AWAY_DURATION_MS      = 4000
FSM_TICK_MS                = 33
CLICK_THROUGH_POLL_MS      = 50

# --- Engagement / silence detection ---
SILENCE_THRESHOLD = 5          # consecutive non-engaged outputs before backoff
ENGAGED_THRESHOLD = 2          # consecutive engaged outputs to restore normal rate
BASE_INTERVAL_SEC = 15         # normal autonomous interval
MAX_BACKOFF_SEC = 120          # max interval when silenced (2 min)
BACKOFF_MULTIPLIER = 1.5       # exponential backoff multiplier per silence event

# --- Rendering ---
PET_WIDTH                  = 40
PET_HEIGHT                 = 50
PET_CORNER_RADIUS          = 10

BODY_BLUE                  = "#5B8DEF"
BODY_DARK                  = "#2C3E6B"
EYE_WHITE                  = "#FFFFFF"
EYE_PUPIL                  = "#1A1A2E"
ACCENT_YELLOW              = "#F5C542"
ACCENT_RED                 = "#E74C3C"
BUBBLE_BG                  = "#FFFDE7"
BUBBLE_BORDER              = "#BDBDBD"
HYPER_FLASH                = ("#FF6B6B", "#FFE66D", "#6BCB77", "#4D96FF")
BUBBLE_TEXT_COLOR          = "#1A1A2E"

BUBBLE_MAX_WIDTH           = 220
BUBBLE_PADDING             = 8
BUBBLE_CORNER_RADIUS       = 8
BUBBLE_FONT_SIZE           = 11

INPUT_WIDTH                = 260
INPUT_HEIGHT               = 28
INPUT_Y_OFFSET             = 10

MEMORY_PATH = str(STORAGE_DIR / ".daemon_memory.json")
HISTORY_PATH = str(STORAGE_DIR / ".daemon_history.json")
DIARY_PATH = str(STORAGE_DIR / ".daemon_diary.json")
STATE_PATH = str(STORAGE_DIR / ".daemon_state.json")
CONFIG_PATH = STORAGE_DIR / ".daemon_config.json"
RESPONSE_CACHE_PATH = str(STORAGE_DIR / ".daemon_response_cache.json")

_PERSONA_HINT = "You are Daemon, the user's desktop pet. Continue in character. Keep responses brief."

# Pool configuration
THOUGHT_POOL_SIZE = 20
THOUGHT_POOL_THRESHOLD = 5
THOUGHT_POOL_REFILL_COUNT = 5

POOL_DECAY_INTERVAL_SEC = 120       # priority -1 every 2 min
POOL_REFILL_PERIODIC_SEC = 600      # periodic refill every 10 min

BUBBLE_QUEUE_MAX_SIZE = 10
SHORT_BUBBLE_DURATION_MS = 4000
SHORT_BUBBLE_CHAR_LIMIT = 40

DEBUG: bool = False
THOUGHTS_LOG_PATH = STORAGE_DIR / ".daemon_thoughts.log"

TTS_ENABLED: bool = True
TTS_BASE_RATE: int = 120
TTS_VOICE_ID: str = "en-US-GuyNeural"
TTS_PITCH_FACTOR: float = 1.15

SQUASH_STRETCH_DURATION_MS: int = 400
MIN_CHASE_DURATION_MS: int = 500

PERIMETER_FALL_CHANCE: float = 0.2

SETTINGS_SCALE_MIN: float = 0.5
SETTINGS_SCALE_MAX: float = 2.0
SETTINGS_OPACITY_MIN: float = 0.3
SETTINGS_OPACITY_MAX: float = 1.0
SETTINGS_SPEED_MIN: float = 0.5
SETTINGS_SPEED_MAX: float = 2.0

# --- Firebase Admin SDK ---
FIREBASE_CREDENTIALS_PATH: Path = STORAGE_DIR / "firebase-credentials.json"
FIREBASE_PROJECT_ID: str = "daemon-87f81"

# --- Firebase Auth REST API (user identity) ---
FIREBASE_API_KEY: str = "AIzaSyAX0n85NY4F7WycIYfVwEjfM25hSkDt33U"
AUTH_TOKEN_PATH: Path = STORAGE_DIR / ".daemon_auth.json"

RISKY_KEYWORDS: Final[dict[str, list[dict]]] = {
    "--force": [
        {"dialogue": "Holy crap, --force?! You're gonna break everything!", "action": "shake"},
        {"dialogue": "Aw geez, force-pushing? That's how repos die, man!", "action": "shake"},
    ],
    "rm -rf": [
        {"dialogue": "RM — RF?! ARE YOU INSANE?!", "action": "shake"},
        {"dialogue": "Oh man, oh man, recursive delete? I-I can't watch!", "action": "look_away"},
    ],
    "drop table": [
        {"dialogue": "DROP TABLE?! You're gonna delete data, man! Holy crap!", "action": "hyper"},
        {"dialogue": "Aw geez, not the— the database, man! That's where things live!", "action": "shake"},
    ],
    "TODO": [
        {"dialogue": "A TODO? That's not a plan, that's a graveyard for dreams.", "action": "idle"},
        {"dialogue": "Oh look, another TODO. You know that's never getting done, right?", "action": "look_away"},
    ],
    "FIXME": [
        {"dialogue": "FIXME? You wrote the bug AND left a note. That's rich.", "action": "shake"},
        {"dialogue": "Aw geez, you're leaving FIXMEs for Future You? Poor guy...", "action": "devastated"},
    ],
    "git push": [
        {"dialogue": "Pushing without testing? You're a gambler, huh?", "action": "idle"},
        {"dialogue": "Straight to prod? No PR? No review? You maniac!", "action": "shake"},
    ],
}

# MCP Server
MCP_HOST = "127.0.0.1"
MCP_PORT = 4097

# Structured Output Schema — only thought + dialogue are required
STRUCTURED_SCHEMA = {
    "type": "array",
    "items": {
        "type": "object",
        "properties": {
            "thought":      {"type": "string", "maxLength": 200},
            "dialogue":     {"type": "string", "maxLength": 150},
            "brain_update": {
                "type": "object",
                "description": "Optional dict to update user memory facts.",
                "additionalProperties": {
                    "type": "array",
                    "items": {"type": "string"}
                }
            }
        },
        "required": ["thought", "dialogue"],
        "additionalProperties": False,
    },
    "minItems": 1,
    "maxItems": 5,
}

