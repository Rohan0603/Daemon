# tests/test_tts_worker.py
from __future__ import annotations
import sys
import os
import tempfile
import wave
import struct
from unittest.mock import patch, MagicMock
from PyQt6.QtWidgets import QApplication
from src.tts_worker import TTSWorker


def app():
    _app = QApplication.instance()
    if _app is None:
        _app = QApplication(sys.argv)
    return _app


class TestTTSWorker:
    def test_enqueue_adds_to_queue(self):
        worker = TTSWorker()
        worker.enqueue("hello")
        assert worker._queue.get_nowait() == "hello"

    def test_enqueue_ignores_empty_text(self):
        worker = TTSWorker()
        worker.enqueue("")
        worker.enqueue("   ")
        assert worker._queue.empty()

    def test_set_enabled_disables_enqueue(self):
        worker = TTSWorker()
        worker.set_enabled(False)
        worker.enqueue("hello")
        assert worker._queue.empty()
        worker.set_enabled(True)
        worker.enqueue("world")
        assert worker._queue.get_nowait() == "world"

    def test_stop_clears_queue_and_shuts_down(self):
        worker = TTSWorker()
        worker.enqueue("hello")
        worker.enqueue("world")
        worker.stop()
        assert worker._shutdown.is_set()
        assert worker._queue.empty()

    def test_speaking_signals_are_pyqt_signals(self):
        _ = app()
        worker = TTSWorker()
        emitted_started = []
        emitted_finished = []
        worker.speaking_started.connect(lambda: emitted_started.append(None))
        worker.speaking_finished.connect(lambda: emitted_finished.append(None))
        worker.speaking_started.emit()
        worker.speaking_finished.emit()
        assert len(emitted_started) == 1
        assert len(emitted_finished) == 1

    def test_rate_volume_properties(self):
        worker = TTSWorker(rate=220, volume=0.8)
        assert worker.rate == 220
        assert worker.volume == 0.8
        worker.rate = 180
        worker.volume = 0.5
        assert worker.rate == 180
        assert worker.volume == 0.5

    def test_voice_id_property(self):
        worker = TTSWorker(voice_id="en-US-GuyNeural")
        assert worker.voice_id == "en-US-GuyNeural"

    def test_apply_morty_filter_wave_pitch_shifts(self):
        worker = TTSWorker()
        tmp = os.path.join(tempfile.gettempdir(), "tts_test_in.wav")
        nch, sw, rate, nframes = 1, 2, 22050, 1000
        frames = struct.pack(f"<{nframes}h", *([500] * nframes))
        with wave.open(tmp, "wb") as w:
            w.setnchannels(nch)
            w.setsampwidth(sw)
            w.setframerate(rate)
            w.writeframes(frames)
        try:
            result = worker._apply_morty_filter_wave(tmp)
            assert result is not None
            raw, play_rate, r_nch, r_sw = result
            assert play_rate == rate
            assert r_nch == nch
            assert r_sw == sw
            assert len(raw) > 0
        finally:
            try:
                os.remove(tmp)
            except OSError:
                pass

    def test_pyttsx3_fallback_generates_wav(self):
        worker = TTSWorker(rate=220)
        engine = MagicMock()
        with patch("pyttsx3.init", return_value=engine):
            engine.getProperty.return_value = []
            result = worker._generate_pyttsx3("test")
            assert result is not None
            assert result.endswith(".wav")

    def test_clear_empties_queue(self):
        worker = TTSWorker()
        worker.enqueue("hello")
        worker.enqueue("world")
        worker.clear()
        assert worker._queue.empty()
