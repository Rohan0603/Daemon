# tests/test_settings_dialog.py
from __future__ import annotations
import sys
from unittest.mock import patch, MagicMock
from PyQt6.QtWidgets import QApplication
from src.settings_dialog import SettingsDialog


def app():
    _app = QApplication.instance()
    if _app is None:
        _app = QApplication(sys.argv)
    return _app


class TestSettingsDialog:
    def test_initial_values_from_args(self):
        _ = app()
        dialog = SettingsDialog(
            pet_scale=1.5, pet_opacity=0.7, pet_speed=0.8, tts_enabled=False,
            tts_rate=180, tts_volume=0.5,
        )
        assert dialog._size_slider.value() == 150
        assert dialog._opacity_slider.value() == 70
        assert dialog._speed_slider.value() == 80
        assert dialog._rate_slider.value() == 180
        assert dialog._volume_slider.value() == 50

    def test_initial_values_defaults(self):
        _ = app()
        dialog = SettingsDialog()
        assert dialog._size_slider.value() == 100
        assert dialog._opacity_slider.value() == 85
        assert dialog._speed_slider.value() == 100
        assert dialog._voice_checkbox.isChecked() is True
        assert dialog._rate_slider.value() == 220

    def test_slider_ranges(self):
        _ = app()
        dialog = SettingsDialog()
        assert dialog._size_slider.minimum() == 50
        assert dialog._size_slider.maximum() == 200
        assert dialog._rate_slider.minimum() == 50
        assert dialog._rate_slider.maximum() == 400

    def test_get_values_after_change(self):
        _ = app()
        dialog = SettingsDialog()
        dialog._size_slider.setValue(120)
        dialog._opacity_slider.setValue(50)
        dialog._speed_slider.setValue(150)
        dialog._voice_checkbox.setChecked(False)
        dialog._rate_slider.setValue(200)
        dialog._volume_slider.setValue(80)
        values = dialog.get_values()
        assert values["pet_scale"] == 1.2
        assert values["pet_opacity"] == 0.5
        assert values["pet_speed"] == 1.5
        assert values["tts_enabled"] is False
        assert values["tts_rate"] == 200
        assert values["tts_volume"] == 0.8

    def test_value_changed_signal_emits_on_slider_change(self):
        _ = app()
        dialog = SettingsDialog()
        emitted = []
        dialog.value_changed.connect(lambda: emitted.append(None))
        dialog._size_slider.setValue(130)
        assert len(emitted) >= 1
