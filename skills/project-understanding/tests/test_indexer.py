"""
Unit tests for the indexer module.

Tests cover:
- Indexer initialization
- File scanning
- Hash computation
- Language detection
- Incremental updates
- Statistics tracking
"""

import pytest
import tempfile
from pathlib import Path

from scripts.lib.indexer import Indexer, IndexStats, FileInfo


class TestIndexStats:
    """Tests for IndexStats class."""
    
    def test_default_values(self):
        """Default values should be zero."""
        stats = IndexStats()
        
        assert stats.files_scanned == 0
        assert stats.files_new == 0
        assert stats.files_changed == 0
    
    def test_duration_calculation(self):
        """Duration should be calculated correctly."""
        import time
        
        stats = IndexStats()
        time.sleep(0.01)  # Small delay
        stats.end_time = time.time()
        
        assert stats.duration >= 0.01
    
    def test_to_dict(self):
        """Should convert to dictionary."""
        stats = IndexStats()
        stats.files_scanned = 10
        stats.symbols_added = 5
        
        data = stats.to_dict()
        
        assert data['files_scanned'] == 10
        assert data['symbols_added'] == 5
        assert 'duration_seconds' in data
    
    def test_str_format(self):
        """String representation should include stats."""
        stats = IndexStats()
        stats.files_scanned = 10
        
        output = str(stats)
        
        assert "Files scanned: 10" in output
        assert "Index Statistics:" in output


class TestIndexerInitialization:
    """Tests for indexer initialization."""
    
    def test_create_indexer(self):
        """Should create indexer with paths."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = Path(tmpdir) / "repo"
            skill = Path(tmpdir) / "skill"
            repo.mkdir()
            skill.mkdir()
            
            indexer = Indexer(repo, skill)
            
            assert indexer.repo_root == repo
            assert indexer.skill_root == skill
    
    def test_initialize_components(self):
        """Should initialize all components."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = Path(tmpdir) / "repo"
            skill = Path(tmpdir) / "skill"
            repo.mkdir()
            skill.mkdir()
            
            # Create default ignore file
            assets_dir = skill / "assets"
            assets_dir.mkdir()
            (assets_dir / "default-ignore.txt").write_text("*.pyc\n")
            
            indexer = Indexer(repo, skill)
            indexer.initialize()
            
            assert indexer.config is not None
            assert indexer.ignore_manager is not None
            assert indexer.db is not None
            
            indexer.close()


