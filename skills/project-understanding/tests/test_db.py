"""
Unit tests for the database module.

Tests cover:
- Database initialization and schema creation
- File operations (add, get, delete)
- Symbol operations (add, get, search)
- Edge operations (add, get)
- Transaction batching
- Metadata operations
"""

import pytest
import tempfile
import sqlite3
from pathlib import Path

from scripts.lib.db import Database, get_db_path, DatabaseError


class TestDatabaseInitialization:
    """Tests for database initialization."""
    
    def test_create_new_database(self):
        """Creating a new database should initialize schema."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            db = Database(db_path)
            db.connect()
            
            # Check that tables exist
            cursor = db._conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
            tables = {row[0] for row in cursor.fetchall()}
            
            assert 'files' in tables
            assert 'symbols' in tables
            assert 'edges' in tables
            assert 'callsites' in tables
            assert 'meta' in tables
            assert 'symbols_fts' in tables
            
            db.close()
    
    def test_schema_version_stored(self):
        """Schema version should be stored in meta table."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            db = Database(db_path)
            db.connect()
            
            version = db._get_schema_version()
            assert version > 0
            
            db.close()
    
    def test_wal_mode_enabled(self):
        """WAL mode should be enabled for better concurrency."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            db = Database(db_path)
            db.connect()
            
            cursor = db._conn.execute("PRAGMA journal_mode")
            mode = cursor.fetchone()[0]
            assert mode.lower() == 'wal'
            
            db.close()
    
    def test_foreign_keys_enabled(self):
        """Foreign keys should be enabled."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            db = Database(db_path)
            db.connect()
            
            cursor = db._conn.execute("PRAGMA foreign_keys")
            enabled = cursor.fetchone()[0]
            assert enabled == 1
            
            db.close()


