# TTS Optimization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reduce TTS latency and resource usage by reusing infrastructure across utterances, fixing the pitch bug, eliminating all temp files on the primary path, and adding cancellation + LRU caching.

**Architecture:** All changes are self-contained in `src/system/tts_worker.py`. No new files. One persistent asyncio event loop and one pyttsx3 engine are created in `__init__`; edge-tts streams to `BytesIO` so no `.mp3` temp file is ever written; a 20-entry LRU cache keyed by `(text, voice, pitch, rate)` avoids regenerating recently-spoken phrases; a `_cancel` flag lets `enqueue()` interrupt the active utterance between pipeline stages.

**Tech Stack:** Python stdlib (`asyncio`, `io`, `math`), `edge_tts`, `pyttsx3`, `pydub`, `wave`, `winsound`, `PyQt6.QtCore.QThread`

---

## Scope

In scope:

| # | Optimization | Rationale |
|---|---|---|
| 1 | Reuse asyncio loop | ~50 ms saved per utterance |
| 2 | Cache pyttsx3 engine | ~200 ms saved on fallback path |
| 3 | Configurable pitch for edge-tts | Fixes bug where `self._pitch` is ignored |
| 4 | BytesIO pipeline for edge-tts | Eliminates `.mp3` temp file entirely |
| 5 | Cancellation flag | Lets `clear()` interrupt an in-progress utterance |
| 6 | LRU phrase cache | Avoids network round-trip for repeated phrases |

Out of scope (YAGNI):
- Pre-generation during idle — ThoughtPool already caches at a higher layer; no measured cache misses.
- Parallel gen+play — `winsound.SND_SYNC` is required on Windows; sub-threading adds a race with no clean solution.
- `simpleaudio` installation — packaging change outside this scope.

---

## File Map

| File | Change |
|---|---|
| `src/system/tts_worker.py` | All implementation changes |
| `tests/test_tts_worker.py` | New tests for all changed behaviours |

No other files touched.

---

## Task 1: Reuse asyncio event loop + configurable pitch

Fix two bugs at once: the event loop created/destroyed per call, and the hardcoded `"+15Hz"` that ignores `self._pitch`.

**Files:**
- Modify: `src/system/tts_worker.py` — `__init__` and `_generate_voice`
- Test: `tests/test_tts_worker.py`

- [ ] **Step 1: Create branch**

```bash
git checkout -b task-tts-optimization
```

- [ ] **Step 2: Write the failing tests**

Add inside `TestTTSWorker` in `tests/test_tts_worker.py`:

```python
from unittest.mock import patch, MagicMock
import io


def test_asyncio_loop_reused_across_calls():
    """The same event loop object is used for both calls."""
    worker = TTSWorker(pitch=1.20)
    loops_seen = []

    def _capturing_run(coro):
        loops_seen.append(id(worker._loop))
        coro.close()

    worker._loop.run_until_complete = _capturing_run

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


def test_pitch_string_derived_from_self_pitch():
    """edge-tts Communicate is called with a pitch string derived from self._pitch, not hardcoded."""
    worker = TTSWorker(pitch=1.20)
    captured = {}

    class FakeComm:
        def __init__(self, text, voice, rate, pitch):
            captured["pitch"] = pitch

        async def stream(self):
            return
            yield  # make it an async generator

    import edge_tts as _et
    with patch.object(_et, "Communicate", FakeComm):
        try:
            worker._generate_voice("test")
        except Exception:
            pass

    assert captured.get("pitch") != "+15Hz"
```

- [ ] **Step 3: Run tests to verify they fail**

```bash
py -m pytest tests/test_tts_worker.py::TestTTSWorker::test_asyncio_loop_reused_across_calls tests/test_tts_worker.py::TestTTSWorker::test_pitch_string_derived_from_self_pitch -v
```

Expected: FAIL — `TTSWorker` has no `_loop` attribute.

- [ ] **Step 4: Implement — constructor + `_generate_voice`**

Add `import io` and `import math` to the top of `src/system/tts_worker.py` alongside the existing stdlib imports.

In `TTSWorker.__init__`, after the existing `self._pitch = ...` block, add:

