"""
Parallel parsing with multi-process support.

Provides:
- Multi-process file parsing
- Worker pool management
- Result aggregation
- Progress tracking
"""

import os
import sys
import multiprocessing as mp
from pathlib import Path
from typing import List, Dict, Any, Optional, Callable, Tuple
from dataclasses import dataclass, field
from concurrent.futures import ProcessPoolExecutor, as_completed
import time


@dataclass
class ParseResult:
    """Result of parsing a single file."""
    file_path: str
    success: bool
    symbols: List[Dict[str, Any]] = field(default_factory=list)
    imports: List[Dict[str, Any]] = field(default_factory=list)
    callsites: List[Dict[str, Any]] = field(default_factory=list)
    error: Optional[str] = None
    duration: float = 0.0


@dataclass
class ParallelStats:
    """Statistics for parallel parsing."""
    files_total: int = 0
    files_success: int = 0
    files_failed: int = 0
    symbols_found: int = 0
    start_time: float = field(default_factory=time.time)
    end_time: Optional[float] = None
    
    @property
    def duration(self) -> float:
        """Get duration of parsing run."""
        end = self.end_time or time.time()
        return end - self.start_time
    
    @property
    def files_per_second(self) -> float:
        """Get parsing rate."""
        if self.duration < 0.001:
            return 0.0
        return self.files_total / self.duration


def _parse_file_worker(args: Tuple[str, str, Optional[str]]) -> ParseResult:
    """
    Worker function to parse a single file.
    
    Must be at module level for pickle serialization.
    """
    file_path, repo_root, language = args
    
    start_time = time.time()
    
    try:
        from scripts.lib.parser import parse_file
        
        result = parse_file(
            Path(file_path),
            repo_root=Path(repo_root),
            language=language
        )
        
        if result is None:
            return ParseResult(
                file_path=file_path,
                success=False,
                error="Parsing returned None"
            )
        
        # Convert to serializable format
        symbols = []
        for sym in result.symbols:
            symbols.append({
                'name': sym.name,
                'kind': sym.kind,
                'line_start': sym.line_start,
                'line_end': sym.line_end,
                'column_start': sym.column_start,
                'column_end': sym.column_end,
                'signature': sym.signature,
                'docstring': sym.docstring,
                'parent_name': sym.parent_name,
                'calls': sym.calls,
            })
        
        imports = []
        for imp in result.imports:
            imports.append({
                'module': imp.module,
                'name': imp.name,
                'alias': imp.alias,
                'line': imp.line,
                'raw_text': imp.raw_text,
            })
        
        callsites = []
        for cs in result.callsites:
            callsites.append({
                'callee_text': cs.callee_text,
                'line': cs.line,
                'column': cs.column,
                'scope_symbol_id': cs.scope_symbol_id,
                'confidence': cs.confidence,
            })
        
        return ParseResult(
            file_path=file_path,
            success=True,
            symbols=symbols,
            imports=imports,
            callsites=callsites,
            duration=time.time() - start_time
        )
        
    except Exception as e:
        return ParseResult(
            file_path=file_path,
            success=False,
            error=str(e),
            duration=time.time() - start_time
        )


