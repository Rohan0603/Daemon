from __future__ import annotations
import json
import logging
import os
from pathlib import Path
from typing import TYPE_CHECKING
from src.constants import MEMORY_PATH

logger = logging.getLogger(__name__)


if TYPE_CHECKING:
    from src.write_coalescer import WriteCoalescer


_MAX_FACTS = 50


class Memory:
    def __init__(self, path: str | None = None,
                 coalescer: "WriteCoalescer | None" = None) -> None:
        self._path = path or MEMORY_PATH
        self._facts: dict[str, str] = {}
        self._coalescer = coalescer
        self._load()

    def remember(
        self,
        key: str,
        value: str,
        coalescer: "WriteCoalescer | None" = None,
    ) -> None:
        self._facts[key.strip()] = value.strip()
        if len(self._facts) > _MAX_FACTS:
            oldest = sorted(self._facts.keys())[: len(self._facts) - _MAX_FACTS]
            for k in oldest:
                del self._facts[k]
        effective = coalescer if coalescer is not None else self._coalescer
        if effective is not None:
            effective.mark_dirty("memory")
        else:
            self._save()

    def recall(self, key: str) -> str | None:
        return self._facts.get(key)

    def forget(self, key: str, coalescer: "WriteCoalescer | None" = None) -> bool:
        result = self._facts.pop(key, None) is not None
        if result:
            effective = coalescer if coalescer is not None else self._coalescer
            if effective is not None:
                effective.mark_dirty("memory")
            else:
                self._save()
        return result

    def get_all(self) -> dict[str, str]:
        return dict(self._facts)

    def get_context_block(self, max_facts: int | None = None) -> str:
        if not self._facts:
            return ""
        items = list(self._facts.items())
        if max_facts is not None:
            if max_facts <= 0:
                return ""
            items = items[-max_facts:]
        lines = ["## What Daemon remembers about you:"]
        for k, v in items:
            lines.append(f"- {k}: {v}")
        return "\n".join(lines)

    def save(self) -> None:
        self._save()

    def _save(self) -> None:
        tmp = self._path + ".tmp"
        try:
            bak_path = self._path + ".bak"
            if os.path.exists(self._path):
                try:
                    os.replace(self._path, bak_path)
                except OSError:
                    pass
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump({"facts": self._facts}, f)
            os.replace(tmp, self._path)
        except Exception as e:
            logger.warning("Memory save failed for %s: %s", self._path, e)

    def _load(self) -> None:
        try:
            data = json.loads(Path(self._path).read_text(encoding="utf-8"))
            self._facts = data.get("facts", {})
        except Exception:
            logger.warning("Memory load failed for %s: %s — trying .bak", self._path, self._path)
            try:
                bak_path = self._path + ".bak"
                data = json.loads(Path(bak_path).read_text(encoding="utf-8"))
                self._facts = data.get("facts", {})
                logger.info("Memory loaded from backup (%d facts)", len(self._facts))
            except Exception as e2:
                logger.warning("Memory backup load also failed for %s: %s", self._path, e2)
                self._facts = {}