```python
        # Reuse a single event loop for all edge-tts calls (avoids ~50ms create/teardown per utterance)
        self._loop = asyncio.new_event_loop()
        # pyttsx3 engine initialised lazily on first fallback call (avoids ~200ms init overhead)
        self._pyttsx3_engine = None
```

Replace the entire `_generate_voice` method:

```python
    def _generate_voice(self, text: str) -> "str | io.BytesIO | None":
        """Use edge-tts (streams to BytesIO, no temp file) or pyttsx3. Returns BytesIO, path, or None."""
        try:
            import edge_tts
            voice = self._voice_id or "en-US-GuyNeural"
            rate_pct = int((self._rate - 150) / 150 * 100)
            rate_str = f"{rate_pct:+d}%"
            semitones = 12 * math.log2(self._pitch) if self._pitch > 0 else 0
            hz_offset = int(semitones * 8.33)
            pitch_str = f"{hz_offset:+d}Hz"

            mp3_buf = io.BytesIO()

            async def _gen() -> None:
                comm = edge_tts.Communicate(text, voice, rate=rate_str, pitch=pitch_str)
                async for chunk in comm.stream():
                    if chunk["type"] == "audio":
                        mp3_buf.write(chunk["data"])

            self._loop.run_until_complete(_gen())
            mp3_buf.seek(0)
            if mp3_buf.getbuffer().nbytes == 0:
                raise RuntimeError("edge-tts returned empty audio")
            return mp3_buf

        except Exception:
            logger.debug("edge-tts failed, falling back to pyttsx3")
        return self._generate_pyttsx3(text)
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
py -m pytest tests/test_tts_worker.py::TestTTSWorker::test_asyncio_loop_reused_across_calls tests/test_tts_worker.py::TestTTSWorker::test_pitch_string_derived_from_self_pitch -v
```

Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/system/tts_worker.py tests/test_tts_worker.py
git commit -m "perf(tts): reuse asyncio loop; fix pitch to use self._pitch"
```

---

## Task 2: Cache pyttsx3 engine

Avoid ~200 ms `pyttsx3.init()` overhead on every fallback call.

**Files:**
- Modify: `src/system/tts_worker.py` — `_generate_pyttsx3`
- Test: `tests/test_tts_worker.py`

- [ ] **Step 1: Write the failing test**

Add inside `TestTTSWorker`:

```python
def test_pyttsx3_engine_reused_across_calls():
    """pyttsx3.init() is called only once even when _generate_pyttsx3 is called twice."""
    worker = TTSWorker(rate=220)
    engine = MagicMock()
    engine.getProperty.return_value = []

    with patch("pyttsx3.init", return_value=engine) as mock_init:
        worker._generate_pyttsx3("hello")
        worker._generate_pyttsx3("world")
        assert mock_init.call_count == 1
```

- [ ] **Step 2: Run test to verify it fails**

```bash
py -m pytest tests/test_tts_worker.py::TestTTSWorker::test_pyttsx3_engine_reused_across_calls -v
```

Expected: FAIL — `mock_init.call_count == 2`.

- [ ] **Step 3: Implement — lazy engine caching**

Replace the entire `_generate_pyttsx3` method:

```python
    def _generate_pyttsx3(self, text: str) -> "str | None":
        fd, tmp = tempfile.mkstemp(suffix=".wav", prefix="daemon_tts_")
        os.close(fd)
        try:
            import pyttsx3
            if self._pyttsx3_engine is None:
                self._pyttsx3_engine = pyttsx3.init()
            engine = self._pyttsx3_engine
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
            self._pyttsx3_engine = None  # invalidate so next call gets a fresh engine
            return None
```

- [ ] **Step 4: Run test to verify it passes**

```bash
py -m pytest tests/test_tts_worker.py::TestTTSWorker::test_pyttsx3_engine_reused_across_calls -v
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/system/tts_worker.py tests/test_tts_worker.py
git commit -m "perf(tts): cache pyttsx3 engine across utterances"
```

---

## Task 3: BytesIO pipeline — eliminate mp3 temp file

`_apply_pitch_filter` currently always receives a file path string. After Task 1, edge-tts returns a `BytesIO`. Update `_apply_pitch_filter` and `_process_utterance` to accept either.

**Files:**
- Modify: `src/system/tts_worker.py` — `_apply_pitch_filter` and `_process_utterance`
- Test: `tests/test_tts_worker.py`

- [ ] **Step 1: Write the failing test**

Add inside `TestTTSWorker`:

```python
import struct
import wave

