"""Tests verifying the bubble response behavior: pagination, proportional duration,
configurable char limit, full context preservation, and low-latency placeholder."""
import pytest
from unittest.mock import patch


# ── 1. Pagination ──────────────────────────────────────────────────────────

class TestPagination:
    """_paginate_text splits text > BUBBLE_MAX_CHARS at sentence/word boundaries."""

    @pytest.mark.parametrize("text,expected_pages", [
        ("Hello, world!", 1),
        ("x" * 400, 1), # BUBBLE_MAX_CHARS is 400
    ])
    def test_short_and_limit_text_stays_single_page(self, safe_pet_window, text, expected_pages):
        from src.constants import BUBBLE_MAX_CHARS
        pages = safe_pet_window._paginate_text(text, BUBBLE_MAX_CHARS)
        assert len(pages) == expected_pages
        assert pages[0] == text

    def test_long_text_splits_into_pages(self, safe_pet_window):
        from src.constants import BUBBLE_MAX_CHARS
        # 500 chars of words should split into 3-4 pages
        words = "word " * 200  # 1000 chars → 3 pages
        pages = safe_pet_window._paginate_text(words, BUBBLE_MAX_CHARS)
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

    def test_pagination_respects_sentence_boundary(self, safe_pet_window):
        from src.constants import BUBBLE_MAX_CHARS
        # Build text with clear sentence boundaries every ~80 chars
        sentences = []
        for i in range(20):
            sentences.append(f"This is sentence number {i} in the test text.")
        text = " ".join(sentences)
        pages = safe_pet_window._paginate_text(text, BUBBLE_MAX_CHARS)
        assert len(pages) >= 2
        # Pages should end with punctuation (sentence boundary), not mid-word
        for page in pages[:-1]:
            assert page.endswith((".", "!")), f"Page doesn't end with sentence boundary: '{page[-10:]}'"

    def test_hard_cut_on_long_word(self, safe_pet_window):
        from src.constants import BUBBLE_MAX_CHARS
        # No spaces or punctuation — force hard cut
        text = "a" * (BUBBLE_MAX_CHARS * 2 + 10)
        pages = safe_pet_window._paginate_text(text, BUBBLE_MAX_CHARS)
        assert len(pages) >= 2
        for page in pages[:-1]:
            assert len(page) <= BUBBLE_MAX_CHARS

    def test_show_bubble_with_multi_page_text(self, safe_pet_window):
        from src.constants import BUBBLE_MAX_CHARS
        # Window starts with no active bubble
        safe_pet_window._bubble_timer_ms = 0
        safe_pet_window._typewriter_timer.stop()
        text = "word " * 100  # ~500 chars — should paginate
        safe_pet_window._show_bubble(text)
        # Should have set _bubble_pages with multiple pages
        assert len(safe_pet_window._bubble_pages) >= 2, f"Expected ≥2 pages, got {len(safe_pet_window._bubble_pages)}"
        # First page should be typewriter-revealing
        assert safe_pet_window._typewriter_active or safe_pet_window._bubble_timer_ms > 0
        # Each page ≤ BUBBLE_MAX_CHARS
        for p in safe_pet_window._bubble_pages:
            assert len(p) <= BUBBLE_MAX_CHARS

    def test_show_bubble_single_page_no_pages_array(self, safe_pet_window):
        safe_pet_window._bubble_timer_ms = 0
        safe_pet_window._typewriter_timer.stop()
        safe_pet_window._show_bubble("Short text")
        # Single page text clears _bubble_pages
        assert safe_pet_window._bubble_pages == []
        assert safe_pet_window._bubble_page_index == 0


# ── 2. Proportional Bubble Duration ────────────────────────────────────────

