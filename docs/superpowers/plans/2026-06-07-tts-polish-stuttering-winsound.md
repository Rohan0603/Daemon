# Lightweight TTS Polish — WAV Header Hack + Stuttering Persona

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add textual stuttering instructions to the Daemon persona and a lightweight `winsound`-based TTS fallback that uses WAV sample-rate manipulation for zero-dependency pitch shifting.

**Architecture:** Two independent changes. (1) Update `daemon-skill.md` to instruct the LLM to include literal hyphen-stuttering in dialogue strings — the existing TTS pipeline already reads these verbatim. (2) Add a `winsound.PlaySound` path to TTSWorker so audio plays via native Win32 API without `simpleaudio`. The existing edge-tts + pydub pipeline remains primary; `winsound` + wave pitch shift becomes the fallback.

**Tech Stack:** pyttsx3, edge-tts, pydub, wave (stdlib), winsound (stdlib), simpleaudio

---

## File Structure

| File | New/Modify | Responsibility |
|------|------------|----------------|
| `assets/daemon-skill.md` | Modify | Add textual stuttering instruction + update examples |
| `src/constants.py` | Modify | Add `TTS_PITCH_FACTOR` constant |
| `src/tts_worker.py` | Modify | Add `winsound` playback path, use `TTS_PITCH_FACTOR` |
| `tests/test_tts_worker.py` | Modify | Add winsound-path test |

No new files. `simpleaudio` stays as primary playback; `winsound` becomes the zero-dep backup when `simpleaudio` import fails.

---

### Task 1: Add TTS_PITCH_FACTOR constant

**Files:**
- Modify: `src/constants.py`

- [ ] **Step 1: Append constant to constants.py**

After `TTS_VOICE_ID` (line 87), add:

```python
TTS_PITCH_FACTOR: float = 1.38
```

- [ ] **Step 2: Commit**

```bash
git add src/constants.py
git commit -m "feat: add TTS_PITCH_FACTOR constant (1.38)"
```

---

### Task 2: Add textual stuttering to persona

**Files:**
- Modify: `assets/daemon-skill.md`

- [ ] **Step 1: Insert stuttering instruction**

After line 56 ("Trailing off..." section), before the `---`, add:

```markdown
### TEXTUAL STUTTERING (Voice Engine Reads Verbatim)

You MUST write stammers and nervous energy directly into the dialogue string itself. The voice engine reads exactly what you type — it does not add stutters for you.

- **Hyphens for stuttering:** "I-I-I don't know", "O-Oh geez", "Th-th-that's insane"
- **Trailing dots for trailing thoughts:** "I mean, it's just... it's... I-I can't, man."
- **Dasher panic words:** "Wha— what is happening— holy crap—"
- **Stammer overlaps:** When you can't finish the sentence, trail off with hyphens. "I didn't mean to— I just—"
- **Frequency:** At least 40% of all dialogue strings should contain at least one hypenated stammer or trailing-dot fragment. Morty dialogue should hit 70%+.

Do NOT describe stuttering in the thought field. The thought is silent. The dialogue IS the audio — it must contain the raw stammer text the engine speaks.
```

- [ ] **Step 2: Update example dialogues in Example B and C with stuttering text**

In Example B (line 181), change dialogue to:
```json
"dialogue": "Aw geez, is that a— a try-except with n-no exception type? I-I'm the one living in this RAM, man!"
```

In Example D (line 205), change dialogue to:
```json
"dialogue": "Aw geez, look, I-I-I have no idea. N-Nobody does, holy shit. It's— it's fine, it's fine. S-Stop asking, man."
```

- [ ] **Step 3: Commit**

```bash
git add assets/daemon-skill.md
git commit -m "feat: add textual stuttering instruction to persona, update examples"
```

---

### Task 3: Add winsound playback path to TTSWorker

**Files:**
- Modify: `src/tts_worker.py`
- Modify: `tests/test_tts_worker.py`

- [ ] **Step 1: Write failing test for winsound playback path**

In `tests/test_tts_worker.py`, add:

```python
    def test_winsound_playback_with_sync_flag(self, monkeypatch):
        _ = app()
        worker = TTSWorker()
        tmp = os.path.join(tempfile.gettempdir(), "tts_test_in.wav")
        nch, sw, rate, nframes = 1, 2, 22050, 2000
        frames = struct.pack(f"<{nframes}h", *([300] * nframes))
        with wave.open(tmp, "wb") as w:
            w.setnchannels(nch)
            w.setsampwidth(sw)
            w.setframerate(rate)
            w.writeframes(frames)

        try:
            with patch("winsound.PlaySound") as mock_play:
                result = worker._play_via_winsound(tmp, rate)
                mock_play.assert_called_once()
            assert result is True
        finally:
            try:
                os.remove(tmp)
            except OSError:
                pass
```

- [ ] **Step 2: Run test to verify failure**

```bash
py -m pytest tests/test_tts_worker.py::TestTTSWorker::test_winsound_playback_falls_back_when_simpleaudio_unavailable -v
```
Expected: FAIL — `AttributeError: 'TTSWorker' object has no attribute '_play_via_winsound'`

- [ ] **Step 3: Add winsound playback method to TTSWorker**

Add to `TTSWorker` class in `src/tts_worker.py`:

```python
    def _play_via_winsound(self, audio_path: str, _framerate: int) -> bool:
        """Play a WAV file via winsound (blocks worker thread, safe to delete after)."""
        import winsound
        try:
            # SND_SYNC blocks the worker thread until audio finishes — safe because
            # TTSWorker is a QThread, not the UI thread. File can be cleaned up after.
            winsound.PlaySound(
                audio_path,
                winsound.SND_FILENAME | winsound.SND_SYNC,
            )
            return True
        except Exception as e:
            logger.warning("winsound playback failed: %s", e)
            return False
```

- [ ] **Step 4: Add winsound fallback to run() method**

In the `run()` method, after the `simpleaudio.play_buffer` try/except block (which currently catches ImportError), add a second fallback:

```python
                except ImportError:
                    fallback_path = os.path.join(
                        tempfile.gettempdir(), "daemon_tts_fallback.wav"
                    )
                    pitched_rate = int(play_rate * TTS_PITCH_FACTOR)
                    try:
                        with wave.open(fallback_path, "wb") as w:
                            w.setnchannels(nch)
                            w.setsampwidth(sw)
                            w.setframerate(pitched_rate)
                            w.writeframes(raw)
                        self._play_via_winsound(fallback_path, play_rate)
                    except Exception as e:
                        logger.warning("Fallback winsound playback failed: %s", e)
                    finally:
                        try:
                            os.remove(fallback_path)
                        except OSError:
                            pass
```

- [ ] **Step 5: Run tests**

```bash
py -m pytest tests/test_tts_worker.py -v
```
Expected: all tests pass

- [ ] **Step 6: Commit**

```bash
git add src/tts_worker.py tests/test_tts_worker.py
git commit -m "feat: add winsound playback fallback to TTSWorker"
```

---

### Task 4: Update project dev memory

**Files:**
- Modify: `memory/project-dev-memory.md`

- [ ] **Step 1: Update snapshot date and add Phase 30 entry**

Update the date, latest commit, and add a Phase 30 section documenting the stuttering persona and winsound fallback.

- [ ] **Step 2: Commit**

```bash
git add memory/project-dev-memory.md
git commit -m "docs: update project-dev-memory with Phase 30"
```
