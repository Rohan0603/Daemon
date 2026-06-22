"""Tests for PluginRegistry and PluginManager."""

from __future__ import annotations

import math
import os
import sys
import tempfile
from pathlib import Path

import pytest

# Add project root to path for imports
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


class TestPluginRegistry:
    """Test the PluginRegistry class in isolation."""

    @pytest.fixture
    def registry(self):
        from src.plugin_registry import PluginRegistry
        return PluginRegistry()

    def test_create_registry(self, registry):
        assert registry.plugin_count == 0
        assert registry.emotion_rule_count == 0
        assert registry.behavior_trigger_count == 0

    def test_register_emotion_profile(self, registry):
        from src.animator import Emotion, EmotionProfile
        profile = EmotionProfile(
            name="test_emotion",
            color_override="#FF0000",
        )
        registry.register_emotion_profile(Emotion.ANGER, profile, plugin_name="test_plugin")

        profiles = registry.get_emotion_profiles()
        assert Emotion.ANGER in profiles
        assert profiles[Emotion.ANGER] is profile
        # Name mismatch is fine — profile carries its own name
        assert profiles[Emotion.ANGER].name == "test_emotion"

    def test_register_multiple_emotion_profiles(self, registry):
        from src.animator import Emotion, EmotionProfile
        p1 = EmotionProfile(name="p1")
        p2 = EmotionProfile(name="p2")
        registry.register_emotion_profile(Emotion.MIRTH, p1)
        registry.register_emotion_profile(Emotion.FEAR, p2)
        assert len(registry.get_emotion_profiles()) == 2

    def test_register_emotion_rule(self, registry):
        from src.animator import Emotion

        def my_rule(ctx):
            if "legacy" in (ctx.get("window_title") or "").lower():
                return Emotion.PATHOS
            return None

        registry.register_emotion_rule(
            "test_rule", my_rule, plugin_name="test", priority=50
        )
        assert registry.emotion_rule_count == 1

        # Should fire for legacy windows
        result = registry.evaluate_emotion({"window_title": "Legacy App"})
        assert result == Emotion.PATHOS

        # Should not fire for modern windows
        result = registry.evaluate_emotion({"window_title": "Modern App"})
        assert result is None

    def test_emotion_rule_priority_order(self, registry):
        from src.animator import Emotion

        # Register a high-priority rule that always returns ANGER
        registry.register_emotion_rule(
            "always_anger",
            lambda ctx: Emotion.ANGER,
            priority=10,  # Low number = high priority
        )
        # Register a low-priority rule that always returns MIRTH
        registry.register_emotion_rule(
            "always_mirth",
            lambda ctx: Emotion.MIRTH,
            priority=100,  # High number = low priority
        )

        # Should get ANGER (higher priority runs first)
        result = registry.evaluate_emotion({"window_title": "anything"})
        assert result == Emotion.ANGER

    def test_emotion_rule_exception_handled(self, registry):
        """A broken rule should not prevent other rules from running."""

        def broken_rule(ctx):
            raise ValueError("I'm broken")

        registry.register_emotion_rule("broken", broken_rule, priority=50)
        # This one should still run
        registry.register_emotion_rule(
            "working",
            lambda ctx: None,
            priority=100,
        )

        # Should not raise
        result = registry.evaluate_emotion({"window_title": "test"})
        assert result is None  # No rule returned a result

    def test_register_behavior_trigger(self, registry):
        def my_trigger(ctx):
            if ctx.get("apm", 0) > 100:
                return {"mode": "excitement", "emotion": "hyper"}
            return None

        registry.register_behavior_trigger(
            "test_trigger", my_trigger, plugin_name="test", cooldown_sec=10
        )
        assert registry.behavior_trigger_count == 1

        # Should fire for high APM
        triggered = registry.get_ready_behavior_triggers({"apm": 150})
        assert len(triggered) == 1
        assert triggered[0]["mode"] == "excitement"

        # Should NOT fire for low APM
        triggered = registry.get_ready_behavior_triggers({"apm": 10})
        assert len(triggered) == 0

    def test_behavior_trigger_cooldown(self, registry):
        calls = 0

        def always_fire(ctx):
            nonlocal calls
            calls += 1
            return {"mode": "test"}

        registry.register_behavior_trigger(
            "cooldown_test", always_fire, cooldown_sec=3600  # Long cooldown
        )

        # First call: should fire
        triggered = registry.get_ready_behavior_triggers({})
        assert len(triggered) == 1

        # Second call immediately after: cooldown, should NOT fire
        triggered = registry.get_ready_behavior_triggers({})
        assert len(triggered) == 0

    def test_register_brain_field(self, registry):
        # Register a valid brain field
        registry.register_brain_field(
            field_name="custom_mood_scale",
            field_type="float",
            default=0.5,
            locked=False,
            plugin_name="mood_tracker"
        )
        fields = registry.get_brain_fields()
        assert "custom_mood_scale" in fields
        assert fields["custom_mood_scale"] == {
            "type": "float",
            "locked": False,
            "default": 0.5,
            "plugin": "mood_tracker"
        }

    def test_register_brain_field_invalid_type(self, registry):
        # Invalid type should raise ValueError
        with pytest.raises(ValueError) as excinfo:
            registry.register_brain_field(
                field_name="custom_invalid",
                field_type="invalid_type",
                default=None
            )
        assert "Invalid field_type 'invalid_type'" in str(excinfo.value)

    def test_register_brain_field_locked(self, registry):
        registry.register_brain_field(
            field_name="secret_key",
            field_type="str",
            default="init",
            locked=True,
            plugin_name="auth"
        )
        fields = registry.get_brain_fields()
        assert fields["secret_key"]["locked"] is True

    def test_plugin_brain_schema_merge(self, registry):
        import src.brain_schema as _bs

        # Save original schema and defaults
        orig_schema = dict(_bs.BRAIN_SCHEMA)
        orig_defaults = dict(_bs.DEFAULT_BRAIN)

        try:
            registry.register_brain_field(
                field_name="plugin_mood_indicator",
                field_type="str",
                default="neutral",
                locked=False,
                plugin_name="mood_indicator_plugin"
            )

            # Merge logic (simulated from daemon.py)
            from src.brain_schema import load_brain_schema
            loaded_schema = load_brain_schema()
            loaded_schema.update(registry.get_brain_fields())
            _bs.BRAIN_SCHEMA = loaded_schema
            _bs.DEFAULT_BRAIN = {k: v["default"] for k, v in loaded_schema.items()}

            # Verify custom field exists in BRAIN_SCHEMA and DEFAULT_BRAIN
            assert "plugin_mood_indicator" in _bs.BRAIN_SCHEMA
            assert _bs.DEFAULT_BRAIN["plugin_mood_indicator"] == "neutral"

            # Verify apply_brain_update supports the new field
            from src.brain_schema import apply_brain_update
            update = {"plugin_mood_indicator": "happy", "user_name": "ignore_locked_field"}
            applied = apply_brain_update(update)
            assert applied.get("plugin_mood_indicator") == "happy"

        finally:
            # Restore original state
            _bs.BRAIN_SCHEMA = orig_schema
            _bs.DEFAULT_BRAIN = orig_defaults


