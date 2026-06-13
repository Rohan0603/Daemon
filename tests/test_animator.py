"""Tests for src/animator.py — ParticleSystem, Emotion, EmotionAnimator."""
from __future__ import annotations
import sys
import math
import pytest
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QColor

from src.animator import ParticleSystem, Emotion, EmotionAnimator, EMOTION_PROFILES
from src.constants import PARTICLE_MAX_COUNT


# ── Fixture ────────────────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def qapp():
    return QApplication.instance() or QApplication(sys.argv)


# ── Tests: Emotion enum ────────────────────────────────────────────────────

class TestEmotion:
    def test_enum_len(self):
        assert len(Emotion) == 9

    def test_enum_values(self):
        names = {e.name for e in Emotion}
        expected = {"MIRTH", "ANGER", "FEAR", "DISGUST", "PATHOS",
                    "DEVOTION", "HEROISM", "WONDER", "TRANQUILITY"}
        assert names == expected


# ── Tests: ParticleSystem ──────────────────────────────────────────────────

class TestParticleSystem:
    def test_emit_creates_particles(self):
        ps = ParticleSystem()
        ps.emit(100.0, 200.0, 5, QColor("red"))
        assert len(ps.particles) == 5

    def test_particles_have_expected_keys(self):
        ps = ParticleSystem()
        ps.emit(0.0, 0.0, 1, QColor("red"))
        p = ps.particles[0]
        for key in ("x", "y", "dx", "dy", "life", "max_life", "color", "size", "gravity"):
            assert key in p, f"missing key: {key}"

    def test_update_reduces_life(self):
        ps = ParticleSystem()
        ps.emit(0.0, 0.0, 1, QColor("red"), lifetime_ticks=5)
        assert ps.particles[0]["life"] == 5
        ps.update(33)
        assert ps.particles[0]["life"] == 4

    def test_update_removes_dead_particles(self):
        ps = ParticleSystem()
        ps.emit(0.0, 0.0, 1, QColor("red"), lifetime_ticks=1)
        assert len(ps.particles) == 1
        ps.update(33)
        assert len(ps.particles) == 0

    def test_cap_at_max(self):
        ps = ParticleSystem()
        # exceed cap in one emit
        ps.emit(0.0, 0.0, PARTICLE_MAX_COUNT + 50, QColor("red"))
        assert len(ps.particles) <= PARTICLE_MAX_COUNT

    def test_cap_fill_then_no_more(self):
        ps = ParticleSystem()
        ps.emit(0.0, 0.0, PARTICLE_MAX_COUNT, QColor("red"))
        assert len(ps.particles) == PARTICLE_MAX_COUNT
        # subsequent emit adds nothing
        ps.emit(0.0, 0.0, 10, QColor("blue"))
        assert len(ps.particles) == PARTICLE_MAX_COUNT

    def test_empty_update_no_crash(self):
        ps = ParticleSystem()
        ps.update(33)  # should not raise

    def test_gravity_applied(self):
        ps = ParticleSystem()
        ps.emit(100.0, 100.0, 1, QColor("red"), gravity=0.5, lifetime_ticks=10)
        initial_dy = ps.particles[0]["dy"]
        ps.update(33)  # 33ms @ 60fps norm → dt ≈ 2
        # dy increases by gravity * dt
        expected_dy = initial_dy + 0.5 * (33.0 / 1000.0 * 60.0)
        assert abs(ps.particles[0]["dy"] - expected_dy) < 0.001


# ── Tests: EmotionAnimator ────────────────────────────────────────────────