class ParallelParser:
    """Parse files in parallel using multiple processes."""
    
    def __init__(
        self,
        max_workers: Optional[int] = None,
        verbose: bool = False
    ):
        self.max_workers = max_workers or max(1, mp.cpu_count() - 1)
        self.verbose = verbose
        self.stats = ParallelStats()
    
    def _log(self, message: str) -> None:
        """Log message if verbose mode enabled."""
        if self.verbose:
            print(f"[Parallel] {message}")
    
    def parse_files(
        self,
        file_paths: List[Path],
        repo_root: Path,
        languages: Optional[Dict[str, str]] = None
    ) -> List[ParseResult]:
        """
        Parse multiple files in parallel.
        
        Args:
            file_paths: List of file paths to parse
            repo_root: Repository root directory
            languages: Optional dict mapping file paths to language
        
        Returns:
            List of ParseResult objects
        """
        if not file_paths:
            return []
        
        self.stats = ParallelStats(files_total=len(file_paths))
        
        # Prepare arguments
        args_list = []
        for fp in file_paths:
            lang = languages.get(str(fp)) if languages else None
            args_list.append((str(fp), str(repo_root), lang))
        
        self._log(f"Parsing {len(file_paths)} files with {self.max_workers} workers")
        
        results = []
        
        # Use process pool for parallel parsing
        with ProcessPoolExecutor(max_workers=self.max_workers) as executor:
            # Submit all tasks
            future_to_file = {
                executor.submit(_parse_file_worker, args): args[0]
                for args in args_list
            }
            
            # Collect results as they complete
            for future in as_completed(future_to_file):
                file_path = future_to_file[future]
                try:
                    result = future.result()
                    results.append(result)
                    
                    if result.success:
                        self.stats.files_success += 1
                        self.stats.symbols_found += len(result.symbols)
                        self._log(f"Parsed {file_path}: {len(result.symbols)} symbols")
                    else:
                        self.stats.files_failed += 1
                        self._log(f"Failed to parse {file_path}: {result.error}")
                        
                except Exception as e:
                    self.stats.files_failed += 1
                    self._log(f"Exception parsing {file_path}: {e}")
                    results.append(ParseResult(
                        file_path=file_path,
                        success=False,
                        error=str(e)
                    ))
        
        self.stats.end_time = time.time()
        self._log(f"Completed: {self.stats.files_success}/{self.stats.files_total} files, "
                  f"{self.stats.symbols_found} symbols, "
                  f"{self.stats.duration:.2f}s")
        
        return results
    
    def parse_files_sequential(
        self,
        file_paths: List[Path],
        repo_root: Path,
        languages: Optional[Dict[str, str]] = None
    ) -> List[ParseResult]:
        """
        Parse files sequentially (fallback when parallel fails).
        
        Args:
            file_paths: List of file paths to parse
            repo_root: Repository root directory
            languages: Optional dict mapping file paths to language
        
        Returns:
            List of ParseResult objects
        """
        if not file_paths:
            return []
        
        self.stats = ParallelStats(files_total=len(file_paths))
        
        results = []
        
        for fp in file_paths:
            lang = languages.get(str(fp)) if languages else None
            args = (str(fp), str(repo_root), lang)
            
            result = _parse_file_worker(args)
            results.append(result)
            
            if result.success:
                self.stats.files_success += 1
                self.stats.symbols_found += len(result.symbols)
            else:
                self.stats.files_failed += 1
        
        self.stats.end_time = time.time()
        return results


class ScalabilityGuardrails:
    """Guardrails to prevent runaway resource usage."""
    
    def __init__(
        self,
        max_symbols_per_file: int = 1000,
        max_edges_per_symbol: int = 100,
        collapse_auto_generated: bool = True
    ):
        self.max_symbols_per_file = max_symbols_per_file
        self.max_edges_per_symbol = max_edges_per_symbol
        self.collapse_auto_generated = collapse_auto_generated
    
    def check_file(self, file_path: str, symbol_count: int) -> bool:
        """
        Check if file exceeds symbol limit.
        
        Returns:
            True if within limits
        """
        if symbol_count > self.max_symbols_per_file:
            return False
        return True
    
    def should_collapse(self, symbol: Dict[str, Any]) -> bool:
        """
        Check if symbol should be collapsed (auto-generated code).
        
        Returns:
            True if symbol should be collapsed
        """
        if not self.collapse_auto_generated:
            return False
        
        name = symbol.get('name', '')
        
        # Common auto-generated patterns
        auto_patterns = [
            '_generated_',
            '_auto_',
            '__generated__',
            'Generated',
            'pb2.',  # Protocol buffers
            '_pb2',
            'swagger_',
            'openapi_',
        ]
        
        return any(pattern in name for pattern in auto_patterns)
    
    def apply_to_results(self, results: List[ParseResult]) -> List[ParseResult]:
        """
        Apply guardrails to parse results.
        
        Args:
            results: List of parse results
        
        Returns:
            Filtered results
        """
        filtered = []
        
        for result in results:
            if not result.success:
                filtered.append(result)
                continue
            
            # Check symbol limit
            if not self.check_file(result.file_path, len(result.symbols)):
                # Mark as truncated
                result.symbols = result.symbols[:self.max_symbols_per_file]
                # Add truncation marker
                result.symbols.append({
                    'name': '__TRUNCATED__',
                    'kind': 'meta',
                    'line_start': 0,
                    'signature': f'(truncated at {self.max_symbols_per_file} symbols)',
                })
            
            # Filter auto-generated symbols
            if self.collapse_auto_generated:
                result.symbols = [
                    s for s in result.symbols
                    if not self.should_collapse(s)
                ]
            
            filtered.append(result)
        
        return filtered


def parse_parallel(
    file_paths: List[Path],
    repo_root: Path,
    max_workers: Optional[int] = None,
    verbose: bool = False
) -> List[ParseResult]:
    """
    Convenience function for parallel parsing.
    
    Args:
        file_paths: List of file paths to parse
        repo_root: Repository root directory
        max_workers: Maximum worker processes
        verbose: Enable verbose logging
    
    Returns:
        List of ParseResult objects
    """
    parser = ParallelParser(max_workers=max_workers, verbose=verbose)
    return parser.parse_files(file_paths, repo_root)
