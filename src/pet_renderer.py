# src/pet_renderer.py
from __future__ import annotations
import math
from dataclasses import dataclass, field
from typing import Optional, TYPE_CHECKING
if TYPE_CHECKING:
    from PyQt6.QtCore import QRect
    from src.animator import Emotion, EmotionAnimator
from PyQt6.QtCore import QRect, QPoint, Qt
from PyQt6.QtGui import QPainter, QColor, QPen, QBrush, QFont, QFontMetrics
from src.pet_fsm import PetState
from src.constants import (
    PET_WIDTH, PET_HEIGHT, PET_CORNER_RADIUS,
    BODY_BLUE, BODY_DARK, EYE_WHITE, EYE_PUPIL,
    ACCENT_YELLOW, ACCENT_RED,
    BUBBLE_BG, BUBBLE_BORDER, BUBBLE_TEXT_COLOR,
    BUBBLE_MAX_WIDTH, BUBBLE_PADDING, BUBBLE_CORNER_RADIUS, BUBBLE_FONT_SIZE,
    HYPER_FLASH, SQUASH_STRETCH_DURATION_MS,
)
from PyQt6.QtCore import QRectF, QPointF
from PyQt6.QtGui import QPainterPath, QPolygon


@dataclass
class RenderContext:
    state: PetState
    pet_x: int
    pet_y: int
    anim_tick: int           # monotonically increasing tick counter (33ms per tick)
    hyper_color_index: int   # 0-3, cycles at 8Hz
    fall_velocity: float
    wander_direction: int    # -1 = left, 1 = right
    bubble_text: str
    drag_velocity_x: float   # used for drag rotation
    scale: float             # devicePixelRatio, applied to all coord math
    cursor_x: int = 0        # global cursor x in logical pixels (same space as pet_x/pet_y)
    cursor_y: int = 0        # global cursor y in logical pixels
    state_elapsed_ms: int = 0
    land_elapsed_ms: float = 0.0   # ms since last ground contact; 0.0 = no animation
    edge: str = "bottom"    # "bottom" | "left" | "top" | "right"
    facing: str = "right"   # direction along edge: "right" | "left" | "up" | "down"
    screen_rect: QRect = field(default_factory=lambda: QRect(0, 0, 0, 0))
    bubble_rect: QRect = field(default_factory=lambda: QRect(0, 0, 0, 0))
    emotion: 'Emotion | None' = None
    animator: 'EmotionAnimator | None' = None
    takeoff_elapsed_ms: float = 0.0
    title_land_elapsed_ms: float = 0.0


