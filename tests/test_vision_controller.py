import base64
import io

import pytest
from PIL import Image

from src.system.vision_controller import VisionController


def test_capture_screen_returns_png_and_grid(monkeypatch):
    image = Image.new("RGB", (200, 100), "black")
    monkeypatch.setattr("PIL.ImageGrab.grab", lambda **kwargs: image.copy())
    controller = VisionController(grid_spacing=50, screen_bounds_provider=lambda: (100, 200, 300, 300))

    result = controller.capture_screen(add_grid=True)

    decoded = base64.b64decode(result["image_base64"])
    captured = Image.open(io.BytesIO(decoded))
    assert captured.size == (200, 100)
    assert result["region"] == (100, 200, 300, 300)
    assert result["grid_overlay"] is True
    assert result["monitor_info"][0]["dpi_scale"] == 1.0


def test_capture_region_is_clamped_to_virtual_screen(monkeypatch):
    seen = {}
    monkeypatch.setattr(
        "PIL.ImageGrab.grab",
        lambda **kwargs: seen.update(kwargs) or Image.new("RGB", (10, 10)),
    )
    controller = VisionController(screen_bounds_provider=lambda: (10, 20, 110, 120))

    controller.capture_screen(region=(-50, -20, 500, 500), add_grid=False)

    assert seen["bbox"] == (10, 20, 110, 120)
    assert seen["all_screens"] is True


def test_click_coordinate_clamps_and_supports_double_click():
    positions = []
    clicks = []
    controller = VisionController(
        screen_bounds_provider=lambda: (10, 20, 110, 120),
        cursor_position_provider=lambda: (50, 60),
        cursor_provider=lambda x, y: positions.append((x, y)),
        click_provider=lambda click: clicks.append(click),
        sleep_provider=lambda _: None,
    )

    result = controller.click_coordinate(999, -1, "double", smooth=False)

    assert result == {
        "success": True,
        "error": None,
        "x": 109,
        "y": 20,
        "click_type": "double",
    }
    assert positions == [(109, 20)]
    assert clicks == ["left", "left"]


def test_smooth_click_interpolates_from_current_cursor():
    positions = []
    controller = VisionController(
        screen_bounds_provider=lambda: (0, 0, 100, 100),
        cursor_position_provider=lambda: (0, 0),
        cursor_provider=lambda x, y: positions.append((x, y)),
        click_provider=lambda _: None,
        sleep_provider=lambda _: None,
    )

    controller.click_coordinate(60, 40, smooth=True, duration=0.1)

    assert positions[0] != (60, 40)
    assert positions[-1] == (60, 40)


def test_click_rejects_invalid_type_without_cursor_action():
    controller = VisionController(
        screen_bounds_provider=lambda: (0, 0, 100, 100),
        cursor_provider=lambda *_: pytest.fail("cursor should not move"),
    )

    result = controller.click_coordinate(1, 2, "invalid", smooth=False)

    assert result["success"] is False
    assert "Unsupported click type" in result["error"]


def test_type_text_uses_injected_keyboard():
    calls = []

    class Keyboard:
        def type(self, text, interval):
            calls.append((text, interval))

    controller = VisionController(keyboard_provider=lambda: Keyboard())

    assert controller.type_text("abc", 0.02) == {
        "success": True,
        "error": None,
        "characters": 3,
    }
    assert calls == [("abc", 0.02)]


def test_invalid_capture_region_is_reported():
    controller = VisionController(screen_bounds_provider=lambda: (0, 0, 100, 100))

    with pytest.raises(ValueError, match="region must contain four"):
        controller.capture_screen(region=(1, 2, 3), add_grid=False)
