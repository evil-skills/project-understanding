"""
Impact Analysis for Project Understanding.

Provides diff-aware impact analysis including:
- Git diff parsing
- Changed symbol detection
- Blast radius computation
- Test selection intelligence
- API boundary detection
"""

import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class ChangedSymbol:
    """Represents a symbol that was changed."""
    name: str
    file: str
    kind: str
    line_start: int
    line_end: int
    change_type: str  # 'modified', 'added', 'deleted'
    confidence: float = 1.0


@dataclass
class ImpactResult:
    """Result of impact analysis."""
    changed_files: List[str] = field(default_factory=list)
    changed_symbols: List[ChangedSymbol] = field(default_factory=list)
    affected_files: List[str] = field(default_factory=list)
    affected_symbols: List[str] = field(default_factory=list)
    affected_tests: List[str] = field(default_factory=list)
    api_risk_level: str = "none"  # none, low, medium, high
    api_risk_reasons: List[str] = field(default_factory=list)
    blast_radius: int = 0
    inspection_queue: List[Dict[str, Any]] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'changed_files': self.changed_files,
            'changed_symbols': [
                {
                    'name': s.name,
                    'file': s.file,
                    'kind': s.kind,
                    'line_start': s.line_start,
                    'change_type': s.change_type,
                    'confidence': s.confidence
                }
                for s in self.changed_symbols
            ],
            'affected_files': self.affected_files,
            'affected_symbols': self.affected_symbols,
            'affected_tests': self.affected_tests,
            'api_risk_level': self.api_risk_level,
            'api_risk_reasons': self.api_risk_reasons,
            'blast_radius': self.blast_radius,
            'inspection_queue': self.inspection_queue
        }
    
    def to_markdown(self) -> str:
        """Generate markdown report."""
        lines = [
            "# Impact Analysis Report",
            "",
            "## Summary",
            f"- **Changed Files**: {len(self.changed_files)}",
            f"- **Changed Symbols**: {len(self.changed_symbols)}",
            f"- **Affected Files**: {len(self.affected_files)}",
            f"- **Affected Tests**: {len(self.affected_tests)}",
            f"- **Blast Radius**: {self.blast_radius} symbols",
            f"- **API Risk Level**: {self.api_risk_level}",
            ""
        ]
        
        if self.api_risk_reasons:
            lines.append("### API Risk Reasons")
            for reason in self.api_risk_reasons:
                lines.append(f"- {reason}")
            lines.append("")
        
        if self.changed_symbols:
            lines.append("## Changed Symbols")
            for sym in self.changed_symbols:
                lines.append(f"- `{sym.name}` ({sym.kind}) in `{sym.file}:{sym.line_start}` - {sym.change_type}")
            lines.append("")
        
        if self.affected_tests:
            lines.append("## Affected Tests")
            for test in self.affected_tests[:20]:  # Limit output
                lines.append(f"- `{test}`")
            if len(self.affected_tests) > 20:
                lines.append(f"- ... and {len(self.affected_tests) - 20} more")
            lines.append("")
        
        if self.inspection_queue:
            lines.append("## Inspection Queue (Prioritized)")
            for i, item in enumerate(self.inspection_queue[:15], 1):
                lines.append(f"{i}. `{item.get('symbol', 'unknown')}` - {item.get('reason', 'affected')}")
            lines.append("")
        
        return "\n".join(lines)


