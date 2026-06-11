# src/animator.py
from __future__ import annotations
import logging
import math
import random
from enum import Enum
from PyQt6.QtCore import QPointF, Qt
from PyQt6.QtGui import QPainter, QColor
from src.constants import PARTICLE_MAX_COUNT

logger = logging.getLogger(__name__)


class ParticleSystem:
    """Manages a capped pool of particle dicts.

    Each particle::
        x, y          — float screen position (logical pixels)
        dx, dy        — float velocity per 60fps frame
        life, max_life — int remaining / starting life in ticks
        color         — QColor
        size          — int radius
        gravity       — float vertical acceleration per 60fps frame
    """

    def __init__(self) -> None:
        self.particles: list[dict] = []

    def emit(
        self,
        x: float, y: float,
        count: int,
        color: QColor,
        spread: float = 1.0,
        gravity: float = 0.0,
        lifetime_ticks: int = 30,
    ) -> None:
        """Emit *count* particles at (x, y) clipped to PARTICLE_MAX_COUNT."""
        max_new = PARTICLE_MAX_COUNT - len(self.particles)
        if max_new <= 0:
            logger.debug("Particle cap (%d) reached, dropping new emissions", PARTICLE_MAX_COUNT)
            return
        count = min(count, max_new)
        for _ in range(count):
            self.particles.append({
                "x": x,
                "y": y,
                "dx": random.uniform(-spread, spread),
                "dy": random.uniform(-spread, spread),
                "life": lifetime_ticks,
                "max_life": lifetime_ticks,
                "color": QColor(color),
                "size": random.randint(2, 4),
                "gravity": gravity,
            })

    def update(self, dt_ms: int) -> None:
        """Advance all particles by *dt_ms*. Removes dead particles."""
        dt = dt_ms / 1000.0 * 60.0  # normalise to ~60 fps steps
        remaining: list[dict] = []
        for p in self.particles:
            p["life"] -= 1
            if p["life"] <= 0:
                continue
            p["x"] += p["dx"] * dt
            p["dy"] += p["gravity"] * dt
            p["y"] += p["dy"] * dt
            remaining.append(p)
        self.particles = remaining

    def draw(self, painter: QPainter) -> None:
        """Alpha-faded circles for every living particle."""
        for p in self.particles:
            alpha = int(255 * (p["life"] / p["max_life"]))
            c = QColor(p["color"])
            c.setAlpha(alpha)
            painter.setBrush(c)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(QPointF(p["x"], p["y"]), p["size"], p["size"])


class Emotion(Enum):
    MIRTH = "mirth"
    ANGER = "anger"
    FEAR = "fear"
    DISGUST = "disgust"
    PATHOS = "pathos"
    DEVOTION = "devotion"
    HEROISM = "heroism"
    WONDER = "wonder"
    TRANQUILITY = "tranquility"


# ── Single-fire auto-decay durations (ms) ──────────────────────────────
_SINGLE_FIRE_DECAY: dict[Emotion, int] = {
    Emotion.HEROISM: 1000,
    Emotion.WONDER: 800,
    Emotion.DISGUST: 3000,
}

# ── Emotions that override body colour (others use base / transform) ───
_EMOTION_OVERRIDE_COLOR: dict[Emotion, QColor] = {
    Emotion.ANGER: QColor("#E74C3C"),
    Emotion.FEAR: QColor("#6B5B95"),
    Emotion.DEVOTION: QColor("#FF69B4"),
    Emotion.HEROISM: QColor("#FFD700"),
    Emotion.WONDER: QColor("#FFFFFF"),
}

# ── Particles emitted per update: (count, color, spread, gravity, lifetime) ─
_PARTICLE_EMIT: dict[Emotion, tuple[int, QColor, float, float, int]] = {
    Emotion.ANGER: (1, QColor("#E74C3C"), 1.5, 0.2, 20),
    Emotion.FEAR: (1, QColor("#6B5B95"), 1.5, 0.1, 25),
    Emotion.DEVOTION: (1, QColor("#FF69B4"), 2.0, 0.1, 30),
    Emotion.HEROISM: (2, QColor("#FFD700"), 3.0, 0.0, 15),
}


