import json
import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)

class BrainStore:
    _instances = {}
    
    @classmethod
    def get_instance(cls, path: str = None):
        if path is None:
            from src.constants import BRAIN_PATH, pet_id
            path = BRAIN_PATH.format(pet_id=pet_id) if "{pet_id}" in BRAIN_PATH else BRAIN_PATH
        if path not in cls._instances:
            cls._instances[path] = cls(path)
        return cls._instances[path]

    def __init__(self, path: str):
        self._path = path
        self.version = 2
        self.facts = {}
        self.diary = []
        self.diary_synced = 0
        self.history = []
        self._load()

    def _migrate_v1_data(self):
        project_root = Path(__file__).parent.parent
        old_mem = project_root / "data" / ".daemon_memory.json"
        old_diary = project_root / "data" / ".daemon_diary.json"
        old_history = project_root / "data" / ".daemon_history.json"
        
        migrated = False
        if old_mem.exists():
            try:
                self.facts = json.loads(old_mem.read_text(encoding="utf-8")).get("facts", {})
                migrated = True
            except Exception:
                pass
        if old_diary.exists():
            try:
                diary_data = json.loads(old_diary.read_text(encoding="utf-8"))
                self.diary = diary_data.get("entries", [])
                self.diary_synced = diary_data.get("synced", 0)
                migrated = True
            except Exception:
                pass
        if old_history.exists():
            try:
                self.history = json.loads(old_history.read_text(encoding="utf-8")).get("entries", [])
                migrated = True
            except Exception:
                pass
                
        if migrated:
            logger.info("Migrated V1 data to %s", self._path)
            self.save()

    def _load(self):
        main_path = Path(self._path)
        bak_path = Path(self._path + ".bak")

        if not main_path.exists() and not bak_path.exists():
            self._migrate_v1_data()
            return

        data = None
        if main_path.exists():
            try:
                data = json.loads(main_path.read_text(encoding="utf-8"))
            except Exception:
                pass
                
        if data is None and bak_path.exists():
            try:
                data = json.loads(bak_path.read_text(encoding="utf-8"))
            except Exception:
                pass

        if data:
            self.facts = data.get("facts", {})
            self.diary = data.get("diary", [])
            self.diary_synced = data.get("diary_synced", 0)
            self.history = data.get("history", [])

    def save(self):
        data = {
            "version": self.version,
            "facts": self.facts,
            "diary": self.diary,
            "diary_synced": self.diary_synced,
            "history": self.history
        }
        tmp = self._path + ".tmp"
        try:
            bak_path = self._path + ".bak"
            if os.path.exists(self._path):
                try:
                    os.replace(self._path, bak_path)
                except OSError:
                    pass
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(data, f)
            os.replace(tmp, self._path)
        except Exception as e:
            logger.warning("BrainStore save failed: %s", e)
