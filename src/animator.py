# src/animator.py
from __future__ import annotations
import logging
import math
import random
from dataclasses import dataclass
from enum import Enum
from typing import Callable, Optional
from PyQt6.QtCore import QPointF, Qt
from PyQt6.QtGui import QPainter, QColor, QPen
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
        drift_x: float = 0.0,
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
                "dx": random.uniform(-spread, spread) + drift_x,
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
        write_idx = 0
        for p in self.particles:
            p["life"] -= 1
            if p["life"] <= 0:
                continue
            p["x"] += p["dx"] * dt
            p["dy"] += p["gravity"] * dt
            p["y"] += p["dy"] * dt
            self.particles[write_idx] = p
            write_idx += 1
        del self.particles[write_idx:]

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


@dataclass
class EmotionProfile:
    name: str
    
    # Color & Opacity (No body shape transforms)
    color_override: Optional[str] = None
    color_hue_shift: int = 0
    opacity_func: Callable[[float], float] = lambda t: 1.0
    
    # Eyes (Sclera remains perfectly round)
    pupil_scale: float = 1.0
    pupil_shape: str = "circle"  # "circle" | "heart"
    pupil_color_override: Optional[str] = None
    pupil_offset_x: float = 0.0  # For eye rolling/shifting
    brow_angle: float = 0.0      # degrees: positive = angry furrow, negative = sad
    
    # Overlay (Border, Aura, Flash)
    overlay_kind: Optional[str] = None      
    overlay_color: Optional[str] = None
    overlay_alpha_func: Callable[[float], int] = lambda t: 255
    overlay_width: int = 2
    
    # Particles
    particle_count: int = 0
    particle_color: Optional[str] = None
    particle_spread: float = 1.0
    particle_gravity: float = 0.0
    particle_drift_x: float = 0.0 
    particle_lifetime_ticks: int = 30
    
    # Misc
    single_fire_decay_ms: int = 0


# ── Emotion Profile Registry (the single source of truth) ───────────────

EMOTION_PROFILES: dict[Emotion, EmotionProfile] = {
    Emotion.MIRTH: EmotionProfile(
        name="mirth"
    ),
    Emotion.ANGER: EmotionProfile(
        name="anger",
        color_override="#E74C3C",
        pupil_scale=0.5,
        brow_angle=20.0,
        overlay_kind="border",
        overlay_color="#E74C3C",
        overlay_alpha_func=lambda t: 180,
        particle_count=1,
        particle_color="#E74C3C"
    ),
    Emotion.FEAR: EmotionProfile(
        name="fear",
        color_override="#6B5B95",
        pupil_scale=0.3,
        brow_angle=-10.0,
        particle_count=1,
        particle_color="#8888FF", # Light blue sweat
        particle_gravity=0.1
    ),
    Emotion.DISGUST: EmotionProfile(
        name="disgust",
        color_hue_shift=-30,
        pupil_offset_x=2.0,
        brow_angle=10.0,
        single_fire_decay_ms=3000
    ),
    Emotion.PATHOS: EmotionProfile(
        name="pathos",
        # Sine wave pulsing opacity between 0.6 and 0.9
        opacity_func=lambda t: 0.75 + 0.15 * math.sin(t * math.pi / 1000),
        brow_angle=-15.0
    ),
    Emotion.DEVOTION: EmotionProfile(
        name="devotion",
        color_override="#FF69B4",
        pupil_shape="heart",
        particle_count=1,
        particle_color="#FF69B4"
    ),
    Emotion.HEROISM: EmotionProfile(
        name="heroism",
        color_override="#FFD700",
        pupil_color_override="#FFD700",
        pupil_scale=1.2,
        brow_angle=15.0,
        overlay_kind="aura",
        overlay_color="#FFD700",
        overlay_alpha_func=lambda t: 80,
        particle_count=2,
        particle_color="#FFD700",
        single_fire_decay_ms=1000
    ),
    Emotion.WONDER: EmotionProfile(
        name="wonder",
        color_override="#FFFFFF",
        # 1-frame glitch: opacity drops to 0 halfway through the 800ms WONDER state
        opacity_func=lambda t: 0.0 if 380 < t < 420 else 1.0,
        pupil_scale=1.5,
        overlay_kind="flash",
        overlay_alpha_func=lambda t: 80,
        single_fire_decay_ms=800
    ),
    Emotion.TRANQUILITY: EmotionProfile(
        name="tranquility",
        opacity_func=lambda t: 0.8,
        pupil_scale=0.3
    )
}


