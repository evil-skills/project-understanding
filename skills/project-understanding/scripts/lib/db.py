"""
Database management module for Project Understanding Index.

Provides SQLite database management with:
- Schema creation and versioning
- FTS5 full-text search for symbols
- Transaction batching for performance
- Migration support
"""

import sqlite3
import hashlib
import json
from pathlib import Path
from typing import Optional, List, Dict, Any
from datetime import datetime


SCHEMA_VERSION = 1

# Schema definition
CREATE_TABLES_SQL = """
-- Files table: stores metadata about indexed source files
CREATE TABLE IF NOT EXISTS files (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    path TEXT UNIQUE NOT NULL,
    mtime INTEGER NOT NULL,
    size INTEGER NOT NULL,
    content_hash TEXT NOT NULL,
    indexed_at INTEGER NOT NULL,
    language TEXT
);

-- Symbols table: stores symbol definitions
CREATE TABLE IF NOT EXISTS symbols (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    file_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    kind TEXT NOT NULL,
    line_start INTEGER NOT NULL,
    line_end INTEGER,
    column_start INTEGER,
    column_end INTEGER,
    signature TEXT,
    docstring TEXT,
    parent_id INTEGER,
    FOREIGN KEY (file_id) REFERENCES files(id) ON DELETE CASCADE,
    FOREIGN KEY (parent_id) REFERENCES symbols(id) ON DELETE CASCADE
);

-- Edges table: stores relationships between symbols
CREATE TABLE IF NOT EXISTS edges (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id INTEGER NOT NULL,
    target_id INTEGER NOT NULL,
    kind TEXT NOT NULL,
    file_id INTEGER NOT NULL,
    metadata TEXT,  -- JSON-encoded metadata for import/call info
    FOREIGN KEY (source_id) REFERENCES symbols(id) ON DELETE CASCADE,
    FOREIGN KEY (target_id) REFERENCES symbols(id) ON DELETE CASCADE,
    FOREIGN KEY (file_id) REFERENCES files(id) ON DELETE CASCADE
);

-- Callsites table: stores specific call site information
CREATE TABLE IF NOT EXISTS callsites (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    edge_id INTEGER NOT NULL,
    line INTEGER NOT NULL,
    column INTEGER,
    context TEXT,
    FOREIGN KEY (edge_id) REFERENCES edges(id) ON DELETE CASCADE
);

-- Meta table: stores index metadata
CREATE TABLE IF NOT EXISTS meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

-- Indices for performance
CREATE INDEX IF NOT EXISTS idx_files_path ON files(path);
CREATE INDEX IF NOT EXISTS idx_files_language ON files(language);
CREATE INDEX IF NOT EXISTS idx_symbols_file ON symbols(file_id);
CREATE INDEX IF NOT EXISTS idx_symbols_name ON symbols(name);
CREATE INDEX IF NOT EXISTS idx_symbols_kind ON symbols(kind);
CREATE INDEX IF NOT EXISTS idx_symbols_parent ON symbols(parent_id);
CREATE INDEX IF NOT EXISTS idx_edges_source ON edges(source_id);
CREATE INDEX IF NOT EXISTS idx_edges_target ON edges(target_id);
CREATE INDEX IF NOT EXISTS idx_edges_kind ON edges(kind);
CREATE INDEX IF NOT EXISTS idx_edges_file ON edges(file_id);
CREATE INDEX IF NOT EXISTS idx_callsites_edge ON callsites(edge_id);
CREATE INDEX IF NOT EXISTS idx_callsites_line ON callsites(line);
"""

CREATE_FTS_SQL = """
-- FTS5 virtual table for symbol search
CREATE VIRTUAL TABLE IF NOT EXISTS symbols_fts USING fts5(
    name,
    content='symbols',
    content_rowid='id',
    tokenize='porter'
);

-- Triggers to keep FTS index in sync
CREATE TRIGGER IF NOT EXISTS symbols_ai AFTER INSERT ON symbols BEGIN
    INSERT INTO symbols_fts(rowid, name) VALUES (new.id, new.name);
END;

CREATE TRIGGER IF NOT EXISTS symbols_ad AFTER DELETE ON symbols BEGIN
    INSERT INTO symbols_fts(symbols_fts, rowid, name) VALUES ('delete', old.id, old.name);
END;

CREATE TRIGGER IF NOT EXISTS symbols_au AFTER UPDATE ON symbols BEGIN
    INSERT INTO symbols_fts(symbols_fts, rowid, name) VALUES ('delete', old.id, old.name);
    INSERT INTO symbols_fts(rowid, name) VALUES (new.id, new.name);
END;
"""


