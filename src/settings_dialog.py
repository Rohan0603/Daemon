# src/settings_dialog.py
from __future__ import annotations
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QSlider,
    QCheckBox, QComboBox, QDialogButtonBox,
    QGroupBox, QTabWidget, QWidget,
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
                 allow_intrusive_animations: bool = True,
                 allow_system_notifications: bool = False,
                 allow_browser_redirection: bool = False,
                 allow_clipboard_reading: bool = False,
                 allow_mouse_interference: bool = False,
                 allow_screenshot_capture: bool = False,
                 allow_keyboard_injection: bool = False,
                 parent=None):
        super().__init__(parent)
        self.setWindowTitle("Daemon Settings")
        self.setFixedSize(420, 400)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint)

        layout = QVBoxLayout(self)

        self._tabs = QTabWidget()
        layout.addWidget(self._tabs)

        # --- Tab 1: Appearance ---
        tab1 = QWidget()
        tab1_layout = QVBoxLayout(tab1)

        label = QLabel("Pet Appearance")
        label.setStyleSheet("font-weight: bold; color: #5B8DEF;")
        tab1_layout.addWidget(label)

        self._size_slider = self._make_slider_row(
            tab1_layout, "Size", int(pet_scale * 100),
            int(SETTINGS_SCALE_MIN * 100), int(SETTINGS_SCALE_MAX * 100),
        )
        self._opacity_slider = self._make_slider_row(
            tab1_layout, "Opacity", int(pet_opacity * 100),
            int(SETTINGS_OPACITY_MIN * 100), int(SETTINGS_OPACITY_MAX * 100),
        )
        self._speed_slider = self._make_slider_row(
            tab1_layout, "Speed", int(pet_speed * 100),
            int(SETTINGS_SPEED_MIN * 100), int(SETTINGS_SPEED_MAX * 100),
        )

        self._chattiness_slider = self._make_chattiness_row(tab1_layout, chattiness)

        tab1_layout.addStretch()
        self._tabs.addTab(tab1, "Appearance")

        # --- Tab 2: Voice ---
        tab2 = QWidget()
        tab2_layout = QVBoxLayout(tab2)

        label2 = QLabel("Voice")
        label2.setStyleSheet("font-weight: bold; color: #5B8DEF;")
        tab2_layout.addWidget(label2)

        self._voice_checkbox = QCheckBox("Enable voice responses")
        self._voice_checkbox.setChecked(tts_enabled)
        tab2_layout.addWidget(self._voice_checkbox)

        self._rate_slider = self._make_rate_row(tab2_layout, tts_rate)
        self._volume_slider = self._make_slider_row(
            tab2_layout, "Volume", int(tts_volume * 100), 0, 100,
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
        tab2_layout.addLayout(voice_row)

        tab2_layout.addStretch()
        self._tabs.addTab(tab2, "Voice")

        # --- Tab 3: Boundaries ---
        tab3 = QWidget()
        tab3_layout = QVBoxLayout(tab3)

        tier1 = QGroupBox("Tier 1: Passive Annoyance (Low Risk)")
        tier1_layout = QVBoxLayout(tier1)
        self._cb_intrusive_animations = QCheckBox("Allow intrusive animations")
        self._cb_intrusive_animations.setChecked(allow_intrusive_animations)
        self._cb_intrusive_animations.toggled.connect(self.value_changed.emit)
        tier1_layout.addWidget(self._cb_intrusive_animations)
        self._cb_system_notifications = QCheckBox("Allow system notifications (toasts)")
        self._cb_system_notifications.setChecked(allow_system_notifications)
        self._cb_system_notifications.toggled.connect(self.value_changed.emit)
        tier1_layout.addWidget(self._cb_system_notifications)
        tab3_layout.addWidget(tier1)

        tier2 = QGroupBox("Tier 2: Workflow Interference (Medium Risk)")
        tier2_layout = QVBoxLayout(tier2)
        self._cb_browser_redirection = QCheckBox("Allow browser redirection")
        self._cb_browser_redirection.setChecked(allow_browser_redirection)
        self._cb_browser_redirection.toggled.connect(self.value_changed.emit)
        tier2_layout.addWidget(self._cb_browser_redirection)
        self._cb_clipboard_reading = QCheckBox("Allow clipboard reading")
        self._cb_clipboard_reading.setChecked(allow_clipboard_reading)
        self._cb_clipboard_reading.toggled.connect(self.value_changed.emit)
        tier2_layout.addWidget(self._cb_clipboard_reading)
        self._cb_mouse_interference = QCheckBox("Allow mouse interference")
        self._cb_mouse_interference.setChecked(allow_mouse_interference)
        self._cb_mouse_interference.toggled.connect(self.value_changed.emit)
        tier2_layout.addWidget(self._cb_mouse_interference)
        tab3_layout.addWidget(tier2)

        tier3 = QGroupBox("Tier 3: OS Write Access (High Risk - EXPERIMENTAL)")
        tier3.setStyleSheet("QGroupBox { color: #ff4444; font-weight: bold; }")
        tier3_layout = QVBoxLayout(tier3)
        self._cb_screenshot_capture = QCheckBox("Allow screenshot capture")
        self._cb_screenshot_capture.setChecked(allow_screenshot_capture)
        self._cb_screenshot_capture.toggled.connect(self.value_changed.emit)
        tier3_layout.addWidget(self._cb_screenshot_capture)
        self._cb_keyboard_injection = QCheckBox("Allow keyboard injection")
        self._cb_keyboard_injection.setChecked(allow_keyboard_injection)
        self._cb_keyboard_injection.toggled.connect(self.value_changed.emit)
        tier3_layout.addWidget(self._cb_keyboard_injection)
        tab3_layout.addWidget(tier3)

        tab3_layout.addStretch()
        self._tabs.addTab(tab3, "Boundaries")

        # --- Buttons ---
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
            "allow_intrusive_animations": self._cb_intrusive_animations.isChecked(),
            "allow_system_notifications": self._cb_system_notifications.isChecked(),
            "allow_browser_redirection": self._cb_browser_redirection.isChecked(),
            "allow_clipboard_reading": self._cb_clipboard_reading.isChecked(),
            "allow_mouse_interference": self._cb_mouse_interference.isChecked(),
            "allow_screenshot_capture": self._cb_screenshot_capture.isChecked(),
            "allow_keyboard_injection": self._cb_keyboard_injection.isChecked(),
        }
