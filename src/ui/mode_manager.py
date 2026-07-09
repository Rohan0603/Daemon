from __future__ import annotations
import json
import logging
from enum import Enum
from pathlib import Path
from typing import Callable, Optional

logger = logging.getLogger(__name__)


class PetMode(str, Enum):
    DESKTOP_PET = "desktop_pet"
    CODING_ASSISTANT = "coding_assistant"


class ModeManager:
    """Single source of truth for pet operating mode."""

    def __init__(self, persist_path: Optional[str] = None) -> None:
        self._mode = PetMode.DESKTOP_PET
        self._callbacks: list[Callable[[PetMode, PetMode], None]] = []
        self._persist_path = Path(persist_path) if persist_path else None

    @property
    def current_mode(self) -> PetMode:
        return self._mode

    def is_coding_mode(self) -> bool:
        return self._mode == PetMode.CODING_ASSISTANT

    def is_desktop_pet_mode(self) -> bool:
        return self._mode == PetMode.DESKTOP_PET

    def set_mode(self, mode: PetMode) -> None:
        if mode == self._mode:
            return
        old = self._mode
        self._mode = mode
        logger.info("Pet mode: %s -> %s", old.value, mode.value)
        for cb in list(self._callbacks):
            try:
                cb(old, mode)
            except Exception:
                logger.exception("ModeManager callback raised")

    def toggle(self) -> PetMode:
        new = (PetMode.CODING_ASSISTANT
               if self._mode == PetMode.DESKTOP_PET
               else PetMode.DESKTOP_PET)
        self.set_mode(new)
        return new

    def on_mode_changed(self, callback: Callable[[PetMode, PetMode], None]) -> None:
        self._callbacks.append(callback)

    def save(self) -> None:
        if not self._persist_path:
            return
        try:
            self._persist_path.write_text(
                json.dumps({"mode": self._mode.value}), encoding="utf-8"
            )
        except Exception:
            logger.warning("ModeManager: failed to persist mode")

    def load(self) -> None:
        if not self._persist_path or not self._persist_path.exists():
            return
        try:
            data = json.loads(self._persist_path.read_text(encoding="utf-8"))
            self._mode = PetMode(data.get("mode", PetMode.DESKTOP_PET.value))
        except Exception:
            logger.warning("ModeManager: failed to load mode; using default")