class GitDiffParser:
    """Parses git diff output to extract changes."""
    
    def __init__(self, repo_root: Path):
        self.repo_root = self._resolve_repo_root(repo_root)

    def _resolve_repo_root(self, repo_root: Path) -> Path:
        try:
            result = subprocess.run(
                ["git", "rev-parse", "--show-toplevel"],
                cwd=repo_root,
                capture_output=True,
                text=True,
                check=True
            )
        except FileNotFoundError as exc:
            raise RuntimeError("Git not found") from exc
        except subprocess.CalledProcessError as exc:
            raise RuntimeError(f"Git command failed: {exc.stderr}") from exc

        return Path(result.stdout.strip())
    
    def get_changed_files(self, ref_range: str) -> List[Path]:
        """Get list of changed files from git diff."""
        try:
            result = subprocess.run(
                ["git", "diff", "--name-only", ref_range],
                cwd=self.repo_root,
                capture_output=True,
                text=True,
                check=True
            )
            
            files = []
            for line in result.stdout.strip().split('\n'):
                if line:
                    files.append(self.repo_root / line)
            
            return files
            
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"Git command failed: {e.stderr}")
        except FileNotFoundError:
            raise RuntimeError("Git not found")
    
    def get_diff_hunks(self, ref_range: str, file_path: Path) -> List[Dict[str, Any]]:
        """Get diff hunks for a specific file."""
        try:
            result = subprocess.run(
                ["git", "diff", "-U0", ref_range, "--", str(file_path.relative_to(self.repo_root))],
                cwd=self.repo_root,
                capture_output=True,
                text=True,
                check=True
            )
            
            return self._parse_diff_output(result.stdout)
            
        except subprocess.CalledProcessError:
            return []
    
    def _parse_diff_output(self, diff_text: str) -> List[Dict[str, Any]]:
        """Parse unified diff output."""
        hunks = []
        current_hunk = None
        
        for line in diff_text.split('\n'):
            if line.startswith('@@'):
                # Parse hunk header: @@ -start,count +start,count @@
                match = re.match(r'@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@', line)
                if match:
                    old_start = int(match.group(1))
                    old_count = int(match.group(2)) if match.group(2) else 1
                    new_start = int(match.group(3))
                    new_count = int(match.group(4)) if match.group(4) else 1
                    
                    current_hunk = {
                        'old_start': old_start,
                        'old_count': old_count,
                        'new_start': new_start,
                        'new_count': new_count,
                        'lines_added': [],
                        'lines_deleted': []
                    }
                    hunks.append(current_hunk)
            
            elif current_hunk:
                if line.startswith('+'):
                    current_hunk['lines_added'].append(line[1:])
                elif line.startswith('-'):
                    current_hunk['lines_deleted'].append(line[1:])
        
        return hunks


