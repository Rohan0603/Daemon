import json
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
from src import config


class TestConfigAutoCreate:
    """Verify load_config creates default config when file is missing."""

    def test_creates_default_config_on_missing_file(self, tmp_path):
        """When config file doesn't exist, load_config should create it with defaults."""
        fake_path = tmp_path / ".daemon_config.json"
        assert not fake_path.exists()

        with patch.object(config, "_CONFIG_PATH", fake_path):
            result = config.load_config()

        assert fake_path.exists(), "Config file should be created"
        saved = json.loads(fake_path.read_text(encoding="utf-8"))
        assert "pet_scale" in saved
        assert "pet_opacity" in saved
        assert isinstance(result, dict)

    def test_does_not_overwrite_existing_config(self, tmp_path):
        """When config file exists with custom values, load_config should not overwrite."""
        fake_path = tmp_path / ".daemon_config.json"
        custom = {"pet_scale": 1.5, "pet_opacity": 0.7}
        fake_path.write_text(json.dumps(custom), encoding="utf-8")

        with patch.object(config, "_CONFIG_PATH", fake_path):
            result = config.load_config()

        saved = json.loads(fake_path.read_text(encoding="utf-8"))
        # Should NOT have been overwritten with defaults
        assert saved.get("pet_scale") == 1.5