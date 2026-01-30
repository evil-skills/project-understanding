"""
Benchmarking suite for Project Understanding Skill.

Provides performance measurement and comparison tools:
- Cold start timing
- Incremental update timing
- Query latency measurement
- Memory usage tracking
- Comparative benchmarks
"""

import time
import tempfile
import statistics
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Callable
from contextlib import contextmanager
import os

from scripts.lib.indexer import Indexer
from scripts.lib.db import Database
from scripts.lib.packs import RepoMapPackGenerator, ZoomPackGenerator, ImpactPackGenerator


@dataclass
class BenchmarkResult:
    """Result of a single benchmark run."""
    name: str
    duration_ms: float
    memory_mb: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'name': self.name,
            'duration_ms': round(self.duration_ms, 2),
            'memory_mb': round(self.memory_mb, 2) if self.memory_mb else None,
            'metadata': self.metadata
        }


@dataclass
class BenchmarkSuite:
    """Collection of benchmark results."""
    name: str
    results: List[BenchmarkResult] = field(default_factory=list)
    timestamp: float = field(default_factory=time.time)
    
    def add_result(self, result: BenchmarkResult):
        """Add a result to the suite."""
        self.results.append(result)
    
    def get_summary(self) -> Dict[str, Any]:
        """Get summary statistics."""
        if not self.results:
            return {}
        
        durations = [r.duration_ms for r in self.results]
        
        return {
            'suite_name': self.name,
            'total_tests': len(self.results),
            'total_duration_ms': round(sum(durations), 2),
            'mean_duration_ms': round(statistics.mean(durations), 2),
            'median_duration_ms': round(statistics.median(durations), 2),
            'min_duration_ms': round(min(durations), 2),
            'max_duration_ms': round(max(durations), 2),
            'timestamp': self.timestamp
        }
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert entire suite to dictionary."""
        return {
            'suite_name': self.name,
            'timestamp': self.timestamp,
            'summary': self.get_summary(),
            'results': [r.to_dict() for r in self.results]
        }
    
    def to_markdown(self) -> str:
        """Format as markdown report."""
        lines = [
            f"# Benchmark Report: {self.name}",
            f"",
            f"**Timestamp**: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(self.timestamp))}",
            f"",
            f"## Summary",
            f"",
            f"| Metric | Value |",
            f"|--------|-------|",
        ]
        
        summary = self.get_summary()
        for key, value in summary.items():
            if key not in ['suite_name', 'timestamp']:
                lines.append(f"| {key} | {value} |")
        
        lines.extend([
            f"",
            f"## Detailed Results",
            f"",
            f"| Test | Duration (ms) | Memory (MB) |",
            f"|------|---------------|-------------|",
        ])
        
        for result in self.results:
            mem_str = f"{result.memory_mb:.2f}" if result.memory_mb else "N/A"
            lines.append(f"| {result.name} | {result.duration_ms:.2f} | {mem_str} |")
        
        lines.append("")
        return '\n'.join(lines)


@contextmanager
def timed_execution(name: str):
    """Context manager for timing code blocks."""
    start = time.perf_counter()
    yield
    end = time.perf_counter()
    duration_ms = (end - start) * 1000
    print(f"  {name}: {duration_ms:.2f}ms")


def get_memory_usage() -> Optional[float]:
    """Get current memory usage in MB."""
    try:
        import psutil
        process = psutil.Process(os.getpid())
        return process.memory_info().rss / 1024 / 1024
    except ImportError:
        return None


class BenchmarkRunner:
    """Runs benchmarks for Project Understanding Skill."""
    
    def __init__(self, repo_root: Path, skill_root: Path):
        self.repo_root = repo_root
        self.skill_root = skill_root
    
    def run_cold_start_benchmark(self) -> BenchmarkResult:
        """Benchmark cold start indexing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create test repository
            test_repo = Path(tmpdir) / "test_repo"
            test_repo.mkdir()
            
            # Create sample files
            self._create_sample_repo(test_repo, num_files=100)
            
            # Time cold start
            start = time.perf_counter()
            indexer = Indexer(test_repo, self.skill_root)
            indexer.initialize()
            stats = indexer.run()
            duration_ms = (time.perf_counter() - start) * 1000
            
            return BenchmarkResult(
                name="cold_start_100_files",
                duration_ms=duration_ms,
                memory_mb=get_memory_usage(),
                metadata={
                    'files_indexed': stats.files_scanned,
                    'symbols_added': stats.symbols_added
                }
            )
    
    def run_incremental_benchmark(self) -> BenchmarkResult:
        """Benchmark incremental update."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_repo = Path(tmpdir) / "test_repo"
            test_repo.mkdir()
            
            # Initial index
            self._create_sample_repo(test_repo, num_files=100)
            indexer = Indexer(test_repo, self.skill_root)
            indexer.initialize()
            indexer.run()
            
            # Modify some files
            self._modify_files(test_repo, num_files=10)
            
            # Time incremental update
            start = time.perf_counter()
            stats = indexer.run()
            duration_ms = (time.perf_counter() - start) * 1000
            
            return BenchmarkResult(
                name="incremental_10_files",
                duration_ms=duration_ms,
                memory_mb=get_memory_usage(),
                metadata={
                    'files_changed': stats.files_changed,
                    'files_unchanged': stats.files_unchanged
                }
            )
    
    def run_query_benchmarks(self) -> List[BenchmarkResult]:
        """Benchmark query operations."""
        results = []
        
        with tempfile.TemporaryDirectory() as tmpdir:
            test_repo = Path(tmpdir) / "test_repo"
            test_repo.mkdir()
            
            # Setup repo
            self._create_sample_repo(test_repo, num_files=50)
            indexer = Indexer(test_repo, self.skill_root)
            indexer.initialize()
            indexer.run()
            
            db_path = test_repo / ".pui" / "index.sqlite"
            db = Database(db_path)
            db.connect()
            
            # Benchmark repomap
            start = time.perf_counter()
            gen = RepoMapPackGenerator(test_repo, db)
            pack = gen.generate(budget_tokens=4000)
            duration_ms = (time.perf_counter() - start) * 1000
            results.append(BenchmarkResult(
                name="repomap_query",
                duration_ms=duration_ms,
                metadata={'token_budget': 4000}
            ))
            
            # Benchmark zoom
            start = time.perf_counter()
            gen = ZoomPackGenerator(test_repo, db)
            pack = gen.generate("func_0_0", budget_tokens=2000)
            duration_ms = (time.perf_counter() - start) * 1000
            results.append(BenchmarkResult(
                name="zoom_query",
                duration_ms=duration_ms,
                metadata={'token_budget': 2000}
            ))
            
            # Benchmark impact
            start = time.perf_counter()
            gen = ImpactPackGenerator(test_repo, db)
            pack = gen.generate("func_0_0", depth=2, budget_tokens=3000)
            duration_ms = (time.perf_counter() - start) * 1000
            results.append(BenchmarkResult(
                name="impact_query",
                duration_ms=duration_ms,
                metadata={'depth': 2, 'token_budget': 3000}
            ))
            
            db.close()
        
        return results
    
    def run_all_benchmarks(self) -> BenchmarkSuite:
        """Run all benchmarks."""
        suite = BenchmarkSuite(name="Project Understanding Skill")
        
        print("Running cold start benchmark...")
        suite.add_result(self.run_cold_start_benchmark())
        
        print("Running incremental benchmark...")
        suite.add_result(self.run_incremental_benchmark())
        
        print("Running query benchmarks...")
        for result in self.run_query_benchmarks():
            suite.add_result(result)
        
        return suite
    
    def _create_sample_repo(self, repo_path: Path, num_files: int):
        """Create a sample repository with Python files."""
        src_dir = repo_path / "src"
        src_dir.mkdir()
        
        for i in range(num_files):
            code = f'''"""Module {i}."""

def func_{i}_a():
    """Function A in module {i}."""
    return {i}

def func_{i}_b():
    """Function B in module {i}."""
    result = func_{i}_a()
    return result * 2

class Class_{i}:
    """Class {i}."""
    
    def method_1(self):
        return func_{i}_a()
    
    def method_2(self):
        return func_{i}_b()
'''
            (src_dir / f"module_{i}.py").write_text(code)
    
    def _modify_files(self, repo_path: Path, num_files: int):
        """Modify some files in the repository."""
        src_dir = repo_path / "src"
        for i in range(min(num_files, 100)):
            file_path = src_dir / f"module_{i}.py"
            if file_path.exists():
                content = file_path.read_text()
                content = content.replace(f"return {i}", f"return {i} + 1")
                file_path.write_text(content)


def run_benchmark_command(output_format: str = "markdown", output_file: Optional[Path] = None) -> int:
    """Run benchmarks and output results."""
    repo_root = Path.cwd()
    skill_root = Path(__file__).parent.parent
    
    runner = BenchmarkRunner(repo_root, skill_root)
    suite = runner.run_all_benchmarks()
    
    if output_format == "json":
        import json
        output = json.dumps(suite.to_dict(), indent=2)
    else:
        output = suite.to_markdown()
    
    if output_file:
        output_file.write_text(output)
        print(f"Benchmark results written to {output_file}")
    else:
        print(output)
    
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(run_benchmark_command())