class TestFileOperations:
    """Tests for file operations."""
    
    @pytest.fixture
    def db(self):
        """Create a temporary database."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            db = Database(db_path)
            db.connect()
            yield db
            db.close()
    
    def test_add_file(self, db):
        """Adding a file should return ID."""
        file_id = db.add_file(
            path="src/main.py",
            mtime=1234567890,
            size=1024,
            content_hash="abc123",
            language="python"
        )
        
        assert isinstance(file_id, int)
        assert file_id > 0
    
    def test_add_file_duplicate_updates(self, db):
        """Adding duplicate file should update existing."""
        file_id1 = db.add_file(
            path="src/main.py",
            mtime=1234567890,
            size=1024,
            content_hash="abc123",
            language="python"
        )
        
        file_id2 = db.add_file(
            path="src/main.py",
            mtime=1234567891,
            size=2048,
            content_hash="def456",
            language="python"
        )
        
        assert file_id1 == file_id2  # Same ID returned
        
        # Verify update
        file = db.get_file("src/main.py")
        assert file['size'] == 2048
        assert file['content_hash'] == "def456"
    
    def test_get_file(self, db):
        """Getting a file should return file data."""
        db.add_file(
            path="src/main.py",
            mtime=1234567890,
            size=1024,
            content_hash="abc123",
            language="python"
        )
        
        file = db.get_file("src/main.py")
        
        assert file is not None
        assert file['path'] == "src/main.py"
        assert file['size'] == 1024
        assert file['language'] == "python"
    
    def test_get_file_not_found(self, db):
        """Getting non-existent file should return None."""
        file = db.get_file("nonexistent.py")
        assert file is None
    
    def test_get_file_by_id(self, db):
        """Getting file by ID should work."""
        file_id = db.add_file(
            path="src/main.py",
            mtime=1234567890,
            size=1024,
            content_hash="abc123",
            language="python"
        )
        
        file = db.get_file_by_id(file_id)
        
        assert file is not None
        assert file['path'] == "src/main.py"
    
    def test_delete_file(self, db):
        """Deleting a file should remove it."""
        db.add_file(
            path="src/main.py",
            mtime=1234567890,
            size=1024,
            content_hash="abc123"
        )
        
        result = db.delete_file("src/main.py")
        assert result is True
        
        file = db.get_file("src/main.py")
        assert file is None
    
    def test_delete_file_not_found(self, db):
        """Deleting non-existent file should return False."""
        result = db.delete_file("nonexistent.py")
        assert result is False
    
    def test_get_all_files(self, db):
        """Getting all files should return list."""
        db.add_file("src/a.py", 1, 100, "hash1")
        db.add_file("src/b.py", 2, 200, "hash2")
        db.add_file("src/c.py", 3, 300, "hash3")
        
        files = db.get_all_files()
        
        assert len(files) == 3
        paths = {f['path'] for f in files}
        assert paths == {"src/a.py", "src/b.py", "src/c.py"}


class TestSymbolOperations:
    """Tests for symbol operations."""
    
    @pytest.fixture
    def db_with_file(self):
        """Create a database with a file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            db = Database(db_path)
            db.connect()
            
            file_id = db.add_file("src/main.py", 1, 100, "hash1")
            yield db, file_id
            
            db.close()
    
    def test_add_symbol(self, db_with_file):
        """Adding a symbol should return ID."""
        db, file_id = db_with_file
        
        symbol_id = db.add_symbol(
            file_id=file_id,
            name="my_function",
            kind="function",
            line_start=10,
            line_end=20,
            signature="def my_function()"
        )
        
        assert isinstance(symbol_id, int)
        assert symbol_id > 0
    
    def test_get_symbols_in_file(self, db_with_file):
        """Getting symbols in file should return list."""
        db, file_id = db_with_file
        
        db.add_symbol(file_id, "func1", "function", 1)
        db.add_symbol(file_id, "func2", "function", 10)
        db.add_symbol(file_id, "MyClass", "class", 20)
        
        symbols = db.get_symbols_in_file(file_id)
        
        assert len(symbols) == 3
        names = {s['name'] for s in symbols}
        assert names == {"func1", "func2", "MyClass"}
    
    def test_delete_symbols_in_file(self, db_with_file):
        """Deleting symbols in file should remove them."""
        db, file_id = db_with_file
        
        db.add_symbol(file_id, "func1", "function", 1)
        db.add_symbol(file_id, "func2", "function", 10)
        
        count = db.delete_symbols_in_file(file_id)
        
        assert count == 2
        
        symbols = db.get_symbols_in_file(file_id)
        assert len(symbols) == 0
    
    def test_search_symbols(self, db_with_file):
        """Searching symbols should use FTS."""
        db, file_id = db_with_file
        
        db.add_symbol(file_id, "authenticate", "function", 1)
        db.add_symbol(file_id, "authorization", "function", 10)
        db.add_symbol(file_id, "login", "function", 20)
        
        # Commit to ensure FTS is updated
        db.commit()
        
        results = db.search_symbols("auth*", limit=10)
        
        assert len(results) == 2
        names = {r['name'] for r in results}
        assert "authenticate" in names
        assert "authorization" in names


class TestEdgeOperations:
    """Tests for edge operations."""
    
    @pytest.fixture
    def db_with_symbols(self):
        """Create a database with symbols."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            db = Database(db_path)
            db.connect()
            
            file_id = db.add_file("src/main.py", 1, 100, "hash1")
            source_id = db.add_symbol(file_id, "caller", "function", 1)
            target_id = db.add_symbol(file_id, "callee", "function", 10)
            
            yield db, file_id, source_id, target_id
            
            db.close()
    
    def test_add_edge(self, db_with_symbols):
        """Adding an edge should return ID."""
        db, file_id, source_id, target_id = db_with_symbols
        
        edge_id = db.add_edge(source_id, target_id, "call", file_id)
        
        assert isinstance(edge_id, int)
        assert edge_id > 0
    
    def test_add_callsite(self, db_with_symbols):
        """Adding a callsite should return ID."""
        db, file_id, source_id, target_id = db_with_symbols
        
        edge_id = db.add_edge(source_id, target_id, "call", file_id)
        callsite_id = db.add_callsite(edge_id, 5, 10, "context here")
        
        assert isinstance(callsite_id, int)
        assert callsite_id > 0
    
    def test_get_outgoing_edges(self, db_with_symbols):
        """Getting outgoing edges should work."""
        db, file_id, source_id, target_id = db_with_symbols
        
        db.add_edge(source_id, target_id, "call", file_id)
        
        edges = db.get_outgoing_edges(source_id)
        
        assert len(edges) == 1
        assert edges[0]['target_id'] == target_id
    
    def test_get_incoming_edges(self, db_with_symbols):
        """Getting incoming edges should work."""
        db, file_id, source_id, target_id = db_with_symbols
        
        db.add_edge(source_id, target_id, "call", file_id)
        
        edges = db.get_incoming_edges(target_id)
        
        assert len(edges) == 1
        assert edges[0]['source_id'] == source_id


class TestTransactionBatching:
    """Tests for transaction batching."""
    
    def test_batch_commit(self):
        """Batch should commit when size reached."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            db = Database(db_path)
            db.connect()
            db.begin_batch(size=2)
            
            # Add 2 files (should trigger commit)
            db.add_file("a.py", 1, 100, "hash1")
            db.add_file("b.py", 2, 100, "hash2")
            
            # Both should be visible
            files = db.get_all_files()
            assert len(files) == 2
            
            db.close()
    
    def test_explicit_commit(self):
        """Explicit commit should flush all operations."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            db = Database(db_path)
            db.connect()
            db.begin_batch(size=100)
            
            db.add_file("a.py", 1, 100, "hash1")
            db.commit()
            
            files = db.get_all_files()
            assert len(files) == 1
            
            db.close()
    
    def test_rollback(self):
        """Rollback should undo uncommitted operations."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            db = Database(db_path)
            db.connect()
            db.begin_batch(size=100)
            
            db.add_file("a.py", 1, 100, "hash1")
            db.rollback()
            
            files = db.get_all_files()
            assert len(files) == 0
            
            db.close()


