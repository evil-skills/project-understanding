"""
File ignore pattern management.

Merges .gitignore patterns with default ignore patterns and supports
CLI-level include/exclude overrides.
"""

import fnmatch
import os
from pathlib import Path
from typing import List, Optional, Set


class IgnorePattern:
    """Represents a single ignore pattern."""
    
    def __init__(self, pattern: str, source: str = "default"):
        """
        Initialize ignore pattern.
        
        Args:
            pattern: The glob pattern to match
            source: Source of pattern (default, gitignore, cli)
        """
        self.pattern = pattern.strip()
        self.source = source
        self.is_negation = self.pattern.startswith('!')
        
        if self.is_negation:
            self.pattern = self.pattern[1:]
        
        # Handle directory-only patterns
        self.is_directory = self.pattern.endswith('/')
        if self.is_directory:
            self.pattern = self.pattern[:-1]
        
        # Handle anchored patterns
        self.is_anchored = self.pattern.startswith('/')
        if self.is_anchored:
            self.pattern = self.pattern[1:]
    
    def matches(self, path: str, is_dir: bool = False) -> bool:
        """
        Check if path matches this pattern.
        
        Args:
            path: Path to check (relative to repo root)
            is_dir: Whether path is a directory
        
        Returns:
            True if pattern matches
        """
        # Directory-only patterns only match directories
        if self.is_directory and not is_dir:
            return False
        
        # For anchored patterns, match only at root
        if self.is_anchored:
            # Anchored patterns must match at the start of path
            # /build matches build, build/, build/file but not src/build
            return path == self.pattern or \
                   path.startswith(self.pattern + '/') or \
                   (is_dir and path == self.pattern)
        
        # Unanchored patterns match at any level
        # Check full path
        if fnmatch.fnmatch(path, self.pattern):
            return True
        
        # Check each component
        parts = path.split('/')
        for part in parts:
            if fnmatch.fnmatch(part, self.pattern):
                return True
        
        # Check path with **/ prefix
        if fnmatch.fnmatch(path, f"**/{self.pattern}"):
            return True
        
        return False


class IgnoreManager:
    """Manages ignore patterns from multiple sources."""
    
    def __init__(self, repo_root: Path, verbose: bool = False):
        """
        Initialize ignore manager.
        
        Args:
            repo_root: Repository root directory
            verbose: Enable verbose logging
        """
        self.repo_root = Path(repo_root)
        self.verbose = verbose
        self.patterns: List[IgnorePattern] = []
        self.include_patterns: List[IgnorePattern] = []
        self.exclude_patterns: List[IgnorePattern] = []
        self._loaded = False
    
    def _log(self, message: str) -> None:
        """Log message if verbose mode enabled."""
        if self.verbose:
            print(f"[Ignore] {message}")
    
    def load(self, 
             default_ignore_path: Optional[Path] = None,
             gitignore_path: Optional[Path] = None) -> "IgnoreManager":
        """
        Load ignore patterns from sources.
        
        Args:
            default_ignore_path: Path to default ignore file
            gitignore_path: Path to .gitignore file
        
        Returns:
            Self for chaining
        """
        if self._loaded:
            return self
        
        # Load default patterns
        if default_ignore_path and default_ignore_path.exists():
            self._load_file(default_ignore_path, "default")
        
        # Load .gitignore
        gitignore = gitignore_path or (self.repo_root / ".gitignore")
        if gitignore.exists():
            self._load_file(gitignore, "gitignore")
        
        self._loaded = True
        return self
    
    def _load_file(self, path: Path, source: str) -> None:
        """Load patterns from a file."""
        self._log(f"Loading patterns from {path}")
        
        try:
            with open(path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    # Skip empty lines and comments
                    if not line or line.startswith('#'):
                        continue
                    self.patterns.append(IgnorePattern(line, source))
        except Exception as e:
            self._log(f"Error loading {path}: {e}")
    
    def add_include(self, pattern: str) -> None:
        """
        Add CLI include pattern (forces inclusion).
        
        Args:
            pattern: Glob pattern to include
        """
        self._log(f"Adding include pattern: {pattern}")
        self.include_patterns.append(IgnorePattern(pattern, "cli-include"))
    
    def add_exclude(self, pattern: str) -> None:
        """
        Add CLI exclude pattern (forces exclusion).
        
        Args:
            pattern: Glob pattern to exclude
        """
        self._log(f"Adding exclude pattern: {pattern}")
        self.exclude_patterns.append(IgnorePattern(pattern, "cli-exclude"))
    
    def should_ignore(self, path: str, is_dir: bool = False) -> bool:
        """
        Check if a path should be ignored.
        
        Processing order:
        1. Check CLI includes (override everything)
        2. Check CLI excludes
        3. Check default/gitignore patterns
        
        Args:
            path: Path to check (relative to repo root)
            is_dir: Whether path is a directory
        
        Returns:
            True if path should be ignored
        """
        # Normalize path
        path = str(path).replace('\\', '/')
        
        # 1. Check CLI includes first (highest priority)
        for pattern in self.include_patterns:
            if pattern.matches(path, is_dir):
                return False  # Force include
        
        # 2. Check CLI excludes
        for pattern in self.exclude_patterns:
            if pattern.matches(path, is_dir):
                return True  # Force exclude
        
        # 3. Ignore hidden directories and files by default (starting with .)
        basename = os.path.basename(path)
        if basename.startswith('.') and basename not in ('.', '..'):
            return True
        
        # 4. Check default/gitignore patterns
        # Process in order, respecting negations
        ignored = False
        for pattern in self.patterns:
            if pattern.matches(path, is_dir):
                ignored = not pattern.is_negation
        
        return ignored
    
    def get_candidate_files(self, 
                           extensions: Optional[Set[str]] = None,
                           max_size: Optional[int] = None) -> List[Path]:
        """
        Get all candidate files for indexing.
        
        Args:
            extensions: Set of file extensions to include (e.g., {'.py', '.js'})
            max_size: Maximum file size in bytes
        
        Returns:
            List of Path objects for candidate files
        """
        candidates = []
        
        for root, dirs, files in os.walk(self.repo_root):
            root_path = Path(root)
            rel_root = root_path.relative_to(self.repo_root)
            
            # Filter directories
            dirs[:] = [
                d for d in dirs 
                if not self.should_ignore(str(rel_root / d), is_dir=True)
            ]
            
            # Filter files
            for filename in files:
                rel_path = str(rel_root / filename)
                
                # Skip ignored files
                if self.should_ignore(rel_path, is_dir=False):
                    continue
                
                # Check extension
                if extensions:
                    ext = Path(filename).suffix.lower()
                    if ext not in extensions:
                        continue
                
                # Check size
                file_path = root_path / filename
                if max_size:
                    try:
                        if file_path.stat().st_size > max_size:
                            self._log(f"Skipping large file: {rel_path}")
                            continue
                    except OSError:
                        continue
                
                candidates.append(file_path)
        
        return candidates
    
    def get_stats(self) -> dict:
        """Get ignore manager statistics."""
        return {
            'total_patterns': len(self.patterns),
            'include_patterns': len(self.include_patterns),
            'exclude_patterns': len(self.exclude_patterns),
            'sources': list(set(p.source for p in self.patterns))
        }


def load_default_ignore(skill_root: Path) -> Path:
    """Get path to default ignore file."""
    return skill_root / "assets" / "default-ignore.txt"