class TestFileScanning:
    """Tests for file scanning."""
    
    @pytest.fixture
    def setup_repo(self):
        """Create a test repository."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = Path(tmpdir) / "repo"
            skill = Path(tmpdir) / "skill"
            repo.mkdir()
            skill.mkdir()
            
            # Create files
            (repo / "src").mkdir()
            (repo / "src" / "main.py").write_text("# main")
            (repo / "src" / "utils.py").write_text("# utils")
            (repo / "src" / "test.pyc").write_text("# compiled")
            
            # Create ignore file
            assets_dir = skill / "assets"
            assets_dir.mkdir()
            (assets_dir / "default-ignore.txt").write_text("*.pyc\n")
            
            yield repo, skill
    
    def test_scan_files_finds_candidates(self, setup_repo):
        """Should find candidate files."""
        repo, skill = setup_repo
        
        indexer = Indexer(repo, skill)
        indexer.initialize()
        
        files = indexer.scan_files()
        paths = {f.relative_path for f in files}
        
        assert "src/main.py" in paths
        assert "src/utils.py" in paths
        assert "src/test.pyc" not in paths  # Ignored
        
        indexer.close()
    
    def test_scan_populates_stats(self, setup_repo):
        """Should populate files_scanned stat."""
        repo, skill = setup_repo
        
        indexer = Indexer(repo, skill)
        indexer.initialize()
        
        indexer.scan_files()
        
        assert indexer.stats.files_scanned == 2
        
        indexer.close()


class TestHashComputation:
    """Tests for file hash computation."""
    
    def test_compute_hash_consistent(self):
        """Same content should produce same hash."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = Path(tmpdir) / "repo"
            skill = Path(tmpdir) / "skill"
            repo.mkdir()
            skill.mkdir()
            
            test_file = repo / "test.txt"
            test_file.write_text("Hello, World!")
            
            indexer = Indexer(repo, skill)
            indexer.initialize()
            
            hash1 = indexer.compute_file_hash(test_file)
            hash2 = indexer.compute_file_hash(test_file)
            
            assert hash1 == hash2
            assert len(hash1) == 64  # SHA256 hex
            
            indexer.close()
    
    def test_compute_hash_different_content(self):
        """Different content should produce different hashes."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = Path(tmpdir) / "repo"
            skill = Path(tmpdir) / "skill"
            repo.mkdir()
            skill.mkdir()
            
            file1 = repo / "a.txt"
            file2 = repo / "b.txt"
            file1.write_text("Content A")
            file2.write_text("Content B")
            
            indexer = Indexer(repo, skill)
            indexer.initialize()
            
            hash1 = indexer.compute_file_hash(file1)
            hash2 = indexer.compute_file_hash(file2)
            
            assert hash1 != hash2
            
            indexer.close()


class TestLanguageDetection:
    """Tests for language detection."""
    
    @pytest.fixture
    def setup_indexer(self):
        """Create an initialized indexer."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = Path(tmpdir) / "repo"
            skill = Path(tmpdir) / "skill"
            repo.mkdir()
            skill.mkdir()
            
            assets_dir = skill / "assets"
            assets_dir.mkdir()
            (assets_dir / "default-ignore.txt").write_text("")
            
            indexer = Indexer(repo, skill)
            indexer.initialize()
            
            yield indexer
            
            indexer.close()
    
    def test_detect_python(self, setup_indexer):
        """Should detect Python files."""
        indexer = setup_indexer
        
        test_file = indexer.repo_root / "test.py"
        test_file.write_text("# test")
        
        lang = indexer.detect_language(test_file)
        
        assert lang == "python"
    
    def test_detect_javascript(self, setup_indexer):
        """Should detect JavaScript files."""
        indexer = setup_indexer
        
        test_file = indexer.repo_root / "test.js"
        test_file.write_text("// test")
        
        lang = indexer.detect_language(test_file)
        
        assert lang == "javascript"
    
    def test_detect_unknown(self, setup_indexer):
        """Should return None for unknown extensions."""
        indexer = setup_indexer
        
        test_file = indexer.repo_root / "test.unknown"
        test_file.write_text("test")
        
        lang = indexer.detect_language(test_file)
        
        assert lang is None


class TestIncrementalIndexing:
    """Tests for incremental indexing logic."""
    
    @pytest.fixture
    def setup_indexer(self):
        """Create an initialized indexer."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = Path(tmpdir) / "repo"
            skill = Path(tmpdir) / "skill"
            repo.mkdir()
            skill.mkdir()
            
            assets_dir = skill / "assets"
            assets_dir.mkdir()
            (assets_dir / "default-ignore.txt").write_text("")
            
            indexer = Indexer(repo, skill)
            indexer.initialize()
            
            yield indexer
            
            indexer.close()
    
    def test_should_reindex_new_file(self, setup_indexer):
        """New files should need reindexing."""
        indexer = setup_indexer
        
        file_info = FileInfo(
            path=indexer.repo_root / "test.py",
            relative_path="test.py",
            mtime=1234567890,
            size=100
        )
        
        assert indexer.should_reindex(file_info, None) is True
    
    def test_should_reindex_mtime_changed(self, setup_indexer):
        """Files with changed mtime should need reindexing."""
        indexer = setup_indexer
        
        file_info = FileInfo(
            path=indexer.repo_root / "test.py",
            relative_path="test.py",
            mtime=1234567891,
            size=100
        )
        
        db_file = {
            'mtime': 1234567890,
            'size': 100,
            'content_hash': 'abc123'
        }
        
        assert indexer.should_reindex(file_info, db_file) is True
    
    def test_should_not_reindex_unchanged(self, setup_indexer):
        """Unchanged files should not need reindexing."""
        indexer = setup_indexer
        
        # Create a file and compute its hash
        test_file = indexer.repo_root / "test.py"
        test_file.write_text("# test content")
        content_hash = indexer.compute_file_hash(test_file)
        
        file_info = FileInfo(
            path=test_file,
            relative_path="test.py",
            mtime=test_file.stat().st_mtime,
            size=test_file.stat().st_size,
            content_hash=content_hash
        )
        
        db_file = {
            'mtime': int(file_info.mtime),
            'size': file_info.size,
            'content_hash': content_hash
        }
        
        assert indexer.should_reindex(file_info, db_file) is False


class TestRemoveStaleFiles:
    """Tests for stale file removal."""
    
    def test_remove_deleted_files(self):
        """Should remove files no longer present."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = Path(tmpdir) / "repo"
            skill = Path(tmpdir) / "skill"
            repo.mkdir()
            skill.mkdir()
            
            assets_dir = skill / "assets"
            assets_dir.mkdir()
            (assets_dir / "default-ignore.txt").write_text("")
            
            indexer = Indexer(repo, skill)
            indexer.initialize()
            
            # Add a file to the database
            indexer.db.add_file("old_file.py", 1, 100, "hash1")
            indexer.db.commit()
            
            # Remove stale files (old_file.py no longer exists)
            count = indexer.remove_stale_files([])
            
            assert count == 1
            assert indexer.db.get_file("old_file.py") is None
            assert indexer.stats.files_deleted == 1
            
            indexer.close()