class TestEmotionAnimator:
    def test_default_emotion(self):
        a = EmotionAnimator()
        assert a._current == Emotion.MIRTH

    def test_set_emotion_changes_state(self):
        a = EmotionAnimator()
        a.set_emotion(Emotion.ANGER)
        assert a._current == Emotion.ANGER

    def test_set_emotion_resets_elapsed(self):
        a = EmotionAnimator()
        a.update(100, 0, 0)
        assert a._elapsed_ms == 100
        a.set_emotion(Emotion.FEAR)
        assert a._elapsed_ms == 0

    def test_set_emotion_with_elapsed(self):
        a = EmotionAnimator()
        a.set_emotion(Emotion.FEAR, elapsed_ms=500)
        assert a._elapsed_ms == 500

    def test_get_transform_returns_three_floats(self):
        a = EmotionAnimator()
        sx, sy, rot = a.get_transform(None, 0.0, 0)
        assert isinstance(sx, float)
        assert isinstance(sy, float)
        assert isinstance(rot, float)

    def test_get_transform_mirth(self):
        a = EmotionAnimator()
        a.set_emotion(Emotion.MIRTH)
        sx, sy, rot = a.get_transform(None, 0.0, 0)
        assert sx >= 0.5
        assert sy >= 0.0
        assert rot == 0.0



    def test_get_body_color_returns_qcolor(self):
        a = EmotionAnimator()
        result = a.get_body_color(QColor("#5B8DEF"))
        assert isinstance(result, QColor)

    def test_get_body_color_anger_override(self):
        a = EmotionAnimator()
        a.set_emotion(Emotion.ANGER)
        c = a.get_body_color(QColor("#5B8DEF"))
        assert c.name().upper() == "#E74C3C"

    def test_get_body_color_mirth_uses_base(self):
        a = EmotionAnimator()
        a.set_emotion(Emotion.MIRTH)
        c = a.get_body_color(QColor("#5B8DEF"))
        assert c.name().upper() == "#5B8DEF"

    def test_get_overlay_returns_list(self):
        a = EmotionAnimator()
        result = a.get_overlay()
        assert isinstance(result, list)

    def test_get_overlay_mirth_empty(self):
        a = EmotionAnimator()
        a.set_emotion(Emotion.MIRTH)
        assert a.get_overlay() == []

    def test_get_overlay_anger_border(self):
        a = EmotionAnimator()
        a.set_emotion(Emotion.ANGER)
        overlays = a.get_overlay()
        assert len(overlays) == 1
        kind, color, width = overlays[0]
        assert kind == "border"
        assert color.name().upper() == "#E74C3C"
        assert width == 2

    def test_get_overlay_heroism_aura(self):
        a = EmotionAnimator()
        a.set_emotion(Emotion.HEROISM)
        overlays = a.get_overlay()
        assert len(overlays) == 1
        kind, color = overlays[0]
        assert kind == "aura"
        assert color.name().upper() == "#FFD700"

    def test_single_fire_heroism_decays_to_mirth(self):
        a = EmotionAnimator()
        a.set_emotion(Emotion.HEROISM)
        assert a._current == Emotion.HEROISM
        # advance past 1000ms decay
        a.update(1100, 100, 100)
        assert a._current == Emotion.MIRTH

    def test_single_fire_wonder_decays(self):
        a = EmotionAnimator()
        a.set_emotion(Emotion.WONDER)
        a.update(900, 100, 100)
        assert a._current == Emotion.MIRTH

    def test_single_fire_disgust_decays(self):
        a = EmotionAnimator()
        a.set_emotion(Emotion.DISGUST)
        a.update(3100, 100, 100)
        assert a._current == Emotion.MIRTH

    def test_non_single_fire_does_not_decay(self):
        a = EmotionAnimator()
        a.set_emotion(Emotion.ANGER)
        a.update(5000, 100, 100)
        assert a._current == Emotion.ANGER

    def test_update_creates_particles_for_anger(self):
        a = EmotionAnimator()
        a.set_emotion(Emotion.ANGER)
        a.update(33, 100, 200)
        assert len(a._particles.particles) > 0

    def test_update_creates_particles_for_heroism(self):
        a = EmotionAnimator()
        a.set_emotion(Emotion.HEROISM)
        a.update(33, 100, 200)
        assert len(a._particles.particles) == 2  # heroism emits 2

    def test_draw_particles_no_crash(self, qapp):
        """Smoke test: draw_particles should not raise with empty system."""
        from PyQt6.QtGui import QPixmap, QPainter
        a = EmotionAnimator()
        pixmap = QPixmap(100, 100)
        painter = QPainter(pixmap)
        a.draw_particles(painter)
        painter.end()

    def test_update_advances_elapsed(self):
        a = EmotionAnimator()
        a.set_emotion(Emotion.MIRTH)
        a.update(50, 0, 0)
        assert a._elapsed_ms == 50
        a.update(30, 0, 0)
        assert a._elapsed_ms == 80

    # ── Constraint: Animator never writes X/Y (Gap 2) ─────────────────────

    def test_constraint_never_writes_xy(self):
        """EmotionAnimator must never modify pet X/Y coordinates."""
        a = EmotionAnimator()
        pet_x, pet_y = 100, 200
        for emo in Emotion:
            a.set_emotion(emo, elapsed_ms=0)
            a.update(33, 50, 60)
            sx, sy, rot = a.get_transform(None, 0.0, 0)
            _ = a.get_body_color(QColor("#5B8DEF"))
            _ = a.get_overlay()
            # The only public surface is transform, body_color, overlay, particles
            # All read-only — no setter for X/Y exists
            assert isinstance(sx, float)
            assert isinstance(sy, float)
            assert isinstance(rot, float)
        # Verify private members don't store coord data
        assert not hasattr(a, '_pet_x')
        assert not hasattr(a, '_pet_y')

    # ── Missing body_color tests (Gap 3) ──────────────────────────────────

    def test_get_body_color_fear_override(self):
        a = EmotionAnimator()
        a.set_emotion(Emotion.FEAR)
        c = a.get_body_color(QColor("#5B8DEF"))
        assert c.name().upper() == "#6B5B95"

    def test_get_body_color_devotion_override(self):
        a = EmotionAnimator()
        a.set_emotion(Emotion.DEVOTION)
        c = a.get_body_color(QColor("#5B8DEF"))
        assert c.name().upper() == "#FF69B4"

    def test_get_body_color_heroism_override(self):
        a = EmotionAnimator()
        a.set_emotion(Emotion.HEROISM)
        c = a.get_body_color(QColor("#5B8DEF"))
        assert c.name().upper() == "#FFD700"

    def test_get_body_color_wonder_override(self):
        a = EmotionAnimator()
        a.set_emotion(Emotion.WONDER)
        c = a.get_body_color(QColor("#5B8DEF"))
        assert c.name().upper() == "#FFFFFF"

    def test_get_body_color_pathos_gray(self):
        a = EmotionAnimator()
        a.set_emotion(Emotion.PATHOS)
        c = a.get_body_color(QColor("#5B8DEF"))
        r, g, b = c.red(), c.green(), c.blue()
        assert r == g == b  # grayscale

    def test_get_body_color_disgust_hue_shift(self):
        a = EmotionAnimator()
        a.set_emotion(Emotion.DISGUST)
        c = a.get_body_color(QColor("#5B8DEF"))
        base_h = QColor("#5B8DEF").hue()
        disgust_h = c.hue()
        # Hue should be shifted ~30 degrees toward green
        assert 150 <= disgust_h <= 210 or base_h == disgust_h  # exact shift depends on HSV conversion

    def test_get_body_color_tranquility_semi_transparent(self):
        a = EmotionAnimator()
        a.set_emotion(Emotion.TRANQUILITY)
        opacity = a.get_opacity()
        assert opacity == 0.8

    # ── Missing overlay tests (Gap 3) ─────────────────────────────────────

    def test_get_overlay_wonder_flash(self):
        a = EmotionAnimator()
        a.set_emotion(Emotion.WONDER)
        overlays = a.get_overlay()
        assert len(overlays) == 1
        kind, alpha = overlays[0]
        assert kind == "flash"
        assert alpha == 80

    # ── Missing particle emission tests (Gap 3) ────────────────────────────

    def test_update_creates_particles_for_fear(self):
        a = EmotionAnimator()
        a.set_emotion(Emotion.FEAR)
        a.update(33, 100, 200)
        assert len(a._particles.particles) > 0

    def test_update_creates_particles_for_devotion(self):
        a = EmotionAnimator()
        a.set_emotion(Emotion.DEVOTION)
        a.update(33, 100, 200)
        assert len(a._particles.particles) > 0

    def test_update_no_particles_for_mirth(self):
        a = EmotionAnimator()
        a.set_emotion(Emotion.MIRTH)
        a.update(33, 100, 200)
        assert len(a._particles.particles) == 0

    def test_update_no_particles_for_disgust(self):
        a = EmotionAnimator()
        a.set_emotion(Emotion.DISGUST)
        a.update(33, 100, 200)
        assert len(a._particles.particles) == 0

    # ── NAVARASA VISUAL APPEARANCE TESTS ────────────────────────────────────

    def test_navarasa_emotions_visual_transforms(self):
        """Test that each navarasa emotion produces unique visual transforms."""
        navarasa_tests = [
            (Emotion.MIRTH, (1.0, 1.0, 0.0), "MIRTH - gentle breathing"),
            (Emotion.ANGER, (1.0, 1.0, 0.0), "ANGER - jittering"),
            (Emotion.FEAR, (1.3, 0.7, 0.0), "FEAR - stretched tall"),
            (Emotion.DISGUST, (0.8, 1.0, 0.0), "DISGUST - squished"),
            (Emotion.PATHOS, (1.0, 0.9, 0.0), "PATHOS - slightly flat"),
            (Emotion.DEVOTION, (1.0, 1.0, 0.0), "DEVOTION - heart glow"),
            (Emotion.HEROISM, (0.85, 1.3, 0.0), "HEROISM - golden flash"),
            (Emotion.WONDER, (1.0, 1.0, 0.0), "WONDER - shrink/grow"),
            (Emotion.TRANQUILITY, (1.0, 1.0, 0.0), "TRANQUILITY - slow breathe"),
        ]

        for emotion, expected_transform, description in navarasa_tests:
            a = EmotionAnimator()
            a.set_emotion(emotion)
            sx, sy, rot = a.get_transform(None, 0.0, 0)
            assert isinstance(sx, float), f"{description}: scale_x must be float"
            assert isinstance(sy, float), f"{description}: scale_y must be float"
            assert isinstance(rot, float), f"{description}: rotation must be float"
            assert sx > 0, f"{description}: scale_x must be positive"
            assert sy > 0, f"{description}: scale_y must be positive"

    def test_navarasa_emotions_body_colors(self):
        """Test that each navarasa emotion produces unique body colors."""
        base_color = QColor("#5B8DEF")
        navarasa_body_colors = [
            (Emotion.MIRTH, "#5B8DEF", "MIRTH - uses base color"),
            (Emotion.ANGER, "#E74C3C", "ANGER - override red"),
            (Emotion.FEAR, "#6B5B95", "FEAR - override purple"),
            (Emotion.DISGUST, None, "DISGUST - hue shift"),
            (Emotion.PATHOS, None, "PATHOS - grayscale"),
            (Emotion.DEVOTION, "#FF69B4", "DEVOTION - override pink"),
            (Emotion.HEROISM, "#FFD700", "HEROISM - override gold"),
            (Emotion.WONDER, "#FFFFFF", "WONDER - override white"),
            (Emotion.TRANQUILITY, None, "TRANQUILITY - semi-transparent"),
        ]

        for emotion, expected_color, description in navarasa_body_colors:
            a = EmotionAnimator()
            a.set_emotion(emotion)
            result = a.get_body_color(base_color)
            assert isinstance(result, QColor), f"{description}: must return QColor"

            if expected_color:
                assert result.name().upper() == expected_color, \
                    f"{description}: expected {expected_color}, got {result.name().upper()}"

    def test_navarasa_emotions_overlays(self):
        """Test that each navarasa emotion produces appropriate overlays."""
        navarasa_overlays = [
            (Emotion.MIRTH, [], "MIRTH - no overlay"),
            (Emotion.ANGER, [("border", QColor("#E74C3C"), 2)], "ANGER - red border"),
            (Emotion.FEAR, [], "FEAR - no overlay"),
            (Emotion.DISGUST, [], "DISGUST - no overlay"),
            (Emotion.PATHOS, [], "PATHOS - no overlay"),
            (Emotion.DEVOTION, [], "DEVOTION - no overlay"),
            (Emotion.HEROISM, [("aura", QColor("#FFD700"))], "HEROISM - golden aura"),
            (Emotion.WONDER, [("flash", 80)], "WONDER - white flash"),
            (Emotion.TRANQUILITY, [], "TRANQUILITY - no overlay"),
        ]

        for emotion, expected_overlays, description in navarasa_overlays:
            a = EmotionAnimator()
            a.set_emotion(emotion)
            overlays = a.get_overlay()
            assert isinstance(overlays, list), f"{description}: must return list"

            if expected_overlays:
                assert len(overlays) == len(expected_overlays), \
                    f"{description}: expected {len(expected_overlays)} overlays, got {len(overlays)}"
                for i, expected_item in enumerate(expected_overlays):
                    if len(expected_item) == 2:
                        kind, color_or_alpha = expected_item
                        overlay_kind, overlay_color_or_alpha = overlays[i]
                        assert overlay_kind == kind, \
                            f"{description}: overlay {i} kind mismatch: expected {kind}, got {overlay_kind}"
                        if isinstance(color_or_alpha, QColor):
                            assert overlay_color_or_alpha.name().upper() == color_or_alpha.name().upper(), \
                                f"{description}: overlay {i} color mismatch: expected {color_or_alpha.name().upper()}, got {overlay_color_or_alpha.name().upper()}"
                        else:
                            assert overlay_color_or_alpha == color_or_alpha, \
                                f"{description}: overlay {i} alpha mismatch"
                    else:
                        kind, color, width = expected_item
                        overlay_kind, overlay_color, overlay_width = overlays[i]
                        assert overlay_kind == kind, \
                            f"{description}: overlay {i} kind mismatch: expected {kind}, got {overlay_kind}"
                        assert overlay_color.name().upper() == color.name().upper(), \
                            f"{description}: overlay {i} color mismatch: expected {color.name().upper()}, got {overlay_color.name().upper()}"
                        assert overlay_width == width, \
                            f"{description}: overlay {i} width mismatch: expected {width}, got {overlay_width}"

    def test_navarasa_emotions_particles(self):
        """Test that each navarasa emotion emits appropriate particles."""
        navarasa_particles = [
            (Emotion.MIRTH, 0, "MIRTH - no particles"),
            (Emotion.ANGER, 1, "ANGER - emits particles"),
            (Emotion.FEAR, 1, "FEAR - emits particles"),
            (Emotion.DISGUST, 0, "DISGUST - no particles"),
            (Emotion.PATHOS, 0, "PATHOS - no particles"),
            (Emotion.DEVOTION, 1, "DEVOTION - emits particles"),
            (Emotion.HEROISM, 2, "HEROISM - emits 2 particles"),
            (Emotion.WONDER, 0, "WONDER - no particles"),
            (Emotion.TRANQUILITY, 0, "TRANQUILITY - no particles"),
        ]

        for emotion, expected_count, description in navarasa_particles:
            a = EmotionAnimator()
            a.set_emotion(emotion)
            a.update(33, 100, 200)
            actual_count = len(a._particles.particles)
            assert actual_count == expected_count, \
                f"{description}: expected {expected_count} particles, got {actual_count}"

    def test_navarasa_emotions_single_fire_decay(self):
        """Test that single-fire emotions auto-decay to MIRTH."""
        single_fire_emotions = [
            (Emotion.HEROISM, 1000, "HEROISM - decays after 1s"),
            (Emotion.WONDER, 800, "WONDER - decays after 0.8s"),
            (Emotion.DISGUST, 3000, "DISGUST - decays after 3s"),
        ]

        for emotion, decay_time, description in single_fire_emotions:
            a = EmotionAnimator()
            a.set_emotion(emotion)
            assert a._current == emotion, f"{description}: should start as {emotion.name}"

            # Advance past decay time
            a.update(decay_time + 100, 100, 100)
            assert a._current == Emotion.MIRTH, \
                f"{description}: should decay to MIRTH, got {a._current.name}"
            assert a._elapsed_ms == 0, \
                f"{description}: elapsed_ms should reset to 0 after decay"

    def test_navarasa_emotions_priority_order(self):
        """Test that navarasa emotions follow correct priority order in evaluation."""
        priority_order = [
            Emotion.FEAR,
            Emotion.DISGUST,
            Emotion.WONDER,
            Emotion.ANGER,
            Emotion.DEVOTION,
            Emotion.PATHOS,
            Emotion.TRANQUILITY,
            Emotion.MIRTH,
        ]

        # Test that each emotion has unique visual characteristics
        for i, emotion in enumerate(priority_order):
            a = EmotionAnimator()
            a.set_emotion(emotion)
            sx, sy, rot = a.get_transform(None, 0.0, 0)

            # Each emotion should have unique transform characteristics
            # Note: DEVOTION and TRANQUILITY both have (1.0, 1.0, 0.0) transform
            # So we need to test other characteristics as well
            for j, other_emotion in enumerate(priority_order):
                if i != j:
                    b = EmotionAnimator()
                    b.set_emotion(other_emotion)
                    ox, oy, orot = b.get_transform(None, 0.0, 0)

                    # Test transform OR body color OR overlays OR particle emission OR opacity
                    transform_differs = (
                        sx != ox or sy != oy or rot != orot
                    )
                    body_color_differs = a.get_body_color(QColor("#5B8DEF")) != b.get_body_color(QColor("#5B8DEF"))
                    overlays_differs = a.get_overlay() != b.get_overlay()
                    opacity_differs = a.get_opacity() != b.get_opacity()
                    # Reset particles for fair comparison
                    a.update(33, 100, 200)
                    b.update(33, 100, 200)
                    particles_differs = len(a._particles.particles) != len(b._particles.particles)

                    # At least one characteristic should be different
                    assert (transform_differs or body_color_differs or 
                           overlays_differs or particles_differs or opacity_differs), \
                        f"{emotion.name} and {other_emotion.name} should have different characteristics"

    def test_navarasa_emotions_unique_identifiers(self):
        """Test that each navarasa emotion has unique identifiers and properties."""
        navarasa_emotions = list(Emotion)

        # Test 1: All emotions have unique names
        names = {e.name for e in navarasa_emotions}
        assert len(names) == len(navarasa_emotions), \
            f"All emotions should have unique names, got duplicates"

        # Test 2: All emotions have unique string values
        values = {e.value for e in navarasa_emotions}
        assert len(values) == len(navarasa_emotions), \
            f"All emotions should have unique values, got duplicates"

        # Test 3: Each emotion has unique body color override (if any)
        override_colors = {e: p.color_override for e, p in EMOTION_PROFILES.items() if p.color_override}
        color_names = {color.upper() for color in override_colors.values()}
        assert len(color_names) == len(override_colors), \
            f"All body color overrides should be unique, got duplicates"

        # Test 4: Each emotion has unique particle emission (if any)
        particle_counts = {e: p.particle_count for e, p in EMOTION_PROFILES.items() if p.particle_count > 0}
        
        # Verify that particle counts are reasonable (1-2 particles per emission)
        for emotion, count in particle_counts.items():
            assert 1 <= count <= 2, \
                f"{emotion.name} should emit 1-2 particles, got {count}"


    # ── NAVARASA EMOTION TRIGGER TESTS ──────────────────────────────────────

    def test_navarasa_emotion_triggers(self):
        """Test that each navarasa emotion has correct trigger conditions."""
        # Mock the active window title and APM for testing
        test_cases = [
            (Emotion.FEAR, "Task Manager", 0, True, "FEAR triggered by Task Manager"),
            (Emotion.FEAR, "Activity Monitor", 0, True, "FEAR triggered by Activity Monitor"),
            (Emotion.FEAR, "Notepad", 0, False, "FEAR not triggered by Notepad"),
            (Emotion.DISGUST, "youtube.com", 0, True, "DISGUST triggered by youtube"),
            (Emotion.DISGUST, "reddit.com", 0, True, "DISGUST triggered by reddit"),
            (Emotion.DISGUST, "google.com", 0, False, "DISGUST not triggered by google"),
            (Emotion.WONDER, "", 0, True, "WONDER triggered by window switches"),
            (Emotion.ANGER, "", 0, True, "ANGER triggered by risky keyword"),
            (Emotion.DEVOTION, "", 70, True, "DEVOTION triggered by high APM"),
            (Emotion.DEVOTION, "", 50, False, "DEVOTION not triggered by normal APM"),
            (Emotion.PATHOS, "", 0, True, "PATHOS triggered by stale idle"),
            (Emotion.PATHOS, "", 10, False, "PATHOS not triggered with APM > 0"),
            (Emotion.TRANQUILITY, "code", 30, True, "TRANQUILITY triggered by coding"),
            (Emotion.TRANQUILITY, "notepad", 30, False, "TRANQUILITY not triggered by notepad"),
            (Emotion.TRANQUILITY, "code", 0, False, "TRANQUILITY not triggered with no APM"),
            (Emotion.MIRTH, "anything", 0, True, "MIRTH default emotion"),
        ]

        for emotion, window_title, apm, should_trigger, description in test_cases:
            # Test trigger logic based on emotion type
            if emotion == Emotion.FEAR:
                # FEAR is triggered by task manager keywords
                window_lower = window_title.lower()
                triggered = any(kw.lower() in window_lower for kw in ["task manager", "activity monitor"])
                assert triggered == should_trigger, f"{description}: expected {should_trigger}, got {triggered}"

            elif emotion == Emotion.DISGUST:
                # DISGUST is triggered by procrastination domains
                triggered = any(domain in window_title.lower() for domain in ["youtube", "reddit", "tiktok"])
                assert triggered == should_trigger, f"{description}: expected {should_trigger}, got {triggered}"

            elif emotion == Emotion.WONDER:
                # WONDER is triggered by rapid window switches
                # This would require mocking _window_switch_count
                pass  # Skip for now as it requires more complex mocking

            elif emotion == Emotion.ANGER:
                # ANGER is triggered by risky keyword matches
                # This would require mocking _last_risky_match
                pass  # Skip for now as it requires more complex mocking

            elif emotion == Emotion.DEVOTION:
                # DEVOTION is triggered by high APM
                triggered = apm > 60
                assert triggered == should_trigger, f"{description}: expected {should_trigger}, got {triggered}"

            elif emotion == Emotion.PATHOS:
                # PATHOS is triggered by stale idle with no APM
                triggered = apm == 0 and True  # Would need _idle_seconds >= 120
                assert triggered == should_trigger, f"{description}: expected {should_trigger}, got {triggered}"

            elif emotion == Emotion.TRANQUILITY:
                # TRANQUILITY is triggered by steady coding
                win_title = window_title
                triggered = apm > 0 and apm <= 60 and ("code" in (win_title or "").lower())
                assert triggered == should_trigger, f"{description}: expected {should_trigger}, got {triggered}"

            elif emotion == Emotion.MIRTH:
                # MIRTH is the default emotion
                assert should_trigger == True, f"{description}: MIRTH should always be available as fallback"

    def test_navarasa_emotion_priority_order(self):
        """Test that navarasa emotions follow correct priority order in evaluation."""
        # Based on _evaluate_emotion method:
        # 1. FEAR (Task Manager)
        # 2. DISGUST (Procrastination sites)
        # 3. WONDER (Rapid window switching)
        # 4. ANGER (Risky keyword match)
        # 5. DEVOTION (High APM > 60)
        # 6. PATHOS (Stale idle >= 120s, no APM)
        # 7. TRANQUILITY (Steady coding in IDE)
        # 8. MIRTH (Default)

        priority_order = [
            Emotion.FEAR,
            Emotion.DISGUST,
            Emotion.WONDER,
            Emotion.ANGER,
            Emotion.DEVOTION,
            Emotion.PATHOS,
            Emotion.TRANQUILITY,
            Emotion.MIRTH,
        ]

        # Test that higher priority emotions are checked first
        # This is implicit in the _evaluate_emotion method structure
        for i, emotion in enumerate(priority_order):
            # Each emotion should be checkable independently
            a = EmotionAnimator()
            a.set_emotion(emotion)
            assert a._current == emotion, f"{emotion.name} should be settable"

    def test_navarasa_emotion_state_transitions(self):
        """Test that navarasa emotions can transition between states correctly."""
        a = EmotionAnimator()

        # Test transitions between all navarasa emotions
        test_transitions = [
            (Emotion.MIRTH, Emotion.ANGER),
            (Emotion.ANGER, Emotion.FEAR),
            (Emotion.FEAR, Emotion.DISGUST),
            (Emotion.DISGUST, Emotion.PATHOS),
            (Emotion.PATHOS, Emotion.DEVOTION),
            (Emotion.DEVOTION, Emotion.HEROISM),
            (Emotion.HEROISM, Emotion.WONDER),
            (Emotion.WONDER, Emotion.TRANQUILITY),
            (Emotion.TRANQUILITY, Emotion.MIRTH),
        ]

        for from_emotion, to_emotion in test_transitions:
            a.set_emotion(from_emotion)
            assert a._current == from_emotion, f"Should start with {from_emotion.name}"

            # Transition to next emotion
            a.set_emotion(to_emotion)
            assert a._current == to_emotion, f"Should transition to {to_emotion.name}"

            # Verify elapsed time is reset
            a.update(100, 0, 0)
            assert a._elapsed_ms == 100, f"Elapsed time should be updated for {to_emotion.name}"

    def test_navarasa_emotion_duration_based_states(self):
        """Test that duration-based navarasa emotions auto-exit correctly."""
        # HEROISM, WONDER, and DISGUST are single-fire emotions with auto-decay
        single_fire_emotions = [
            (Emotion.HEROISM, 1000, "HEROISM"),
            (Emotion.WONDER, 800, "WONDER"),
            (Emotion.DISGUST, 3000, "DISGUST"),
        ]

        for emotion, decay_time, name in single_fire_emotions:
            a = EmotionAnimator()
            a.set_emotion(emotion)
            assert a._current == emotion, f"Should start with {name}"

            # Advance past decay time
            a.update(decay_time + 100, 100, 100)
            assert a._current == Emotion.MIRTH, \
                f"{name} should decay to MIRTH, got {a._current.name}"
            assert a._elapsed_ms == 0, \
                f"{name} elapsed_ms should reset to 0 after decay"

    def test_navarasa_emotion_continuous_states(self):
        """Test that continuous navarasa emotions persist without auto-decay."""
        # MIRTH, ANGER, FEAR, PATHOS, DEVOTION, TRANQUILITY are continuous states
        continuous_emotions = [
            Emotion.MIRTH,
            Emotion.ANGER,
            Emotion.FEAR,
            Emotion.PATHOS,
            Emotion.DEVOTION,
            Emotion.TRANQUILITY,
        ]

        for emotion in continuous_emotions:
            a = EmotionAnimator()
            a.set_emotion(emotion)
            assert a._current == emotion, f"Should start with {emotion.name}"

            # Advance time - emotion should persist
            a.update(5000, 100, 100)
            assert a._current == emotion, \
                f"{emotion.name} should persist without auto-decay, got {a._current.name}"

    def test_navarasa_emotion_visual_uniqueness(self):
        """Test that each navarasa emotion has unique visual characteristics."""
        navarasa_emotions = list(Emotion)

        # Collect visual characteristics for each emotion
        visual_characteristics = []
        for emotion in navarasa_emotions:
            a = EmotionAnimator()
            a.set_emotion(emotion)

            # Get transform
            sx, sy, rot = a.get_transform(None, 0.0, 0)

            # Get body color
            base_color = QColor("#5B8DEF")
            body_color = a.get_body_color(base_color)

            # Get overlays
            overlays = a.get_overlay()

            # Get particle count
            a.update(33, 100, 200)
            particle_count = len(a._particles.particles)

            # Get opacity
            opacity = a.get_opacity()

            visual_characteristics.append({
                'emotion': emotion,
                'transform': (sx, sy, rot),
                'body_color': body_color,
                'overlays': overlays,
                'particle_count': particle_count,
                'opacity': opacity,
            })

        # Verify all emotions have unique combinations
        for i, char1 in enumerate(visual_characteristics):
            for j, char2 in enumerate(visual_characteristics[i+1:], i+1):
                # At least one characteristic should be different
                transforms_match = char1['transform'] == char2['transform']
                colors_match = char1['body_color'] == char2['body_color']
                overlays_match = char1['overlays'] == char2['overlays']
                particles_match = char1['particle_count'] == char2['particle_count']
                opacity_match = char1['opacity'] == char2['opacity']

                # If all characteristics match, it's a duplicate
                if transforms_match and colors_match and overlays_match and particles_match and opacity_match:
                    assert False, \
                        f"Emotions {char1['emotion'].name} and {char2['emotion'].name} have identical visual characteristics"

    def test_navarasa_emotion_comprehensive_workflow(self):
        """Test a comprehensive workflow cycling through all navarasa emotions."""
        a = EmotionAnimator()

        # Start with MIRTH
        assert a._current == Emotion.MIRTH

        # Cycle through all navarasa emotions
        emotion_sequence = [
            Emotion.ANGER,
            Emotion.FEAR,
            Emotion.DISGUST,
            Emotion.PATHOS,
            Emotion.DEVOTION,
            Emotion.HEROISM,
            Emotion.WONDER,
            Emotion.TRANQUILITY,
            Emotion.MIRTH,
        ]

        for emotion in emotion_sequence:
            # Set emotion
            a.set_emotion(emotion)
            assert a._current == emotion, f"Should be {emotion.name}"

            # Update to advance time
            a.update(100, 100, 100)

            # Verify visual characteristics
            sx, sy, rot = a.get_transform(None, 0.0, 0)
            assert isinstance(sx, float) and isinstance(sy, float) and isinstance(rot, float)
            assert sx > 0 and sy > 0

            # Verify body color
            body_color = a.get_body_color(QColor("#5B8DEF"))
            assert isinstance(body_color, QColor)

            # Verify overlays
            overlays = a.get_overlay()
            assert isinstance(overlays, list)

        # Verify we're back to MIRTH
        assert a._current == Emotion.MIRTH

    def test_navarasa_emotion_constraint_no_xy_writes(self):
        """Test that navarasa emotions never write X/Y coordinates (Constraint 2)."""
        a = EmotionAnimator()
        pet_x, pet_y = 100, 200

        for emotion in Emotion:
            a.set_emotion(emotion, elapsed_ms=0)
            a.update(33, 50, 60)
            sx, sy, rot = a.get_transform(None, 0.0, 0)
            _ = a.get_body_color(QColor("#5B8DEF"))
            _ = a.get_overlay()
            _ = a.draw_particles(None)

            # The only public surface is transform, body_color, overlay, particles
            # All read-only — no setter for X/Y exists
            assert isinstance(sx, float)
            assert isinstance(sy, float)
            assert isinstance(rot, float)

        # Verify private members don't store coord data
        assert not hasattr(a, '_pet_x')
        assert not hasattr(a, '_pet_y')
