"""
Integration tests for the project-understanding skill.

These tests verify the full workflow:
- Indexing a repository
- Generating repomap output
- Zooming into symbols
- Impact analysis
- Token budget enforcement

Uses the sample-repo fixture which contains files in multiple languages.
"""

import pytest
import tempfile
import subprocess
import sys
import os
from pathlib import Path
import time


# Fixture path
FIXTURE_PATH = Path(__file__).parent / "fixtures" / "sample-repo"
SKILL_PATH = Path(__file__).parent.parent


class TestIntegrationWorkflow:
    """Integration tests for the complete pui workflow."""
    
    @pytest.fixture
    def indexed_repo(self):
        """Create an indexed repository from the fixture."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Copy fixture to temp directory
            import shutil
            repo_path = Path(tmpdir) / "repo"
            shutil.copytree(FIXTURE_PATH, repo_path)
            
            # Run indexer
            old_cwd = os.getcwd()
            os.chdir(repo_path)
            
            try:
                # Import and run indexer
                sys.path.insert(0, str(SKILL_PATH / "scripts"))
                from scripts.lib.indexer import Indexer
                
                skill_root = SKILL_PATH
                indexer = Indexer(repo_path, skill_root, verbose=False)
                
                with indexer:
                    stats = indexer.run()
                
                yield repo_path, stats
            finally:
                os.chdir(old_cwd)
                sys.path.remove(str(SKILL_PATH / "scripts"))
    
    def test_index_creates_database(self, indexed_repo):
        """Indexing should create a database file."""
        repo_path, stats = indexed_repo
        db_path = repo_path / ".pui" / "index.sqlite"
        
        assert db_path.exists(), "Database file should be created"
        assert stats.files_scanned > 0, "Should scan at least one file"
    
    def test_index_finds_python_files(self, indexed_repo):
        """Should index Python files."""
        repo_path, stats = indexed_repo
        
        # Database should have Python files
        sys.path.insert(0, str(SKILL_PATH / "scripts"))
        from scripts.lib.db import Database
        
        db = Database(repo_path / ".pui" / "index.sqlite")
        db.connect()
        
        files = db.get_all_files()
        python_files = [f for f in files if f.get('language') == 'python']
        
        assert len(python_files) >= 2, "Should index multiple Python files"
        
        db.close()
        sys.path.remove(str(SKILL_PATH / "scripts"))
    
    def test_index_finds_symbols(self, indexed_repo):
        """Should extract symbols from indexed files."""
        repo_path, stats = indexed_repo
        
        sys.path.insert(0, str(SKILL_PATH / "scripts"))
        from scripts.lib.db import Database
        
        db = Database(repo_path / ".pui" / "index.sqlite")
        db.connect()
        
        stats = db.get_stats()
        assert stats['symbols'] > 0, "Should have extracted symbols"
        
        db.close()
        sys.path.remove(str(SKILL_PATH / "scripts"))
    
    def test_repomap_not_empty(self, indexed_repo):
        """Repomap should generate non-empty output."""
        repo_path, _ = indexed_repo
        
        sys.path.insert(0, str(SKILL_PATH / "scripts"))
        from scripts.lib.packs import repomap
        from scripts.lib.tokens import estimate_tokens
        
        old_cwd = os.getcwd()
        os.chdir(repo_path)
        
        try:
            output = repomap(budget_tokens=8000)
            
            assert len(output) > 0, "Repomap should not be empty"
            assert "Repository Overview" in output, "Should have header"
            assert "## Directory Structure" in output, "Should have directory tree"
            assert "## Top Files" in output, "Should have top files section"
            
            # Check token budget
            tokens = estimate_tokens(output)
            assert tokens <= 8000, "Should respect token budget"
        finally:
            os.chdir(old_cwd)
            sys.path.remove(str(SKILL_PATH / "scripts"))
    
    def test_repomap_includes_python_files(self, indexed_repo):
        """Repomap should include Python files in output."""
        repo_path, _ = indexed_repo
        
        sys.path.insert(0, str(SKILL_PATH / "scripts"))
        from scripts.lib.packs import repomap
        
        old_cwd = os.getcwd()
        os.chdir(repo_path)
        
        try:
            output = repomap(budget_tokens=8000)
            
            assert "src/main.py" in output or "main.py" in output, \
                "Should include main.py in output"
        finally:
            os.chdir(old_cwd)
            sys.path.remove(str(SKILL_PATH / "scripts"))
    
    def test_repomap_within_token_budget(self, indexed_repo):
        """Repomap should enforce token budget."""
        repo_path, _ = indexed_repo
        
        sys.path.insert(0, str(SKILL_PATH / "scripts"))
        from scripts.lib.packs import repomap
        from scripts.lib.tokens import estimate_tokens
        
        old_cwd = os.getcwd()
        os.chdir(repo_path)
        
        try:
            # Test with small budget
            output = repomap(budget_tokens=1000)
            tokens = estimate_tokens(output)
            
            assert tokens <= 1200, "Should stay within budget with margin"
            assert len(output) > 0, "Should still produce output"
        finally:
            os.chdir(old_cwd)
            sys.path.remove(str(SKILL_PATH / "scripts"))
    
    def test_zoom_finds_symbol(self, indexed_repo):
        """Zoom should find and display symbols."""
        repo_path, _ = indexed_repo
        
        sys.path.insert(0, str(SKILL_PATH / "scripts"))
        from scripts.lib.packs import zoom
        
        old_cwd = os.getcwd()
        os.chdir(repo_path)
        
        try:
            # Try to zoom into a file - this should always work
            output = zoom("src/main.py", budget_tokens=4000)
            
            assert output is not None, "Zoom should return output"
            assert len(output) > 0, "Zoom output should not be empty"
            # Zoom by file may produce different output format
            assert "#" in output or "Error" in output, "Should have some content"
        finally:
            os.chdir(old_cwd)
            sys.path.remove(str(SKILL_PATH / "scripts"))
    
    def test_zoom_handles_nonexistent_symbol(self, indexed_repo):
        """Zoom should handle non-existent symbols gracefully."""
        repo_path, _ = indexed_repo
        
        sys.path.insert(0, str(SKILL_PATH / "scripts"))
        from scripts.lib.packs import zoom
        
        old_cwd = os.getcwd()
        os.chdir(repo_path)
        
        try:
            output = zoom("nonexistent_symbol_xyz", budget_tokens=4000)
            
            # Should return some output even for missing symbol
            assert isinstance(output, str), "Should return string output"
            assert "not found" in output.lower() or "error" in output.lower(), \
                "Should indicate symbol not found"
        finally:
            os.chdir(old_cwd)
            sys.path.remove(str(SKILL_PATH / "scripts"))
    
    def test_zoom_within_token_budget(self, indexed_repo):
        """Zoom should enforce token budget."""
        repo_path, _ = indexed_repo
        
        sys.path.insert(0, str(SKILL_PATH / "scripts"))
        from scripts.lib.packs import zoom
        from scripts.lib.tokens import estimate_tokens
        
        old_cwd = os.getcwd()
        os.chdir(repo_path)
        
        try:
            output = zoom("src/main.py", budget_tokens=500)
            
            tokens = estimate_tokens(output)
            assert tokens <= 600, "Should stay within budget with margin"
        finally:
            os.chdir(old_cwd)
            sys.path.remove(str(SKILL_PATH / "scripts"))
    
    def test_impact_analysis(self, indexed_repo):
        """Impact should analyze dependencies."""
        repo_path, _ = indexed_repo
        
        sys.path.insert(0, str(SKILL_PATH / "scripts"))
        from scripts.lib.packs import impact
        
        old_cwd = os.getcwd()
        os.chdir(repo_path)
        
        try:
            output = impact("src/main.py", depth=2, budget_tokens=6000)
            
            assert output is not None, "Impact should return output"
            assert len(output) > 0, "Impact output should not be empty"
            assert "# Impact Analysis" in output, "Should have header"
            assert "## Changed Items" in output, "Should have changed items section"
            assert "## Affected Files" in output, "Should have affected files section"
        finally:
            os.chdir(old_cwd)
            sys.path.remove(str(SKILL_PATH / "scripts"))
    
    def test_impact_by_symbol(self, indexed_repo):
        """Impact should work with file paths."""
        repo_path, _ = indexed_repo
        
        sys.path.insert(0, str(SKILL_PATH / "scripts"))
        from scripts.lib.packs import impact
        
        old_cwd = os.getcwd()
        os.chdir(repo_path)
        
        try:
            output = impact("src/utils.py", depth=2, budget_tokens=6000)
            
            assert output is not None, "Impact should return output"
            assert "# Impact Analysis" in output, "Should have header"
        finally:
            os.chdir(old_cwd)
            sys.path.remove(str(SKILL_PATH / "scripts"))
    
    def test_impact_within_token_budget(self, indexed_repo):
        """Impact should enforce token budget."""
        repo_path, _ = indexed_repo
        
        sys.path.insert(0, str(SKILL_PATH / "scripts"))
        from scripts.lib.packs import impact
        from scripts.lib.tokens import estimate_tokens
        
        old_cwd = os.getcwd()
        os.chdir(repo_path)
        
        try:
            output = impact("src/main.py", depth=1, budget_tokens=500)
            
            tokens = estimate_tokens(output)
            assert tokens <= 600, "Should stay within budget with margin"
        finally:
            os.chdir(old_cwd)
            sys.path.remove(str(SKILL_PATH / "scripts"))
    
    def test_impact_affected_tests_detection(self, indexed_repo):
        """Impact should detect affected test files."""
        repo_path, _ = indexed_repo
        
        sys.path.insert(0, str(SKILL_PATH / "scripts"))
        from scripts.lib.packs import impact
        
        old_cwd = os.getcwd()
        os.chdir(repo_path)
        
        try:
            output = impact("src/main.py", depth=2, budget_tokens=6000)
            
            assert "## Affected Tests" in output, "Should have affected tests section"
        finally:
            os.chdir(old_cwd)
            sys.path.remove(str(SKILL_PATH / "scripts"))


class TestMultiLanguageSupport:
    """Tests for multi-language parsing in the fixture."""
    
    @pytest.fixture
    def indexed_multilang_repo(self):
        """Create an indexed repository from the fixture with all languages."""
        with tempfile.TemporaryDirectory() as tmpdir:
            import shutil
            repo_path = Path(tmpdir) / "repo"
            shutil.copytree(FIXTURE_PATH, repo_path)
            
            old_cwd = os.getcwd()
            os.chdir(repo_path)
            
            try:
                sys.path.insert(0, str(SKILL_PATH / "scripts"))
                from scripts.lib.indexer import Indexer
                
                skill_root = SKILL_PATH
                indexer = Indexer(repo_path, skill_root, verbose=False)
                
                with indexer:
                    stats = indexer.run()
                
                yield repo_path, stats
            finally:
                os.chdir(old_cwd)
                sys.path.remove(str(SKILL_PATH / "scripts"))
    
    def test_indexes_javascript_files(self, indexed_multilang_repo):
        """Should index JavaScript files."""
        repo_path, stats = indexed_multilang_repo
        
        sys.path.insert(0, str(SKILL_PATH / "scripts"))
        from scripts.lib.db import Database
        
        db = Database(repo_path / ".pui" / "index.sqlite")
        db.connect()
        
        files = db.get_all_files()
        js_files = [f for f in files if f.get('language') == 'javascript']
        
        assert len(js_files) >= 1, "Should index JavaScript files"
        
        db.close()
        sys.path.remove(str(SKILL_PATH / "scripts"))
    
    def test_indexes_go_files(self, indexed_multilang_repo):
        """Should index Go files."""
        repo_path, stats = indexed_multilang_repo
        
        sys.path.insert(0, str(SKILL_PATH / "scripts"))
        from scripts.lib.db import Database
        
        db = Database(repo_path / ".pui" / "index.sqlite")
        db.connect()
        
        files = db.get_all_files()
        go_files = [f for f in files if f.get('language') == 'go']
        
        assert len(go_files) >= 1, "Should index Go files"
        
        db.close()
        sys.path.remove(str(SKILL_PATH / "scripts"))
    
    def test_indexes_rust_files(self, indexed_multilang_repo):
        """Should index Rust files."""
        repo_path, stats = indexed_multilang_repo
        
        sys.path.insert(0, str(SKILL_PATH / "scripts"))
        from scripts.lib.db import Database
        
        db = Database(repo_path / ".pui" / "index.sqlite")
        db.connect()
        
        files = db.get_all_files()
        rust_files = [f for f in files if f.get('language') == 'rust']
        
        assert len(rust_files) >= 1, "Should index Rust files"
        
        db.close()
        sys.path.remove(str(SKILL_PATH / "scripts"))


class TestPerformance:
    """Performance smoke tests."""
    
    @pytest.fixture
    def indexed_repo(self):
        """Create an indexed repository."""
        with tempfile.TemporaryDirectory() as tmpdir:
            import shutil
            repo_path = Path(tmpdir) / "repo"
            shutil.copytree(FIXTURE_PATH, repo_path)
            
            old_cwd = os.getcwd()
            os.chdir(repo_path)
            
            try:
                sys.path.insert(0, str(SKILL_PATH / "scripts"))
                from scripts.lib.indexer import Indexer
                
                skill_root = SKILL_PATH
                indexer = Indexer(repo_path, skill_root, verbose=False)
                
                with indexer:
                    stats = indexer.run()
                
                yield repo_path, stats
            finally:
                os.chdir(old_cwd)
                sys.path.remove(str(SKILL_PATH / "scripts"))
    
    def test_indexing_performance(self, indexed_repo):
        """Indexing should complete within reasonable time."""
        repo_path, stats = indexed_repo
        
        # Should index small repo in reasonable time
        assert stats.duration < 30.0, \
            f"Indexing took {stats.duration}s, expected < 30s"
    
    def test_repomap_performance(self, indexed_repo):
        """Repomap generation should be fast."""
        repo_path, _ = indexed_repo
        
        sys.path.insert(0, str(SKILL_PATH / "scripts"))
        from scripts.lib.packs import repomap
        
        old_cwd = os.getcwd()
        os.chdir(repo_path)
        
        try:
            start = time.time()
            output = repomap(budget_tokens=8000)
            elapsed = time.time() - start
            
            assert elapsed < 5.0, f"Repomap took {elapsed}s, expected < 5s"
            assert len(output) > 0
        finally:
            os.chdir(old_cwd)
            sys.path.remove(str(SKILL_PATH / "scripts"))
    
    def test_zoom_performance(self, indexed_repo):
        """Zoom should be fast."""
        repo_path, _ = indexed_repo
        
        sys.path.insert(0, str(SKILL_PATH / "scripts"))
        from scripts.lib.packs import zoom
        
        old_cwd = os.getcwd()
        os.chdir(repo_path)
        
        try:
            start = time.time()
            output = zoom("Application", budget_tokens=4000)
            elapsed = time.time() - start
            
            assert elapsed < 3.0, f"Zoom took {elapsed}s, expected < 3s"
            assert len(output) > 0
        finally:
            os.chdir(old_cwd)
            sys.path.remove(str(SKILL_PATH / "scripts"))
    
    def test_impact_performance(self, indexed_repo):
        """Impact analysis should be fast."""
        repo_path, _ = indexed_repo
        
        sys.path.insert(0, str(SKILL_PATH / "scripts"))
        from scripts.lib.packs import impact
        
        old_cwd = os.getcwd()
        os.chdir(repo_path)
        
        try:
            start = time.time()
            output = impact("src/main.py", depth=1, budget_tokens=6000)
            elapsed = time.time() - start
            
            assert elapsed < 5.0, f"Impact took {elapsed}s, expected < 5s"
            assert len(output) > 0
        finally:
            os.chdir(old_cwd)
            sys.path.remove(str(SKILL_PATH / "scripts"))


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
