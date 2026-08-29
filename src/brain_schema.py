from __future__ import annotations
import json
import logging
from pathlib import Path

VALID_FIELD_TYPES = frozenset({"str", "int", "float", "list", "dict", "bool"})
_DEFAULT_SCHEMA_PATH = str(Path(__file__).parent.parent / "data" / "brain_schema.json")
logger = logging.getLogger(__name__)

def load_brain_schema(schema_path: str = _DEFAULT_SCHEMA_PATH) -> dict:
    path = Path(schema_path)
    if not path.exists():
        raise FileNotFoundError(f"Brain schema file not found: {schema_path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    fields = data.get("fields", {})
    for fname, spec in fields.items():
        if spec.get("type") not in VALID_FIELD_TYPES:
            raise ValueError(f"Invalid type {spec.get('type')!r} for field {fname!r}")
    logger.debug("Loaded brain schema: %d fields from %s", len(fields), path)
    return fields

BRAIN_SCHEMA: dict = load_brain_schema()

USER_LEVEL_KEYS = {
    "user_name", "user_profession", "user_habits",
    "user_preferences", "user_long_term_goals", "user_imposed_rules",
    "user_partner_name", "user_engineer_name", "user_nickname",
    "user_current_project", "user_focus_apps", "user_distraction_apps",
}

_TYPO_CORRECTIONS = {}

def apply_brain_update(update: dict, schema: dict | None = None) -> dict:
    if schema is None:
        schema = BRAIN_SCHEMA
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

DEFAULT_BRAIN: dict = {k: v["default"] for k, v in BRAIN_SCHEMA.items()}

def _validate_brain_consistency() -> None:
    for key in DEFAULT_BRAIN:
        assert key in BRAIN_SCHEMA, f"Key {key!r} in DEFAULT_BRAIN but missing from BRAIN_SCHEMA"
    for key in BRAIN_SCHEMA:
        assert key in DEFAULT_BRAIN, f"Key {key!r} in BRAIN_SCHEMA but missing from DEFAULT_BRAIN"
        t = BRAIN_SCHEMA[key]["type"]
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
