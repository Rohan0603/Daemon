# src/settings_dialog.py
from __future__ import annotations
import threading
from PyQt6.QtWidgets import (
    QApplication, QDialog, QVBoxLayout, QHBoxLayout, QLabel, QSlider,
    QCheckBox, QComboBox, QDialogButtonBox,
    QGroupBox, QTabWidget, QWidget, QLineEdit,
    QPushButton, QApplication,
)
from pathlib import Path
from PyQt6.QtCore import Qt, pyqtSignal, pyqtSlot, QTimer
import requests
from src.constants import (
    SETTINGS_SCALE_MIN, SETTINGS_SCALE_MAX,
    SETTINGS_OPACITY_MIN, SETTINGS_OPACITY_MAX,
    SETTINGS_SPEED_MIN, SETTINGS_SPEED_MAX,
    CHATTINESS_DEFAULT, CHATTINESS_MIN, CHATTINESS_MAX,
)


class SettingsDialog(QDialog):
    value_changed = pyqtSignal()
    # Internal signals used to marshal background-thread network results back
    # onto the Qt UI thread (never touch widgets from a worker thread).
    _models_fetched = pyqtSignal(list)
    _model_validated = pyqtSignal(str, str)  # status_text, style_sheet

    def __init__(self, current_mode: str = "desktop_pet", pet_scale: float = 1.0, pet_opacity: float = 0.85,
                 pet_speed: float = 1.0, tts_enabled: bool = True,
                 tts_rate: int = 220, tts_volume: float = 1.0,
                 tts_voice_id: str | None = None, chattiness: float = 1.0,
                 allow_intrusive_animations: bool = True,
                 allow_audio_disruptions: bool = False,
                 allow_browser_redirection: bool = False,
                 allow_clipboard_hijacking: bool = False,
                 allow_mouse_interference: bool = False,
                 allow_keyboard_injection: bool = False,
                 allow_window_management: bool = False,
                 feature_pet_interaction: bool = True,
                 feature_activity_tracking: bool = True,
                 feature_autonomous_behavior: bool = True,
                 feature_memory_sync: bool = True,
                 feature_code_intelligence: bool = True,
                 feature_desktop_interaction: bool = True,
                 llm_provider: str = "opencode",
                 ollama_url: str = "http://127.0.0.1:11434",
                 ollama_model: str = "llama3.2-1b-q8:latest",
                 ollama_status: str = "",
                 llm_model_id: str = "",
                 llm_api_key: str = "",
                 llm_server_url: str = "http://127.0.0.1:4096",
                 firebase_project_id: str = "",
                 parent=None):
        super().__init__(parent)
        self.setWindowTitle("Daemon Settings")
        self.setFixedSize(500, 620)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint)

        layout = QVBoxLayout(self)

        self._tabs = QTabWidget()
        layout.addWidget(self._tabs)

        # --- Tab 0: Mode ---
        tab_mode = QWidget()
        tab_mode_layout = QVBoxLayout(tab_mode)
        
        mode_label = QLabel("Operating Mode")
        mode_label.setStyleSheet("font-weight: bold; color: #5B8DEF;")
        tab_mode_layout.addWidget(mode_label)
        
        self._mode_combo = QComboBox()
        self._mode_combo.addItem("Desktop Pet (Default)", "desktop_pet")
        self._mode_combo.addItem("Active Coding Assistant", "coding_assistant")
        if current_mode == "coding_assistant":
            self._mode_combo.setCurrentIndex(1)
        self._mode_combo.currentIndexChanged.connect(self.value_changed.emit)
        tab_mode_layout.addWidget(self._mode_combo)
        
        tab_mode_layout.addStretch()
        self._tabs.addTab(tab_mode, "Mode")

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

        # --- Tab 3: Capabilities and boundaries ---
        tab3 = QWidget()
        tab3_layout = QVBoxLayout(tab3)
        tab3_layout.addWidget(QLabel("Choose capabilities to enable. All are enabled by default."))

        feature_groups = (
            ("Core pet interaction", "feature_pet_interaction", feature_pet_interaction),
            ("System activity awareness", "feature_activity_tracking", feature_activity_tracking),
            ("Autonomous behavior and thoughts", "feature_autonomous_behavior", feature_autonomous_behavior),
            ("Memory and cloud synchronization", "feature_memory_sync", feature_memory_sync),
            ("Code intelligence (file watcher and LSP)", "feature_code_intelligence", feature_code_intelligence),
            ("Desktop interaction (UIA and vision)", "feature_desktop_interaction", feature_desktop_interaction),
        )
        self._feature_checkboxes = {}
        features_group = QGroupBox("Main functionalities")
        features_layout = QVBoxLayout(features_group)
        for label_text, key, checked in feature_groups:
            checkbox = QCheckBox(label_text)
            checkbox.setChecked(checked)
            checkbox.toggled.connect(self.value_changed.emit)
            features_layout.addWidget(checkbox)
            self._feature_checkboxes[key] = checkbox
        tab3_layout.addWidget(features_group)

        tier1 = QGroupBox("Tier 1: Passive Annoyance (Low Risk)")
        tier1_layout = QVBoxLayout(tier1)
        self._cb_intrusive_animations = QCheckBox("Allow intrusive animations")
        self._cb_intrusive_animations.setChecked(allow_intrusive_animations)
        self._cb_intrusive_animations.toggled.connect(self.value_changed.emit)
        tier1_layout.addWidget(self._cb_intrusive_animations)
        self._cb_audio_disruptions = QCheckBox("Allow audio disruptions")
        self._cb_audio_disruptions.setChecked(allow_audio_disruptions)
        self._cb_audio_disruptions.toggled.connect(self.value_changed.emit)
        tier1_layout.addWidget(self._cb_audio_disruptions)
        tab3_layout.addWidget(tier1)

        tier2 = QGroupBox("Tier 2: Workflow Interference (Medium Risk)")
        tier2_layout = QVBoxLayout(tier2)
        self._cb_browser_redirection = QCheckBox("Allow browser redirection")
        self._cb_browser_redirection.setChecked(allow_browser_redirection)
        self._cb_browser_redirection.toggled.connect(self.value_changed.emit)
        tier2_layout.addWidget(self._cb_browser_redirection)
        self._cb_clipboard_hijacking = QCheckBox("Allow clipboard hijacking")
        self._cb_clipboard_hijacking.setChecked(allow_clipboard_hijacking)
        self._cb_clipboard_hijacking.toggled.connect(self.value_changed.emit)
        tier2_layout.addWidget(self._cb_clipboard_hijacking)
        self._cb_mouse_interference = QCheckBox("Allow mouse interference")
        self._cb_mouse_interference.setChecked(allow_mouse_interference)
        self._cb_mouse_interference.toggled.connect(self.value_changed.emit)
        tier2_layout.addWidget(self._cb_mouse_interference)
        tab3_layout.addWidget(tier2)

        tier3 = QGroupBox("Tier 3: OS Write Access (High Risk - EXPERIMENTAL)")
        tier3.setStyleSheet("QGroupBox { color: #ff4444; font-weight: bold; }")
        tier3_layout = QVBoxLayout(tier3)
        self._cb_keyboard_injection = QCheckBox("Allow keyboard injection")
        self._cb_keyboard_injection.setChecked(allow_keyboard_injection)
        self._cb_keyboard_injection.toggled.connect(self.value_changed.emit)
        tier3_layout.addWidget(self._cb_keyboard_injection)
        self._cb_window_management = QCheckBox("Allow window management")
        self._cb_window_management.setChecked(allow_window_management)
        self._cb_window_management.toggled.connect(self.value_changed.emit)
        tier3_layout.addWidget(self._cb_window_management)
        tab3_layout.addWidget(tier3)

        tab3_layout.addStretch()
        self._tabs.addTab(tab3, "Capabilities")

        # --- Tab 5: Connections ---
        tab4 = QWidget()
        tab4_layout = QVBoxLayout(tab4)
        
        llm_group = QGroupBox("LLM Configuration")
        llm_layout = QVBoxLayout(llm_group)

        provider_row = QHBoxLayout()
        provider_row.addWidget(QLabel("Provider:"))
        self._provider_combo = QComboBox()
        self._provider_combo.addItem("opencode serve", "opencode")
        self._provider_combo.addItem("Ollama (Local)", "ollama")
        provider_idx = 0 if llm_provider == "opencode" else 1
        self._provider_combo.setCurrentIndex(provider_idx)
        self._provider_combo.currentIndexChanged.connect(self._on_provider_changed)
        provider_row.addWidget(self._provider_combo)
        llm_layout.addLayout(provider_row)

        # Opencode fields
        self._opencode_widget = QWidget()
        oc_layout = QVBoxLayout(self._opencode_widget)
        oc_layout.setContentsMargins(0, 0, 0, 0)
        self._llm_model_id = QLineEdit(llm_model_id)
        self._llm_api_key = QLineEdit(llm_api_key)
        self._llm_api_key.setEchoMode(QLineEdit.EchoMode.PasswordEchoOnEdit)
        self._llm_server_url = QLineEdit(llm_server_url)
        oc_layout.addWidget(QLabel("Model ID:"))
        oc_layout.addWidget(self._llm_model_id)
        oc_layout.addWidget(QLabel("API Key:"))
        oc_layout.addWidget(self._llm_api_key)
        oc_layout.addWidget(QLabel("Server URL:"))
        oc_layout.addWidget(self._llm_server_url)
        llm_layout.addWidget(self._opencode_widget)
        llm_layout.addStretch(1)

        # Ollama fields
        self._ollama_widget = QWidget()
        ol_layout = QVBoxLayout(self._ollama_widget)
        ol_layout.setContentsMargins(0, 0, 0, 0)
        self._ollama_url_edit = QLineEdit(ollama_url)

        model_row = QHBoxLayout()
        model_row.addWidget(QLabel("Model:"))
        self._ollama_model_combo = QComboBox()
        self._ollama_model_combo.setEditable(True)
        self._ollama_model_combo.currentTextChanged.connect(self.value_changed.emit)
        # Debounce per-keystroke validation so we don't fire a network probe on
        # every character typed into the editable model box.
        self._validate_debounce = QTimer(self)
        self._validate_debounce.setSingleShot(True)
        self._validate_debounce.setInterval(400)
        self._validate_debounce.timeout.connect(self._validate_selected_model)
        self._ollama_model_combo.currentTextChanged.connect(
            lambda _=None: self._validate_debounce.start()
        )
        model_row.addWidget(self._ollama_model_combo)
        self._ollama_refresh_btn = QPushButton("Refresh")
        self._ollama_refresh_btn.clicked.connect(self._refresh_ollama_models)
        model_row.addWidget(self._ollama_refresh_btn)
        ol_layout.addWidget(QLabel("Ollama URL:"))
        ol_layout.addWidget(self._ollama_url_edit)
        ol_layout.addLayout(model_row)
        llm_layout.addWidget(self._ollama_widget)
        llm_layout.addStretch(1)

        # Marshal background-thread results back onto the UI thread.
        self._models_fetched.connect(self._apply_fetched_models)
        self._model_validated.connect(self._apply_validation_result)

        self._ollama_model_combo.setCurrentText(ollama_model)
        QTimer.singleShot(500, self._refresh_ollama_models)

        self._on_provider_changed(provider_idx)

        tab4_layout.addWidget(llm_group)

        fb_group = QGroupBox("Firebase Configuration")
        fb_layout = QVBoxLayout(fb_group)
        self._fb_project_id = QLineEdit(firebase_project_id)
        self._fb_project_id.setReadOnly(True)
        fb_layout.addWidget(QLabel("Project ID (managed by the release):"))
        fb_layout.addWidget(self._fb_project_id)
        tab4_layout.addWidget(fb_group)
        
        tab4_layout.addStretch()
        self._tabs.addTab(tab4, "Connections")

        # --- Buttons ---
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _on_provider_changed(self, index: int) -> None:
        is_ollama = self._provider_combo.currentData() == "ollama"
        self._opencode_widget.setVisible(not is_ollama)
        self._ollama_widget.setVisible(is_ollama)
        self._opencode_widget.updateGeometry()
        self._ollama_widget.updateGeometry()
        QApplication.processEvents()
        self.value_changed.emit()

    def _refresh_ollama_models(self) -> None:
        """Probe Ollama for available models on a background thread."""
        url = self._ollama_url_edit.text().strip().rstrip("/")

        def _work() -> None:
            models: list[str] = []
            try:
                resp = requests.get(f"{url}/api/tags", timeout=3)
                if resp.status_code == 200:
                    models = [m.get("name", "") for m in resp.json().get("models", [])]
            except requests.RequestException:
                pass
            self._models_fetched.emit(models)

        threading.Thread(target=_work, daemon=True).start()

    @pyqtSlot(list)
    def _apply_fetched_models(self, models: list) -> None:
        """UI-thread: repopulate the model combo, preserving the current text."""
        current = self._ollama_model_combo.currentText()
        self._ollama_model_combo.blockSignals(True)
        self._ollama_model_combo.clear()
        for name in models:
            if name:
                self._ollama_model_combo.addItem(name)
        if current:
            idx = self._ollama_model_combo.findText(current)
            if idx >= 0:
                self._ollama_model_combo.setCurrentIndex(idx)
            else:
                self._ollama_model_combo.setCurrentText(current)
        self._ollama_model_combo.blockSignals(False)
        self._validate_selected_model()

    def _validate_selected_model(self) -> None:
        """Probe the selected model's capabilities on a background thread."""
        model = self._ollama_model_combo.currentText().strip()
        if not model:
            self._model_validated.emit("Status: no model selected", "")
            return
        url = self._ollama_url_edit.text().strip().rstrip("/")

        def _work() -> None:
            try:
                resp = requests.post(f"{url}/api/show", json={"name": model}, timeout=3)
                if resp.status_code == 200:
                    caps = resp.json().get("capabilities", [])
                    if "tools" not in caps:
                        self._model_validated.emit(
                            "Status: warning (completion-only model, tool-calling disabled)",
                            "color: #ff4444; font-weight: bold;",
                        )
                    else:
                        self._model_validated.emit(
                            "Status: ready (supports tool-calling)",
                            "color: #6BCB77; font-weight: bold;",
                        )
                else:
                    self._model_validated.emit("Status: unknown model details", "")
            except requests.RequestException:
                self._model_validated.emit("Status: Ollama offline", "color: #ff4444;")

        threading.Thread(target=_work, daemon=True).start()

    @pyqtSlot(str, str)
    def _apply_validation_result(self, status_text: str, style_sheet: str) -> None:
        """UI-thread: apply the validation status label + style."""
        self._ollama_status_label.setText(status_text)
        self._ollama_status_label.setStyleSheet(style_sheet)

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
            "pet_mode": self._mode_combo.currentData(),
            "pet_scale": self._size_slider.value() / 100.0,
            "pet_opacity": self._opacity_slider.value() / 100.0,
            "pet_speed_multiplier": self._speed_slider.value() / 100.0,
            "tts_enabled": self._voice_checkbox.isChecked(),
            "tts_rate": self._rate_slider.value(),
            "tts_volume": self._volume_slider.value() / 100.0,
            "tts_voice_id": voice_data if voice_data else None,
            "chattiness": self._chattiness_slider.value() / 10.0,
            "allow_intrusive_animations": self._cb_intrusive_animations.isChecked(),
            "allow_audio_disruptions": self._cb_audio_disruptions.isChecked(),
            "allow_browser_redirection": self._cb_browser_redirection.isChecked(),
            "allow_clipboard_hijacking": self._cb_clipboard_hijacking.isChecked(),
            "allow_mouse_interference": self._cb_mouse_interference.isChecked(),
            "allow_keyboard_injection": self._cb_keyboard_injection.isChecked(),
            "allow_window_management": self._cb_window_management.isChecked(),
            **{key: checkbox.isChecked() for key, checkbox in self._feature_checkboxes.items()},
            "LLM_PROVIDER": self._provider_combo.currentData(),
            "OLLAMA_URL": self._ollama_url_edit.text(),
            "OLLAMA_MODEL": self._ollama_model_combo.currentText(),
            "OPENCODE_API_MODEL_ID": self._llm_model_id.text(),
            "OPENCODE_API_KEY": self._llm_api_key.text(),
            "OPENCODE_SERVER_URL": self._llm_server_url.text(),
            "FIREBASE_PROJECT_ID": self._fb_project_id.text(),
        }
