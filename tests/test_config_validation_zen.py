import json
import os
import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path

# Import the actual config module
from src.config import load_config, flatten_config, unflatten_config, validate_config, MissingConfigurationError

# Make sure tests directory is in path
import sys
sys.path.insert(0, os.path.abspath('.'))

from tests.test_config_validation_zen import *