"""
Unit tests for the ignore module.

Tests cover:
- Pattern matching (glob patterns)
- Ignore manager loading from files
- Include/exclude CLI overrides
- File discovery
"""

import pytest
import tempfile
from pathlib import Path

from scripts.lib.ignore import IgnorePattern, IgnoreManager


class TestIgnorePattern:
    """Tests for IgnorePattern class."""
    
    def test_simple_pattern(self):
        """Simple pattern should match."""
        pattern = IgnorePattern("*.pyc")
        assert pattern.matches("test.pyc") is True
        assert pattern.matches("test.py") is False
    
    def test_directory_pattern(self):
        """Directory pattern should only match directories."""
        pattern = IgnorePattern("node_modules/")
        assert pattern.matches("node_modules", is_dir=True) is True
        assert pattern.matches("node_modules", is_dir=False) is False
    
    def test_anchored_pattern(self):
        """Anchored pattern should match from start."""
        pattern = IgnorePattern("/build")
        assert pattern.matches("build", is_dir=True) is True
        assert pattern.matches("src/build", is_dir=True) is False
    
    def test_negation_pattern(self):
        """Negation pattern should have is_negation flag."""
        pattern = IgnorePattern("!important.pyc")
        assert pattern.is_negation is True
        assert pattern.pattern == "important.pyc"
    
    def test_path_matching(self):
        """Pattern should match at any path level."""
        pattern = IgnorePattern("*.log")
        assert pattern.matches("debug.log") is True
        assert pattern.matches("logs/debug.log") is True
        assert pattern.matches("deep/logs/error.log") is True
    
    def test_exact_match(self):
        """Exact filename should match."""
        pattern = IgnorePattern(".git")
        assert pattern.matches(".git", is_dir=True) is True
        assert pattern.matches(".gitignore", is_dir=False) is False


class TestIgnoreManagerLoading:
    """Tests for IgnoreManager loading."""
    
    def test_load_default_patterns(self):
        """Loading default patterns should work."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create default ignore file
            default_ignore = Path(tmpdir) / "default-ignore.txt"
            default_ignore.write_text("*.pyc\n__pycache__/\n")
            
            manager = IgnoreManager(Path(tmpdir))
            manager.load(default_ignore_path=default_ignore)
            
            assert len(manager.patterns) == 2
    
    def test_load_gitignore(self):
        """Loading .gitignore should work."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create .gitignore
            gitignore = Path(tmpdir) / ".gitignore"
            gitignore.write_text("*.log\nnode_modules/\n")
            
            manager = IgnoreManager(Path(tmpdir))
            manager.load(gitignore_path=gitignore)
            
            assert len(manager.patterns) == 2
    
    def test_load_both_sources(self):
        """Loading both default and gitignore should merge."""
        with tempfile.TemporaryDirectory() as tmpdir:
            default_ignore = Path(tmpdir) / "default-ignore.txt"
            default_ignore.write_text("*.pyc\n")
            
            gitignore = Path(tmpdir) / ".gitignore"
            gitignore.write_text("*.log\n")
            
            manager = IgnoreManager(Path(tmpdir))
            manager.load(default_ignore_path=default_ignore, gitignore_path=gitignore)
            
            assert len(manager.patterns) == 2
    
    def test_skip_comments_and_empty(self):
        """Comments and empty lines should be skipped."""
        with tempfile.TemporaryDirectory() as tmpdir:
            default_ignore = Path(tmpdir) / "default-ignore.txt"
            default_ignore.write_text("\n# This is a comment\n*.pyc\n\n")
            
            manager = IgnoreManager(Path(tmpdir))
            manager.load(default_ignore_path=default_ignore)
            
            assert len(manager.patterns) == 1


