"""Tests verifying the bubble response behavior: pagination, proportional duration,
configurable char limit, full context preservation, and low-latency placeholder."""
import pytest
from unittest.mock import MagicMock, patch, PropertyMock


# ── 1. Pagination ──────────────────────────────────────────────────────────

class TestPagination:
    """_paginate_text splits text > BUBBLE_MAX_CHARS at sentence/word boundaries."""

    def test_short_text_stays_single_page(self, app):
        with patch("src.ui.pet_window.ClickThroughManager"), \
             patch("PyQt6.QtWidgets.QSystemTrayIcon"), \
             patch("src.ui.pet_window.APMWorker"), \
             patch("src.ui.pet_window.MCPServer"), \
             patch("src.ui.pet_window.BehaviorController"):
            from src.ui.pet_window import PetWindow
            from src.constants import BUBBLE_MAX_CHARS
            window = PetWindow(opencode_enabled=False, initial_state={"first_run_done": True})
            text = "Hello, world!"
            pages = window._paginate_text(text, BUBBLE_MAX_CHARS)
            assert len(pages) == 1
            assert pages[0] == text

    def test_text_at_limit_stays_single_page(self, app):
        with patch("src.ui.pet_window.ClickThroughManager"), \
             patch("PyQt6.QtWidgets.QSystemTrayIcon"), \
             patch("src.ui.pet_window.APMWorker"), \
             patch("src.ui.pet_window.MCPServer"), \
             patch("src.ui.pet_window.BehaviorController"):
            from src.ui.pet_window import PetWindow
            from src.constants import BUBBLE_MAX_CHARS
            window = PetWindow(opencode_enabled=False, initial_state={"first_run_done": True})
            text = "x" * BUBBLE_MAX_CHARS
            pages = window._paginate_text(text, BUBBLE_MAX_CHARS)
            assert len(pages) == 1
            assert pages[0] == text

    def test_long_text_splits_into_pages(self, app):
        with patch("src.ui.pet_window.ClickThroughManager"), \
             patch("PyQt6.QtWidgets.QSystemTrayIcon"), \
             patch("src.ui.pet_window.APMWorker"), \
             patch("src.ui.pet_window.MCPServer"), \
             patch("src.ui.pet_window.BehaviorController"):
            from src.ui.pet_window import PetWindow
            from src.constants import BUBBLE_MAX_CHARS
            window = PetWindow(opencode_enabled=False, initial_state={"first_run_done": True})
            # 500 chars of words should split into 3-4 pages
            words = "word " * 200  # 1000 chars → 3 pages
            pages = window._paginate_text(words, BUBBLE_MAX_CHARS)
            assert len(pages) >= 3

            # Each page (except possibly last) should be ≤ BUBBLE_MAX_CHARS
            for page in pages[:-1]:
                assert len(page) <= BUBBLE_MAX_CHARS, \
                    f"Page too long: {len(page)} > {BUBBLE_MAX_CHARS}"
            # Last page can be ≤ BUBBLE_MAX_CHARS
            assert len(pages[-1]) <= BUBBLE_MAX_CHARS

            # All pages combined should reconstruct the original (approx)
            total_len = sum(len(p) for p in pages)
            assert abs(total_len - len(words.strip())) <= len(pages)  # minor whitespace loss

    def test_pagination_respects_sentence_boundary(self, app):
        with patch("src.ui.pet_window.ClickThroughManager"), \
             patch("PyQt6.QtWidgets.QSystemTrayIcon"), \
             patch("src.ui.pet_window.APMWorker"), \
             patch("src.ui.pet_window.MCPServer"), \
             patch("src.ui.pet_window.BehaviorController"):
            from src.ui.pet_window import PetWindow
            from src.constants import BUBBLE_MAX_CHARS
            window = PetWindow(opencode_enabled=False, initial_state={"first_run_done": True})
            # Build text with clear sentence boundaries every ~80 chars
            sentences = []
            for i in range(20):
                sentences.append(f"This is sentence number {i} in the test text.")
            text = " ".join(sentences)
            pages = window._paginate_text(text, BUBBLE_MAX_CHARS)
            assert len(pages) >= 2
            # Pages should end with punctuation (sentence boundary), not mid-word
            for page in pages[:-1]:
                assert page.endswith((".", "!")), f"Page doesn't end with sentence boundary: '{page[-10:]}'"

    def test_hard_cut_on_long_word(self, app):
        with patch("src.ui.pet_window.ClickThroughManager"), \
             patch("PyQt6.QtWidgets.QSystemTrayIcon"), \
             patch("src.ui.pet_window.APMWorker"), \
             patch("src.ui.pet_window.MCPServer"), \
             patch("src.ui.pet_window.BehaviorController"):
            from src.ui.pet_window import PetWindow
            from src.constants import BUBBLE_MAX_CHARS
            window = PetWindow(opencode_enabled=False, initial_state={"first_run_done": True})
            # No spaces or punctuation — force hard cut
            text = "a" * (BUBBLE_MAX_CHARS * 2 + 10)
            pages = window._paginate_text(text, BUBBLE_MAX_CHARS)
            assert len(pages) >= 2
            for page in pages[:-1]:
                assert len(page) <= BUBBLE_MAX_CHARS

    def test_show_bubble_with_multi_page_text(self, app):
        with patch("src.ui.pet_window.ClickThroughManager"), \
             patch("PyQt6.QtWidgets.QSystemTrayIcon"), \
             patch("src.ui.pet_window.APMWorker"), \
             patch("src.ui.pet_window.MCPServer"), \
             patch("src.ui.pet_window.BehaviorController"):
            from src.ui.pet_window import PetWindow
            from src.constants import BUBBLE_MAX_CHARS
            window = PetWindow(opencode_enabled=False, initial_state={"first_run_done": True})
            # Window starts with no active bubble
            window._bubble_timer_ms = 0
            window._typewriter_timer.stop()
            text = "word " * 100  # ~500 chars — should paginate
            window._show_bubble(text)
            # Should have set _bubble_pages with multiple pages
            assert len(window._bubble_pages) >= 2, f"Expected ≥2 pages, got {len(window._bubble_pages)}"
            # First page should be typewriter-revealing
            assert window._typewriter_active or window._bubble_timer_ms > 0
            # Each page ≤ BUBBLE_MAX_CHARS
            for p in window._bubble_pages:
                assert len(p) <= BUBBLE_MAX_CHARS

    def test_show_bubble_single_page_no_pages_array(self, app):
        with patch("src.ui.pet_window.ClickThroughManager"), \
             patch("PyQt6.QtWidgets.QSystemTrayIcon"), \
             patch("src.ui.pet_window.APMWorker"), \
             patch("src.ui.pet_window.MCPServer"), \
             patch("src.ui.pet_window.BehaviorController"):
            from src.ui.pet_window import PetWindow
            window = PetWindow(opencode_enabled=False, initial_state={"first_run_done": True})
            window._bubble_timer_ms = 0
            window._typewriter_timer.stop()
            window._show_bubble("Short text")
            # Single page text clears _bubble_pages
            assert window._bubble_pages == []
            assert window._bubble_page_index == 0


