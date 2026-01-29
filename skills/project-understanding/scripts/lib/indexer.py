"""
Incremental indexer for Project Understanding.

Scans files, computes hashes, skips unchanged files, and updates the database.
Provides batching, timing logs, and statistics.
"""

import os
import time
import hashlib
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple, Callable
from dataclasses import dataclass, field
from collections import defaultdict

from scripts.lib.db import Database, get_db_path
from scripts.lib.ignore import IgnoreManager, load_default_ignore
from scripts.lib.config import ConfigManager, Config


@dataclass
class IndexStats:
    """Statistics for an indexing run."""
    files_scanned: int = 0
    files_new: int = 0
    files_changed: int = 0
    files_unchanged: int = 0
    files_deleted: int = 0
    files_error: int = 0
    symbols_added: int = 0
    symbols_removed: int = 0
    edges_added: int = 0
    edges_removed: int = 0
    start_time: float = field(default_factory=time.time)
    end_time: Optional[float] = None
    
    @property
    def duration(self) -> float:
        """Get duration of indexing run."""
        end = self.end_time or time.time()
        return end - self.start_time
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert stats to dictionary."""
        return {
            'files_scanned': self.files_scanned,
            'files_new': self.files_new,
            'files_changed': self.files_changed,
            'files_unchanged': self.files_unchanged,
            'files_deleted': self.files_deleted,
            'files_error': self.files_error,
            'symbols_added': self.symbols_added,
            'symbols_removed': self.symbols_removed,
            'edges_added': self.edges_added,
            'edges_removed': self.edges_removed,
            'duration_seconds': round(self.duration, 2)
        }
    
    def __str__(self) -> str:
        """Format stats for display."""
        lines = [
            "Index Statistics:",
            f"  Files scanned: {self.files_scanned}",
            f"  Files new: {self.files_new}",
            f"  Files changed: {self.files_changed}",
            f"  Files unchanged: {self.files_unchanged}",
            f"  Files deleted: {self.files_deleted}",
            f"  Files with errors: {self.files_error}",
            f"  Symbols added: {self.symbols_added}",
            f"  Symbols removed: {self.symbols_removed}",
            f"  Edges added: {self.edges_added}",
            f"  Edges removed: {self.edges_removed}",
            f"  Duration: {self.duration:.2f}s"
        ]
        return '\n'.join(lines)


@dataclass
class FileInfo:
    """Information about a file to be indexed."""
    path: Path
    relative_path: str
    mtime: float
    size: int
    content_hash: Optional[str] = None
    language: Optional[str] = None


class Indexer:
    """Incremental indexer for source code."""
    
    def __init__(self, 
                 repo_root: Path,
                 skill_root: Path,
                 verbose: bool = False,
                 batch_size: int = 100):
        """
        Initialize indexer.
        
        Args:
            repo_root: Repository root directory
            skill_root: Skill installation directory
            verbose: Enable verbose logging
            batch_size: Number of files per transaction batch
        """
        self.repo_root = Path(repo_root)
        self.skill_root = Path(skill_root)
        self.verbose = verbose
        self.batch_size = batch_size
        self.stats = IndexStats()
        
        # Initialize components
        self.db: Optional[Database] = None
        self.ignore_manager: Optional[IgnoreManager] = None
        self.config_manager: Optional[ConfigManager] = None
        self.config: Optional[Config] = None
        
        # Timing logs
        self.timings: Dict[str, List[float]] = defaultdict(list)
    
    def _log(self, message: str) -> None:
        """Log message if verbose mode enabled."""
        if self.verbose:
            print(f"[Indexer] {message}")
    
    def _time(self, operation: str) -> Callable:
        """Context manager for timing operations."""
        class Timer:
            def __enter__(timer):
                timer.start = time.time()
                return timer
            
            def __exit__(timer, *args):
                elapsed = time.time() - timer.start
                self.timings[operation].append(elapsed)
                if self.verbose:
                    print(f"[Timer] {operation}: {elapsed:.3f}s")
        
        return Timer()
    
    def initialize(self) -> "Indexer":
        """Initialize all components."""
        with self._time("initialize"):
            # Load configuration
            self.config_manager = ConfigManager(self.repo_root, self.verbose)
            self.config = self.config_manager.load()
            
            # Override batch size from config
            self.batch_size = self.config.indexing.batch_size
            
            # Initialize ignore manager
            default_ignore = load_default_ignore(self.skill_root)
            self.ignore_manager = IgnoreManager(self.repo_root, self.verbose)
            self.ignore_manager.load(default_ignore_path=default_ignore)
            
            # Apply CLI include/exclude from config
            for pattern in self.config.ignore.include:
                self.ignore_manager.add_include(pattern)
            for pattern in self.config.ignore.exclude:
                self.ignore_manager.add_exclude(pattern)
            
            # Initialize database
            db_path = get_db_path(self.repo_root)
            self.db = Database(db_path, self.verbose)
            self.db.connect()
            self.db.begin_batch(self.batch_size)
            
            self._log("Initialization complete")
        
        return self
    
    def close(self) -> None:
        """Close all resources."""
        if self.db:
            self.db.close()
            self.db = None
    
    def __enter__(self) -> "Indexer":
        """Context manager entry."""
        return self.initialize()
    
    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Context manager exit."""
        self.close()
    
    def compute_file_hash(self, path: Path) -> str:
        """Compute SHA256 hash of file content."""
        sha256 = hashlib.sha256()
        with open(path, 'rb') as f:
            for chunk in iter(lambda: f.read(8192), b''):
                sha256.update(chunk)
        return sha256.hexdigest()
    
    def detect_language(self, path: Path) -> Optional[str]:
        """Detect programming language from file extension."""
        if not self.config:
            return None
        
        ext = path.suffix.lower()
        return self.config.languages.extensions.get(ext)
    
    def scan_files(self) -> List[FileInfo]:
        """
        Scan repository for candidate files.
        
        Returns:
            List of FileInfo objects
        """
        with self._time("scan_files"):
            if not self.config or not self.ignore_manager:
                raise RuntimeError("Indexer not initialized")
            
            extensions = set(self.config.languages.extensions.keys())
            max_size = self.config.indexing.max_file_size
            
            candidates = self.ignore_manager.get_candidate_files(
                extensions=extensions,
                max_size=max_size
            )
            
            files = []
            for path in candidates:
                try:
                    stat = path.stat()
                    rel_path = str(path.relative_to(self.repo_root))
                    
                    files.append(FileInfo(
                        path=path,
                        relative_path=rel_path,
                        mtime=stat.st_mtime,
                        size=stat.st_size,
                        language=self.detect_language(path)
                    ))
                except OSError as e:
                    self._log(f"Error stat-ing {path}: {e}")
                    self.stats.files_error += 1
            
            self._log(f"Found {len(files)} candidate files")
            self.stats.files_scanned = len(files)
            return files
    
    def should_reindex(self, file_info: FileInfo, db_file: Optional[Dict]) -> bool:
        """
        Check if file needs reindexing.
        
        Args:
            file_info: File information
            db_file: Existing database record
        
        Returns:
            True if file needs reindexing
        """
        if not db_file:
            return True
        
        # Check modification time
        if int(file_info.mtime) != db_file['mtime']:
            return True
        
        # Check size
        if file_info.size != db_file['size']:
            return True
        
        # Compute and compare hash
        content_hash = self.compute_file_hash(file_info.path)
        if content_hash != db_file['content_hash']:
            return True
        
        return False
    
    def remove_stale_files(self, current_files: List[str]) -> int:
        """
        Remove files from index that no longer exist.
        
        Args:
            current_files: List of current file paths
        
        Returns:
            Number of files removed
        """
        with self._time("remove_stale"):
            if not self.db:
                raise RuntimeError("Database not initialized")
            
            current_set = set(current_files)
            indexed_files = self.db.get_all_files()
            
            removed = 0
            for file_record in indexed_files:
                if file_record['path'] not in current_set:
                    self._log(f"Removing stale file: {file_record['path']}")
                    self.db.delete_file(file_record['path'])
                    removed += 1
                    self.stats.files_deleted += 1
            
            if removed > 0:
                self.db.commit()
            
            return removed
    
    def index_file(self, file_info: FileInfo) -> bool:
        """
        Index a single file.
        
        Args:
            file_info: File information
        
        Returns:
            True if indexing succeeded
        """
        if not self.db:
            raise RuntimeError("Database not initialized")
        
        try:
            # Compute content hash
            content_hash = self.compute_file_hash(file_info.path)
            file_info.content_hash = content_hash
            
            # Add/update file record
            file_id = self.db.add_file(
                path=file_info.relative_path,
                mtime=int(file_info.mtime),
                size=file_info.size,
                content_hash=content_hash,
                language=file_info.language
            )
            
            # Remove old symbols and edges for this file
            old_symbols = self.db.get_symbols_in_file(file_id)
            self.stats.symbols_removed += len(old_symbols)
            self.db.delete_symbols_in_file(file_id)
            self.db.delete_edges_in_file(file_id)
            
            # Parse and extract symbols
            symbols = self.parse_file(file_info)
            
            # Add new symbols
            symbol_map: Dict[str, int] = {}
            for symbol in symbols:
                parent_id = None
                if symbol.get('parent_name') and symbol['parent_name'] in symbol_map:
                    parent_id = symbol_map[symbol['parent_name']]
                
                symbol_id = self.db.add_symbol(
                    file_id=file_id,
                    name=symbol['name'],
                    kind=symbol['kind'],
                    line_start=symbol['line_start'],
                    line_end=symbol.get('line_end'),
                    column_start=symbol.get('column_start'),
                    column_end=symbol.get('column_end'),
                    signature=symbol.get('signature'),
                    docstring=symbol.get('docstring'),
                    parent_id=parent_id
                )
                symbol_map[symbol['name']] = symbol_id
                self.stats.symbols_added += 1
                
                # Add edges for calls
                for call in symbol.get('calls', []):
                    # We can't resolve the target yet, so we create an unresolved edge
                    # This will be resolved in a second pass
                    pass
            
            return True
            
        except Exception as e:
            self._log(f"Error indexing {file_info.relative_path}: {e}")
            self.stats.files_error += 1
            return False
    
    def parse_file(self, file_info: FileInfo) -> List[Dict[str, Any]]:
        """
        Parse a file and extract symbols.
        
        This is a placeholder that will be replaced with tree-sitter parsing.
        For now, returns basic file-level information.
        
        Args:
            file_info: File information
        
        Returns:
            List of symbol dictionaries
        """
        # TODO: Replace with tree-sitter parser
        # For now, just return a single symbol for the file
        return [{
            'name': file_info.path.stem,
            'kind': 'file',
            'line_start': 1,
            'line_end': None,
            'column_start': None,
            'column_end': None,
            'signature': None,
            'docstring': None,
            'parent_name': None,
            'calls': []
        }]
    
    def run(self, force: bool = False) -> IndexStats:
        """
        Run the indexer.
        
        Args:
            force: Force reindex all files
        
        Returns:
            Indexing statistics
        """
        self._log("Starting index run")
        
        try:
            # Scan for files
            files = self.scan_files()
            self.stats.files_scanned = len(files)
            
            # Remove stale files
            current_paths = [f.relative_path for f in files]
            self.remove_stale_files(current_paths)
            
            # Process each file
            for file_info in files:
                if not self.db:
                    continue
                
                # Check if file needs reindexing
                db_file = self.db.get_file(file_info.relative_path)
                
                if force or self.should_reindex(file_info, db_file):
                    if db_file:
                        self.stats.files_changed += 1
                        self._log(f"Reindexing changed file: {file_info.relative_path}")
                    else:
                        self.stats.files_new += 1
                        self._log(f"Indexing new file: {file_info.relative_path}")
                    
                    self.index_file(file_info)
                else:
                    self.stats.files_unchanged += 1
                    self._log(f"Skipping unchanged file: {file_info.relative_path}")
            
            # Final commit
            if self.db:
                self.db.commit()
                
                # Update index stats
                db_stats = self.db.get_stats()
                self.db.update_index_stats(
                    file_count=db_stats['files'],
                    symbol_count=db_stats['symbols']
                )
            
        except Exception as e:
            self._log(f"Error during indexing: {e}")
            if self.db:
                self.db.rollback()
            raise
        
        finally:
            self.stats.end_time = time.time()
        
        self._log("Index run complete")
        return self.stats
    
    def print_timings(self) -> None:
        """Print timing statistics."""
        if not self.verbose:
            return
        
        print("\nTiming Statistics:")
        for operation, times in sorted(self.timings.items()):
            total = sum(times)
            avg = total / len(times) if times else 0
            print(f"  {operation}: {total:.3f}s total, {avg:.3f}s avg ({len(times)} calls)")
