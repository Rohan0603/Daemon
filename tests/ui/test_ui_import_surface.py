# tests/ui/test_import_surface.py
"""Verify that src.ui re-exports everything and backward-compat wrappers match."""

from __future__ import annotations

from src.ui import (
    DataViewerDialog,
    LoginDialog,
    PetContextMenu,
    PetRenderer,
    PetWindow,
    SettingsDialog,
    ThoughtLogDialog,
)
from src.context_menu import PetContextMenu as LegacyPetContextMenu
from src.data_viewer_dialog import DataViewerDialog as LegacyDataViewerDialog
from src.login_dialog import LoginDialog as LegacyLoginDialog
from src.pet_renderer import PetRenderer as LegacyPetRenderer
from src.pet_window import PetWindow as LegacyPetWindow
from src.settings_dialog import SettingsDialog as LegacySettingsDialog
from src.thought_log_dialog import ThoughtLogDialog as LegacyThoughtLogDialog


def test_ui_package_exports_current_widgets():
    assert PetContextMenu is LegacyPetContextMenu
    assert DataViewerDialog is LegacyDataViewerDialog
    assert LoginDialog is LegacyLoginDialog
    assert PetRenderer is LegacyPetRenderer
    assert PetWindow is LegacyPetWindow
    assert SettingsDialog is LegacySettingsDialog
    assert ThoughtLogDialog is LegacyThoughtLogDialog
