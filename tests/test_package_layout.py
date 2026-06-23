# tests/test_package_layout.py
"""AST-based boundary guards that enforce canonical package import directions.

Canonical dependency flow:
  system  ←  llm  ←  autonomy  ←  ui
          ↕
     (no cross imports between llm and system)

Allowed:
  - system → (nothing from src)
  - llm → {system}
  - autonomy → {llm, system}
  - ui → {autonomy, llm, system}

Forbidden:
  - system → ui
  - system → llm
  - llm → ui
  - autonomy → ui
  - ui → nothing (no restriction outward)
"""

from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path("src")


def _collect_imports(path: Path) -> list[str]:
    """Return all module-level import paths in a Python file."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    found: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            found.append(node.module)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                found.append(alias.name)
    return found


def _pkg(name: str) -> str:
    """Shortcut for 'src.<name>'."""
    return f"src.{name}"


def test_system_does_not_import_ui() -> None:
    for path in sorted((ROOT / "system").glob("*.py")):
        imports = _collect_imports(path)
        # system/__init__.py re-exports, so it may reference src.ui for the wrapper
        # but actual implementation files should not
        violations = [i for i in imports if i.startswith(_pkg("ui"))]
        assert not violations, f"{path} imports ui: {violations}"


def test_system_does_not_import_llm() -> None:
    for path in sorted((ROOT / "system").glob("*.py")):
        imports = _collect_imports(path)
        violations = [i for i in imports if i.startswith(_pkg("llm"))]
        assert not violations, f"{path} imports llm: {violations}"


def test_llm_does_not_import_ui() -> None:
    for path in sorted((ROOT / "llm").glob("*.py")):
        imports = _collect_imports(path)
        violations = [i for i in imports if i.startswith(_pkg("ui"))]
        assert not violations, f"{path} imports ui: {violations}"


def test_autonomy_does_not_import_ui() -> None:
    for path in sorted((ROOT / "autonomy").glob("*.py")):
        imports = _collect_imports(path)
        violations = [i for i in imports if i.startswith(_pkg("ui"))]
        assert not violations, f"{path} imports ui: {violations}"
