"""
Configuration management for Project Understanding Index.

Stores user preferences in .pui/config.json including:
- Token budgets for different output types
- Language preferences and detection
- Ignore patterns and overrides
"""

import json
from pathlib import Path
from typing import Dict, Any, List, Optional, Set
from dataclasses import dataclass, field, asdict


DEFAULT_CONFIG = {
    "version": 1,
    "budgets": {
        "repomap": 8000,
        "zoom": 4000,
        "impact": 6000,
        "find": 2000
    },
    "languages": {
        "enabled": [
            "python",
            "javascript",
            "typescript",
            "rust",
            "go",
            "java",
            "c",
            "cpp",
            "ruby"
        ],
        "extensions": {
            ".py": "python",
            ".js": "javascript",
            ".jsx": "javascript",
            ".ts": "typescript",
            ".tsx": "typescript",
            ".rs": "rust",
            ".go": "go",
            ".java": "java",
            ".c": "c",
            ".h": "c",
            ".cpp": "cpp",
            ".hpp": "cpp",
            ".cc": "cpp",
            ".rb": "ruby"
        }
    },
    "indexing": {
        "batch_size": 100,
        "max_file_size": 1048576,  # 1MB
        "follow_symlinks": False,
        "include_hidden": False
    },
    "ignore": {
        "patterns": [],
        "include": [],
        "exclude": []
    },
    "output": {
        "format": "markdown",
        "verbose": False,
        "color": True
    }
}


@dataclass
class Budgets:
    """Token budgets for different output types."""
    repomap: int = 8000
    zoom: int = 4000
    impact: int = 6000
    find: int = 2000


@dataclass
class Languages:
    """Language configuration."""
    enabled: List[str] = field(default_factory=lambda: [
        "python", "javascript", "typescript", "rust", "go", 
        "java", "c", "cpp", "ruby"
    ])
    extensions: Dict[str, str] = field(default_factory=lambda: {
        ".py": "python",
        ".js": "javascript",
        ".jsx": "javascript",
        ".ts": "typescript",
        ".tsx": "typescript",
        ".rs": "rust",
        ".go": "go",
        ".java": "java",
        ".c": "c",
        ".h": "c",
        ".cpp": "cpp",
        ".hpp": "cpp",
        ".cc": "cpp",
        ".rb": "ruby"
    })


@dataclass
class Indexing:
    """Indexing configuration."""
    batch_size: int = 100
    max_file_size: int = 1048576
    follow_symlinks: bool = False
    include_hidden: bool = False


@dataclass
class Ignore:
    """Ignore pattern configuration."""
    patterns: List[str] = field(default_factory=list)
    include: List[str] = field(default_factory=list)
    exclude: List[str] = field(default_factory=list)


@dataclass
class Output:
    """Output configuration."""
    format: str = "markdown"
    verbose: bool = False
    color: bool = True


@dataclass
class Config:
    """Complete configuration."""
    version: int = 1
    budgets: Budgets = field(default_factory=Budgets)
    languages: Languages = field(default_factory=Languages)
    indexing: Indexing = field(default_factory=Indexing)
    ignore: Ignore = field(default_factory=Ignore)
    output: Output = field(default_factory=Output)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary."""
        return {
            "version": self.version,
            "budgets": asdict(self.budgets),
            "languages": asdict(self.languages),
            "indexing": asdict(self.indexing),
            "ignore": asdict(self.ignore),
            "output": asdict(self.output)
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Config":
        """Create configuration from dictionary."""
        return cls(
            version=data.get("version", 1),
            budgets=Budgets(**data.get("budgets", {})),
            languages=Languages(**data.get("languages", {})),
            indexing=Indexing(**data.get("indexing", {})),
            ignore=Ignore(**data.get("ignore", {})),
            output=Output(**data.get("output", {}))
        )


class ConfigManager:
    """Manages configuration loading and saving."""
    
    def __init__(self, repo_root: Path, verbose: bool = False):
        """
        Initialize configuration manager.
        
        Args:
            repo_root: Repository root directory
            verbose: Enable verbose logging
        """
        self.repo_root = Path(repo_root)
        self.verbose = verbose
        self.config_dir = self.repo_root / ".pui"
        self.config_file = self.config_dir / "config.json"
        self._config: Optional[Config] = None
    
    def _log(self, message: str) -> None:
        """Log message if verbose mode enabled."""
        if self.verbose:
            print(f"[Config] {message}")
    
    def load(self) -> Config:
        """
        Load configuration from file or create default.
        
        Returns:
            Configuration object
        """
        if self._config:
            return self._config
        
        if self.config_file.exists():
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                self._config = Config.from_dict(data)
                self._log(f"Loaded config from {self.config_file}")
            except (json.JSONDecodeError, KeyError, TypeError) as e:
                self._log(f"Error loading config: {e}, using defaults")
                self._config = Config()
        else:
            self._log("Config file not found, using defaults")
            self._config = Config()
        
        return self._config
    
    def save(self, config: Optional[Config] = None) -> None:
        """
        Save configuration to file.
        
        Args:
            config: Configuration to save (uses loaded config if None)
        """
        if config:
            self._config = config
        elif not self._config:
            self._config = Config()
        
        self.config_dir.mkdir(parents=True, exist_ok=True)
        
        with open(self.config_file, 'w', encoding='utf-8') as f:
            json.dump(self._config.to_dict(), f, indent=2)
        
        self._log(f"Saved config to {self.config_file}")
    
    def get_config_path(self) -> Path:
        """Get path to configuration file."""
        return self.config_file
    
    def exists(self) -> bool:
        """Check if configuration file exists."""
        return self.config_file.exists()
    
    def update(self, **kwargs) -> Config:
        """
        Update configuration values.
        
        Args:
            **kwargs: Key-value pairs to update
        
        Returns:
            Updated configuration
        """
        config = self.load()
        
        for key, value in kwargs.items():
            if '.' in key:
                # Handle nested keys like "budgets.repomap"
                parts = key.split('.')
                obj = config
                for part in parts[:-1]:
                    obj = getattr(obj, part)
                setattr(obj, parts[-1], value)
            else:
                setattr(config, key, value)
        
        self.save(config)
        return config
    
    def get_language_for_extension(self, ext: str) -> Optional[str]:
        """
        Get language name for a file extension.
        
        Args:
            ext: File extension (including dot, e.g., '.py')
        
        Returns:
            Language name or None
        """
        config = self.load()
        ext = ext.lower()
        return config.languages.extensions.get(ext)
    
    def get_extensions_for_language(self, language: str) -> Set[str]:
        """
        Get all file extensions for a language.
        
        Args:
            language: Language name
        
        Returns:
            Set of file extensions
        """
        config = self.load()
        language = language.lower()
        return {
            ext for ext, lang in config.languages.extensions.items()
            if lang == language
        }
    
    def get_all_extensions(self) -> Set[str]:
        """Get all configured file extensions."""
        config = self.load()
        return set(config.languages.extensions.keys())
    
    def is_language_enabled(self, language: str) -> bool:
        """Check if a language is enabled for indexing."""
        config = self.load()
        return language.lower() in [lang.lower() for lang in config.languages.enabled]


def get_config(repo_root: Path, verbose: bool = False) -> Config:
    """
    Get configuration for a repository.
    
    Args:
        repo_root: Repository root directory
        verbose: Enable verbose logging
    
    Returns:
        Configuration object
    """
    manager = ConfigManager(repo_root, verbose)
    return manager.load()
