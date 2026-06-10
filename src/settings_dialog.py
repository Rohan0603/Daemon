# src/settings_dialog.py
from __future__ import annotations
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QSlider,
    QCheckBox, QComboBox, QDialogButtonBox,
)
from PyQt6.QtCore import Qt, pyqtSignal
from src.constants import (
    SETTINGS_SCALE_MIN, SETTINGS_SCALE_MAX,
    SETTINGS_OPACITY_MIN, SETTINGS_OPACITY_MAX,
    SETTINGS_SPEED_MIN, SETTINGS_SPEED_MAX,
    CHATTINESS_DEFAULT, CHATTINESS_MIN, CHATTINESS_MAX,
)


class SettingsDialog(QDialog):
    value_changed = pyqtSignal()

    def __init__(self, pet_scale: float = 1.0, pet_opacity: float = 0.85,
                 pet_speed: float = 1.0, tts_enabled: bool = True,
                 tts_rate: int = 220, tts_volume: float = 1.0,
                 tts_voice_id: str | None = None, chattiness: float = 1.0,
                 parent=None):
        super().__init__(parent)
        self.setWindowTitle("Daemon Settings")
        self.setFixedSize(360, 400)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint)

        layout = QVBoxLayout(self)

        label = QLabel("Pet Appearance")
        label.setStyleSheet("font-weight: bold; color: #5B8DEF;")
        layout.addWidget(label)

        self._size_slider = self._make_slider_row(
            layout, "Size", int(pet_scale * 100),
            int(SETTINGS_SCALE_MIN * 100), int(SETTINGS_SCALE_MAX * 100),
        )
        self._opacity_slider = self._make_slider_row(
            layout, "Opacity", int(pet_opacity * 100),
            int(SETTINGS_OPACITY_MIN * 100), int(SETTINGS_OPACITY_MAX * 100),
        )
        self._speed_slider = self._make_slider_row(
            layout, "Speed", int(pet_speed * 100),
            int(SETTINGS_SPEED_MIN * 100), int(SETTINGS_SPEED_MAX * 100),
        )

        self._chattiness_slider = self._make_chattiness_row(layout, chattiness)

        label2 = QLabel("Voice")
        label2.setStyleSheet("font-weight: bold; color: #5B8DEF;")
        layout.addWidget(label2)

        self._voice_checkbox = QCheckBox("Enable voice responses")
        self._voice_checkbox.setChecked(tts_enabled)
        layout.addWidget(self._voice_checkbox)

        self._rate_slider = self._make_rate_row(layout, tts_rate)
        self._volume_slider = self._make_slider_row(
            layout, "Volume", int(tts_volume * 100), 0, 100,
        )

        voices = self._get_voices()
        voice_row = QHBoxLayout()
        voice_row.addWidget(QLabel("Voice"))
        self._voice_combo = QComboBox()
        selected_idx = 0
        for i, (vid, vname) in enumerate(voices):
            self._voice_combo.addItem(vname, vid)
            if tts_voice_id and vid == tts_voice_id:
                selected_idx = i
        self._voice_combo.setCurrentIndex(selected_idx)
        self._voice_combo.currentIndexChanged.connect(self.value_changed.emit)
        voice_row.addWidget(self._voice_combo)
        layout.addLayout(voice_row)

        layout.addStretch()

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _get_voices(self) -> list[tuple[str, str]]:
        voices = [("en-US-GuyNeural", "Guy (Edge Neural)")]
        try:
            import pyttsx3
            engine = pyttsx3.init()
            for v in engine.getProperty("voices"):
                voices.append((v.id, f"{v.name} (SAPI)"))
        except Exception:
            pass
        return voices

    def _make_rate_row(self, layout, rate):
        row = QHBoxLayout()
        label = QLabel("Rate")
        label.setFixedWidth(50)
        row.addWidget(label)

        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setRange(50, 400)
        slider.setValue(rate)
        slider.valueChanged.connect(self.value_changed.emit)
        row.addWidget(slider)

        value_label = QLabel(f"{rate}")
        value_label.setFixedWidth(40)
        row.addWidget(value_label)

        def update_label(v, lbl=value_label):
            lbl.setText(f"{v}")
        slider.valueChanged.connect(update_label)

        layout.addLayout(row)
        return slider

    def _make_slider_row(self, layout, label_text, value, min_val, max_val):
        row = QHBoxLayout()
        label = QLabel(label_text)
        label.setFixedWidth(50)
        row.addWidget(label)

        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setRange(min_val, max_val)
        slider.setValue(value)
        slider.valueChanged.connect(self.value_changed.emit)
        row.addWidget(slider)

        value_label = QLabel(f"{value}%")
        value_label.setFixedWidth(40)
        row.addWidget(value_label)

        def update_label(v, lbl=value_label):
            lbl.setText(f"{v}%")
        slider.valueChanged.connect(update_label)

        layout.addLayout(row)
        return slider

    def _make_chattiness_row(self, layout, chattiness: float):
        row = QHBoxLayout()
        label = QLabel("Chattiness")
        label.setFixedWidth(50)
        row.addWidget(label)

        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setRange(int(CHATTINESS_MIN * 10), int(CHATTINESS_MAX * 10))
        slider.setValue(int(chattiness * 10))
        slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        slider.setTickInterval(5)
        slider.valueChanged.connect(self.value_changed.emit)
        row.addWidget(slider)

        value_label = QLabel(f"{chattiness:.1f}")
        value_label.setFixedWidth(40)
        row.addWidget(value_label)

        def update_label(v, lbl=value_label):
            lbl.setText(f"{v / 10.0:.1f}")
        slider.valueChanged.connect(update_label)

        layout.addLayout(row)
        return slider

    def get_values(self) -> dict:
        voice_data = self._voice_combo.currentData()
        return {
            "pet_scale": self._size_slider.value() / 100.0,
            "pet_opacity": self._opacity_slider.value() / 100.0,
            "pet_speed_multiplier": self._speed_slider.value() / 100.0,
            "tts_enabled": self._voice_checkbox.isChecked(),
            "tts_rate": self._rate_slider.value(),
            "tts_volume": self._volume_slider.value() / 100.0,
            "tts_voice_id": voice_data if voice_data else None,
            "chattiness": self._chattiness_slider.value() / 10.0,
        }
