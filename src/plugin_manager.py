"""PluginManager — plugin discovery, loading, and lifecycle.

Scans the `plugins/` directory for Python modules that export a
`register(registry)` function and calls it with the active PluginRegistry.

Discovery strategies:
  1. Directory scanning — plugins/<name>.py
  2. (Future) Entry points — via pyproject.toml [project.entry-points."daemon.plugins"]
"""

from __future__ import annotations

import importlib
import importlib.util
import logging
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from src.plugin_registry import PluginRegistry

logger = logging.getLogger(__name__)

# Default plugin directory relative to project root
_DEFAULT_PLUGIN_DIR = "plugins"


def _find_project_root() -> Path:
    """Find the project root (the daemon.py directory)."""
    # Walk up from the current file until we find daemon.py
    here = Path(__file__).resolve().parent  # src/
    for ancestor in [here, here.parent, here.parent.parent]:
        if (ancestor / "daemon.py").exists():
            return ancestor
    # Fallback: use CWD
    return Path.cwd()


class PluginManager:
    """Discovers, loads, and manages plugins.

    Usage::

        registry = PluginRegistry()
        manager = PluginManager(registry)
        manager.discover()
        manager.load_all()
        for info in manager.loaded_plugins:
            print(info)
    """

    def __init__(
        self,
        registry: PluginRegistry,
        plugin_dir: Optional[str] = None,
    ) -> None:
        self._registry = registry
        self._plugin_dir = Path(plugin_dir or _DEFAULT_PLUGIN_DIR)
        if not self._plugin_dir.is_absolute():
            self._plugin_dir = _find_project_root() / self._plugin_dir

        self._discovered: list[Path] = []
        self._loaded: list[PluginInfo] = []

    # ── Public API ────────────────────────────────────────────────────

    @property
    def loaded_plugins(self) -> list[PluginInfo]:
        """Info about successfully loaded plugins."""
        return list(self._loaded)

    def discover(self) -> list[Path]:
        """Scan the plugin directory for importable Python files.

        Returns list of discovered file paths.
        """
        self._discovered.clear()
        if not self._plugin_dir.is_dir():
            logger.info("Plugin directory %s does not exist; skipping discovery", self._plugin_dir)
            return []

        for entry in sorted(self._plugin_dir.iterdir()):
            if entry.suffix == ".py" and entry.stem != "__init__":
                # Skip files starting with _
                if entry.stem.startswith("_"):
                    continue
                self._discovered.append(entry)

        logger.info("Discovered %d plugin(s) in %s", len(self._discovered), self._plugin_dir)
        for d in self._discovered:
            logger.debug("  - %s", d.name)
        return self._discovered

    def load_all(self) -> list[PluginInfo]:
        """Load all discovered plugins.

        Returns list of PluginInfo for successfully loaded plugins.
        """
        self._loaded.clear()
        for path in self._discovered:
            info = self._load_plugin(path)
            if info is not None:
                self._loaded.append(info)
        logger.info(
            "Loaded %d / %d plugin(s)",
            len(self._loaded),
            len(self._discovered),
        )
        return self._loaded

    def load_plugin(self, module_name: str) -> Optional[PluginInfo]:
        """Load a single plugin by module name (without .py suffix).

        Useful for testing or selective loading.
        """
        path = self._plugin_dir / f"{module_name}.py"
        if not path.exists():
            logger.warning("Plugin %s not found at %s", module_name, path)
            return None
        return self._load_plugin(path)

    # ── Internal ──────────────────────────────────────────────────────

    def _load_plugin(self, path: Path) -> Optional[PluginInfo]:
        """Import and register a single plugin module.

        Returns PluginInfo on success, None on failure.
        """
        module_name = f"plugins.{path.stem}"

        # Remove any cached version
        if module_name in sys.modules:
            del sys.modules[module_name]

        try:
            spec = importlib.util.spec_from_file_location(module_name, path)
            if spec is None or spec.loader is None:
                logger.warning("Could not create spec for %s", path)
                return None

            module = importlib.util.module_from_spec(spec)
            sys.modules[module_name] = module
            spec.loader.exec_module(module)

            # Validate: must have register()
            if not hasattr(module, "register") or not callable(module.register):
                logger.warning(
                    "Plugin %s has no callable register() function; skipping",
                    path.name,
                )
                del sys.modules[module_name]
                return None

            # Get metadata (optional)
            meta = getattr(module, "metadata", {})
            name = meta.get("name", path.stem)
            version = meta.get("version", "0.1")
            description = meta.get("description", "")

            # Register
            module.register(self._registry)

            info = PluginInfo(
                name=name,
                module_name=module_name,
                version=version,
                description=description,
                path=str(path),
            )
            logger.info("Loaded plugin: %s v%s (%s)", name, version, path.name)
            return info

        except Exception as e:
            logger.exception("Failed to load plugin %s: %s", path.name, e)
            if module_name in sys.modules:
                del sys.modules[module_name]
            return None


@dataclass
class PluginInfo:
    """Metadata about a loaded plugin."""
    name: str
    module_name: str
    version: str
    description: str
    path: str
