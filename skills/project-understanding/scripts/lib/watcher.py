"""
File watcher for automatic index updates.

Provides:
- Cross-platform file watching (watchdog-based)
- Debounced update triggers
- Index locking for concurrent access
- Integration with Indexer
"""

import os
import time
import threading
from pathlib import Path
from typing import Optional, Callable, Set, List
from dataclasses import dataclass, field
from collections import defaultdict

try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler, FileModifiedEvent, FileCreatedEvent, FileDeletedEvent
    WATCHDOG_AVAILABLE = True
except ImportError:
    WATCHDOG_AVAILABLE = False
    FileSystemEventHandler = object


@dataclass
class WatchStats:
    """Statistics for watch mode."""
    events_received: int = 0
    updates_triggered: int = 0
    updates_completed: int = 0
    files_changed: Set[str] = field(default_factory=set)
    start_time: float = field(default_factory=time.time)
    last_update: Optional[float] = None
    
    @property
    def duration(self) -> float:
        """Get duration of watch session."""
        return time.time() - self.start_time
    
    @property
    def update_rate(self) -> float:
        """Get updates per minute."""
        if self.duration < 1:
            return 0.0
        return (self.updates_completed / self.duration) * 60
    
    def to_dict(self):
        """Convert to dictionary."""
        return {
            'events_received': self.events_received,
            'updates_triggered': self.updates_triggered,
            'updates_completed': self.updates_completed,
            'files_changed': len(self.files_changed),
            'duration_seconds': round(self.duration, 2),
            'update_rate_per_min': round(self.update_rate, 2),
            'last_update': self.last_update,
        }
    
    def __str__(self):
        """Format stats for display."""
        lines = [
            "Watch Statistics:",
            f"  Events received: {self.events_received}",
            f"  Updates triggered: {self.updates_triggered}",
            f"  Updates completed: {self.updates_completed}",
            f"  Unique files changed: {len(self.files_changed)}",
            f"  Duration: {self.duration:.2f}s",
            f"  Update rate: {self.update_rate:.2f}/min",
        ]
        return '\n'.join(lines)


class IndexLock:
    """File-based lock for index access."""
    
    def __init__(self, lock_path: Path):
        self.lock_path = Path(lock_path)
        self._held = False
        self._pid = os.getpid()
    
    def acquire(self, blocking: bool = True, timeout: Optional[float] = None) -> bool:
        """Acquire the lock."""
        if self._held:
            return True
        
        start_time = time.time()
        
        while True:
            try:
                # Try to create lock file exclusively
                fd = os.open(
                    str(self.lock_path),
                    os.O_CREAT | os.O_EXCL | os.O_WRONLY
                )
                
                # Write our PID
                os.write(fd, str(self._pid).encode())
                os.close(fd)
                
                self._held = True
                return True
                
            except FileExistsError:
                # Lock is held by someone else
                if not blocking:
                    return False
                
                # Check timeout
                if timeout is not None and (time.time() - start_time) > timeout:
                    return False
                
                # Check for stale lock
                try:
                    with open(self.lock_path, 'r') as f:
                        lock_pid = int(f.read().strip())
                    
                    # Check if process still exists
                    try:
                        os.kill(lock_pid, 0)
                    except OSError:
                        # Process doesn't exist, remove stale lock
                        try:
                            os.remove(self.lock_path)
                            continue
                        except OSError:
                            pass
                except (ValueError, FileNotFoundError):
                    pass
                
                # Wait before retry
                time.sleep(0.1)
    
    def release(self) -> bool:
        """Release the lock."""
        if not self._held:
            return True
        
        try:
            # Verify we own the lock
            with open(self.lock_path, 'r') as f:
                lock_pid = f.read().strip()
            
            if int(lock_pid) == self._pid:
                os.remove(self.lock_path)
                self._held = False
                return True
        except (ValueError, FileNotFoundError, OSError):
            pass
        
        return False
    
    def __enter__(self):
        self.acquire()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.release()


class FileChangeHandler(FileSystemEventHandler):
    """Handles file change events."""
    
    def __init__(
        self,
        callback: Callable[[str, str], None],
        ignore_patterns: Optional[List[str]] = None,
        extensions: Optional[Set[str]] = None
    ):
        self.callback = callback
        self.ignore_patterns = ignore_patterns or [
            '.git', '.pui', '__pycache__', '.pytest_cache',
            'node_modules', '.venv', 'venv', '.env'
        ]
        self.extensions = extensions or {'.py', '.js', '.ts', '.rs', '.go', '.java'}
    
    def _should_ignore(self, path: str) -> bool:
        """Check if path should be ignored."""
        path_parts = path.split(os.sep)
        
        # Check ignore patterns
        for pattern in self.ignore_patterns:
            if pattern in path_parts:
                return True
        
        # Check extension
        if self.extensions:
            if not any(path.endswith(ext) for ext in self.extensions):
                return True
        
        return False
    
    def on_modified(self, event):
        if isinstance(event, FileModifiedEvent):
            if not self._should_ignore(event.src_path):
                self.callback('modified', event.src_path)
    
    def on_created(self, event):
        if isinstance(event, FileCreatedEvent):
            if not self._should_ignore(event.src_path):
                self.callback('created', event.src_path)
    
    def on_deleted(self, event):
        if isinstance(event, FileDeletedEvent):
            if not self._should_ignore(event.src_path):
                self.callback('deleted', event.src_path)