class TestIgnoreManagerMatching:
    """Tests for IgnoreManager matching."""
    
    @pytest.fixture
    def manager(self):
        """Create a manager with test patterns."""
        with tempfile.TemporaryDirectory() as tmpdir:
            default_ignore = Path(tmpdir) / "default-ignore.txt"
            default_ignore.write_text("*.pyc\n__pycache__/\n*.log\n")
            
            manager = IgnoreManager(Path(tmpdir))
            manager.load(default_ignore_path=default_ignore)
            yield manager
    
    def test_should_ignore_pattern_match(self, manager):
        """Should ignore matching patterns."""
        assert manager.should_ignore("test.pyc") is True
        assert manager.should_ignore("__pycache__", is_dir=True) is True
    
    def test_should_not_ignore_non_match(self, manager):
        """Should not ignore non-matching files."""
        assert manager.should_ignore("test.py") is False
        assert manager.should_ignore("src/main.py") is False
    
    def test_cli_include_override(self, manager):
        """CLI include should override ignore."""
        manager.add_include("important.pyc")
        
        # Should NOT ignore this file even though *.pyc matches
        assert manager.should_ignore("important.pyc") is False
        assert manager.should_ignore("other.pyc") is True  # Still ignore others
    
    def test_cli_exclude_override(self, manager):
        """CLI exclude should force ignore."""
        manager.add_exclude("secret.py")
        
        # Should ignore this file even though it wouldn't normally be ignored
        assert manager.should_ignore("secret.py") is True
    
    def test_include_priority_over_exclude(self, manager):
        """Include should have priority over exclude."""
        manager.add_exclude("test.py")
        manager.add_include("test.py")
        
        # Include has higher priority
        assert manager.should_ignore("test.py") is False


class TestFileDiscovery:
    """Tests for file discovery."""
    
    @pytest.fixture
    def test_repo(self):
        """Create a test repository structure."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = Path(tmpdir)
            
            # Create some files
            (repo / "src").mkdir()
            (repo / "src" / "main.py").write_text("# main")
            (repo / "src" / "utils.py").write_text("# utils")
            (repo / "src" / "test.pyc").write_text("# compiled")
            
            (repo / "tests").mkdir()
            (repo / "tests" / "test_main.py").write_text("# tests")
            
            (repo / "node_modules").mkdir()
            (repo / "node_modules" / "package.json").write_text("{}")
            
            (repo / ".git").mkdir()
            (repo / ".git" / "config").write_text("[core]")
            
            yield repo
    
    def test_get_candidate_files_all(self, test_repo):
        """Should discover all non-ignored files."""
        default_ignore = test_repo.parent / "default-ignore.txt"
        default_ignore.write_text("*.pyc\nnode_modules/\n.git/\n")
        
        manager = IgnoreManager(test_repo)
        manager.load(default_ignore_path=default_ignore)
        
        candidates = manager.get_candidate_files()
        paths = {str(c.relative_to(test_repo)) for c in candidates}
        
        assert "src/main.py" in paths
        assert "src/utils.py" in paths
        assert "tests/test_main.py" in paths
        assert "src/test.pyc" not in paths
        assert "node_modules/package.json" not in paths
        assert ".git/config" not in paths
    
    def test_get_candidate_files_by_extension(self, test_repo):
        """Should filter by extension."""
        # Add a .js file
        (test_repo / "src" / "app.js").write_text("// app")
        
        manager = IgnoreManager(test_repo)
        manager.load()
        
        candidates = manager.get_candidate_files(extensions={".py"})
        paths = {str(c.relative_to(test_repo)) for c in candidates}
        
        assert "src/main.py" in paths
        assert "src/utils.py" in paths
        assert "src/app.js" not in paths
    
    def test_get_candidate_files_max_size(self, test_repo):
        """Should filter by max size."""
        # Create a large file
        (test_repo / "src" / "large.py").write_text("x" * 10000)
        
        manager = IgnoreManager(test_repo)
        manager.load()
        
        candidates = manager.get_candidate_files(max_size=5000)
        paths = {str(c.relative_to(test_repo)) for c in candidates}
        
        assert "src/main.py" in paths
        assert "src/large.py" not in paths
    
    def test_get_candidate_files_hidden_dirs(self, test_repo):
        """Should ignore hidden directories by default."""
        (test_repo / ".hidden").mkdir()
        (test_repo / ".hidden" / "file.py").write_text("# hidden")
        
        manager = IgnoreManager(test_repo)
        manager.load()
        
        candidates = manager.get_candidate_files()
        paths = {str(c.relative_to(test_repo)) for c in candidates}
        
        assert ".hidden/file.py" not in paths


class TestIgnoreManagerStats:
    """Tests for ignore manager statistics."""
    
    def test_get_stats(self):
        """Should return correct stats."""
        with tempfile.TemporaryDirectory() as tmpdir:
            default_ignore = Path(tmpdir) / "default-ignore.txt"
            default_ignore.write_text("*.pyc\n*.log\n")
            
            manager = IgnoreManager(Path(tmpdir))
            manager.load(default_ignore_path=default_ignore)
            manager.add_include("important.pyc")
            manager.add_exclude("secret.py")
            
            stats = manager.get_stats()
            
            assert stats['total_patterns'] == 2
            assert stats['include_patterns'] == 1
            assert stats['exclude_patterns'] == 1
            assert "default" in stats['sources']