class TestPluginManager:
    """Test PluginManager with a temporary plugins directory."""

    @pytest.fixture
    def registry(self):
        from src.plugin_registry import PluginRegistry
        return PluginRegistry()

    @pytest.fixture
    def tmp_plugins(self, tmp_path):
        """Create a temporary plugins directory with test plugins."""
        plugins_dir = tmp_path / "plugins"
        plugins_dir.mkdir()

        # Valid plugin
        (plugins_dir / "valid_plugin.py").write_text("""
metadata = {
    "name": "Valid Plugin",
    "version": "1.0.0",
    "description": "A valid test plugin",
}

def register(registry):
    from src.animator import Emotion, EmotionProfile
    registry.register_emotion_profile(
        Emotion.MIRTH,
        EmotionProfile(name="custom_mirth", color_override="#00FF00"),
        plugin_name="valid_plugin",
    )
""")

        # Plugin without register function (should be skipped)
        (plugins_dir / "no_register.py").write_text("""
metadata = {"name": "No Register"}
# No register() function — should be skipped
""")

        # Plugin that raises during register (should be caught)
        (plugins_dir / "broken_plugin.py").write_text("""
metadata = {"name": "Broken Plugin", "version": "0.1"}

def register(registry):
    raise RuntimeError("I am broken!")
""")

        # Plugin that adds a behavior trigger
        (plugins_dir / "behavior_plugin.py").write_text("""
metadata = {"name": "Behavior Plugin", "version": "1.0.0"}

def register(registry):
    def trigger(ctx):
        return {"mode": "plugin_behavior"} if ctx.get("apm", 0) > 50 else None
    registry.register_behavior_trigger("burst_trigger", trigger, plugin_name="behavior_plugin")
""")

        # Skippable files
        (plugins_dir / "__init__.py").write_text("")
        (plugins_dir / "_hidden.py").write_text("""
# Starts with underscore, should be skipped
""")

        return plugins_dir

    def test_discover(self, tmp_plugins, registry):
        from src.plugin_manager import PluginManager
        manager = PluginManager(registry, plugin_dir=str(tmp_plugins))
        discovered = manager.discover()

        # Should find 3 valid plugins (not __init__.py, not _hidden.py)
        names = {p.name for p in discovered}
        assert "valid_plugin.py" in names
        assert "no_register.py" in names
        assert "broken_plugin.py" in names
        assert "behavior_plugin.py" in names
        assert "__init__.py" not in names
        assert "_hidden.py" not in names

    def test_load_all(self, tmp_plugins, registry):
        from src.plugin_manager import PluginManager
        manager = PluginManager(registry, plugin_dir=str(tmp_plugins))
        manager.discover()
        manager.load_all()

        # valid_plugin and behavior_plugin should load, broken and no_register should fail silently
        loaded_names = [p.name for p in manager.loaded_plugins]
        assert "Valid Plugin" in loaded_names
        assert "Behavior Plugin" in loaded_names
        assert "Broken Plugin" not in loaded_names
        assert "No Register" not in loaded_names

        # Registry should have profiles from valid_plugin
        from src.animator import Emotion
        profiles = registry.get_emotion_profiles()
        assert Emotion.MIRTH in profiles
        assert profiles[Emotion.MIRTH].name == "custom_mirth"

        # Registry should have behavior triggers from behavior_plugin
        assert registry.behavior_trigger_count == 1

    def test_load_nonexistent_plugin(self, tmp_plugins, registry):
        from src.plugin_manager import PluginManager
        manager = PluginManager(registry, plugin_dir=str(tmp_plugins))
        info = manager.load_plugin("nonexistent")
        assert info is None

    def test_load_single_plugin(self, tmp_plugins, registry):
        from src.plugin_manager import PluginManager
        manager = PluginManager(registry, plugin_dir=str(tmp_plugins))
        info = manager.load_plugin("valid_plugin")
        assert info is not None
        assert info.name == "Valid Plugin"
        assert info.version == "1.0.0"
        assert registry.emotion_rule_count == 0  # No rules registered, only profile

    def test_plugin_file_not_python(self, tmp_plugins, registry):
        """Non-.py files in plugins dir should be ignored."""
        (tmp_plugins / "readme.txt").write_text("not a plugin")
        from src.plugin_manager import PluginManager
        manager = PluginManager(registry, plugin_dir=str(tmp_plugins))
        discovered = manager.discover()
        assert all(p.suffix == ".py" for p in discovered)
        assert "readme.txt" not in {p.name for p in discovered}

    def test_apply_plugin_profiles(self, registry):
        """Test the animator integration function."""
        from src.animator import Emotion, EmotionProfile, EMOTION_PROFILES, apply_plugin_profiles

        # Register a plugin profile
        profile = EmotionProfile(name="override", color_override="#123456")
        registry.register_emotion_profile(Emotion.MIRTH, profile)

        # Save original
        original_profile = EMOTION_PROFILES[Emotion.MIRTH]

        try:
            apply_plugin_profiles(registry)
            # EMOTION_PROFILES should be updated
            assert EMOTION_PROFILES[Emotion.MIRTH] is profile
            assert EMOTION_PROFILES[Emotion.MIRTH].color_override == "#123456"
        finally:
            # Restore
            EMOTION_PROFILES[Emotion.MIRTH] = original_profile

    def test_apply_plugin_profiles_invalid_arg(self, registry):
        from src.animator import apply_plugin_profiles
        # Should not raise when given wrong type
        apply_plugin_profiles("not_a_registry")  # noqa


