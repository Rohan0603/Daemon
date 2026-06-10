"""Utility to view and seed Firestore core_brain document.

Usage:
  py seed_brain.py                    # show current brain + diff from defaults (uses saved auth)
  py seed_brain.py --uid <uid>        # target a specific user
  py seed_brain.py --pet-id <id>      # target a specific pet (default: kenny)
  py seed_brain.py --merge file.json  # merge JSON fields into core_brain
  py seed_brain.py --seed-defaults    # merge all _DEFAULT_BRAIN fields into core_brain
  py seed_brain.py --dry-run          # preview without writing
"""
import json
import logging
import sys
from pathlib import Path

from src.brain_schema import (
    BRAIN_SCHEMA as _BRAIN_SCHEMA,
    DEFAULT_BRAIN as _DEFAULT_BRAIN,
    apply_brain_update,
)
from src.firebase_auth import FirebaseAuth
from src.firebase_crud import FirebaseCRUD
from src.constants import FIREBASE_PROJECT_ID

logger = logging.getLogger(__name__)


def _show_diff(current: dict, defaults: dict) -> None:
    print("\n=== FIELDS IN DEFAULTS MISSING FROM CURRENT ===")
    for key in defaults:
        if key not in current:
            print(f"  [+] {key} ({len(defaults[key])} items)" if isinstance(defaults[key], list) else f"  [+] {key}")
        elif isinstance(defaults[key], list) and isinstance(current.get(key), list):
            extra = [v for v in defaults[key] if v not in current[key]]
            if extra:
                print(f"  [~] {key}: {len(extra)} new item(s)")
                for e in extra:
                    print(f"       -> {e}")

    print("\n=== FIELDS IN CURRENT NOT IN DEFAULTS ===")
    for key in current:
        if key not in defaults:
            print(f"  [-] {key} (custom field, will NOT be removed)")


def main() -> None:
    args = sys.argv[1:]
    dry_run = "--dry-run" in args
    do_seed = "--seed-defaults" in args
    uid = None
    pet_id = "kenny"
    do_merge = None
    for i, a in enumerate(args):
        if a == "--merge" and i + 1 < len(args):
            do_merge = args[i + 1]
        if a == "--uid" and i + 1 < len(args):
            uid = args[i + 1]
        if a == "--pet-id" and i + 1 < len(args):
            pet_id = args[i + 1]

    # Read auth token from saved session
    auth = FirebaseAuth()
    if not auth.load():
        print("[seed_brain] No saved auth session found. Log in via the app first.", file=sys.stderr)
        print("[seed_brain] Alternatively, set FIREBASE_API_KEY and FIREBASE_PROJECT_ID in constants.py", file=sys.stderr)
        sys.exit(1)

    token = auth.get_valid_token()
    if not token:
        print("[seed_brain] Auth token expired and refresh failed. Log in again.", file=sys.stderr)
        sys.exit(1)

    uid = uid or auth.uid
    if not uid:
        print("[seed_brain] No UID available. Use --uid <uid> or log in first.", file=sys.stderr)
        sys.exit(1)

    print(f"[seed_brain] Using uid={uid}")

    def token_provider() -> str:
        return auth.get_valid_token() or ""

    crud = FirebaseCRUD(token_provider=token_provider, project_id=FIREBASE_PROJECT_ID)
    if not crud.available:
        print("[seed_brain] Cannot connect to Firestore.", file=sys.stderr)
        sys.exit(1)

    collection = f"users/{uid}/pets"
    current = crud.get(collection, pet_id) or {}
    print(f"\n=== CURRENT core_brain ({len(current)} fields) ===")
    print(json.dumps(current, indent=2, ensure_ascii=False))

    _show_diff(current, _DEFAULT_BRAIN)

    if do_merge:
        merge_path = Path(do_merge)
        if not merge_path.exists():
            print(f"[seed_brain] File not found: {do_merge}", file=sys.stderr)
            sys.exit(1)
        merge_data = json.loads(merge_path.read_text(encoding="utf-8"))
        print(f"\n=== MERGING from {do_merge} ===")
        print(json.dumps(merge_data, indent=2, ensure_ascii=False))
        current.update(merge_data)

    if do_seed:
        print(f"\n=== SEEDING DEFAULT BRAIN ({len(_DEFAULT_BRAIN)} fields) ===")
        for key in _DEFAULT_BRAIN:
            if key not in current:
                current[key] = _DEFAULT_BRAIN[key]
                print(f"  + {key}")
            elif isinstance(_DEFAULT_BRAIN[key], list) and isinstance(current[key], list):
                merged = list(dict.fromkeys(current[key] + _DEFAULT_BRAIN[key]))
                if len(merged) > len(current[key]):
                    current[key] = merged
                    print(f"  ~ {key}: {len(merged)} items")

    if dry_run:
        print("\n=== DRY RUN — no changes written ===")
        sys.exit(0)

    if do_merge or do_seed:
        crud.set(collection, pet_id, current, merge=True)
        print(f"\n=== UPDATED core_brain ({len(current)} fields) ===")
        print(json.dumps(crud.get(collection, pet_id), indent=2, ensure_ascii=False))
        print("[seed_brain] Done.")
    else:
        print("\n[seed_brain] No changes requested. Use --seed-defaults or --merge <file>.")


if __name__ == "__main__":
    main()