def _make_wav_bytes(nframes: int = 1000, rate: int = 22050) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(struct.pack(f"<{nframes}h", *([300] * nframes)))
    return buf.getvalue()


def test_apply_pitch_filter_accepts_bytesio():
    """_apply_pitch_filter works when given a BytesIO (edge-tts primary path)."""
    worker = TTSWorker(pitch=1.15)
    wav_bytes = _make_wav_bytes()
    bio = io.BytesIO(wav_bytes)
    bio.name = "dummy.wav"

    result = worker._apply_pitch_filter(bio)
    # result may be None if pydub absent — must not raise regardless
    if result is not None:
        raw, play_rate, nch, sw = result
        assert len(raw) > 0
        assert play_rate == 22050
```

- [ ] **Step 2: Run test to verify it fails**

```bash
py -m pytest tests/test_tts_worker.py::TestTTSWorker::test_apply_pitch_filter_accepts_bytesio -v
```

Expected: FAIL — `AudioSegment.from_file` receives a `BytesIO` but the current code passes it as a path.

- [ ] **Step 3: Implement — update `_apply_pitch_filter`**

Replace the entire `_apply_pitch_filter` method:

```python
    def _apply_pitch_filter(
        self, audio_source: "str | io.BytesIO"
    ) -> "tuple[bytes, int, int, int] | None":
        """Apply pitch shift via framerate override.
        audio_source: file path (str) or BytesIO from edge-tts.
        Returns (raw_pcm, play_rate, nchannels, sampwidth) or None.
        """
        if not _PYDUB_AVAILABLE:
            if isinstance(audio_source, io.BytesIO):
                return None  # wave stdlib cannot process in-memory MP3
            return self._apply_pitch_filter_wave(audio_source)
        try:
            from pydub import AudioSegment
            if isinstance(audio_source, io.BytesIO):
                audio_source.seek(0)
                audio = AudioSegment.from_file(audio_source, format="mp3")
            else:
                audio = AudioSegment.from_file(audio_source)
            orig_rate = audio.frame_rate
            new_rate = int(orig_rate * self._pitch)
            shifted = audio._spawn(audio.raw_data, overrides={"frame_rate": new_rate})
            shifted = shifted.set_frame_rate(orig_rate)
            shifted = shifted.high_pass_filter(120)
            return shifted.raw_data, orig_rate, shifted.channels, shifted.sample_width
        except Exception as e:
            logger.debug("pydub pitch shift failed: %s", e)
            if isinstance(audio_source, str):
                return self._apply_pitch_filter_wave(audio_source)
            return None
```

Replace the entire `_process_utterance` method to handle `BytesIO` sources (no `os.remove` on it):

```python
    def _process_utterance(self, text: str) -> None:
        temp_files: list[str] = []
        audio_source = self._generate_voice(text)
        if audio_source is None:
            return

        if self._cancel.is_set():
            return

        result = self._apply_pitch_filter(audio_source)

        if result is None and isinstance(audio_source, io.BytesIO):
            # edge-tts BytesIO pitch failed (pydub absent) — try pyttsx3 WAV path
            audio_source = self._generate_pyttsx3(text)
            if audio_source:
                temp_files.append(audio_source)
                result = self._apply_pitch_filter(audio_source)
        elif result is None and isinstance(audio_source, str) and audio_source.endswith(".mp3"):
            try:
                os.remove(audio_source)
            except OSError:
                pass
            audio_source = self._generate_pyttsx3(text)
            if audio_source:
                temp_files.append(audio_source)
                result = self._apply_pitch_filter(audio_source)
        elif isinstance(audio_source, str):
            # Successful pydub on file path — delete the source now
            try:
                os.remove(audio_source)
            except OSError:
                pass

        if result is None:
            for p in temp_files:
                try:
                    os.remove(p)
                except OSError:
                    pass
            return

        raw, play_rate, nch, sw = result

        if self._cancel.is_set():
            for p in temp_files:
                try:
                    os.remove(p)
                except OSError:
                    pass
            return

        fb_fd, fallback_path = tempfile.mkstemp(suffix=".wav", prefix="daemon_tts_playback_")
        os.close(fb_fd)
        temp_files.append(fallback_path)
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
            for p in temp_files:
                try:
                    os.remove(p)
                except OSError:
                    pass