def test_behavior_controller_plugin_emotion_integration():
    """Verify BehaviorController._evaluate_plugin_emotion works with PluginRegistry."""
    from src.plugin_registry import PluginRegistry
    from src.animator import Emotion

    registry = PluginRegistry()

    # Register a plugin rule
    def custom_rule(ctx):
        if "special" in (ctx.get("window_title") or "").lower():
            return Emotion.ANGER
        return None

    registry.register_emotion_rule("special_rule", custom_rule, priority=10)

    # Verify the rule works
    context = {"window_title": "Special Project", "apm": 0, "idle_seconds": 0}
    result = registry.evaluate_emotion(context)
    assert result == Emotion.ANGER

    context = {"window_title": "Normal Project", "apm": 0, "idle_seconds": 0}
    result = registry.evaluate_emotion(context)
    assert result is None


def test_behavior_controller_passes_context():
    """Verify the context dict passed to plugin rules contains expected keys."""
    from src.plugin_registry import PluginRegistry

    captured = {}

    def capture_rule(ctx):
        captured.update(ctx)
        return None

    registry = PluginRegistry()
    registry.register_emotion_rule("capture", capture_rule, priority=10)

    context = {
        "apm": 42,
        "idle_seconds": 30.5,
        "window_title": "Test App",
        "typing_content": "hello",
        "window_switch_count": 3,
        "last_risky_match": None,
    }
    registry.evaluate_emotion(context)
    assert captured.get("apm") == 42
    assert captured.get("idle_seconds") == 30.5
    assert captured.get("window_title") == "Test App"
    assert captured.get("typing_content") == "hello"
    assert captured.get("window_switch_count") == 3
    assert "last_risky_match" in captured
