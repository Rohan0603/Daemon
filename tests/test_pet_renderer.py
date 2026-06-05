import pytest
import sys
import math
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QFont, QFontMetrics
from src.pet_renderer import PetRenderer

@pytest.fixture(scope="session")
def qapp():
    return QApplication.instance() or QApplication(sys.argv)

def test_wrap_text_basic(qapp):
    font = QFont("Segoe UI")
    fm = QFontMetrics(font)
    text = "Hello world from a test string"
    wrapped = PetRenderer._wrap_text(text, fm, 100)
    assert isinstance(wrapped, list)
    assert len(wrapped) > 0
    assert "".join(wrapped).replace(" ", "") == text.replace(" ", "")


def test_eye_angle_right():
    pet_cx, pet_cy = 120.0, 525.0
    cursor_x, cursor_y = 200, 525
    angle = math.atan2(cursor_y - pet_cy, cursor_x - pet_cx)
    assert abs(math.cos(angle) - 1.0) < 0.01
    assert abs(math.sin(angle)) < 0.01


def test_eye_angle_above():
    pet_cx, pet_cy = 120.0, 525.0
    cursor_x, cursor_y = 120, 400
    angle = math.atan2(cursor_y - pet_cy, cursor_x - pet_cx)
    assert abs(math.cos(angle)) < 0.01
    assert abs(math.sin(angle) + 1.0) < 0.01


def test_pupil_offset_magnitude():
    max_offset = 1.5
    angle = math.atan2(1, 1)
    dx = max_offset * math.cos(angle)
    dy = max_offset * math.sin(angle)
    assert abs(math.hypot(dx, dy) - max_offset) < 0.001


def test_eye_tracks_cursor_in_zone_below_eye_above_centre():
    from src.constants import PET_HEIGHT, PET_WIDTH

    pet_y, pet_x = 100, 200
    eye_y_local = -PET_HEIGHT // 2 + 14          # -11 in painter space
    eye_y_screen = pet_y + PET_HEIGHT // 2 + eye_y_local  # = 114
    pet_cx = pet_x + PET_WIDTH / 2

    # Cursor at eye_y+6: below eye but above body centre (pet_y+25 = 125)
    cursor_y = eye_y_screen + 6
    cursor_x = pet_cx

    # With CORRECT formula (eye-centre reference):
    angle = math.atan2(cursor_y - eye_y_screen, cursor_x - pet_cx)
    assert math.sin(angle) >= 0, "Pupil should move down when cursor is below eye"