class TestMetadata:
    """Tests for metadata operations."""
    
    @pytest.fixture
    def db(self):
        """Create a temporary database."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            db = Database(db_path)
            db.connect()
            yield db
            db.close()
    
    def test_get_meta(self, db):
        """Getting metadata should return value."""
        value = db.get_meta("schema_version")
        assert value is not None
        assert int(value) > 0
    
    def test_get_meta_not_found(self, db):
        """Getting non-existent metadata should return None."""
        value = db.get_meta("nonexistent")
        assert value is None
    
    def test_update_index_stats(self, db):
        """Updating index stats should work."""
        db.update_index_stats(10, 100)
        db.commit()
        
        files = db.get_meta("indexed_files")
        symbols = db.get_meta("indexed_symbols")
        
        assert files == "10"
        assert symbols == "100"
    
    def test_get_stats(self, db):
        """Getting stats should return counts."""
        # Add some data
        db.add_file("a.py", 1, 100, "hash1")
        file_id = db.add_file("b.py", 2, 100, "hash2")
        db.add_symbol(file_id, "func", "function", 1)
        db.commit()
        
        stats = db.get_stats()
        
        assert stats['files'] == 2
        assert stats['symbols'] == 1
        assert stats['schema_version'] > 0


class TestUtilityFunctions:
    """Tests for utility functions."""
    
    def test_compute_hash(self):
        """Computing hash should return consistent value."""
        content = "Hello, World!"
        hash1 = Database.compute_hash(content)
        hash2 = Database.compute_hash(content)
        
        assert hash1 == hash2
        assert len(hash1) == 64  # SHA256 hex
    
    def test_compute_hash_different(self):
        """Different content should produce different hashes."""
        hash1 = Database.compute_hash("content1")
        hash2 = Database.compute_hash("content2")
        
        assert hash1 != hash2
    
    def test_get_db_path(self):
        """Getting DB path should return correct location."""
        repo = Path("/my/repo")
        db_path = get_db_path(repo)
        
        assert db_path == Path("/my/repo/.pui/index.sqlite")


class TestContextManager:
    """Tests for context manager usage."""
    
    def test_context_manager(self):
        """Context manager should auto-close."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            
            with Database(db_path) as db:
                db.add_file("test.py", 1, 100, "hash")
                assert db._conn is not None
            
            assert db._conn is None
    
    def test_context_manager_exception(self):
        """Context manager should rollback on exception."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            
            try:
                with Database(db_path) as db:
                    db.add_file("test.py", 1, 100, "hash")
                    raise ValueError("Test error")
            except ValueError:
                pass
            
            # Reconnect and verify file was not saved
            with Database(db_path) as db:
                files = db.get_all_files()
                assert len(files) == 0