class PetRenderer:
    def render(self, painter: QPainter, ctx: RenderContext) -> None:
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        self._draw_pet(painter, ctx)
        if ctx.bubble_text:
            self._draw_bubble(painter, ctx)

    # ── Pet body ──────────────────────────────────────────────────────────

    def _draw_pet(self, painter: QPainter, ctx: RenderContext) -> None:
        painter.save()

        cx = ctx.pet_x + PET_WIDTH / 2
        cy = ctx.pet_y + PET_HEIGHT / 2
        ox, oy = self._state_offset(ctx)
        painter.translate(cx + ox, cy + oy)

        scale_x, scale_y, rotation = self._state_transform(ctx)
        if rotation != 0:
            painter.rotate(rotation)
        painter.scale(scale_x, scale_y)

        body_color = self._body_color(ctx)

        # Apply emotion opacity (juice: pulsing, glitch, etc.)
        if ctx.animator:
            painter.setOpacity(ctx.animator.get_opacity())

        self._draw_body(painter, body_color, ctx.state)
        self._draw_eyes(painter, ctx)

        painter.restore()

        self._draw_state_overlay(painter, ctx)

        if ctx.animator:
            ctx.animator.draw_particles(painter)
            for overlay in ctx.animator.get_overlay():
                self._draw_overlay(painter, ctx, overlay)

    def _state_offset(self, ctx: RenderContext) -> tuple[float, float]:
        t = ctx.state_elapsed_ms / 1000.0
        if ctx.state == PetState.SHAKING:
            return math.sin(t * math.pi * 15) * 5, 0.0
        if ctx.state == PetState.BOUNCING:
            return 0.0, -abs(math.sin(t * math.pi * 2)) * 12
        return 0.0, 0.0

    def _state_transform(self, ctx: RenderContext):
        state = ctx.state
        t = ctx.anim_tick

        if state == PetState.IDLE:
            breathe = 1.0 + 0.03 * math.sin(t * 0.05)
            return breathe, breathe, 0.0

        if state == PetState.PERIMETER:
            edge = ctx.edge
            facing = ctx.facing
            if edge == "bottom" and facing == "right":
                return 1.0, 1.0, 0.0
            if edge == "bottom" and facing == "left":
                return -1.0, 1.0, 0.0
            if edge == "left" and facing == "up":
                return 1.0, 1.0, -90.0
            if edge == "left" and facing == "down":
                return 1.0, 1.0, 90.0
            if edge == "right" and facing == "up":
                return 1.0, 1.0, 90.0
            if edge == "right" and facing == "down":
                return 1.0, 1.0, -90.0
            if edge == "top" and facing == "right":
                return 1.0, 1.0, 180.0
            if edge == "top" and facing == "left":
                return -1.0, 1.0, 180.0
            return 1.0, 1.0, 0.0

        if state == PetState.DRAGGED:
            rotation = 5.0 * (1 if ctx.drag_velocity_x >= 0 else -1)
            return 1.0, 0.9, rotation

        if state == PetState.FALLING:
            lean = min(15.0, ctx.fall_velocity * 0.5)
            return 1.0, 1.15, lean

        if state == PetState.CELEBRATE:
            return 1.0, 1.0, 0.0

        if state == PetState.DEVASTATED:
            return 1.0, 1.0, 0.0

        if state == PetState.THINKING:
            return 1.0, 1.0, 0.0

        if state == PetState.CHASE:
            return 1.0, 1.0, 10.0 * ctx.wander_direction

        if state == PetState.HYPER:
            pulse = 1.0 + 0.08 * math.sin(t * 0.4)
            return pulse, pulse, 0.0

        if state == PetState.SLEEP:
            return 1.0, 1.0, 0.0

        if state == PetState.AUTONOMOUS_THINKING:
            return 1.0, 1.0, 0.0

        if state == PetState.SHAKING:
            t = ctx.anim_tick
            rotation = 6.0 * math.sin(t * 0.9)
            return 1.0, 1.0, rotation

        if state == PetState.BOUNCING:
            t = ctx.state_elapsed_ms / 1000.0
            sx = 1.0 + 0.05 * abs(math.sin(t * math.pi * 2))
            return sx, 1.0, 0.0

        if state == PetState.SPINNING:
            t = ctx.state_elapsed_ms / 1000.0
            rotation = t * 360.0
            return 1.0, 1.0, rotation

        if state == PetState.LOOK_AWAY:
            return 1.0, 1.0, -4.0

        if getattr(ctx, 'takeoff_elapsed_ms', 0.0) > 0:
            return 0.8, 1.3, 0.0
            
        if getattr(ctx, 'title_land_elapsed_ms', 0.0) > 0:
            return 1.3, 0.7, 0.0

        if ctx.land_elapsed_ms > 0:
            ms = ctx.land_elapsed_ms
            if ms < 120:
                frac = ms / 120.0
                sx = 1.25 + frac * 0.05
                sy = 0.85 - frac * 0.15
                return sx, sy, 0.0
            elif ms < 240:
                frac = (ms - 120) / 120.0
                sx = 1.30 - frac * 0.55
                sy = 0.70 + frac * 0.55
                return sx, sy, 0.0
            elif ms < SQUASH_STRETCH_DURATION_MS:
                frac = (ms - 240) / (SQUASH_STRETCH_DURATION_MS - 240)
                sx = 0.75 + frac * 0.25
                sy = 1.25 - frac * 0.25
                return sx, sy, 0.0

        return 1.0, 1.0, 0.0

    def _body_color(self, ctx: RenderContext) -> QColor:
        state = ctx.state
        if state == PetState.HYPER:
            return QColor(HYPER_FLASH[ctx.hyper_color_index % 4])
        if state == PetState.DEVASTATED:
            c = QColor(BODY_BLUE)
            gray = int(c.red() * 0.3 + c.green() * 0.59 + c.blue() * 0.11)
            return QColor(gray, gray, gray)
        if state == PetState.THINKING:
            return QColor("#7B9EC7")
        if state == PetState.AUTONOMOUS_THINKING:
            return QColor("#9B7EC8")  # muted purple
        if state == PetState.SLEEP:
            c = QColor(BODY_BLUE)
            c.setAlpha(204)  # 80% opacity
            return c
        if state == PetState.SHAKING:
            return QColor("#E87722")  # orange panic
        if state == PetState.BOUNCING:
            return QColor(BODY_BLUE)
        if state == PetState.SPINNING:
            return QColor(ACCENT_YELLOW)  # yellow mind-blown
        if state == PetState.LOOK_AWAY:
            c = QColor(BODY_BLUE)
            c.setAlpha(220)
            return c
        if ctx.animator:
            return ctx.animator.get_body_color(QColor(BODY_BLUE))
        return QColor(BODY_BLUE)

    def _draw_body(self, painter: QPainter, color: QColor, state: PetState) -> None:
        hw, hh = PET_WIDTH // 2, PET_HEIGHT // 2
        rect = QRectF(-hw, -hh, PET_WIDTH, PET_HEIGHT)

        painter.setBrush(QBrush(color))
        painter.setPen(QPen(QColor(BODY_DARK), 2))
        painter.drawRoundedRect(rect, PET_CORNER_RADIUS, PET_CORNER_RADIUS)

        if state == PetState.DEVASTATED:
            overlay = QColor(ACCENT_RED)
            overlay.setAlpha(77)  # 30% opacity
            painter.setBrush(QBrush(overlay))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(rect, PET_CORNER_RADIUS, PET_CORNER_RADIUS)

    def _draw_eyes(self, painter: QPainter, ctx: RenderContext) -> None:
        state = ctx.state
        eye_y = -PET_HEIGHT // 2 + 14

        if state == PetState.SLEEP:
            painter.setPen(QPen(QColor(EYE_PUPIL), 2))
            painter.drawLine(-8, eye_y, -4, eye_y)
            painter.drawLine(4, eye_y, 8, eye_y)
            return

        if state == PetState.DEVASTATED:
            painter.setPen(QPen(QColor(EYE_PUPIL), 2))
            for ex in (-6, 6):
                painter.drawLine(ex - 3, eye_y - 3, ex + 3, eye_y + 3)
                painter.drawLine(ex + 3, eye_y - 3, ex - 3, eye_y + 3)
            return

        pet_cx = ctx.pet_x + PET_WIDTH / 2
        if state == PetState.LOOK_AWAY:
            # Look away from cursor
            cursor_angle = math.pi if ctx.cursor_x > pet_cx else 0.0
            max_offset = 1.5
            for ex in (-6, 6):
                painter.setBrush(QBrush(QColor(EYE_WHITE)))
                painter.setPen(Qt.PenStyle.NoPen)
                painter.drawEllipse(QPointF(ex, eye_y), 4, 4)
                painter.setBrush(QBrush(QColor(EYE_PUPIL)))
                painter.drawEllipse(
                    QPointF(ex + max_offset * math.cos(cursor_angle), eye_y + max_offset * math.sin(cursor_angle)),
                    2, 2,
                )
            return

        # Default case: apply eye_modifier from Animator
        eye_mod = ctx.animator.get_eye_modifier() if ctx.animator else {}
        
        pupil_scale = eye_mod.get("pupil_scale", 1.0)
        pupil_shape = eye_mod.get("pupil_shape", "circle")
        
        pupil_color = QColor(EYE_PUPIL)
        if "pupil_color_override" in eye_mod and eye_mod["pupil_color_override"]:
            pupil_color = QColor(eye_mod["pupil_color_override"])
            
        pupil_offset_x = eye_mod.get("pupil_offset_x", 0.0)
        brow_angle = eye_mod.get("brow_angle", 0.0)

        # Draw left (-6) and right (6) eye
        for ex in (-6, 6):
            is_right_eye = (ex == 6)
            
            # 1. Draw Sclera (Perfectly round, size 4x4)
            painter.setBrush(QBrush(QColor(EYE_WHITE)))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(QPointF(ex, eye_y), 4, 4)
            
            # 2. Draw Pupil
            painter.setBrush(QBrush(pupil_color))
            pupil_r = 2 * pupil_scale
            
            # Cursor tracking
            eye_y_screen = ctx.pet_y + PET_HEIGHT // 2 + eye_y
            cursor_angle = math.atan2(ctx.cursor_y - eye_y_screen, ctx.cursor_x - pet_cx)
            max_offset = 1.5
            
            pupil_center_x = ex + max_offset * math.cos(cursor_angle) + pupil_offset_x
            pupil_center_y = eye_y + max_offset * math.sin(cursor_angle)
            
            if pupil_shape == "heart":
                path = QPainterPath()
                y_offset = pupil_center_y - pupil_r + 1
                path.moveTo(pupil_center_x, y_offset + pupil_r)
                path.cubicTo(pupil_center_x - pupil_r, y_offset, pupil_center_x, y_offset - pupil_r, pupil_center_x, y_offset)
                path.cubicTo(pupil_center_x, y_offset - pupil_r, pupil_center_x + pupil_r, y_offset, pupil_center_x, y_offset + pupil_r)
                painter.drawPath(path)
            else:
                painter.drawEllipse(QPointF(pupil_center_x, pupil_center_y), pupil_r, pupil_r)
                
            # 3. Draw Eyebrows (Symmetric Rotation)
            if abs(brow_angle) > 0.5:
                painter.setPen(QPen(QColor("#111111"), 1.5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
                painter.save()
                painter.translate(ex, eye_y - 6) # Float slightly above the eyeball
                
                # Invert angle for the right eye to maintain facial symmetry
                actual_angle = -brow_angle if is_right_eye else brow_angle
                painter.rotate(actual_angle)
                
                painter.drawLine(-4, 0, 4, 0)
                painter.restore()

    def _draw_state_overlay(self, painter: QPainter, ctx: RenderContext) -> None:
        state = ctx.state
        t = ctx.anim_tick
        px, py = ctx.pet_x, ctx.pet_y
        painter.save()

        if state == PetState.SLEEP:
            zzz_alpha = int(128 + 127 * math.sin(t * 0.04))
            c = QColor(BODY_DARK)
            c.setAlpha(zzz_alpha)
            painter.setPen(QPen(c))
            font = painter.font()
            font.setPointSize(8)
            painter.setFont(font)
            painter.drawText(px + PET_WIDTH, py - 10, "Zzz")

        if state == PetState.THINKING:
            dots = ["•", " •", "  •"]
            for i, dot in enumerate(dots):
                alpha = int(255 * abs(math.sin((t * 0.08) - i * 0.7)))
                c = QColor(BODY_DARK)
                c.setAlpha(alpha)
                painter.setPen(QPen(c))
                painter.drawText(px + i * 10, py - 15, dot)

        if state == PetState.AUTONOMOUS_THINKING:
            dots = ["•", " •", "  •"]
            for i, dot in enumerate(dots):
                alpha = int(200 * abs(math.sin((t * 0.06) - i * 0.9)))
                c = QColor(BODY_DARK)
                c.setAlpha(alpha)
                painter.setPen(QPen(c))
                painter.drawText(px + i * 10, py - 15, dot)

        if state == PetState.CHASE:
            painter.setPen(QPen(QColor(BODY_DARK), 1))
            dx = -10 * ctx.wander_direction
            for i in range(3):
                y_off = (i - 1) * 6
                x_start = px + (PET_WIDTH if ctx.wander_direction > 0 else 0) + dx + i * 4 * (-ctx.wander_direction)
                painter.drawLine(x_start, py + 20 + y_off, x_start + 8 * (-ctx.wander_direction), py + 20 + y_off)

        if state == PetState.CELEBRATE:
            jump_y = int(abs(math.sin(t * 0.25)) * 20)
            star_alpha = max(0, int(255 * math.sin(t * 0.25)))
            if star_alpha > 200:
                c = QColor(ACCENT_YELLOW)
                painter.setPen(QPen(c, 1))
                painter.setBrush(QBrush(c))
                for angle in range(0, 360, 72):
                    rad = math.radians(angle)
                    sx = px + PET_WIDTH // 2 + int(25 * math.cos(rad))
                    sy = py + PET_HEIGHT // 2 - jump_y + int(25 * math.sin(rad))
                    painter.drawEllipse(QPointF(sx, sy), 3, 3)

        if state == PetState.SHAKING:
            c = QColor(ACCENT_RED)
            c.setAlpha(180)
            painter.setPen(QPen(c, 1))
            for i in range(4):
                angle = math.radians(i * 90 + t * 5)
                x1 = px + PET_WIDTH // 2 + int(22 * math.cos(angle))
                y1 = py + PET_HEIGHT // 2 + int(22 * math.sin(angle))
                x2 = px + PET_WIDTH // 2 + int(30 * math.cos(angle))
                y2 = py + PET_HEIGHT // 2 + int(30 * math.sin(angle))
                painter.drawLine(x1, y1, x2, y2)

        if state == PetState.SPINNING:
            c = QColor(ACCENT_YELLOW)
            c.setAlpha(200)
            painter.setPen(QPen(c, 2))
            for i in range(6):
                angle = math.radians(i * 60 + t * 3)
                x1 = px + PET_WIDTH // 2 + int(18 * math.cos(angle))
                y1 = py + PET_HEIGHT // 2 + int(18 * math.sin(angle))
                x2 = px + PET_WIDTH // 2 + int(28 * math.cos(angle))
                y2 = py + PET_HEIGHT // 2 + int(28 * math.sin(angle))
                painter.drawLine(x1, y1, x2, y2)

        painter.restore()

    # ── Emotion Overlays ─────────────────────────────────────────────────

    def _draw_overlay(self, painter: QPainter, ctx: RenderContext,
                      overlay: tuple) -> None:
        """Render a single emotion overlay descriptor.

        Supported types::
            ("border", color, width)  → QPen rounded-rect outline
            ("aura", color)            → filled ellipse with alpha
            ("flash", alpha)           → white screen rect with alpha
        """
        kind = overlay[0]
        px, py = ctx.pet_x, ctx.pet_y

        if kind == "border":
            color, width = overlay[1], overlay[2]
            painter.setPen(QPen(QColor(color), width))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRoundedRect(px, py, PET_WIDTH, PET_HEIGHT,
                                    PET_CORNER_RADIUS, PET_CORNER_RADIUS)

        elif kind == "aura":
            color = overlay[1]
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(color))
            cx = px + PET_WIDTH // 2
            cy = py + PET_HEIGHT // 2
            painter.drawEllipse(QPointF(cx, cy), PET_WIDTH, PET_HEIGHT)

        elif kind == "flash":
            alpha = overlay[1]
            c = QColor(255, 255, 255)
            c.setAlpha(alpha)
            painter.setBrush(QBrush(c))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(px, py, PET_WIDTH, PET_HEIGHT,
                                    PET_CORNER_RADIUS, PET_CORNER_RADIUS)

    # ── Speech Bubble ─────────────────────────────────────────────────────

    def _draw_bubble(self, painter: QPainter, ctx: RenderContext) -> None:
        text = ctx.bubble_text
        font = QFont()
        font.setPointSize(BUBBLE_FONT_SIZE)
        font.setFamilies(["Segoe UI", "Segoe UI Emoji", "Apple Color Emoji", "Noto Color Emoji", "DejaVu Sans", "Helvetica Neue", "Arial"])
        painter.setFont(font)

        fm = painter.fontMetrics()
        line_width = BUBBLE_MAX_WIDTH - 2 * BUBBLE_PADDING
        lines = self._wrap_text(text, fm, line_width)
        line_h = fm.height()
        bubble_w = min(BUBBLE_MAX_WIDTH, max(fm.horizontalAdvance(l) for l in lines) + 2 * BUBBLE_PADDING)
        bubble_h = line_h * len(lines) + 2 * BUBBLE_PADDING

        bx = ctx.pet_x + PET_WIDTH // 2 - bubble_w // 2
        by = ctx.pet_y - bubble_h - 12

        sr = ctx.screen_rect
        below = False
        if sr and sr.width() > 0:
            if bx < sr.left():
                bx = sr.left()
            if bx + bubble_w > sr.right():
                bx = sr.right() - bubble_w
            if by < sr.top():
                by = ctx.pet_y + PET_HEIGHT + 12
                below = True

        ctx.bubble_rect = QRect(bx, by, bubble_w, bubble_h)

        painter.setBrush(QBrush(QColor(BUBBLE_BG)))
        painter.setPen(QPen(QColor(BUBBLE_BORDER), 1))
        painter.drawRoundedRect(bx, by, bubble_w, bubble_h, BUBBLE_CORNER_RADIUS, BUBBLE_CORNER_RADIUS)

        tail_cx = ctx.pet_x + PET_WIDTH // 2
        painter.setBrush(QBrush(QColor(BUBBLE_BG)))
        painter.setPen(Qt.PenStyle.NoPen)
        if below:
            tail = QPolygon([
                QPoint(tail_cx - 4, by),
                QPoint(tail_cx + 4, by),
                QPoint(tail_cx, by - 6),
            ])
        else:
            tail = QPolygon([
                QPoint(tail_cx - 4, by + bubble_h),
                QPoint(tail_cx + 4, by + bubble_h),
                QPoint(tail_cx, by + bubble_h + 6),
            ])
        painter.drawPolygon(tail)

        painter.setPen(QPen(QColor(BUBBLE_TEXT_COLOR)))
        for i, line in enumerate(lines):
            painter.drawText(bx + BUBBLE_PADDING, by + BUBBLE_PADDING + (i + 1) * line_h, line)

    @staticmethod
    def _wrap_text(text: str, fm: QFontMetrics, max_width: int) -> list:
        words = text.split()
        lines, current = [], ""
        for word in words:
            test = (current + " " + word).strip()
            if fm.horizontalAdvance(test) <= max_width:
                current = test
            else:
                if current:
                    lines.append(current)
                current = word
        if current:
            lines.append(current)
        return lines or [""]