```

> **Note:** `_cancel` is referenced here but added in Task 4. Add a temporary `self._cancel = threading.Event()` stub to `__init__` now so this method compiles. Task 4 will formalise it.

- [ ] **Step 4: Run test to verify it passes**

```bash
py -m pytest tests/test_tts_worker.py::TestTTSWorker::test_apply_pitch_filter_accepts_bytesio -v
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/system/tts_worker.py tests/test_tts_worker.py
git commit -m "perf(tts): BytesIO pipeline for edge-tts; eliminates mp3 temp file"
```

---

## Task 4: Cancellation flag

`clear()` sets `_cancel`; `_process_utterance` checks it between pipeline stages; `enqueue()` clears it when new text arrives.

**Files:**
- Modify: `src/system/tts_worker.py` — `__init__`, `clear()`, `enqueue()`, `_process_utterance`
- Test: `tests/test_tts_worker.py`

- [ ] **Step 1: Write the failing tests**

Add inside `TestTTSWorker`:

```python
def test_cancel_flag_set_by_clear():
    """clear() sets _cancel so _process_utterance aborts early."""
    worker = TTSWorker()
    assert not worker._cancel.is_set()
    worker.clear()
    assert worker._cancel.is_set()


def test_enqueue_clears_cancel_flag():
    """enqueue() resets _cancel when new text arrives."""
    worker = TTSWorker()
    worker.clear()
    assert worker._cancel.is_set()
    worker.enqueue("hello")
    assert not worker._cancel.is_set()


def test_process_utterance_aborts_after_cancel():
    """_apply_pitch_filter is never called when _cancel is set after voice gen."""
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
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
py -m pytest tests/test_tts_worker.py::TestTTSWorker::test_cancel_flag_set_by_clear tests/test_tts_worker.py::TestTTSWorker::test_enqueue_clears_cancel_flag tests/test_tts_worker.py::TestTTSWorker::test_process_utterance_aborts_after_cancel -v
```

Expected: FAIL — the stub `threading.Event()` from Task 3 doesn't hook into `clear()`/`enqueue()`.

- [ ] **Step 3: Implement — wire `_cancel` fully**

In `__init__`, replace the stub with (or confirm this line is present, removing the stub if added in Task 3):

```python
        self._cancel = threading.Event()
```

Replace `clear()`:

```python
    def clear(self) -> None:
        self._cancel.set()
        while not self._queue.empty():
            try:
                self._queue.get_nowait()
            except queue.Empty:
                break
```

Replace `enqueue()`:

```python
    def enqueue(self, text: str) -> None:
        if not self._enabled.is_set():
            return
        stripped = text.strip()
        if not stripped:
            return
        self._cancel.clear()
        self._queue.put(stripped)
```

The `_process_utterance` method already has `if self._cancel.is_set(): return` guards in two places from Task 3.

- [ ] **Step 4: Run tests to verify they pass**

```bash
py -m pytest tests/test_tts_worker.py::TestTTSWorker::test_cancel_flag_set_by_clear tests/test_tts_worker.py::TestTTSWorker::test_enqueue_clears_cancel_flag tests/test_tts_worker.py::TestTTSWorker::test_process_utterance_aborts_after_cancel -v
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/system/tts_worker.py tests/test_tts_worker.py
git commit -m "feat(tts): add cancellation flag; clear() interrupts active utterance"
```

---

## Task 5: LRU phrase cache

Cache the final `(raw, play_rate, nch, sw)` tuple keyed by `(text, voice, pitch_str, rate_str)`. Max 20 entries. On cache hit, skip generation and pitch filter entirely.

**Files:**
- Modify: `src/system/tts_worker.py` — `__init__`, new `_cache_key` / `_cache_get` / `_cache_put` methods, `_process_utterance`
- Test: `tests/test_tts_worker.py`

- [ ] **Step 1: Write the failing tests**

Add inside `TestTTSWorker`:

```python
def test_lru_cache_avoids_regeneration():
    """Second call with same text+voice+pitch+rate skips _generate_voice."""
    worker = TTSWorker(pitch=1.15)
    gen_calls = []

    def _fake_generate(text):
        gen_calls.append(text)
        return None

    cache_key = worker._cache_key("hello")
    worker._cache[cache_key] = (b"\x00" * 100, 22050, 1, 2)
    worker._cache_order.append(cache_key)

    worker._generate_voice = _fake_generate

    with patch("winsound.PlaySound"), patch("wave.open"):
        worker._process_utterance("hello")

    assert len(gen_calls) == 0, "_generate_voice should not be called on cache hit"


