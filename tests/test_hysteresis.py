from src.constants import CHASE_ENTER_RADIUS_PX, CHASE_EXIT_RADIUS_PX


def test_hysteresis_gap_exists():
    """Exit radius must be at least 2x enter radius for effective deadzone."""
    assert CHASE_EXIT_RADIUS_PX >= CHASE_ENTER_RADIUS_PX * 2, (
        f"Exit ({CHASE_EXIT_RADIUS_PX}px) should be >= 2x enter ({CHASE_ENTER_RADIUS_PX}px)"
    )


def test_click_through_debounce_wider():
    """Click-through debounce should be at least 0.5s."""
    from src.click_through import _TOGGLE_DEBOUNCE_SEC
    assert _TOGGLE_DEBOUNCE_SEC >= 0.5, (
        f"Debounce ({_TOGGLE_DEBOUNCE_SEC}s) should be >= 0.5s"
    )