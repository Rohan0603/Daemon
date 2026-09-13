from __future__ import annotations
import json
import logging
from pathlib import Path

VALID_FIELD_TYPES = frozenset({"str", "int", "float", "list", "dict", "bool"})
_DEFAULT_SCHEMA_PATH = str(Path(__file__).parent.parent / "data" / "brain_schema.json")
logger = logging.getLogger(__name__)

# Tier classification mapping for v2 hierarchical brain schema
_TIER_MAP = {
    "identity": {
        "user_name", "user_profession", "pet_name", "pet_personality",
        "pet_role", "pet_origin", "pet_appearance", "pet_system_awareness",
    },
    "profile": {
        "user_habits", "user_preferences", "user_long_term_goals",
        "user_imposed_rules", "user_partner_name", "user_engineer_name",
        "user_nickname", "user_current_project", "user_focus_apps",
        "user_distraction_apps",
    },
    "personality": {
        "pet_likes", "pet_quirks", "pet_habits", "pet_fears",
        "pet_catchphrases", "pet_nsfw_level", "pet_pomodoro_config",
    },
    "relationship": {
        "mission_directive", "mission_goals", "pet_affinity_score",
        "pet_current_mood", "progression_flags",
    },
    "intel": {
        "intel_archive", "intel_insider_knowledge", "screen_time_warn_sec",
    },
}

_TIER_ORDER = ["identity", "profile", "personality", "relationship", "intel"]

def _classify_tier(key: str) -> str | None:
    """Return the tier name for a given brain field key, or None if unknown."""
    for tier, keys in _TIER_MAP.items():
        if key in keys:
            return tier
    return None

def load_brain_schema(schema_path: str = _DEFAULT_SCHEMA_PATH) -> dict:
    """Load brain schema from JSON and return tiered structure.

    Returns:
        dict with "fields" (tier -> {field: spec}) and "tier_order" (list of tier names)
    """
    path = Path(schema_path)
    if not path.exists():
        raise FileNotFoundError(f"Brain schema file not found: {schema_path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    flat_fields = data.get("fields", {})
    for fname, spec in flat_fields.items():
        if spec.get("type") not in VALID_FIELD_TYPES:
            raise ValueError(f"Invalid type {spec.get('type')!r} for field {fname!r}")
        # Ensure required fields exist
        if "indexed" not in spec:
            spec["indexed"] = False
        if "default" not in spec:
            spec["default"] = "" if spec.get("type") == "str" else ([] if spec.get("type") == "list" else ({} if spec.get("type") == "dict" else 0))

    # Convert flat fields to tiered structure
    tiered_fields: dict[str, dict] = {tier: {} for tier in _TIER_ORDER}
    for fname, spec in flat_fields.items():
        tier = _classify_tier(fname)
        if tier is not None:
            tiered_fields[tier][fname] = spec
        else:
            # Unknown fields go to identity as fallback
            tiered_fields["identity"][fname] = spec

    logger.debug("Loaded brain schema: %d fields from %s", len(flat_fields), path)
    return {"fields": tiered_fields, "tier_order": _TIER_ORDER}

# Load schema and extract flat BRAIN_SCHEMA for backward compatibility
_loaded_schema = load_brain_schema()
BRAIN_SCHEMA: dict = _loaded_schema["fields"]  # Tiered structure: {tier: {field: spec}}

# Also provide flat view for apply_brain_update
_FLAT_BRAIN_SCHEMA: dict = {}
for tier_specs in BRAIN_SCHEMA.values():
    _FLAT_BRAIN_SCHEMA.update(tier_specs)

USER_LEVEL_KEYS = {
    "user_name", "user_profession", "user_habits",
    "user_preferences", "user_long_term_goals", "user_imposed_rules",
    "user_partner_name", "user_engineer_name", "user_nickname",
    "user_current_project", "user_focus_apps", "user_distraction_apps",
}

_TYPO_CORRECTIONS = {}

def apply_brain_update(update: dict, schema: dict | None = None) -> dict:
    if schema is None:
        schema = _FLAT_BRAIN_SCHEMA
    applied = {}
    skipped = 0
    for key, value in update.items():
        corrected_key = _TYPO_CORRECTIONS.get(key, key)
        field_spec = schema.get(corrected_key)
        if field_spec is None:
            skipped += 1
            continue
        if field_spec.get("locked"):
            skipped += 1
            continue

        t = field_spec.get("type")

        if t == "list":
            if not isinstance(value, list):
                skipped += 1
                continue
            value = list(dict.fromkeys(value))
            applied[corrected_key] = value

        elif t in ("dict", "map"):
            if not isinstance(value, dict):
                skipped += 1
                continue
            applied[corrected_key] = value

        elif t == "int":
            if not isinstance(value, int):
                skipped += 1
                continue
            applied[corrected_key] = value

        elif t == "float":
            if not isinstance(value, (int, float)):
                skipped += 1
                continue
            applied[corrected_key] = float(value)

        elif t == "bool":
            if not isinstance(value, bool):
                skipped += 1
                continue
            applied[corrected_key] = value

        else:
            if not isinstance(value, str):
                skipped += 1
                continue
            applied[corrected_key] = value

    logger.debug("Brain update processed: received=%d applied=%d skipped=%d",
                 len(update), len(applied), skipped)
    return applied

DEFAULT_BRAIN: dict = {k: v["default"] for k, v in _FLAT_BRAIN_SCHEMA.items()}

def _validate_brain_consistency() -> None:
    for key in DEFAULT_BRAIN:
        assert key in _FLAT_BRAIN_SCHEMA, f"Key {key!r} in DEFAULT_BRAIN but missing from BRAIN_SCHEMA"
    for key in _FLAT_BRAIN_SCHEMA:
        assert key in DEFAULT_BRAIN, f"Key {key!r} in BRAIN_SCHEMA but missing from DEFAULT_BRAIN"
        t = _FLAT_BRAIN_SCHEMA[key]["type"]
        if t == "list":
            assert isinstance(DEFAULT_BRAIN[key], list), \
                f"Key {key!r}: BRAIN_SCHEMA type {t!r} but DEFAULT_BRAIN value is {type(DEFAULT_BRAIN[key]).__name__}"
        elif t in ("dict", "map"):
            assert isinstance(DEFAULT_BRAIN[key], dict), \
                f"Key {key!r}: BRAIN_SCHEMA type {t!r} but DEFAULT_BRAIN value is {type(DEFAULT_BRAIN[key]).__name__}"
        elif t == "int":
            assert isinstance(DEFAULT_BRAIN[key], int), \
                f"Key {key!r}: BRAIN_SCHEMA type {t!r} but DEFAULT_BRAIN value is {type(DEFAULT_BRAIN[key]).__name__}"
        elif t == "float":
            assert isinstance(DEFAULT_BRAIN[key], (int, float)), \
                f"Key {key!r}: BRAIN_SCHEMA type {t!r} but DEFAULT_BRAIN value is {type(DEFAULT_BRAIN[key]).__name__}"
        elif t == "bool":
            assert isinstance(DEFAULT_BRAIN[key], bool), \
                f"Key {key!r}: BRAIN_SCHEMA type {t!r} but DEFAULT_BRAIN value is {type(DEFAULT_BRAIN[key]).__name__}"
        else:
            assert isinstance(DEFAULT_BRAIN[key], str), \
                f"Key {key!r}: BRAIN_SCHEMA type {t!r} but DEFAULT_BRAIN value is {type(DEFAULT_BRAIN[key]).__name__}"

_validate_brain_consistency()