class TestSelector:
    """Intelligent test selection based on code changes."""
    
    def __init__(self, repo_root: Path):
        self.repo_root = repo_root
    
    def find_related_tests(self, changed_file: Path, changed_symbol: Optional[str] = None) -> List[str]:
        """Find tests related to a changed file/symbol."""
        tests = []
        
        # Strategy 1: Naming convention (Foo -> FooTest)
        if changed_symbol:
            convention_tests = self._find_by_naming_convention(changed_symbol)
            tests.extend(convention_tests)
        
        # Strategy 2: Directory adjacency
        adjacent_tests = self._find_adjacent_tests(changed_file)
        tests.extend(adjacent_tests)
        
        # Strategy 3: Same directory tests
        same_dir_tests = self._find_same_directory_tests(changed_file)
        tests.extend(same_dir_tests)
        
        # Strategy 4: Import/reference analysis
        reference_tests = self._find_by_references(changed_file, changed_symbol)
        tests.extend(reference_tests)
        
        # Remove duplicates and sort by confidence
        seen = set()
        unique_tests = []
        for test in tests:
            if test not in seen:
                seen.add(test)
                unique_tests.append(test)
        
        return unique_tests
    
    def _find_by_naming_convention(self, symbol_name: str) -> List[str]:
        """Find tests by naming convention (Foo -> FooTest, test_foo)."""
        tests = []
        
        # Common patterns
        patterns = [
            f"{symbol_name}Test",
            f"Test{symbol_name}",
            f"test_{symbol_name.lower()}",
            f"{symbol_name.lower()}_test",
        ]
        
        for pattern in patterns:
            # Search in test directories
            for test_dir in self._get_test_directories():
                for ext in ['.py', '.js', '.ts', '.go', '.rs', '.java']:
                    candidate = test_dir / f"{pattern}{ext}"
                    if candidate.exists():
                        tests.append(str(candidate.relative_to(self.repo_root)))
        
        return tests
    
    def _find_adjacent_tests(self, changed_file: Path) -> List[str]:
        """Find tests in adjacent test directories."""
        tests = []
        
        # Check parent directories for test folders
        for parent in changed_file.parents:
            for test_dir_name in ['tests', 'test', '__tests__', 'spec']:
                test_dir = parent / test_dir_name
                if test_dir.exists() and test_dir.is_dir():
                    # Look for tests related to the file
                    file_stem = changed_file.stem
                    for test_file in test_dir.rglob(f"*{file_stem}*"):
                        if test_file.is_file():
                            tests.append(str(test_file.relative_to(self.repo_root)))
        
        return tests
    
    def _find_same_directory_tests(self, changed_file: Path) -> List[str]:
        """Find tests in the same directory."""
        tests = []
        
        file_stem = changed_file.stem
        for pattern in [f"*{file_stem}*test*", f"*test*{file_stem}*", f"*{file_stem}*spec*"]:
            for test_file in changed_file.parent.glob(pattern):
                if test_file.is_file():
                    tests.append(str(test_file.relative_to(self.repo_root)))
        
        return tests
    
    def _find_by_references(self, changed_file: Path, symbol: Optional[str] = None) -> List[str]:
        """Find tests that import/reference the changed file."""
        tests = []
        
        # Look for imports of this file
        rel_path = str(changed_file.relative_to(self.repo_root))
        module_path = rel_path.replace('/', '.').replace('.py', '')
        
        for test_dir in self._get_test_directories():
            for test_file in test_dir.rglob("*.py"):
                try:
                    content = test_file.read_text()
                    # Simple import check
                    if module_path in content or changed_file.stem in content:
                        tests.append(str(test_file.relative_to(self.repo_root)))
                except Exception:
                    pass
        
        return tests
    
    def _get_test_directories(self) -> List[Path]:
        """Find all test directories in the repository."""
        test_dirs = []
        
        for root, dirs, _ in self.repo_root.walk():
            for test_dir_name in ['tests', 'test', '__tests__', 'spec', 'e2e']:
                if test_dir_name in dirs:
                    test_dirs.append(root / test_dir_name)
        
        return test_dirs


