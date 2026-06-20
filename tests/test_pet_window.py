import pytest
from unittest.mock import ANY, MagicMock, patch

# pytest markers - use module-level decorator for pytest.ini compatibility
pytestmark = pytest.mark.slow

# Fixtures are now provided by tests/conftest.py — mock_background_workers,
# app, and _mock_firebase_diary are shared across all test files.