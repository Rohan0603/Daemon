"""Create a vector sidecar from legacy memory and diary JSON stores."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from src.memory.embedding_engine import EmbeddingEngine


def load_records(memory_path: Path, diary_path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    memory = json.loads(memory_path.read_text(encoding="utf-8")) if memory_path.exists() else {}
    facts = memory.get("facts", memory) if isinstance(memory, dict) else {}
    for key, value in facts.items():
        records.append({"id": f"memory:{key}", "source": "memory", "key": key, "content": str(value)})
    diary = json.loads(diary_path.read_text(encoding="utf-8")) if diary_path.exists() else {}
    entries = diary.get("entries", diary) if isinstance(diary, dict) else diary
    for index, entry in enumerate(entries if isinstance(entries, list) else []):
        content = entry.get("content", entry.get("text", "")) if isinstance(entry, dict) else str(entry)
        if content:
            records.append({"id": f"diary:{index}", "source": "diary", "content": str(content)})
    return records


def migrate(memory_path: Path, diary_path: Path, output_path: Path, *, dry_run: bool = False) -> int:
    engine = EmbeddingEngine()
    records = load_records(memory_path, diary_path)
    vectors = [{**record, "embedding": engine.embed(record["content"])} for record in records]
    if not dry_run:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps({"version": 1, "records": vectors}, indent=2), encoding="utf-8")
    return len(vectors)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--memory", type=Path, required=True)
    parser.add_argument("--diary", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    count = migrate(args.memory, args.diary, args.output, dry_run=args.dry_run)
    print(f"{'Would migrate' if args.dry_run else 'Migrated'} {count} records")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