class APIBoundaryDetector:
    """Detects API boundaries and public surface area."""
    
    def __init__(self, repo_root: Path):
        self.repo_root = repo_root
    
    def analyze_risk(self, changed_file: Path, changed_symbols: List[ChangedSymbol]) -> Tuple[str, List[str]]:
        """
        Analyze API risk level for changes.
        
        Returns:
            Tuple of (risk_level, reasons)
        """
        reasons = []
        
        # Check if file is part of public API
        if self._is_public_api_file(changed_file):
            reasons.append(f"File {changed_file} is part of public API")
        
        # Check for exported symbols
        for sym in changed_symbols:
            if self._is_exported_symbol(sym):
                reasons.append(f"Symbol `{sym.name}` is publicly exported")
            
            if sym.kind in ('class', 'interface', 'function'):
                if self._is_public_class_or_interface(sym):
                    reasons.append(f"`{sym.name}` is a public {sym.kind}")
        
        # Check for CLI/API endpoints
        if self._is_endpoint_or_cli_command(changed_file, changed_symbols):
            reasons.append("Changes affect CLI commands or API endpoints")
        
        # Determine risk level
        if len(reasons) >= 3:
            return "high", reasons
        elif len(reasons) >= 1:
            return "medium", reasons
        else:
            return "low", reasons
    
    def _is_public_api_file(self, file: Path) -> bool:
        """Check if file is part of public API."""
        # Common public API patterns
        public_patterns = [
            '/api/',
            '/public/',
            '/exports/',
            '__init__.py',  # Python module exports
            'index.ts', 'index.js',  # JS/TS barrel exports
            'lib.rs',  # Rust library root
        ]
        
        file_str = str(file)
        return any(pattern in file_str for pattern in public_patterns)
    
    def _is_exported_symbol(self, sym: ChangedSymbol) -> bool:
        """Check if symbol is exported/public."""
        # Check for export keywords in common languages
        file_path = self.repo_root / sym.file
        
        try:
            with open(file_path, 'r') as f:
                lines = f.readlines()
                if 0 <= sym.line_start - 1 < len(lines):
                    line = lines[sym.line_start - 1]
                    
                    # Python
                    if sym.file.endswith('.py'):
                        # Check __all__ or lack of underscore prefix
                        if not sym.name.startswith('_'):
                            return True
                    
                    # JavaScript/TypeScript
                    elif sym.file.endswith(('.js', '.ts', '.jsx', '.tsx')):
                        if 'export ' in line or 'export default' in line:
                            return True
                    
                    # Go
                    elif sym.file.endswith('.go'):
                        if sym.name[0].isupper():  # Exported if capitalized
                            return True
                    
                    # Rust
                    elif sym.file.endswith('.rs'):
                        if 'pub ' in line:
                            return True
        
        except Exception:
            pass
        
        return False
    
    def _is_public_class_or_interface(self, sym: ChangedSymbol) -> bool:
        """Check if class/interface is public."""
        return sym.kind in ('class', 'interface') and self._is_exported_symbol(sym)
    
    def _is_endpoint_or_cli_command(self, file: Path, symbols: List[ChangedSymbol]) -> bool:
        """Check if changes affect endpoints or CLI commands."""
        file_str = str(file)
        
        # API endpoint patterns
        endpoint_patterns = [
            'routes', 'endpoints', 'handlers', 'controllers',
            'views.py', 'urls.py',  # Django/Flask
            'router', 'endpoint',  # Express/FastAPI
        ]
        
        for pattern in endpoint_patterns:
            if pattern in file_str:
                return True
        
        # CLI command patterns
        cli_patterns = [
            'cli/', 'commands/', 'cmd/',
            '@click', '@typer',  # Python CLI decorators
            'command', 'subcommand',
        ]
        
        for pattern in cli_patterns:
            if pattern in file_str:
                return True
        
        return False