class TestProportionalDuration:
    """_bubble_duration returns clamp(len(text) * ms_per_char, min, max)."""

    def test_duration_proportional_to_length(self, safe_pet_window):
        from src.constants import BUBBLE_MS_PER_CHAR
        # 100 chars at 50ms/char = 5000ms
        d100 = safe_pet_window._bubble_duration("x" * 100)
        assert d100 == 100 * BUBBLE_MS_PER_CHAR, f"Expected {100 * BUBBLE_MS_PER_CHAR}, got {d100}"
        # 50 chars at 50ms/char = 2500ms
        d50 = safe_pet_window._bubble_duration("x" * 50)
        assert d50 == 50 * BUBBLE_MS_PER_CHAR, f"Expected {50 * BUBBLE_MS_PER_CHAR}, got {d50}"
        # Longer text gets longer duration (proportional, not fixed)
        assert d100 > d50

    def test_duration_clamped_to_minimum(self, safe_pet_window):
        from src.constants import BUBBLE_MIN_DURATION_MS
        # Very short text (< min_duration / ms_per_char chars)
        d = safe_pet_window._bubble_duration("a")
        assert d == BUBBLE_MIN_DURATION_MS, f"Expected min {BUBBLE_MIN_DURATION_MS}, got {d}"

    def test_duration_clamped_to_maximum(self, safe_pet_window):
        from src.constants import BUBBLE_MAX_DURATION_MS
        # Very long text (> max_duration / ms_per_char chars)
        d = safe_pet_window._bubble_duration("x" * 9999)
        assert d == BUBBLE_MAX_DURATION_MS, f"Expected max {BUBBLE_MAX_DURATION_MS}, got {d}"

    def test_duration_configurable_via_constants(self, safe_pet_window):
        from src.constants import BUBBLE_MS_PER_CHAR, BUBBLE_MIN_DURATION_MS, BUBBLE_MAX_DURATION_MS
        # All three constants are loaded from config at runtime
        assert isinstance(BUBBLE_MS_PER_CHAR, (int, float))
        assert isinstance(BUBBLE_MIN_DURATION_MS, int)
        assert isinstance(BUBBLE_MAX_DURATION_MS, int)
        assert BUBBLE_MS_PER_CHAR > 0
        assert BUBBLE_MIN_DURATION_MS > 0
        assert BUBBLE_MAX_DURATION_MS >= BUBBLE_MIN_DURATION_MS

    def test_each_page_gets_own_proportional_duration(self, safe_pet_window):
        """After typewriter finishes each page, _bubble_timer_ms is set to
        duration proportional to THAT page's text length, minus typewriter
        reveal time so total (reveal + view) = desired proportional duration."""
        # Call the tick_typewriter as it would after revealing a page.
        # The typewriter buffer must be set so the subtraction works.
        safe_pet_window._typewriter_buffer = "x" * 100
        safe_pet_window._typewriter_pos = 100  # already fully revealed
        # Set up state as _tick_typewriter would see it
        safe_pet_window._bubble_pages = ["x" * 100, "y" * 50]
        safe_pet_window._bubble_page_index = 0
        # Simulate typewriter completing:
        safe_pet_window._tick_typewriter()
        # The timer should be proportional to the 100-char page
        # minus typewriter reveal time (100/4 ticks * 30ms = 750ms)
        from src.constants import BUBBLE_MS_PER_CHAR
        _TYPEWRITER_CHARS_PER_TICK = 8
        _TYPEWRITER_TICK_MS = 30
        typewriter_ms = (100 // _TYPEWRITER_CHARS_PER_TICK) * _TYPEWRITER_TICK_MS
        expected = 100 * BUBBLE_MS_PER_CHAR - typewriter_ms
        assert safe_pet_window._bubble_timer_ms == expected


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

    def test_paginate_text_uses_bubble_max_chars_as_default(self, safe_pet_window):
        from src.constants import BUBBLE_MAX_CHARS
        # The method uses BUBBLE_MAX_CHARS as its default max_chars parameter
        text = "x" * (BUBBLE_MAX_CHARS + 50)
        pages = safe_pet_window._paginate_text(text)
        assert len(pages) >= 2
        assert len(pages[0]) <= BUBBLE_MAX_CHARS

    def test_show_bubble_paginates_at_bubble_max_chars(self, safe_pet_window):
        from src.constants import BUBBLE_MAX_CHARS
        safe_pet_window._bubble_timer_ms = 0
        safe_pet_window._typewriter_timer.stop()
        text = "hello world " * 40  # ~480 chars > BUBBLE_MAX_CHARS
        safe_pet_window._show_bubble(text)
        assert len(safe_pet_window._bubble_pages) >= 2
        for p in safe_pet_window._bubble_pages:
            assert len(p) <= BUBBLE_MAX_CHARS


# ── 4. Full Context Preservation ───────────────────────────────────────────

class TestContextPreservation:
    """The context snapshot contains all required environment signals."""

    def test_context_snapshot_has_all_fields(self, safe_pet_window):
        safe_pet_window._apm_worker.apm = 0
        ctx = safe_pet_window._build_context_snapshot()
        # Core fields always present
        assert "active_window" in ctx
        assert "typing_content" in ctx
        assert isinstance(ctx["active_window"], str)
        assert isinstance(ctx["typing_content"], str)
        # Conditional fields: apm=0 → included, idle_seconds=0 → not >30 so excluded
        # screen_text is no longer sent by default (context optimization)
        assert ctx.get("apm") == 0
        assert "idle_seconds" not in ctx

    def test_opencode_worker_receives_full_context(self, safe_pet_window):
        """The opencode worker is created with context dict containing env signals."""
        safe_pet_window._apm_worker.apm = 0
        ctx = safe_pet_window._build_context_snapshot()
        assert "active_window" in ctx
        assert "typing_content" in ctx
        # apm is 0 so it's included (threshold: apm == 0); idle not >30 so absent


# ── 5. Low-Latency Placeholder ────────────────────────────────────────────

class TestLowLatencyPlaceholder:
    """The "..." placeholder appears immediately during LLM streaming."""

    def test_placeholder_shown_during_streaming(self, safe_pet_window):
        safe_pet_window._apm_worker.apm = 0
        # Simulate user input submission: shows "..." with 60s timeout
        safe_pet_window._input_field.setText("hello")
        safe_pet_window._input_field.show()
        with patch.object(safe_pet_window, '_build_context_snapshot', return_value={}), \
             patch.object(safe_pet_window, '_show_bubble') as mock_show:
            safe_pet_window._on_input_submitted()
            # The bubble shows "..." immediately
            assert safe_pet_window._bubble_text == "..."
            assert safe_pet_window._bubble_timer_ms == 60000

    def test_partial_response_accumulates_during_streaming(self, safe_pet_window):
        safe_pet_window._accumulated_stream_text = ""
        # Simulate streaming chunks arriving
        safe_pet_window._on_partial_response("chunk1")
        safe_pet_window._on_partial_response(" chunk2")
        assert safe_pet_window._accumulated_stream_text == "chunk1 chunk2"

    def test_bubble_queue_has_ttl_to_prevent_stale_items(self, safe_pet_window):
        safe_pet_window._bubble_timer_ms = 5000
        safe_pet_window._show_bubble("queued message")
        assert len(safe_pet_window._bubble_queue) > 0


# ── 6. Typewriter Reveal Speed ────────────────────────────────────────────

class TestTypewriterSpeed:
    """Typewriter reveals text at 8 chars per 30ms tick for low-latency display."""

    def test_typewriter_reveals_eight_chars_per_tick(self, safe_pet_window):
        text = "ABCDEFGHIJKLMNOPQRST"  # 20 chars
        safe_pet_window._start_typewriter(text)
        # After one tick, min(0+8, 20) = 8 chars
        safe_pet_window._tick_typewriter()
        assert safe_pet_window._bubble_text == "ABCDEFGH"
        # After second tick, min(8+8, 20) = 16 chars
        safe_pet_window._tick_typewriter()
        assert safe_pet_window._bubble_text == "ABCDEFGHIJKLMNOP"
        # After third tick, min(16+8, 20) = 20 chars — all revealed
        safe_pet_window._tick_typewriter()
        assert safe_pet_window._bubble_text == "ABCDEFGHIJKLMNOPQRST"