class EmotionAnimator:
    """Drives emotion-based transforms, colours, particles, and overlays.

    Hard rule: never writes X or Y coordinates — only reads them.
    """

    def __init__(self) -> None:
        self._current = Emotion.MIRTH
        self._elapsed_ms: int = 0
        self._particles = ParticleSystem()

    # ── Public API ─────────────────────────────────────────────────────

    @property
    def current_emotion(self) -> Emotion:
        return self._current

    def set_emotion(self, emotion: Emotion, elapsed_ms: int = 0) -> None:
        """Change current emotion and reset its timing."""
        if emotion != self._current:
            logger.info("Emotion shifted: %s -> %s", self._current.name, emotion.name)
        self._current = emotion
        self._elapsed_ms = elapsed_ms

    def update(self, dt_ms: int, pet_x: int, pet_y: int) -> None:
        """Advance particle physics and check single-fire decay."""
        self._elapsed_ms += dt_ms
        self._particles.update(dt_ms)

        # Single-fire auto-decay
        decay = _SINGLE_FIRE_DECAY.get(self._current)
        if decay is not None and self._elapsed_ms >= decay:
            self._current = Emotion.MIRTH
            self._elapsed_ms = 0

        # Emit per-update particles
        emit_data = _PARTICLE_EMIT.get(self._current)
        if emit_data is not None:
            count, color, spread, gravity, lifetime = emit_data
            self._particles.emit(
                float(pet_x), float(pet_y),
                count, color, spread, gravity, lifetime,
            )

    def get_transform(
        self,
        pet_rect: object,       # QRect — unused, reserved for position-aware transforms
        velocity_x: float,      # unused, reserved
        elapsed_ms: int,        # unused — uses internal _elapsed_ms
    ) -> tuple[float, float, float]:
        """Return (scale_x, scale_y, rotation) for the current emotion."""
        t = self._elapsed_ms / 1000.0  # seconds
        e = self._current

        if e == Emotion.MIRTH:
            sx = 1.0 + 0.05 * math.sin(t * 2.0 * math.pi)
            sy = 1.0 - 0.2 * abs(math.sin(t * math.pi))
            return sx, sy, 0.0

        if e == Emotion.ANGER:
            return (
                1.0 + random.uniform(-0.02, 0.02),
                1.0 + random.uniform(-0.02, 0.02),
                random.uniform(-2.0, 2.0),
            )

        if e == Emotion.FEAR:
            return 1.3, 0.7, 0.0

        if e == Emotion.DISGUST:
            return 0.8, 1.0, 0.0

        if e == Emotion.PATHOS:
            return 1.0, 0.9, 0.0

        if e == Emotion.DEVOTION:
            return 1.0, 1.0, 0.0

        if e == Emotion.HEROISM:
            if self._elapsed_ms < 500:
                return 0.85, 1.3, 0.0
            frac = (self._elapsed_ms - 500) / 500.0
            sx = 0.85 + frac * 0.15  # 0.85 → 1.0
            sy = 1.30 - frac * 0.30  # 1.30 → 1.0
            return min(sx, 1.0), max(sy, 1.0), 0.0

        if e == Emotion.WONDER:
            if self._elapsed_ms >= 800:
                return 1.0, 1.0, 0.0
            frac = self._elapsed_ms / 800.0
            s = 1.5 - frac * 0.5  # 1.5 → 1.0
            return s, s, 0.0

        if e == Emotion.TRANQUILITY:
            b = 1.0 + 0.02 * math.sin(t * 2.0 * math.pi / 3.0)
            return b, b, 0.0

        return 1.0, 1.0, 0.0

    def get_body_color(self, base_color: QColor) -> QColor:
        """Return emotion-tinted body colour (or *base_color* for MIRTH)."""
        e = self._current

        override = _EMOTION_OVERRIDE_COLOR.get(e)
        if override is not None:
            return QColor(override)

        if e == Emotion.PATHOS:
            gray = int(base_color.red() * 0.30
                       + base_color.green() * 0.59
                       + base_color.blue() * 0.11)
            return QColor(gray, gray, gray)

        if e == Emotion.DISGUST:
            hsv = base_color.toHsv()
            h = max(0, hsv.hue() - 30)
            return QColor.fromHsv(h, hsv.saturation(), hsv.value())

        if e == Emotion.TRANQUILITY:
            c = QColor(base_color)
            c.setAlpha(int(255 * 0.80))
            return c

        if e == Emotion.MIRTH:
            return base_color

        return base_color

    def get_overlay(self) -> list[tuple]:
        """Return overlay descriptors for the current emotion."""
        e = self._current

        if e == Emotion.ANGER:
            c = QColor("#E74C3C")
            c.setAlpha(180)
            return [("border", c, 2)]

        if e == Emotion.HEROISM:
            c = QColor("#FFD700")
            c.setAlpha(80)
            return [("aura", c)]

        if e == Emotion.WONDER:
            return [("flash", 80)]

        return []

    def draw_particles(self, painter: QPainter | None) -> None:
        """Delegate particle rendering to the particle system."""
        if painter is not None:
            self._particles.draw(painter)