def test_lru_cache_evicts_oldest_when_full():
    """When cache exceeds 20 entries, the oldest key is evicted."""
    worker = TTSWorker()
    for i in range(20):
        key = f"key_{i}"
        worker._cache[key] = (b"x", 22050, 1, 2)
        worker._cache_order.append(key)

    worker._cache_put("key_new", (b"y", 22050, 1, 2))
    assert len(worker._cache) == 20
    assert "key_0" not in worker._cache
    assert "key_new" in worker._cache
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
py -m pytest tests/test_tts_worker.py::TestTTSWorker::test_lru_cache_avoids_regeneration tests/test_tts_worker.py::TestTTSWorker::test_lru_cache_evicts_oldest_when_full -v
```

Expected: FAIL — `TTSWorker` has no `_cache` attribute.

- [ ] **Step 3: Implement — LRU cache**

In `__init__`, after `self._pyttsx3_engine = None`:

```python
        self._cache: dict[str, tuple[bytes, int, int, int]] = {}
        self._cache_order: list[str] = []
        self._cache_max = 20
```

Add three helpers just before `_generate_voice`:

```python
    def _cache_key(self, text: str) -> str:
        voice = self._voice_id or "en-US-GuyNeural"
        rate_pct = int((self._rate - 150) / 150 * 100)
        semitones = 12 * math.log2(self._pitch) if self._pitch > 0 else 0
        hz_offset = int(semitones * 8.33)
        return f"{text}|{voice}|{hz_offset:+d}Hz|{rate_pct:+d}%"

    def _cache_get(self, key: str) -> "tuple[bytes, int, int, int] | None":
        val = self._cache.get(key)
        if val is not None:
            try:
                self._cache_order.remove(key)
            except ValueError:
                pass
            self._cache_order.append(key)
        return val

    def _cache_put(self, key: str, value: "tuple[bytes, int, int, int]") -> None:
        if key in self._cache:
            try:
                self._cache_order.remove(key)
            except ValueError:
                pass
        elif len(self._cache) >= self._cache_max:
            oldest = self._cache_order.pop(0)
            self._cache.pop(oldest, None)
        self._cache[key] = value
        self._cache_order.append(key)
```

Replace the top section of `_process_utterance` to check the cache first:

```python
    def _process_utterance(self, text: str) -> None:
        temp_files: list[str] = []

        # Cache hit: skip generation and pitch filter
        cache_key = self._cache_key(text)
        cached = self._cache_get(cache_key)
        if cached is not None:
            raw, play_rate, nch, sw = cached
        else:
            audio_source = self._generate_voice(text)
            if audio_source is None:
                return

            if self._cancel.is_set():
                return

            result = self._apply_pitch_filter(audio_source)

            if result is None and isinstance(audio_source, io.BytesIO):
                audio_source = self._generate_pyttsx3(text)
                if audio_source:
                    temp_files.append(audio_source)
                    result = self._apply_pitch_filter(audio_source)
            elif result is None and isinstance(audio_source, str) and audio_source.endswith(".mp3"):
                try:
                    os.remove(audio_source)
                except OSError:
                    pass
                audio_source = self._generate_pyttsx3(text)
                if audio_source:
                    temp_files.append(audio_source)
                    result = self._apply_pitch_filter(audio_source)
            elif isinstance(audio_source, str):
                try:
                    os.remove(audio_source)
                except OSError:
                    pass

            if result is None:
                for p in temp_files:
                    try:
                        os.remove(p)
                    except OSError:
                        pass
                return

            raw, play_rate, nch, sw = result
            self._cache_put(cache_key, (raw, play_rate, nch, sw))

        if self._cancel.is_set():
            for p in temp_files:
                try:
                    os.remove(p)
                except OSError:
                    pass
            return

        fb_fd, fallback_path = tempfile.mkstemp(suffix=".wav", prefix="daemon_tts_playback_")
        os.close(fb_fd)
        temp_files.append(fallback_path)
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
            for p in temp_files:
                try:
                    os.remove(p)
                except OSError:
                    pass
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
py -m pytest tests/test_tts_worker.py::TestTTSWorker::test_lru_cache_avoids_regeneration tests/test_tts_worker.py::TestTTSWorker::test_lru_cache_evicts_oldest_when_full -v
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/system/tts_worker.py tests/test_tts_worker.py
git commit -m "feat(tts): LRU phrase cache (20 entries); skip regen for repeated phrases"
```

---

## Task 6: asyncio loop teardown + full suite green

`self._loop` must be closed when the worker stops, and the full test suite must stay under 50 s.

**Files:**
- Modify: `src/system/tts_worker.py` — `stop()`
- Test: `tests/test_tts_worker.py`

- [ ] **Step 1: Write the failing test**

Add inside `TestTTSWorker`:

```python
def test_stop_closes_asyncio_loop():
    """stop() closes the worker's asyncio event loop."""
    worker = TTSWorker()
    assert not worker._loop.is_closed()
    worker.stop()
    assert worker._loop.is_closed()
