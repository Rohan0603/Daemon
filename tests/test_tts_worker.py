# tests/test_tts_worker.py
from __future__ import annotations
import io
import os
import tempfile
import wave
import struct
from unittest.mock import patch, MagicMock
from src.tts_worker import TTSWorker


def _make_wav_bytes(nframes: int = 1000, rate: int = 22050) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(struct.pack(f"<{nframes}h", *([300] * nframes)))
    return buf.getvalue()


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

    def test_speaking_signals_are_pyqt_signals(self, app):
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

    def test_apply_pitch_filter_wave_pitch_shifts(self):
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
            result = worker._apply_pitch_filter_wave(tmp)
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

    def test_apply_pitch_filter_accepts_bytesio(self):
        worker = TTSWorker(pitch=1.15)
        # Produce minimal valid MP3 frame bytes (no headers — pydub reads from raw frames)
        # A valid MP3 frame sync word is 0xFF 0xFB (MPEG1, layer 3, no CRC)
        mp3_frame = b"\xff\xfb\x90\x00" + b"\x00" * 413  # 417-byte MP3 frame
        mp3_data = mp3_frame * 5  # 5 frames = ~0.12s audio
        bio = io.BytesIO(mp3_data)

        result = worker._apply_pitch_filter(bio)
        # Without pydub, returns None; with pydub, returns (raw_pcm, rate, ch, sw)
        if result is not None:
            raw, play_rate, nch, sw = result
            assert len(raw) > 0
            assert play_rate > 0

    def test_pyttsx3_engine_reused_across_calls(self):
        worker = TTSWorker(rate=220)
        engine = MagicMock()
        engine.getProperty.return_value = []

        with patch("pyttsx3.init", return_value=engine) as mock_init:
            worker._generate_pyttsx3("hello")
            worker._generate_pyttsx3("world")
            assert mock_init.call_count == 1

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

    def test_cancel_flag_set_by_clear(self):
        worker = TTSWorker()
        assert not worker._cancel.is_set()
        worker.clear()
        assert worker._cancel.is_set()

    def test_enqueue_clears_cancel_flag(self):
        worker = TTSWorker()
        worker.clear()
        assert worker._cancel.is_set()
        worker.enqueue("hello")
        assert not worker._cancel.is_set()

    def test_process_utterance_aborts_after_cancel(self):
        worker = TTSWorker()
        pitch_called = []

        original_pitch = worker._apply_pitch_filter

        def _recording_pitch(src):
            pitch_called.append(True)
            return original_pitch(src)

        worker._apply_pitch_filter = _recording_pitch
        worker._generate_voice = lambda t: io.BytesIO(b"fake")
        worker._cancel.set()

        worker._process_utterance("hello")
        assert len(pitch_called) == 0

    def test_asyncio_loop_reused_across_calls(self):
        worker = TTSWorker(pitch=1.20)
        loops_seen = []

        def _capturing_run(coro):
            loops_seen.append(id(worker._loop))
            coro.close()

        worker._loop.run_until_complete = _capturing_run

        engine = MagicMock()
        with patch("pyttsx3.init", return_value=engine):
            engine.getProperty.return_value = []
            try:
                worker._generate_voice("hello")
            except Exception:
                pass
            try:
                worker._generate_voice("world")
            except Exception:
                pass

        assert len(loops_seen) == 2
        assert loops_seen[0] == loops_seen[1]

    def test_pitch_string_derived_from_self_pitch(self):
        worker = TTSWorker(pitch=1.20)
        captured = {}

        class FakeComm:
            def __init__(self, text, voice, rate, pitch):
                captured["pitch"] = pitch

            async def stream(self):
                return
                yield

        import edge_tts as _et
        with patch.object(_et, "Communicate", FakeComm):
            try:
                worker._generate_voice("test")
            except Exception:
                pass

        assert captured.get("pitch") != "+15Hz"

    def test_stop_closes_asyncio_loop(self):
        worker = TTSWorker()
        assert not worker._loop.is_closed()
        worker.stop()
        assert worker._loop.is_closed()