class ImpactAnalyzer:
    """Main impact analysis orchestrator."""
    
    def __init__(self, repo_root: Path, verbose: bool = False):
        self.repo_root = Path(repo_root)
        self.verbose = verbose
        self.git_parser = GitDiffParser(repo_root)
        self.test_selector = TestSelector(repo_root)
        self.api_detector = APIBoundaryDetector(repo_root)
    
    def _log(self, message: str) -> None:
        if self.verbose:
            print(f"[ImpactAnalyzer] {message}")
    
    def get_changed_files_from_git(self, ref_range: str) -> List[Path]:
        """Get changed files from git diff."""
        return self.git_parser.get_changed_files(ref_range)
    
    def analyze(self, changed_files: List[Path], include_tests: bool = True) -> ImpactResult:
        """
        Perform full impact analysis.
        
        Args:
            changed_files: List of files that were changed
            include_tests: Whether to include test impact analysis
            
        Returns:
            ImpactResult with full analysis
        """
        result = ImpactResult()
        result.changed_files = [str(f.relative_to(self.repo_root)) for f in changed_files]
        
        self._log(f"Analyzing impact of {len(changed_files)} changed files")
        
        # 1. Identify changed symbols
        for file in changed_files:
            symbols = self._identify_changed_symbols(file)
            result.changed_symbols.extend(symbols)
        
        # 2. Compute blast radius
        blast_radius = self._compute_blast_radius(result.changed_symbols)
        result.affected_files = list(set(blast_radius['files']))
        result.affected_symbols = list(set(blast_radius['symbols']))
        result.blast_radius = len(result.affected_symbols)
        
        # 3. Detect API boundaries and risk
        all_symbols = result.changed_symbols
        for file in changed_files:
            risk_level, reasons = self.api_detector.analyze_risk(file, all_symbols)
            if risk_level != "low":
                result.api_risk_level = risk_level
                result.api_risk_reasons.extend(reasons)
        
        # 4. Select affected tests
        if include_tests:
            for file in changed_files:
                tests = self.test_selector.find_related_tests(file)
                result.affected_tests.extend(tests)
            
            # Also check affected symbols for tests
            for sym in result.changed_symbols:
                file_path = self.repo_root / sym.file
                tests = self.test_selector.find_related_tests(file_path, sym.name)
                result.affected_tests.extend(tests)
            
            result.affected_tests = list(set(result.affected_tests))
        
        # 5. Build inspection queue
        result.inspection_queue = self._build_inspection_queue(result)
        
        self._log(f"Analysis complete: {result.blast_radius} symbols affected, {len(result.affected_tests)} tests")
        
        return result
    
    def _identify_changed_symbols(self, file: Path) -> List[ChangedSymbol]:
        """Identify which symbols were changed in a file."""
        symbols = []
        
        # Try to parse the file to get symbols
        try:
            from scripts.lib.parser import TreeSitterParser
            parser = TreeSitterParser(None)
            
            result = parser.parse_file(file)
            if result and result.symbols:
                for sym in result.symbols:
                    symbols.append(ChangedSymbol(
                        name=sym.name,
                        file=str(file.relative_to(self.repo_root)),
                        kind=sym.kind,
                        line_start=sym.line_start,
                        line_end=sym.line_end or sym.line_start,
                        change_type='modified'
                    ))
        
        except Exception as e:
            self._log(f"Error parsing {file}: {e}")
            # Fallback: add file-level symbol
            symbols.append(ChangedSymbol(
                name=file.stem,
                file=str(file.relative_to(self.repo_root)),
                kind='file',
                line_start=1,
                line_end=1,
                change_type='modified'
            ))
        
        return symbols
    
    def _compute_blast_radius(self, changed_symbols: List[ChangedSymbol]) -> Dict[str, List[str]]:
        """Compute blast radius - what else is affected by these changes."""
        affected_files = []
        affected_symbols = []
        
        # Use database to find references
        try:
            from scripts.lib.db import Database, get_db_path
            
            db_path = get_db_path(self.repo_root)
            db = Database(db_path)
            db.connect()
            
            try:
                for sym in changed_symbols:
                    # Find symbols that reference this one
                    # This is a simplified approach - would need proper symbol ID lookup
                    symbol_name = sym.name
                    
                    # Search for references in DB
                    try:
                        results = db.search_symbols(symbol_name, limit=50)
                        for r in results:
                            if r['name'] != symbol_name:  # Exclude self
                                affected_symbols.append(r['name'])
                                # Get file path
                                file_record = db.get_file_by_id(r.get('file_id', 0))
                                if file_record:
                                    affected_files.append(file_record['path'])
                    except Exception as e:
                        self._log(f"Error searching for {symbol_name}: {e}")
            
            finally:
                db.close()
        
        except Exception as e:
            self._log(f"Error computing blast radius: {e}")
        
        return {
            'files': affected_files,
            'symbols': affected_symbols
        }
    
    def _build_inspection_queue(self, result: ImpactResult) -> List[Dict[str, Any]]:
        """Build prioritized inspection queue."""
        queue = []
        
        # Priority 1: Public API changes
        if result.api_risk_level in ('high', 'medium'):
            for sym in result.changed_symbols:
                if any(sym.name in reason for reason in result.api_risk_reasons):
                    queue.append({
                        'symbol': sym.name,
                        'file': sym.file,
                        'priority': 1,
                        'reason': 'Public API change'
                    })
        
        # Priority 2: High reference count
        for sym in result.changed_symbols:
            queue.append({
                'symbol': sym.name,
                'file': sym.file,
                'priority': 2,
                'reason': 'Changed symbol with unknown impact'
            })
        
        # Priority 3: Affected symbols
        for sym_name in result.affected_symbols[:20]:
            queue.append({
                'symbol': sym_name,
                'file': 'unknown',
                'priority': 3,
                'reason': 'Referenced by changed code'
            })
        
        # Sort by priority
        queue.sort(key=lambda x: x['priority'])
        
        return queue
