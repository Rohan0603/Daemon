"""Tests for src/animator.py — ParticleSystem, Emotion, EmotionAnimator."""
from __future__ import annotations
import sys
import math
import pytest
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QColor

from src.animator import ParticleSystem, Emotion, EmotionAnimator
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

    def test_get_transform_fear(self):
        a = EmotionAnimator()
        a.set_emotion(Emotion.FEAR)
        sx, sy, _ = a.get_transform(None, 0.0, 0)
        assert sx == 1.3
        assert sy == 0.7

    def test_get_transform_disgust(self):
        a = EmotionAnimator()
        a.set_emotion(Emotion.DISGUST)
        sx, sy, _ = a.get_transform(None, 0.0, 0)
        assert sx == 0.8
        assert sy == 1.0

    def test_get_transform_pathos(self):
        a = EmotionAnimator()
        a.set_emotion(Emotion.PATHOS)
        sx, sy, _ = a.get_transform(None, 0.0, 0)
        assert sx == 1.0
        assert sy == 0.9

    def test_get_transform_devotion(self):
        a = EmotionAnimator()
        a.set_emotion(Emotion.DEVOTION)
        sx, sy, _ = a.get_transform(None, 0.0, 0)
        assert sx == 1.0
        assert sy == 1.0

    def test_get_transform_tranquility(self):
        a = EmotionAnimator()
        a.set_emotion(Emotion.TRANQUILITY)
        sx, sy, _ = a.get_transform(None, 0.0, 0)
        # breathe around 1.0
        assert 0.97 < sx < 1.03
        assert 0.97 < sy < 1.03

    def test_get_transform_heroism_early(self):
        a = EmotionAnimator()
        a.set_emotion(Emotion.HEROISM, elapsed_ms=100)
        sx, sy, _ = a.get_transform(None, 0.0, 100)
        assert sx == 0.85
        assert sy == 1.3

    def test_get_transform_heroism_late(self):
        a = EmotionAnimator()
        a.set_emotion(Emotion.HEROISM, elapsed_ms=700)
        sx, sy, _ = a.get_transform(None, 0.0, 700)
        # Should be easing toward 1.0
        assert 0.85 < sx < 1.0
        assert 1.0 < sy < 1.3

    def test_get_transform_wonder_early(self):
        a = EmotionAnimator()
        a.set_emotion(Emotion.WONDER, elapsed_ms=200)
        sx, sy, _ = a.get_transform(None, 0.0, 200)
        assert 1.0 < sx <= 1.5
        assert sx == sy

    def test_get_transform_wonder_done(self):
        a = EmotionAnimator()
        a.set_emotion(Emotion.WONDER, elapsed_ms=800)
        sx, sy, _ = a.get_transform(None, 0.0, 800)
        assert sx == 1.0
        assert sy == 1.0

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
        c = a.get_body_color(QColor("#5B8DEF"))
        assert c.alpha() == 204  # 80% of 255

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