class WatchMode:
    """Watch mode for automatic index updates."""
    
    def __init__(
        self,
        repo_root: Path,
        skill_root: Path,
        debounce_seconds: float = 1.0,
        verbose: bool = False
    ):
        self.repo_root = Path(repo_root)
        self.skill_root = Path(skill_root)
        self.debounce_seconds = debounce_seconds
        self.verbose = verbose
        
        self.stats = WatchStats()
        self.lock = IndexLock(self.repo_root / ".pui" / "index.lock")
        
        self._observer: Optional[Observer] = None
        self._pending_changes: Set[str] = set()
        self._debounce_timer: Optional[threading.Timer] = None
        self._running = False
        self._update_callback: Optional[Callable[[Set[str]], None]] = None
    
    def _log(self, message: str) -> None:
        """Log message if verbose mode enabled."""
        if self.verbose:
            print(f"[Watch] {message}")
    
    def _on_file_change(self, change_type: str, path: str) -> None:
        """Handle a file change event."""
        self.stats.events_received += 1
        
        rel_path = os.path.relpath(path, self.repo_root)
        self._log(f"{change_type}: {rel_path}")
        
        self._pending_changes.add(rel_path)
        self.stats.files_changed.add(rel_path)
        
        # Debounce the update
        if self._debounce_timer:
            self._debounce_timer.cancel()
        
        self._debounce_timer = threading.Timer(
            self.debounce_seconds,
            self._trigger_update
        )
        self._debounce_timer.start()
    
    def _trigger_update(self) -> None:
        """Trigger index update."""
        if not self._pending_changes:
            return
        
        changes = self._pending_changes.copy()
        self._pending_changes.clear()
        
        self.stats.updates_triggered += 1
        
        # Acquire lock
        if not self.lock.acquire(blocking=False):
            self._log("Another update in progress, skipping")
            return
        
        try:
            self._log(f"Running update for {len(changes)} file(s)")
            
            if self._update_callback:
                self._update_callback(changes)
            else:
                self._run_indexer(changes)
            
            self.stats.updates_completed += 1
            self.stats.last_update = time.time()
            
        finally:
            self.lock.release()
    
    def _run_indexer(self, changes: Set[str]) -> None:
        """Run the indexer."""
        from scripts.lib.indexer import Indexer
        
        with Indexer(self.repo_root, self.skill_root, self.verbose) as indexer:
            stats = indexer.run()
            if self.verbose:
                print(stats)
    
    def start(
        self,
        update_callback: Optional[Callable[[Set[str]], None]] = None
    ) -> None:
        """
        Start watching for file changes.
        
        Args:
            update_callback: Optional callback to run on updates
                           (receives set of changed file paths)
        """
        if not WATCHDOG_AVAILABLE:
            raise RuntimeError(
                "watchdog not installed. "
                "Install with: pip install watchdog"
            )
        
        self._update_callback = update_callback
        
        # Set up file watcher
        handler = FileChangeHandler(
            callback=self._on_file_change,
            extensions={'.py', '.js', '.ts', '.rs', '.go', '.java'}
        )
        
        self._observer = Observer()
        self._observer.schedule(handler, str(self.repo_root), recursive=True)
        self._observer.start()
        
        self._running = True
        self._log(f"Started watching {self.repo_root}")
        print(f"Watching {self.repo_root} for changes...")
        print("Press Ctrl+C to stop")
        
        try:
            while self._running:
                time.sleep(1)
        except KeyboardInterrupt:
            self.stop()
    
    def stop(self) -> None:
        """Stop watching for file changes."""
        self._running = False
        
        if self._debounce_timer:
            self._debounce_timer.cancel()
        
        if self._observer:
            self._observer.stop()
            self._observer.join()
        
        self._log("Stopped watching")
        print("\nWatch mode stopped")
        print(self.stats)


def watch_repo(
    repo_root: Optional[Path] = None,
    skill_root: Optional[Path] = None,
    debounce_seconds: float = 1.0,
    verbose: bool = False
) -> None:
    """
    Convenience function to watch a repository.
    
    Args:
        repo_root: Repository root (uses current directory if None)
        skill_root: Skill root directory
        debounce_seconds: Debounce delay
        verbose: Enable verbose logging
    """
    if repo_root is None:
        repo_root = Path.cwd()
    
    if skill_root is None:
        skill_root = Path(__file__).parent.parent.parent
    
    watcher = WatchMode(repo_root, skill_root, debounce_seconds, verbose)
    watcher.start()