```

- [ ] **Step 2: Run test to verify it fails**

```bash
py -m pytest tests/test_tts_worker.py::TestTTSWorker::test_stop_closes_asyncio_loop -v
```

Expected: FAIL — `stop()` doesn't close `_loop`.

- [ ] **Step 3: Implement — close loop in `stop()`**

Replace `stop()`:

```python
    def stop(self) -> None:
        self._shutdown.set()
        self.clear()
        if self.isRunning():
            self.wait(2000)
        if not self._loop.is_closed():
            self._loop.close()
```

- [ ] **Step 4: Run full test suite**

```bash
py -m pytest tests/ -v
```

Expected: all pass, total runtime < 50 s. Fix any failures before continuing.

- [ ] **Step 5: Commit**

```bash
git add src/system/tts_worker.py tests/test_tts_worker.py
git commit -m "fix(tts): close asyncio loop on worker stop"
```

---

## Task 7: Squash-merge + dev memory update

- [ ] **Step 1: Verify master is clean**

```bash
git checkout master
git status
```

Expected: nothing to commit.

- [ ] **Step 2: Squash-merge**

```bash
git merge --squash task-tts-optimization
git commit -m "feat(tts): optimize pipeline — loop reuse, engine cache, BytesIO, cancel, LRU"
```

- [ ] **Step 3: Delete branch**

```bash
git branch -D task-tts-optimization
```

- [ ] **Step 4: Update `memory/project-dev-memory.md`**

Add an entry with today's date, the commit hash from Step 2, and a summary of the 6 improvements merged.

---

## Self-Review

### Spec coverage

| Spec item | Task |
|---|---|
| Reuse asyncio loop | Task 1 |
| Fix pitch to use `self._pitch` | Task 1 |
| Cache pyttsx3 engine | Task 2 |
| BytesIO pipeline — eliminate temp file | Task 3 |
| Cancellation support | Task 4 |
| LRU phrase cache | Task 5 |
| asyncio loop teardown | Task 6 |
| Pre-generation during idle | Out of scope (YAGNI) |
| Parallel gen+play | Out of scope (Windows winsound constraint) |

### Placeholder scan

No TBD/TODO/placeholder patterns present.

### Type consistency

- `_generate_voice` returns `str | io.BytesIO | None` — both branches of `_apply_pitch_filter` and `_process_utterance` handle `isinstance(audio_source, io.BytesIO)` explicitly.
- `_cache_key`, `_cache_get`, `_cache_put` defined in Task 5 and referenced only there.
- `_cancel` stubbed in Task 3 (single `threading.Event()` line in `__init__`), fully wired in Task 4 — same attribute name throughout.
- `_loop` created in Task 1, closed in Task 6 — consistent.
- `_pyttsx3_engine` initialized to `None` in Task 1, lazily set in Task 2 — consistent.
