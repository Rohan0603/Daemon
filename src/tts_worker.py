# src/tts_worker.py
from __future__ import annotations
import asyncio
import logging
import os
import queue
import struct
import tempfile
import threading
import wave
from PyQt6.QtCore import QThread, pyqtSignal

logger = logging.getLogger(__name__)

try:
    import pydub  # noqa: F401
    _PYDUB_AVAILABLE = True
except ImportError:
    _PYDUB_AVAILABLE = False


class TTSWorker(QThread):
    speaking_started = pyqtSignal()
    speaking_finished = pyqtSignal()

    def __init__(self, rate: int = 220, volume: float = 1.0,
                 voice_id: str | None = None, pitch: float = 1.15,
                 parent=None, config: dict | None = None):
        super().__init__(parent)
        self._queue: queue.Queue[str] = queue.Queue()
        self._shutdown = threading.Event()
        self._enabled = threading.Event()
        self._enabled.set()
        
        if config is not None:
            tts_cfg = config.get("tts", {})
            self._rate = tts_cfg.get("rate", rate)
            self._volume = tts_cfg.get("volume", volume)
            self._voice_id = tts_cfg.get("voice_id", voice_id)
            self._pitch = tts_cfg.get("pitch", pitch)
        else:
            self._rate = rate
            self._volume = volume
            self._voice_id = voice_id
            self._pitch = pitch

    @property
    def pitch(self) -> float:
        return self._pitch

    @pitch.setter
    def pitch(self, value: float) -> None:
        self._pitch = value

    @property
    def rate(self) -> int:
        return self._rate

    @rate.setter
    def rate(self, value: int) -> None:
        self._rate = value

    @property
    def volume(self) -> float:
        return self._volume

    @volume.setter
    def volume(self, value: float) -> None:
        self._volume = value

    @property
    def voice_id(self) -> str | None:
        return self._voice_id

    @voice_id.setter
    def voice_id(self, value: str | None) -> None:
        self._voice_id = value

    def enqueue(self, text: str) -> None:
        if not self._enabled.is_set():
            return
        stripped = text.strip()
        if not stripped:
            return
        self._queue.put(stripped)

    def set_enabled(self, state: bool) -> None:
        if state:
            self._enabled.set()
        else:
            self._enabled.clear()
            self.clear()

    def clear(self) -> None:
        while not self._queue.empty():
            try:
                self._queue.get_nowait()
            except queue.Empty:
                break

    def stop(self) -> None:
        self._shutdown.set()
        self.clear()
        if self.isRunning():
            self.wait(2000)

    def _generate_voice(self, text: str) -> str | None:
        """Use edge-tts or pyttsx3 to generate an audio file. Returns path."""
        fd, tmp = tempfile.mkstemp(suffix=".mp3", prefix="daemon_tts_")
        os.close(fd)
        try:
            import edge_tts
            voice = self._voice_id or "en-US-GuyNeural"
            rate_pct = int((self._rate - 150) / 150 * 100)
            rate_str = f"{rate_pct:+d}%"
            pitch_str = "+15Hz"

            async def _gen():
                comm = edge_tts.Communicate(text, voice, rate=rate_str, pitch=pitch_str)
                await comm.save(tmp)

            loop = asyncio.new_event_loop()
            try:
                loop.run_until_complete(_gen())
            finally:
                loop.close()
            return tmp

        except Exception:
            logger.debug("edge-tts failed, falling back to pyttsx3")

        return self._generate_pyttsx3(text)

    def _generate_pyttsx3(self, text: str) -> str | None:
        fd, tmp = tempfile.mkstemp(suffix=".wav", prefix="daemon_tts_")
        os.close(fd)
        try:
            import pyttsx3
            engine = pyttsx3.init()
            voices = engine.getProperty("voices")
            if voices:
                if self._voice_id:
                    matching = [v for v in voices if v.id == self._voice_id]
                    vid = matching[0].id if matching else voices[0].id
                else:
                    vid = voices[1].id if len(voices) > 1 else voices[0].id
                engine.setProperty("voice", vid)
            engine.setProperty("rate", self._rate)
            engine.setProperty("volume", self._volume)
            engine.save_to_file(text, tmp)
            engine.runAndWait()
            return tmp
        except Exception as e:
            logger.warning("pyttsx3 fallback failed: %s", e)
            return None

    def _apply_pitch_filter(self, audio_path: str) -> tuple[bytes, int, int, int] | None:
        """Read audio file, apply pitch shift via framerate override.
        Returns (raw_pcm, play_rate, nchannels, sampwidth) or None."""
        if not _PYDUB_AVAILABLE:
            return self._apply_pitch_filter_wave(audio_path)
        try:
            from pydub import AudioSegment

            audio = AudioSegment.from_file(audio_path)
            orig_rate = audio.frame_rate
            new_rate = int(orig_rate * self._pitch)

            shifted = audio._spawn(audio.raw_data, overrides={"frame_rate": new_rate})
            shifted = shifted.set_frame_rate(orig_rate)
            shifted = shifted.high_pass_filter(120)

            raw = shifted.raw_data
            return raw, orig_rate, shifted.channels, shifted.sample_width

        except Exception as e:
            logger.debug("pydub pitch shift failed: %s, falling back to wave", e)
            return self._apply_pitch_filter_wave(audio_path)

    def _apply_pitch_filter_wave(self, audio_path: str) -> tuple[bytes, int, int, int] | None:
        """Fallback pitch shift using only stdlib wave module."""
        if not audio_path.lower().endswith(".wav"):
            return None
        try:
            fd, tmp = tempfile.mkstemp(suffix=".wav", prefix="daemon_tts_")
            os.close(fd)
            with wave.open(audio_path, "rb") as w:
                nch = w.getnchannels()
                sw = w.getsampwidth()
                orig_rate = w.getframerate()
                frames = w.readframes(w.getnframes())

            pitched_rate = int(orig_rate * self._pitch)

            with wave.open(tmp, "wb") as w:
                w.setnchannels(nch)
                w.setsampwidth(sw)
                w.setframerate(pitched_rate)
                w.writeframes(frames)

            with wave.open(tmp, "rb") as w:
                raw = w.readframes(w.getnframes())

            os.remove(tmp)
            return raw, orig_rate, nch, sw

        except Exception as e:
            logger.warning("wave pitch shift failed: %s", e)
            return None

    def _play_via_winsound(self, audio_path: str, _framerate: int) -> bool:
        """Play a WAV file via winsound (blocks worker thread, safe to delete after)."""
        import winsound
        try:
            winsound.PlaySound(
                audio_path,
                winsound.SND_FILENAME | winsound.SND_SYNC,
            )
            return True
        except Exception as e:
            logger.warning("winsound playback failed: %s", e)
            return False

    def run(self) -> None:
        self._shutdown.clear()

        while not self._shutdown.is_set():
            try:
                text = self._queue.get(timeout=1)
            except queue.Empty:
                continue

            self.speaking_started.emit()

            try:
                self._process_utterance(text)
            except Exception as e:
                logger.warning("TTS utterance failed: %s", e)

            self.speaking_finished.emit()

    def _process_utterance(self, text: str) -> None:
        audio_path = self._generate_voice(text)
        if audio_path is None:
            return

        result = self._apply_pitch_filter(audio_path)
        if result is None and audio_path.endswith(".mp3"):
            try:
                os.remove(audio_path)
            except OSError:
                pass
            audio_path = self._generate_pyttsx3(text)
            if audio_path:
                result = self._apply_pitch_filter(audio_path)
        else:
            try:
                os.remove(audio_path)
            except OSError:
                pass

        if result is None:
            if audio_path:
                try:
                    os.remove(audio_path)
                except OSError:
                    pass
            return

        raw, play_rate, nch, sw = result
        fb_fd, fallback_path = tempfile.mkstemp(suffix=".wav", prefix="daemon_tts_playback_")
        os.close(fb_fd)
        try:
            with wave.open(fallback_path, "wb") as w:
                w.setnchannels(nch)
                w.setsampwidth(sw)
                w.setframerate(play_rate)
                w.writeframes(raw)
            self._play_via_winsound(fallback_path, play_rate)
        except Exception as e:
            logger.warning("winsound playback failed: %s", e)
            try:
                import simpleaudio
                play_obj = simpleaudio.play_buffer(raw, nch, sw, play_rate)
                while play_obj.is_playing():
                    if self._shutdown.is_set():
                        play_obj.stop()
                        break
                    self.msleep(50)
            except ImportError:
                logger.warning("simpleaudio not available")
            except Exception as e2:
                logger.warning("simpleaudio fallback failed: %s", e2)
        finally:
            try:
                os.remove(fallback_path)
            except OSError:
                pass
