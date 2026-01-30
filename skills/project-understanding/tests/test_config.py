"""
Unit tests for the config module.

Tests cover:
- Configuration loading and saving
- Default values
- Language detection
- Extension mapping
- Configuration updates
"""

import pytest
import tempfile
import json
from pathlib import Path

from scripts.lib.config import Config, ConfigManager, Budgets, Languages, get_config


class TestConfigDefaults:
    """Tests for default configuration values."""
    
    def test_default_budgets(self):
        """Default budgets should be set."""
        budgets = Budgets()
        
        assert budgets.repomap == 8000
        assert budgets.zoom == 4000
        assert budgets.impact == 6000
        assert budgets.find == 2000
    
    def test_default_languages(self):
        """Default languages should include common languages."""
        langs = Languages()
        
        assert "python" in langs.enabled
        assert "javascript" in langs.enabled
        assert "rust" in langs.enabled
    
    def test_default_extensions(self):
        """Default extensions should map to languages."""
        langs = Languages()
        
        assert langs.extensions[".py"] == "python"
        assert langs.extensions[".js"] == "javascript"
        assert langs.extensions[".rs"] == "rust"
    
    def test_config_to_dict(self):
        """Config should convert to dictionary."""
        config = Config()
        data = config.to_dict()
        
        assert "version" in data
        assert "budgets" in data
        assert "languages" in data
        assert data["budgets"]["repomap"] == 8000


class TestConfigManagerLoading:
    """Tests for configuration loading."""
    
    def test_load_default_config(self):
        """Loading without file should return defaults."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = ConfigManager(Path(tmpdir))
            config = manager.load()
            
            assert config.budgets.repomap == 8000
            assert "python" in config.languages.enabled
    
    def test_load_from_file(self):
        """Loading from file should read values."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_dir = Path(tmpdir) / ".pui"
            config_dir.mkdir()
            
            config_file = config_dir / "config.json"
            config_file.write_text(json.dumps({
                "version": 1,
                "budgets": {"repomap": 5000}
            }))
            
            manager = ConfigManager(Path(tmpdir))
            config = manager.load()
            
            assert config.budgets.repomap == 5000
    
    def test_load_invalid_json_uses_defaults(self):
        """Invalid JSON should use defaults."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_dir = Path(tmpdir) / ".pui"
            config_dir.mkdir()
            
            config_file = config_dir / "config.json"
            config_file.write_text("invalid json")
            
            manager = ConfigManager(Path(tmpdir))
            config = manager.load()
            
            # Should still have valid defaults
            assert config.budgets.repomap == 8000


class TestConfigManagerSaving:
    """Tests for configuration saving."""
    
    def test_save_creates_directory(self):
        """Saving should create config directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = ConfigManager(Path(tmpdir))
            config = Config()
            manager.save(config)
            
            assert (Path(tmpdir) / ".pui").exists()
            assert (Path(tmpdir) / ".pui" / "config.json").exists()
    
    def test_save_and_load_roundtrip(self):
        """Save and load should preserve values."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = ConfigManager(Path(tmpdir))
            
            config = Config()
            config.budgets.repomap = 9999
            manager.save(config)
            
            # Create new manager to test loading
            manager2 = ConfigManager(Path(tmpdir))
            loaded = manager2.load()
            
            assert loaded.budgets.repomap == 9999


class TestLanguageDetection:
    """Tests for language detection."""
    
    @pytest.fixture
    def manager(self):
        """Create a config manager with defaults."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield ConfigManager(Path(tmpdir))
    
    def test_get_language_for_extension(self, manager):
        """Should return language for known extension."""
        manager.load()
        
        assert manager.get_language_for_extension(".py") == "python"
        assert manager.get_language_for_extension(".js") == "javascript"
    
    def test_get_language_case_insensitive(self, manager):
        """Extension matching should be case insensitive."""
        assert manager.get_language_for_extension(".PY") == "python"
        assert manager.get_language_for_extension(".Js") == "javascript"
    
    def test_get_language_unknown_extension(self, manager):
        """Unknown extension should return None."""
        assert manager.get_language_for_extension(".unknown") is None
    
    def test_get_extensions_for_language(self, manager):
        """Should return extensions for language."""
        exts = manager.get_extensions_for_language("python")
        assert ".py" in exts
    
    def test_get_all_extensions(self, manager):
        """Should return all configured extensions."""
        exts = manager.get_all_extensions()
        assert ".py" in exts
        assert ".js" in exts
        assert ".rs" in exts
    
    def test_is_language_enabled(self, manager):
        """Should check if language is enabled."""
        assert manager.is_language_enabled("python") is True
        assert manager.is_language_enabled("unknown") is False


class TestConfigUpdates:
    """Tests for configuration updates."""
    
    def test_update_simple_value(self):
        """Should update simple config value."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = ConfigManager(Path(tmpdir))
            manager.load()
            
            config = manager.update(version=2)
            
            assert config.version == 2
    
    def test_update_nested_value(self):
        """Should update nested config value."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = ConfigManager(Path(tmpdir))
            manager.load()
            
            config = manager.update(**{"budgets.repomap": 5000})
            
            assert config.budgets.repomap == 5000
    
    def test_update_saves_to_file(self):
        """Update should save to file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = ConfigManager(Path(tmpdir))
            manager.load()
            manager.update(version=5)
            
            # Read file directly
            config_file = Path(tmpdir) / ".pui" / "config.json"
            data = json.loads(config_file.read_text())
            
            assert data["version"] == 5


class TestConfigPath:
    """Tests for configuration paths."""
    
    def test_get_config_path(self):
        """Should return correct config path."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = ConfigManager(Path(tmpdir))
            path = manager.get_config_path()
            
            assert path == Path(tmpdir) / ".pui" / "config.json"
    
    def test_exists(self):
        """Should check if config file exists."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = ConfigManager(Path(tmpdir))
            
            assert manager.exists() is False
            
            manager.load()
            manager.save()
            
            assert manager.exists() is True


class TestGetConfig:
    """Tests for get_config convenience function."""
    
    def test_get_config_returns_config(self):
        """Should return Config object."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = get_config(Path(tmpdir))
            
            assert isinstance(config, Config)
            assert config.budgets.repomap == 8000
