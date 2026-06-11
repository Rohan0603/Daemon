import json
import pytest
from pathlib import Path
from unittest.mock import patch
from src import config


class TestConfigAutoCreate:
    """Verify load_config creates default config when file is missing."""

    def test_creates_default_config_on_missing_file(self, tmp_path):
        """When config file doesn't exist, load_config should create it with defaults."""
        fake_path = tmp_path / "daemon_config.json"
        assert not fake_path.exists()

        with patch.object(config, "_CONFIG_PATH", fake_path):
            result = config.load_config()

        assert fake_path.exists(), "Config file should be created"
        saved = json.loads(fake_path.read_text(encoding="utf-8"))
        assert "pet" in saved
        assert "scale" in saved["pet"]
        assert "opacity" in saved["pet"]
        assert isinstance(result, dict)

    def test_does_not_overwrite_existing_config(self, tmp_path):
        """When config file exists with custom values, load_config should not overwrite."""
        fake_path = tmp_path / "daemon_config.json"
        custom = {
            "pet": {
                "scale": 1.5,
                "opacity": 0.7
            }
        }
        fake_path.write_text(json.dumps(custom), encoding="utf-8")

        with patch.object(config, "_CONFIG_PATH", fake_path):
            result = config.load_config()

        saved = json.loads(fake_path.read_text(encoding="utf-8"))
        # Should NOT have been overwritten with defaults
        assert saved.get("pet", {}).get("scale") == 1.5

    def test_migrates_flat_config_to_nested_on_load(self, tmp_path):
        """When flat config exists on disk, load_config should migrate it to nested structure in-memory."""
        fake_path = tmp_path / "daemon_config.json"
        custom_flat = {
            "pet_scale": 1.5,
            "pet_opacity": 0.7,
            "OPENCODE_SERVER_URL": "http://flat-url:4096"
        }
        fake_path.write_text(json.dumps(custom_flat), encoding="utf-8")

        with patch.object(config, "_CONFIG_PATH", fake_path):
            result = config.load_config()

        assert result["pet"]["scale"] == 1.5
        assert result["pet"]["opacity"] == 0.7
        assert result["llm"]["server_url"] == "http://flat-url:4096"