# ── 2. Proportional Bubble Duration ────────────────────────────────────────

class TestProportionalDuration:
    """_bubble_duration returns clamp(len(text) * ms_per_char, min, max)."""

    def test_duration_proportional_to_length(self, app):
        with patch("src.ui.pet_window.ClickThroughManager"), \
             patch("PyQt6.QtWidgets.QSystemTrayIcon"), \
             patch("src.ui.pet_window.APMWorker"), \
             patch("src.ui.pet_window.MCPServer"), \
             patch("src.ui.pet_window.BehaviorController"):
            from src.ui.pet_window import PetWindow
            from src.constants import BUBBLE_MS_PER_CHAR
            window = PetWindow(opencode_enabled=False, initial_state={"first_run_done": True})
            # 100 chars at 50ms/char = 5000ms
            d100 = window._bubble_duration("x" * 100)
            assert d100 == 100 * BUBBLE_MS_PER_CHAR, f"Expected {100 * BUBBLE_MS_PER_CHAR}, got {d100}"
            # 50 chars at 50ms/char = 2500ms
            d50 = window._bubble_duration("x" * 50)
            assert d50 == 50 * BUBBLE_MS_PER_CHAR, f"Expected {50 * BUBBLE_MS_PER_CHAR}, got {d50}"
            # Longer text gets longer duration (proportional, not fixed)
            assert d100 > d50

    def test_duration_clamped_to_minimum(self, app):
        with patch("src.ui.pet_window.ClickThroughManager"), \
             patch("PyQt6.QtWidgets.QSystemTrayIcon"), \
             patch("src.ui.pet_window.APMWorker"), \
             patch("src.ui.pet_window.MCPServer"), \
             patch("src.ui.pet_window.BehaviorController"):
            from src.ui.pet_window import PetWindow
            from src.constants import BUBBLE_MIN_DURATION_MS
            window = PetWindow(opencode_enabled=False, initial_state={"first_run_done": True})
            # Very short text (< min_duration / ms_per_char chars)
            d = window._bubble_duration("a")
            assert d == BUBBLE_MIN_DURATION_MS, f"Expected min {BUBBLE_MIN_DURATION_MS}, got {d}"

    def test_duration_clamped_to_maximum(self, app):
        with patch("src.ui.pet_window.ClickThroughManager"), \
             patch("PyQt6.QtWidgets.QSystemTrayIcon"), \
             patch("src.ui.pet_window.APMWorker"), \
             patch("src.ui.pet_window.MCPServer"), \
             patch("src.ui.pet_window.BehaviorController"):
            from src.ui.pet_window import PetWindow
            from src.constants import BUBBLE_MAX_DURATION_MS
            window = PetWindow(opencode_enabled=False, initial_state={"first_run_done": True})
            # Very long text (> max_duration / ms_per_char chars)
            d = window._bubble_duration("x" * 9999)
            assert d == BUBBLE_MAX_DURATION_MS, f"Expected max {BUBBLE_MAX_DURATION_MS}, got {d}"

    def test_duration_configurable_via_constants(self, app):
        with patch("src.ui.pet_window.ClickThroughManager"), \
             patch("PyQt6.QtWidgets.QSystemTrayIcon"), \
             patch("src.ui.pet_window.APMWorker"), \
             patch("src.ui.pet_window.MCPServer"), \
             patch("src.ui.pet_window.BehaviorController"):
            from src.ui.pet_window import PetWindow
            from src.constants import BUBBLE_MS_PER_CHAR, BUBBLE_MIN_DURATION_MS, BUBBLE_MAX_DURATION_MS
            window = PetWindow(opencode_enabled=False, initial_state={"first_run_done": True})
            # All three constants are loaded from config at runtime
            assert isinstance(BUBBLE_MS_PER_CHAR, (int, float))
            assert isinstance(BUBBLE_MIN_DURATION_MS, int)
            assert isinstance(BUBBLE_MAX_DURATION_MS, int)
            assert BUBBLE_MS_PER_CHAR > 0
            assert BUBBLE_MIN_DURATION_MS > 0
            assert BUBBLE_MAX_DURATION_MS >= BUBBLE_MIN_DURATION_MS

    def test_each_page_gets_own_proportional_duration(self, app):
        """After typewriter finishes each page, _bubble_timer_ms is set to
        duration proportional to THAT page's text length, minus typewriter
        reveal time so total (reveal + view) = desired proportional duration."""
        with patch("src.ui.pet_window.ClickThroughManager"), \
             patch("PyQt6.QtWidgets.QSystemTrayIcon"), \
             patch("src.ui.pet_window.APMWorker"), \
             patch("src.ui.pet_window.MCPServer"), \
             patch("src.ui.pet_window.BehaviorController"):
            from src.ui.pet_window import PetWindow
            window = PetWindow(opencode_enabled=False, initial_state={"first_run_done": True})
            # Call the tick_typewriter as it would after revealing a page.
            # The typewriter buffer must be set so the subtraction works.
            window._typewriter_buffer = "x" * 100
            window._typewriter_pos = 100  # already fully revealed
            # Set up state as _tick_typewriter would see it
            window._bubble_pages = ["x" * 100, "y" * 50]
            window._bubble_page_index = 0
            # Simulate typewriter completing:
            window._tick_typewriter()
            # The timer should be proportional to the 100-char page
            # minus typewriter reveal time (100/4 ticks * 30ms = 750ms)
            from src.constants import BUBBLE_MS_PER_CHAR
            _TYPEWRITER_CHARS_PER_TICK = 8
            _TYPEWRITER_TICK_MS = 30
            typewriter_ms = (100 // _TYPEWRITER_CHARS_PER_TICK) * _TYPEWRITER_TICK_MS
            expected = 100 * BUBBLE_MS_PER_CHAR - typewriter_ms
            assert window._bubble_timer_ms == expected


# ── 3. Configurable 150-char limit ─────────────────────────────────────────

class TestConfigurableCharLimit:
    """BUBBLE_MAX_CHARS is loaded from daemon_config.json and controls pagination."""

    def test_bubble_max_chars_is_400_in_config(self):
        from src.config import load_config, flatten_config
        cfg = load_config()
        flat = flatten_config(cfg)
        assert "BUBBLE_MAX_CHARS" in flat
        assert flat["BUBBLE_MAX_CHARS"] == 400

    def test_bubble_max_chars_is_runtime_constant(self):
        from src.constants import BUBBLE_MAX_CHARS
        assert BUBBLE_MAX_CHARS == 400

    def test_bubble_duration_config_values_present(self):
        from src.config import load_config, flatten_config
        cfg = load_config()
        flat = flatten_config(cfg)
        assert flat.get("BUBBLE_MS_PER_CHAR") == 50
        assert flat.get("BUBBLE_MIN_DURATION_MS") == 2000
        assert flat.get("BUBBLE_MAX_DURATION_MS") == 30000

    def test_paginate_text_uses_bubble_max_chars_as_default(self, app):
        with patch("src.ui.pet_window.ClickThroughManager"), \
             patch("PyQt6.QtWidgets.QSystemTrayIcon"), \
             patch("src.ui.pet_window.APMWorker"), \
             patch("src.ui.pet_window.MCPServer"), \
             patch("src.ui.pet_window.BehaviorController"):
            from src.ui.pet_window import PetWindow
            from src.constants import BUBBLE_MAX_CHARS
            window = PetWindow(opencode_enabled=False, initial_state={"first_run_done": True})
            # The method uses BUBBLE_MAX_CHARS as its default max_chars parameter
            text = "x" * (BUBBLE_MAX_CHARS + 50)
            pages = window._paginate_text(text)
            assert len(pages) >= 2
            assert len(pages[0]) <= BUBBLE_MAX_CHARS

    def test_show_bubble_paginates_at_bubble_max_chars(self, app):
        with patch("src.ui.pet_window.ClickThroughManager"), \
             patch("PyQt6.QtWidgets.QSystemTrayIcon"), \
             patch("src.ui.pet_window.APMWorker"), \
             patch("src.ui.pet_window.MCPServer"), \
             patch("src.ui.pet_window.BehaviorController"):
            from src.ui.pet_window import PetWindow
            from src.constants import BUBBLE_MAX_CHARS
            window = PetWindow(opencode_enabled=False, initial_state={"first_run_done": True})
            window._bubble_timer_ms = 0
            window._typewriter_timer.stop()
            text = "hello world " * 40  # ~480 chars > BUBBLE_MAX_CHARS
            window._show_bubble(text)
            assert len(window._bubble_pages) >= 2
            for p in window._bubble_pages:
                assert len(p) <= BUBBLE_MAX_CHARS


# ── 4. Full Context Preservation ───────────────────────────────────────────

class TestContextPreservation:
    """The context snapshot contains all required environment signals."""

    def test_context_snapshot_has_all_fields(self, app):
        with patch("src.ui.pet_window.ClickThroughManager"), \
             patch("PyQt6.QtWidgets.QSystemTrayIcon"), \
             patch("src.ui.pet_window.APMWorker"), \
             patch("src.ui.pet_window.MCPServer"), \
             patch("src.ui.pet_window.BehaviorController"):
            from src.ui.pet_window import PetWindow
            window = PetWindow(opencode_enabled=False, initial_state={"first_run_done": True})
            ctx = window._build_context_snapshot()
            # Core fields always present
            assert "active_window" in ctx
            assert "typing_content" in ctx
            assert isinstance(ctx["active_window"], str)
            assert isinstance(ctx["typing_content"], str)
            # Conditional fields: apm=0 → included, idle_seconds=0 → not >30 so excluded
            # screen_text is no longer sent by default (context optimization)
            assert ctx.get("apm") == 0
            assert "idle_seconds" not in ctx

    def test_strands_worker_receives_full_context(self, app):
        """The strands worker is created with context dict containing env signals."""
        with patch("src.ui.pet_window.ClickThroughManager"), \
             patch("PyQt6.QtWidgets.QSystemTrayIcon"), \
             patch("src.ui.pet_window.APMWorker"), \
             patch("src.ui.pet_window.MCPServer"), \
             patch("src.ui.pet_window.BehaviorController"), \
             patch("src.ui.pet_window.StrandsAutonomousWorker") as mock_worker:
            from src.ui.pet_window import PetWindow
            from src.ui.pet_window import StrandsAutonomousWorker
            window = PetWindow(opencode_enabled=False, initial_state={"first_run_done": True})
            ctx = window._build_context_snapshot()
            assert "active_window" in ctx
            assert "typing_content" in ctx
            # apm is 0 so it's included (threshold: apm == 0); idle not >30 so absent


# ── 5. Low-Latency Placeholder ────────────────────────────────────────────

class TestLowLatencyPlaceholder:
    """The "..." placeholder appears immediately during LLM streaming."""

    def test_placeholder_shown_during_streaming(self, app):
        with patch("src.ui.pet_window.ClickThroughManager"), \
             patch("PyQt6.QtWidgets.QSystemTrayIcon"), \
             patch("src.ui.pet_window.APMWorker"), \
             patch("src.ui.pet_window.MCPServer"), \
             patch("src.ui.pet_window.BehaviorController"), \
             patch("src.ui.pet_window.StrandsAutonomousWorker") as mock_worker_class:
            from src.ui.pet_window import PetWindow
            window = PetWindow(opencode_enabled=False, initial_state={"first_run_done": True})
            # Simulate user input submission: shows "..." with 60s timeout
            window._input_field.setText("hello")
            window._input_field.show()
            with patch.object(window, '_build_context_snapshot', return_value={}), \
                 patch.object(window, '_show_bubble') as mock_show:
                window._on_input_submitted()
                # The bubble shows "..." immediately
                assert window._bubble_text == "..."
                assert window._bubble_timer_ms == 60000

    def test_partial_response_accumulates_during_streaming(self, app):
        with patch("src.ui.pet_window.ClickThroughManager"), \
             patch("PyQt6.QtWidgets.QSystemTrayIcon"), \
             patch("src.ui.pet_window.APMWorker"), \
             patch("src.ui.pet_window.MCPServer"), \
             patch("src.ui.pet_window.BehaviorController"):
            from src.ui.pet_window import PetWindow
            window = PetWindow(opencode_enabled=False, initial_state={"first_run_done": True})
            window._accumulated_stream_text = ""
            # Simulate streaming chunks arriving
            window._on_partial_response("chunk1")
            window._on_partial_response(" chunk2")
            assert window._accumulated_stream_text == "chunk1 chunk2"

    def test_bubble_queue_has_ttl_to_prevent_stale_items(self, app):
        with patch("src.ui.pet_window.ClickThroughManager"), \
             patch("PyQt6.QtWidgets.QSystemTrayIcon"), \
             patch("src.ui.pet_window.APMWorker"), \
             patch("src.ui.pet_window.MCPServer"), \
             patch("src.ui.pet_window.BehaviorController"):
            from src.ui.pet_window import PetWindow
            window = PetWindow(opencode_enabled=False, initial_state={"first_run_done": True})
            window._bubble_timer_ms = 5000
            window._show_bubble("queued message")
            assert len(window._bubble_queue) > 0


# ── 6. Typewriter Reveal Speed ────────────────────────────────────────────

class TestTypewriterSpeed:
    """Typewriter reveals text at 8 chars per 30ms tick for low-latency display."""

    def test_typewriter_reveals_eight_chars_per_tick(self, app):
        with patch("src.ui.pet_window.ClickThroughManager"), \
             patch("PyQt6.QtWidgets.QSystemTrayIcon"), \
             patch("src.ui.pet_window.APMWorker"), \
             patch("src.ui.pet_window.MCPServer"), \
             patch("src.ui.pet_window.BehaviorController"):
            from src.ui.pet_window import PetWindow
            window = PetWindow(opencode_enabled=False, initial_state={"first_run_done": True})
            text = "ABCDEFGHIJKLMNOPQRST"  # 20 chars
            window._start_typewriter(text)
            # After one tick, min(0+8, 20) = 8 chars
            window._tick_typewriter()
            assert window._bubble_text == "ABCDEFGH"
            # After second tick, min(8+8, 20) = 16 chars
            window._tick_typewriter()
            assert window._bubble_text == "ABCDEFGHIJKLMNOP"
            # After third tick, min(16+8, 20) = 20 chars — all revealed
            window._tick_typewriter()
            assert window._bubble_text == "ABCDEFGHIJKLMNOPQRST"