class TestRunIndexing:
    """Tests for the full indexing run."""
    
    def test_run_index_new_files(self):
        """Should index new files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = Path(tmpdir) / "repo"
            skill = Path(tmpdir) / "skill"
            repo.mkdir()
            skill.mkdir()
            
            # Create files
            (repo / "src").mkdir()
            (repo / "src" / "main.py").write_text("# main")
            
            assets_dir = skill / "assets"
            assets_dir.mkdir()
            (assets_dir / "default-ignore.txt").write_text("")
            
            indexer = Indexer(repo, skill, verbose=False)
            
            with indexer:
                stats = indexer.run()
            
            assert stats.files_new == 1
            assert stats.files_scanned == 1
    
    def test_run_detects_changed_files(self):
        """Should detect and reindex changed files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = Path(tmpdir) / "repo"
            skill = Path(tmpdir) / "skill"
            repo.mkdir()
            skill.mkdir()
            
            # Create file
            (repo / "src").mkdir()
            (repo / "src" / "main.py").write_text("# version 1")
            
            assets_dir = skill / "assets"
            assets_dir.mkdir()
            (assets_dir / "default-ignore.txt").write_text("")
            
            # First run
            indexer = Indexer(repo, skill, verbose=False)
            with indexer:
                stats1 = indexer.run()
            
            assert stats1.files_new == 1
            
            # Modify file
            (repo / "src" / "main.py").write_text("# version 2")
            
            # Second run
            indexer2 = Indexer(repo, skill, verbose=False)
            with indexer2:
                stats2 = indexer2.run()
            
            assert stats2.files_changed == 1
    
    def test_run_skips_unchanged_files(self):
        """Should skip unchanged files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = Path(tmpdir) / "repo"
            skill = Path(tmpdir) / "skill"
            repo.mkdir()
            skill.mkdir()
            
            # Create file
            (repo / "src").mkdir()
            (repo / "src" / "main.py").write_text("# content")
            
            assets_dir = skill / "assets"
            assets_dir.mkdir()
            (assets_dir / "default-ignore.txt").write_text("")
            
            # First run
            indexer = Indexer(repo, skill, verbose=False)
            with indexer:
                indexer.run()
            
            # Second run (no changes)
            indexer2 = Indexer(repo, skill, verbose=False)
            with indexer2:
                stats2 = indexer2.run()
            
            assert stats2.files_unchanged == 1


class TestTiming:
    """Tests for timing functionality."""
    
    def test_time_context_manager(self):
        """Timing context manager should record times."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = Path(tmpdir) / "repo"
            skill = Path(tmpdir) / "skill"
            repo.mkdir()
            skill.mkdir()
            
            indexer = Indexer(repo, skill, verbose=True)
            indexer.initialize()
            
            # Time an operation
            with indexer._time("test_operation"):
                import time
                time.sleep(0.01)
            
            assert "test_operation" in indexer.timings
            assert len(indexer.timings["test_operation"]) == 1
            assert indexer.timings["test_operation"][0] >= 0.01
            
            indexer.close()


class TestContextManager:
    """Tests for indexer context manager."""
    
    def test_context_manager_initializes_and_closes(self):
        """Context manager should handle lifecycle."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = Path(tmpdir) / "repo"
            skill = Path(tmpdir) / "skill"
            repo.mkdir()
            skill.mkdir()
            
            assets_dir = skill / "assets"
            assets_dir.mkdir()
            (assets_dir / "default-ignore.txt").write_text("")
            
            with Indexer(repo, skill) as indexer:
                assert indexer.db is not None
                assert indexer.config is not None
            
            # After exiting, db should be closed
            assert indexer.db is None