class EmotionAnimator:
    """Drives emotion-based transforms, colours, particles, and overlays.

    All per-emotion visual behaviour is read from EMOTION_PROFILES.
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

        profile = EMOTION_PROFILES[self._current]

        # Single-fire auto-decay
        if profile.single_fire_decay_ms and self._elapsed_ms >= profile.single_fire_decay_ms:
            self._current = Emotion.MIRTH
            self._elapsed_ms = 0

        # Emit per-update particles
        if profile.particle_count > 0 and profile.particle_color:
            self._particles.emit(
                float(pet_x), float(pet_y),
                profile.particle_count,
                QColor(profile.particle_color),
                profile.particle_spread,
                profile.particle_gravity,
                profile.particle_lifetime_ticks,
                profile.particle_drift_x,
            )

    def get_transform(
        self,
        pet_rect: object = None,
        velocity_x: float = 0.0,
        elapsed_ms: int = 0,
    ) -> tuple[float, float, float]:
        """Return (scale_x, scale_y, rotation) for the current emotion."""
        return 1.0, 1.0, 0.0

    def get_body_color(self, base_color: QColor) -> QColor:
        """Return emotion-tinted body colour (or *base_color* for MIRTH)."""
        profile = EMOTION_PROFILES[self._current]
        
        if profile.name == "pathos":
            gray = int(base_color.red() * 0.30 + base_color.green() * 0.59 + base_color.blue() * 0.11)
            return QColor(gray, gray, gray)
            
        if profile.color_override:
            color = QColor(profile.color_override)
        else:
            color = QColor(base_color)
            
        if profile.color_hue_shift != 0:
            hsv = color.toHsv()
            h = max(0, min(359, hsv.hue() + profile.color_hue_shift))
            color = QColor.fromHsv(h, hsv.saturation(), hsv.value())
            
        return color

    def get_opacity(self) -> float:
        """Return opacity multiplier (0.0 – 1.0) for the current emotion."""
        return EMOTION_PROFILES[self._current].opacity_func(float(self._elapsed_ms))

    def get_overlay(self) -> list[tuple]:
        """Return overlay descriptors for the current emotion."""
        profile = EMOTION_PROFILES[self._current]
        kind = profile.overlay_kind
        if kind is None:
            return []

        alpha = profile.overlay_alpha_func(float(self._elapsed_ms))

        if kind == "border" and profile.overlay_color:
            c = QColor(profile.overlay_color)
            c.setAlpha(alpha)
            return [("border", c, profile.overlay_width)]

        if kind == "aura" and profile.overlay_color:
            c = QColor(profile.overlay_color)
            c.setAlpha(alpha)
            return [("aura", c)]

        if kind == "flash":
            return [("flash", alpha)]

        return []

    def get_eye_modifier(self) -> dict:
        """Return eye modifier values for the current emotion."""
        profile = EMOTION_PROFILES[self._current]
        return {
            "pupil_scale": profile.pupil_scale,
            "pupil_shape": profile.pupil_shape,
            "pupil_color_override": profile.pupil_color_override,
            "pupil_offset_x": profile.pupil_offset_x,
            "brow_angle": profile.brow_angle,
        }

    def draw_particles(self, painter: QPainter | None) -> None:
        """Delegate particle rendering to the particle system."""
        if painter is not None:
            self._particles.draw(painter)
