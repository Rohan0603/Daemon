"""Tests for _calculate_joke_modifier APM-based scaling."""
import pytest
from unittest.mock import MagicMock, patch
from src.pet_window import PetWindow


class TestJokeModifier:
    def setup_method(self):
        """Create a minimal PetWindow instance for testing."""
        with patch.object(PetWindow, '__init__', lambda self, *a, **kw: None):
            self.pw = PetWindow.__new__(PetWindow)
            self.pw._current_apm = 0

    def test_rapid_fire_apm_lt_10(self):
        self.pw._current_apm = 5
        assert self.pw._calculate_joke_modifier() == 0.5

    def test_normal_apm_10_to_19(self):
        self.pw._current_apm = 15
        assert self.pw._calculate_joke_modifier() == 1.0

    def test_rare_apm_20_to_39(self):
        self.pw._current_apm = 30
        assert self.pw._calculate_joke_modifier() == 2.0

    def test_very_rare_apm_40_plus(self):
        self.pw._current_apm = 50
        assert self.pw._calculate_joke_modifier() == 3.0

    def test_boundary_10(self):
        self.pw._current_apm = 10
        assert self.pw._calculate_joke_modifier() == 1.0

    def test_boundary_20(self):
        self.pw._current_apm = 20
        assert self.pw._calculate_joke_modifier() == 2.0

    def test_boundary_40(self):
        self.pw._current_apm = 40
        assert self.pw._calculate_joke_modifier() == 3.0