class DatabaseError(Exception):
    """Database operation error."""
    pass


class SchemaVersionError(Exception):
    """Schema version mismatch error."""
    pass


class Database:
    """Manages the SQLite database for project indexing."""
    
    def __init__(self, db_path: Path, verbose: bool = False):
        """
        Initialize database connection.
        
        Args:
            db_path: Path to SQLite database file
            verbose: Enable verbose logging
        """
        self.db_path = Path(db_path)
        self.verbose = verbose
        self._conn: Optional[sqlite3.Connection] = None
        self._transaction_count = 0
        self._batch_size = 100
        
    def _log(self, message: str) -> None:
        """Log message if verbose mode enabled."""
        if self.verbose:
            print(f"[DB] {message}")
    
    def connect(self) -> "Database":
        """Connect to database and initialize schema if needed."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        self._conn = sqlite3.connect(str(self.db_path))
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA foreign_keys = ON")
        self._conn.execute("PRAGMA journal_mode = WAL")
        self._conn.execute("PRAGMA synchronous = NORMAL")
        
        self._init_schema()
        return self
    
    def close(self) -> None:
        """Close database connection."""
        if self._conn:
            self._commit_if_needed(force=True)
            self._conn.close()
            self._conn = None
    
    def __enter__(self) -> "Database":
        """Context manager entry."""
        return self.connect()
    
    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Context manager exit."""
        if exc_type is not None:
            self.rollback()
        self.close()
    
    @property
    def conn(self) -> sqlite3.Connection:
        """Get database connection, raising error if not connected."""
        if self._conn is None:
            raise DatabaseError("Database not connected")
        return self._conn

    def _init_schema(self) -> None:
        """Initialize database schema."""
        self._log("Initializing schema...")
        
        # Create tables and indices
        self.conn.executescript(CREATE_TABLES_SQL)
        
        # Create FTS tables
        self.conn.executescript(CREATE_FTS_SQL)
        
        # Check/update schema version
        current_version = self._get_schema_version()
        if current_version == 0:
            self._set_meta("schema_version", str(SCHEMA_VERSION))
            self._set_meta("created_at", str(int(datetime.now().timestamp())))
            self._log(f"Created new database with schema version {SCHEMA_VERSION}")
        elif current_version != SCHEMA_VERSION:
            self._migrate_schema(current_version, SCHEMA_VERSION)
        
        self.conn.commit()
    
    def _get_schema_version(self) -> int:
        """Get current schema version from database."""
        try:
            cursor = self.conn.execute(
                "SELECT value FROM meta WHERE key = 'schema_version'"
            )
            row = cursor.fetchone()
            return int(row[0]) if row else 0
        except sqlite3.OperationalError:
            return 0
    
    def _set_meta(self, key: str, value: str) -> None:
        """Set metadata value."""
        self.conn.execute(
            "INSERT OR REPLACE INTO meta (key, value) VALUES (?, ?)",
            (key, value)
        )
    
    def _migrate_schema(self, from_version: int, to_version: int) -> None:
        """Migrate schema from one version to another."""
        self._log(f"Migrating schema from {from_version} to {to_version}")
        
        # Add migrations here as needed
        # For now, just update version number
        self._set_meta("schema_version", str(to_version))
        self._set_meta("migrated_at", str(int(datetime.now().timestamp())))
    
    def _commit_if_needed(self, force: bool = False) -> None:
        """Commit transaction if batch size reached or forced."""
        if force or self._transaction_count >= self._batch_size:
            if self._transaction_count > 0:
                self.conn.commit()
                self._log(f"Committed {self._transaction_count} operations")
                self._transaction_count = 0
    
    def begin_batch(self, size: int = 100) -> None:
        """Begin a batch transaction."""
        self._batch_size = size
        self._transaction_count = 0
    
    def commit(self) -> None:
        """Commit current transaction."""
        self._commit_if_needed(force=True)
    
    def rollback(self) -> None:
        """Rollback current transaction."""
        if self._conn:
            self._conn.rollback()
            self._transaction_count = 0
    
    # File operations
    
    def add_file(self, path: str, mtime: int, size: int, content_hash: str, 
                  language: Optional[str] = None) -> int:
        """
        Add or update a file record.
        
        Args:
            path: Relative file path
            mtime: Modification timestamp
            size: File size in bytes
            content_hash: SHA256 hash of content
            language: Detected programming language
        
        Returns:
            File ID
        """
        indexed_at = int(datetime.now().timestamp())
        
        cursor = self.conn.execute(
            """
            INSERT INTO files (path, mtime, size, content_hash, indexed_at, language)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(path) DO UPDATE SET
                mtime = excluded.mtime,
                size = excluded.size,
                content_hash = excluded.content_hash,
                indexed_at = excluded.indexed_at,
                language = excluded.language
            RETURNING id
            """,
            (path, mtime, size, content_hash, indexed_at, language)
        )
        
        file_id = cursor.fetchone()[0]
        self._transaction_count += 1
        self._commit_if_needed()
        
        return file_id
    
    def get_file(self, path: str) -> Optional[Dict[str, Any]]:
        """Get file record by path."""
        cursor = self.conn.execute(
            "SELECT * FROM files WHERE path = ?",
            (path,)
        )
        row = cursor.fetchone()
        return dict(row) if row else None
    
    def get_file_by_id(self, file_id: int) -> Optional[Dict[str, Any]]:
        """Get file record by ID."""
        cursor = self.conn.execute(
            "SELECT * FROM files WHERE id = ?",
            (file_id,)
        )
        row = cursor.fetchone()
        return dict(row) if row else None
    
    def delete_file(self, path: str) -> bool:
        """Delete file and all associated symbols/edges."""
        cursor = self.conn.execute(
            "DELETE FROM files WHERE path = ?",
            (path,)
        )
        self._transaction_count += 1
        self._commit_if_needed()
        return cursor.rowcount > 0
    
    def get_all_files(self) -> List[Dict[str, Any]]:
        """Get all indexed files."""
        cursor = self.conn.execute("SELECT * FROM files")
        return [dict(row) for row in cursor.fetchall()]
    
    # Symbol operations
    
    def add_symbol(self, file_id: int, name: str, kind: str, line_start: int,
                   line_end: Optional[int] = None, column_start: Optional[int] = None,
                   column_end: Optional[int] = None, signature: Optional[str] = None,
                   docstring: Optional[str] = None, parent_id: Optional[int] = None) -> int:
        """
        Add a symbol definition.
        
        Returns:
            Symbol ID
        """
        cursor = self.conn.execute(
            """
            INSERT INTO symbols 
            (file_id, name, kind, line_start, line_end, column_start, column_end,
             signature, docstring, parent_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            RETURNING id
            """,
            (file_id, name, kind, line_start, line_end, column_start, column_end,
             signature, docstring, parent_id)
        )
        
        self._transaction_count += 1
        self._commit_if_needed()
        
        return cursor.fetchone()[0]
    
    def get_symbols_in_file(self, file_id: int) -> List[Dict[str, Any]]:
        """Get all symbols defined in a file."""
        cursor = self.conn.execute(
            "SELECT * FROM symbols WHERE file_id = ? ORDER BY line_start",
            (file_id,)
        )
        return [dict(row) for row in cursor.fetchall()]
    
    def delete_symbols_in_file(self, file_id: int) -> int:
        """Delete all symbols in a file. Returns count deleted."""
        cursor = self.conn.execute(
            "DELETE FROM symbols WHERE file_id = ?",
            (file_id,)
        )
        self._transaction_count += 1
        self._commit_if_needed()
        return cursor.rowcount
    
    def search_symbols(self, query: str, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Search symbols using FTS.
        
        Args:
            query: Search query (supports FTS syntax)
            limit: Maximum results
        
        Returns:
            List of matching symbols with rank
        """
        cursor = self.conn.execute(
            """
            SELECT s.*, rank
            FROM symbols_fts
            JOIN symbols s ON symbols_fts.rowid = s.id
            WHERE symbols_fts MATCH ?
            ORDER BY rank
            LIMIT ?
            """,
            (query, limit)
        )
        return [dict(row) for row in cursor.fetchall()]
    
    # Edge operations
    
    def add_edge(self, source_id: int, target_id: int, kind: str, file_id: int,
                 confidence: float = 1.0, metadata: Optional[Dict[str, Any]] = None) -> int:
        """
        Add a relationship edge between symbols.
        
        Args:
            source_id: Source symbol ID
            target_id: Target symbol ID  
            kind: Edge type (call, import, inherit, etc.)
            file_id: File where edge occurs
            confidence: Confidence score (0.0 to 1.0)
            metadata: Optional JSON-serializable metadata dict
        
        Returns:
            Edge ID
        """
        metadata_json = json.dumps(metadata) if metadata else None
        
        # Check if edge already exists to avoid duplicates
        cursor = self.conn.execute(
            """
            SELECT id FROM edges 
            WHERE source_id = ? AND target_id = ? AND kind = ? AND file_id = ?
            LIMIT 1
            """,
            (source_id, target_id, kind, file_id)
        )
        row = cursor.fetchone()
        if row:
            return row[0]

        cursor = self.conn.execute(
            """
            INSERT INTO edges (source_id, target_id, kind, file_id, confidence, metadata)
            VALUES (?, ?, ?, ?, ?, ?)
            RETURNING id
            """,
            (source_id, target_id, kind, file_id, confidence, metadata_json)
        )
        
        self._transaction_count += 1
        self._commit_if_needed()
        
        return cursor.fetchone()[0]
    
    def add_callsite(self, edge_id: int, line: int, column: Optional[int] = None,
                     context: Optional[str] = None) -> int:
        """
        Add a call site record.
        
        Returns:
            Callsite ID
        """
        cursor = self.conn.execute(
            """
            INSERT INTO callsites (edge_id, line, column, context)
            VALUES (?, ?, ?, ?)
            RETURNING id
            """,
            (edge_id, line, column, context)
        )
        
        self._transaction_count += 1
        self._commit_if_needed()
        
        return cursor.fetchone()[0]
    
    def get_outgoing_edges(self, symbol_id: int) -> List[Dict[str, Any]]:
        """Get all edges originating from a symbol."""
        cursor = self.conn.execute(
            """
            SELECT e.*, s.name as target_name, s.kind as target_kind
            FROM edges e
            JOIN symbols s ON e.target_id = s.id
            WHERE e.source_id = ?
            """,
            (symbol_id,)
        )
        return [dict(row) for row in cursor.fetchall()]
    
    def get_incoming_edges(self, symbol_id: int) -> List[Dict[str, Any]]:
        """Get all edges targeting a symbol."""
        cursor = self.conn.execute(
            """
            SELECT e.*, s.name as source_name, s.kind as source_kind
            FROM edges e
            JOIN symbols s ON e.source_id = s.id
            WHERE e.target_id = ?
            """,
            (symbol_id,)
        )
        return [dict(row) for row in cursor.fetchall()]
    
    def delete_edges_in_file(self, file_id: int) -> int:
        """Delete all edges associated with a file."""
        cursor = self.conn.execute(
            "DELETE FROM edges WHERE file_id = ?",
            (file_id,)
        )
        self._transaction_count += 1
        self._commit_if_needed()
        return cursor.rowcount
    
    # Metadata operations
    
    def get_meta(self, key: str) -> Optional[str]:
        """Get metadata value."""
        cursor = self.conn.execute(
            "SELECT value FROM meta WHERE key = ?",
            (key,)
        )
        row = cursor.fetchone()
        return row[0] if row else None
    
    def update_index_stats(self, file_count: int, symbol_count: int) -> None:
        """Update index statistics."""
        self._set_meta("last_indexed", str(int(datetime.now().timestamp())))
        self._set_meta("indexed_files", str(file_count))
        self._set_meta("indexed_symbols", str(symbol_count))
        self._transaction_count += 1
        self._commit_if_needed()
    
    def get_stats(self) -> Dict[str, Any]:
        """Get database statistics."""
        stats = {}
        
        # Table counts
        cursor = self.conn.execute("SELECT COUNT(*) FROM files")
        stats['files'] = cursor.fetchone()[0]
        
        cursor = self.conn.execute("SELECT COUNT(*) FROM symbols")
        stats['symbols'] = cursor.fetchone()[0]
        
        cursor = self.conn.execute("SELECT COUNT(*) FROM edges")
        stats['edges'] = cursor.fetchone()[0]
        
        cursor = self.conn.execute("SELECT COUNT(*) FROM callsites")
        stats['callsites'] = cursor.fetchone()[0]
        
        # Metadata
        stats['schema_version'] = self._get_schema_version()
        stats['created_at'] = self.get_meta('created_at')
        stats['last_indexed'] = self.get_meta('last_indexed')
        
        return stats
    
    # Utility functions
    
    @staticmethod
    def compute_hash(content: str) -> str:
        """Compute SHA256 hash of content."""
        return hashlib.sha256(content.encode('utf-8')).hexdigest()


def get_db_path(repo_root: Path) -> Path:
    """Get default database path for a repository."""
    return repo_root / ".pui" / "index.sqlite"
