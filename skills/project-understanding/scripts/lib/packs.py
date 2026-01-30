"""
Pack Generators for Project Understanding.

Provides three pack generation strategies:
1. RepoMapPack - High-level project overview
2. ZoomPack - Detailed view of specific symbol/region
3. ImpactPack - Change impact analysis

All generators enforce token budgets and provide structured output
suitable for LLM consumption.
"""

import os
import json
from typing import List, Dict, Any, Optional, Set, Tuple, Union
from pathlib import Path
from dataclasses import dataclass, field
from collections import defaultdict
import fnmatch

from scripts.lib.db import Database, get_db_path
from scripts.lib.tokens import (
    estimate_tokens, truncate_to_budget, calculate_budget_allocation
)
from scripts.lib.graph import GraphEngine, create_graph_engine


@dataclass
class PackSection:
    """A section within a pack."""
    title: str
    content: str
    priority: int = 0
    
    def token_count(self) -> int:
        """Estimate tokens in this section."""
        return estimate_tokens(self.content, is_code=True)
    
    def to_text(self) -> str:
        """Format as text."""
        return f"## {self.title}\n\n{self.content}"


@dataclass
class RepoMapPack:
    """Repository overview pack."""
    directory_tree: str
    top_files: List[Dict[str, Any]]
    file_symbols: Dict[str, List[Dict[str, Any]]]
    dependency_summary: Dict[str, Any]
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_text(self) -> str:
        """Convert to formatted text."""
        lines = [
            "# Repository Overview",
            "",
            "## Directory Structure",
            "",
            self.directory_tree,
            "",
            "## Top Files by Importance",
            ""
        ]
        
        for i, f in enumerate(self.top_files[:20], 1):
            lines.append(f"{i}. `{f['path']}` - {f.get('reason', 'N/A')}")
        
        lines.extend(["", "## Key Symbols by File", ""])
        
        for file_path, symbols in list(self.file_symbols.items())[:10]:
            lines.append(f"### {file_path}")
            for sym in symbols[:5]:
                sig = sym.get('signature', sym['name'])
                lines.append(f"- `{sig}` ({sym['kind']})")
            lines.append("")
        
        lines.extend(["## Dependency Summary", ""])
        lines.append(f"Total files: {self.dependency_summary.get('file_count', 0)}")
        lines.append(f"Total symbols: {self.dependency_summary.get('symbol_count', 0)}")
        lines.append(f"Total edges: {self.dependency_summary.get('edge_count', 0)}")
        
        return '\n'.join(lines)


@dataclass
class ZoomPack:
    """Detailed zoom pack for a specific symbol."""
    target_symbol: Dict[str, Any]
    code_slice: str
    signature: str
    docstring: Optional[str]
    callers: List[Dict[str, Any]]
    callees: List[Dict[str, Any]]
    file_context: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_text(self) -> str:
        """Convert to formatted text."""
        lines = [
            f"# Zoom: {self.target_symbol['name']}",
            "",
            f"**File:** `{self.target_symbol.get('file_path', 'unknown')}`",
            f"**Kind:** {self.target_symbol.get('kind', 'unknown')}",
            f"**Line:** {self.target_symbol.get('line_start', 0)}",
            "",
            "## Signature",
            "",
            "```",
            self.signature or self.target_symbol.get('name', 'unknown'),
            "```",
            ""
        ]
        
        if self.docstring:
            lines.extend([
                "## Documentation",
                "",
                self.docstring,
                ""
            ])
        
        lines.extend([
            "## Code",
            "",
            "```python",
            self.code_slice,
            "```",
            "",
            "## Callers",
            ""
        ])
        
        for caller in self.callers[:10]:
            lines.append(f"- `{caller['name']}` in `{caller['file_path']}` (confidence: {caller['confidence']})")
        
        if len(self.callers) > 10:
            lines.append(f"- ... and {len(self.callers) - 10} more")
        
        lines.extend(["", "## Callees", ""])
        
        for callee in self.callees[:10]:
            lines.append(f"- `{callee['name']}` in `{callee['file_path']}` (confidence: {callee['confidence']})")
        
        if len(self.callees) > 10:
            lines.append(f"- ... and {len(self.callees) - 10} more")
        
        return '\n'.join(lines)


@dataclass
class ImpactPack:
    """Change impact analysis pack."""
    changed_items: List[str]
    affected_symbols: List[Dict[str, Any]]
    affected_files: List[str]
    affected_tests: List[str]
    ranked_inspection: List[Dict[str, Any]]
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_text(self) -> str:
        """Convert to formatted text."""
        lines = [
            "# Impact Analysis",
            "",
            "## Changed Items",
            ""
        ]
        
        for item in self.changed_items:
            lines.append(f"- `{item}`")
        
        lines.extend(["", "## Affected Files", ""])
        lines.append(f"Total: {len(self.affected_files)}")
        lines.append("")
        
        for f in self.affected_files[:30]:
            lines.append(f"- `{f}`")
        
        if len(self.affected_files) > 30:
            lines.append(f"- ... and {len(self.affected_files) - 30} more")
        
        lines.extend(["", "## Affected Tests", ""])
        
        if self.affected_tests:
            for f in self.affected_tests[:20]:
                lines.append(f"- `{f}`")
            if len(self.affected_tests) > 20:
                lines.append(f"- ... and {len(self.affected_tests) - 20} more")
        else:
            lines.append("No affected tests found.")
        
        lines.extend(["", "## Recommended Inspection Order", ""])
        lines.append("Files ranked by importance (fan-in, test proximity, centrality):" )
        lines.append("")
        
        for i, item in enumerate(self.ranked_inspection[:20], 1):
            lines.append(
                f"{i}. `{item['path']}` "
                f"(score: {item['score']}, fan-in: {item['fan_in']}, "
                f"reason: {item['reason']})"
            )
        
        return '\n'.join(lines)


class PackGenerator:
    """Base class for pack generators."""
    
    def __init__(self, repo_root: Path, db: Optional[Database] = None):
        """
        Initialize pack generator.
        
        Args:
            repo_root: Repository root path
            db: Optional pre-connected database
        """
        self.repo_root = Path(repo_root)
        self.db = db
        self._db_owned = db is None
        self._graph: Optional[GraphEngine] = None
        
        if self.db is None:
            db_path = get_db_path(self.repo_root)
            self.db = Database(db_path)
            self.db.connect()
    
    @property
    def graph(self) -> GraphEngine:
        """Get or create graph engine."""
        if self._graph is None:
            self._graph = GraphEngine(self.db)
        return self._graph
    
    def close(self) -> None:
        """Close resources."""
        if self._db_owned and self.db:
            self.db.close()
            self.db = None
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()


class RepoMapPackGenerator(PackGenerator):
    """Generator for repository overview packs."""
    
    def generate(self, budget_tokens: int = 4000, focus: Optional[str] = None) -> RepoMapPack:
        """
        Generate a RepoMapPack.
        
        Creates a collapsed directory tree, lists top files by importance,
        shows key symbols per file, and provides a dependency summary.
        
        Args:
            budget_tokens: Maximum tokens for the pack
            focus: Optional subdirectory to focus on (prioritizes files under this path)
        
        Returns:
            RepoMapPack instance
        """
        # Get all files
        files = self.db.get_all_files()
        
        # Filter by focus if specified
        if focus:
            focus_path = focus.rstrip('/')
            files = [f for f in files if f['path'].startswith(focus_path)]
        
        # Build directory tree
        tree = self._build_directory_tree(files, max_depth=4)
        
        # Rank files by importance
        ranked_files = self._rank_files(files)
        
        # Get top symbols per file
        file_symbols = self._get_file_symbols(ranked_files[:20])
        
        # Get dependency summary
        summary = self._get_dependency_summary()
        
        # Create pack
        pack = RepoMapPack(
            directory_tree=tree,
            top_files=ranked_files,
            file_symbols=file_symbols,
            dependency_summary=summary
        )
        
        # Enforce budget
        text = pack.to_text()
        if estimate_tokens(text, is_code=True) > budget_tokens:
            pack = self._truncate_pack(pack, budget_tokens)
        
        return pack
    
    def _build_directory_tree(self, files: List[Dict[str, Any]], 
                              max_depth: int = 4) -> str:
        """Build a collapsed directory tree string."""
        if not files:
            return "(no files)"
        
        # Build tree structure
        tree: Dict[str, Any] = {}
        
        for f in files:
            parts = f['path'].split('/')
            current = tree
            for i, part in enumerate(parts[:max_depth]):
                if part not in current:
                    current[part] = {}
                current = current[part]
        
        # Format as tree
        lines = []
        
        def render(node: Dict[str, Any], prefix: str = "", is_last: bool = True):
            items = sorted(node.items())
            for i, (name, children) in enumerate(items):
                is_last_item = i == len(items) - 1
                connector = "└── " if is_last_item else "├── "
                lines.append(f"{prefix}{connector}{name}")
                
                if children:
                    extension = "    " if is_last_item else "│   "
                    render(children, prefix + extension, is_last_item)
        
        render(tree)
        return '\n'.join(lines) if lines else "(empty)"
    
    def _rank_files(self, files: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Rank files by importance."""
        scored = []
        
        for f in files:
            path = f['path']
            score = 0.0
            reasons = []
            
            # Symbol density
            symbols = self.db.get_symbols_in_file(f['id'])
            symbol_count = len(symbols)
            if symbol_count > 0:
                score += min(symbol_count / 10.0, 1.0) * 0.3
                reasons.append(f"{symbol_count} symbols")
            
            # Entry point indicators
            if path.endswith(('__init__.py', 'main.py', 'app.py', 'index.js')):
                score += 0.5
                reasons.append("entry point")
            
            # Core module indicators
            if any(indicator in path for indicator in ['core/', 'lib/', 'utils/', 'common/']):
                score += 0.2
                reasons.append("core module")
            
            # Configuration files
            if path.endswith(('.json', '.yaml', '.yml', '.toml')):
                score += 0.1
            
            scored.append({
                'path': path,
                'score': round(score, 3),
                'reason': ', '.join(reasons) if reasons else 'standard file',
                'symbol_count': symbol_count
            })
        
        scored.sort(key=lambda x: (-x['score'], x['path']))
        return scored
    
    def _get_file_symbols(self, files: List[Dict[str, Any]], 
                          max_symbols: int = 5) -> Dict[str, List[Dict[str, Any]]]:
        """Get top symbols for each file."""
        result = {}
        
        for f in files:
            file_record = self.db.get_file(f['path'])
            if not file_record:
                continue
            
            symbols = self.db.get_symbols_in_file(file_record['id'])
            
            # Prioritize important symbols
            prioritized = sorted(
                symbols,
                key=lambda s: (
                    0 if s['kind'] in ('class', 'function') else 1,
                    -len(s.get('signature') or '')
                )
            )
            
            result[f['path']] = [
                {
                    'name': s['name'],
                    'kind': s['kind'],
                    'signature': s.get('signature', s['name']),
                    'line': s['line_start']
                }
                for s in prioritized[:max_symbols]
            ]
        
        return result
    
    def _get_dependency_summary(self) -> Dict[str, Any]:
        """Get summary of dependencies in the codebase."""
        stats = self.db.get_stats()
        return {
            'file_count': stats.get('files', 0),
            'symbol_count': stats.get('symbols', 0),
            'edge_count': stats.get('edges', 0),
            'callsites': stats.get('callsites', 0)
        }
    
    def _truncate_pack(self, pack: RepoMapPack, budget_tokens: int) -> RepoMapPack:
        """Truncate pack to fit within budget."""
        # Reduce number of files shown
        while len(pack.top_files) > 5:
            pack.top_files = pack.top_files[:-1]
            pack.file_symbols = {k: v for k, v in pack.file_symbols.items() 
                               if k in [f['path'] for f in pack.top_files]}
            
            text = pack.to_text()
            if estimate_tokens(text, is_code=True) <= budget_tokens:
                break
        
        # Reduce symbols per file
        if estimate_tokens(pack.to_text(), is_code=True) > budget_tokens:
            for path in pack.file_symbols:
                while len(pack.file_symbols[path]) > 2:
                    pack.file_symbols[path] = pack.file_symbols[path][:-1]
                    if estimate_tokens(pack.to_text(), is_code=True) <= budget_tokens:
                        break
        
        return pack


class ZoomPackGenerator(PackGenerator):
    """Generator for zoom/detail packs."""
    
    def generate(self, target: str, budget_tokens: int = 4000) -> Optional[ZoomPack]:
        """
        Generate a ZoomPack for a specific symbol.
        
        Loads the code slice for the target symbol, includes signature
        and docstring, and attaches callers/callees with depth=1.
        
        Args:
            target: Symbol ID (int) or qualified name (str), or file:line format
            budget_tokens: Maximum tokens for the pack
        
        Returns:
            ZoomPack instance or None if symbol not found
        """
        # Resolve target
        symbol, file_path = self._resolve_target(target)
        if not symbol:
            return None
        
        # Load code slice
        code_slice = self._load_code_slice(file_path, symbol)
        
        # Get callers and callees
        callers = self.graph.callers(symbol['id'], depth=1)
        callees = self.graph.callees(symbol['id'], depth=1)
        
        # Get file context (skeleton of surrounding code)
        file_context = self._get_file_context(file_path, symbol)
        
        # Create pack
        pack = ZoomPack(
            target_symbol=symbol,
            code_slice=code_slice,
            signature=symbol.get('signature', symbol['name']),
            docstring=symbol.get('docstring'),
            callers=[c.to_dict() for c in callers],
            callees=[c.to_dict() for c in callees],
            file_context=file_context
        )
        
        # Enforce budget
        text = pack.to_text()
        estimated = estimate_tokens(text, is_code=True)
        if estimated > budget_tokens:
            pack = self._truncate_pack(pack, budget_tokens)
        
        return pack
    
    def _resolve_target(self, target: str) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
        """Resolve target to symbol and file path."""
        # Try as integer ID first
        try:
            symbol_id = int(target)
            cursor = self.db._conn.execute(
                """
                SELECT s.*, f.path as file_path
                FROM symbols s
                JOIN files f ON s.file_id = f.id
                WHERE s.id = ?
                """,
                (symbol_id,)
            )
            row = cursor.fetchone()
            if row:
                symbol = dict(row)
                symbol['id'] = symbol_id
                return symbol, symbol.get('file_path')
        except ValueError:
            pass
        
        # Try as file:line format
        if ':' in target:
            parts = target.rsplit(':', 1)
            if len(parts) == 2:
                file_path, line_str = parts
                try:
                    line = int(line_str)
                    cursor = self.db._conn.execute(
                        """
                        SELECT s.*, f.path as file_path
                        FROM symbols s
                        JOIN files f ON s.file_id = f.id
                        WHERE f.path = ? AND s.line_start <= ? AND (s.line_end >= ? OR s.line_end IS NULL)
                        ORDER BY s.line_start DESC
                        LIMIT 1
                        """,
                        (file_path, line, line)
                    )
                    row = cursor.fetchone()
                    if row:
                        symbol = dict(row)
                        return symbol, file_path
                except ValueError:
                    pass
        
        # Try as symbol name
        cursor = self.db._conn.execute(
            """
            SELECT s.*, f.path as file_path
            FROM symbols s
            JOIN files f ON s.file_id = f.id
            WHERE s.name = ?
            LIMIT 1
            """,
            (target,)
        )
        row = cursor.fetchone()
        if row:
            symbol = dict(row)
            return symbol, symbol.get('file_path')
        
        return None, None
    
    def _load_code_slice(self, file_path: str, symbol: Dict[str, Any]) -> str:
        """Load code slice for a symbol."""
        full_path = self.repo_root / file_path
        
        if not full_path.exists():
            return f"# File not found: {file_path}"
        
        try:
            content = full_path.read_text(encoding='utf-8')
            lines = content.split('\n')
            
            line_start = symbol.get('line_start', 1) - 1  # 0-indexed
            line_end = symbol.get('line_end', line_start + 1)
            
            # Include some context
            context_start = max(0, line_start - 2)
            context_end = min(len(lines), line_end + 2)
            
            slice_lines = lines[context_start:context_end]
            return '\n'.join(slice_lines)
        except Exception as e:
            return f"# Error loading code: {e}"
    
    def _get_file_context(self, file_path: str, 
                          target_symbol: Dict[str, Any]) -> str:
        """Get skeleton context of the file."""
        file_record = self.db.get_file(file_path)
        if not file_record:
            return ""
        
        symbols = self.db.get_symbols_in_file(file_record['id'])
        
        # Filter to major symbols (not the target)
        context_symbols = [
            s for s in symbols
            if s['id'] != target_symbol.get('id') and s['kind'] in ('class', 'function', 'method')
        ]
        
        # Sort by line
        context_symbols.sort(key=lambda s: s['line_start'])
        
        # Build skeleton
        lines = []
        for s in context_symbols[:10]:  # Limit to top 10
            sig = s.get('signature', s['name'])
            lines.append(f"Line {s['line_start']}: {sig}")
        
        return '\n'.join(lines) if lines else "(no other major symbols)"
    
    def _truncate_pack(self, pack: ZoomPack, budget_tokens: int) -> ZoomPack:
        """Truncate pack to fit within budget."""
        # First, reduce code slice
        max_code_lines = 50
        code_lines = pack.code_slice.split('\n')
        
        while len(code_lines) > max_code_lines:
            code_lines = code_lines[:max_code_lines]
            pack.code_slice = '\n'.join(code_lines) + "\n# ... truncated"
            
            if estimate_tokens(pack.to_text(), is_code=True) <= budget_tokens:
                return pack
            
            max_code_lines -= 10
        
        # Reduce callers/callees
        while len(pack.callers) > 3:
            pack.callers = pack.callers[:-1]
            if estimate_tokens(pack.to_text(), is_code=True) <= budget_tokens:
                return pack
        
        while len(pack.callees) > 3:
            pack.callees = pack.callees[:-1]
            if estimate_tokens(pack.to_text(), is_code=True) <= budget_tokens:
                return pack
        
        # Remove docstring if still over budget
        if estimate_tokens(pack.to_text(), is_code=True) > budget_tokens:
            pack.docstring = None
        
        return pack


class ImpactPackGenerator(PackGenerator):
    """Generator for impact analysis packs."""
    
    def generate(self, targets: Union[str, List[str]], 
                 depth: int = 2, budget_tokens: int = 4000) -> ImpactPack:
        """
        Generate an ImpactPack for changed symbols/files.
        
        Identifies changed symbols, traverses the dependency graph to find
        affected code, lists affected tests, and ranks files for inspection.
        
        Args:
            targets: Changed symbol IDs, names, or file paths (or list thereof)
            depth: Traversal depth for impact propagation
            budget_tokens: Maximum tokens for the pack
        
        Returns:
            ImpactPack instance
        """
        # Normalize targets
        if isinstance(targets, str):
            targets = [targets]
        
        # Run impact analysis
        impact_result = self.graph.impact(targets, depth=depth)
        
        # Create pack
        pack = ImpactPack(
            changed_items=targets,
            affected_symbols=[s.to_dict() for s in impact_result.affected_symbols],
            affected_files=impact_result.affected_files,
            affected_tests=impact_result.affected_tests,
            ranked_inspection=impact_result.ranked_inspection
        )
        
        # Enforce budget
        text = pack.to_text()
        if estimate_tokens(text, is_code=True) > budget_tokens:
            pack = self._truncate_pack(pack, budget_tokens)
        
        return pack
    
    def _truncate_pack(self, pack: ImpactPack, budget_tokens: int) -> ImpactPack:
        """Truncate pack to fit within budget."""
        # Reduce affected symbols
        while len(pack.affected_symbols) > 20:
            pack.affected_symbols = pack.affected_symbols[:-1]
            if estimate_tokens(pack.to_text(), is_code=True) <= budget_tokens:
                return pack
        
        # Reduce affected files
        while len(pack.affected_files) > 15:
            pack.affected_files = pack.affected_files[:-1]
            if estimate_tokens(pack.to_text(), is_code=True) <= budget_tokens:
                return pack
        
        # Reduce ranked inspection
        while len(pack.ranked_inspection) > 10:
            pack.ranked_inspection = pack.ranked_inspection[:-1]
            if estimate_tokens(pack.to_text(), is_code=True) <= budget_tokens:
                return pack
        
        return pack


# Convenience functions
def repomap(repo_root: Optional[Path] = None, budget_tokens: int = 4000,
            focus: Optional[str] = None) -> str:
    """
    Generate a RepoMapPack as text.
    
    Args:
        repo_root: Repository root (uses current directory if None)
        budget_tokens: Maximum tokens
        focus: Optional subdirectory to focus on
    
    Returns:
        Formatted text representation
    """
    if repo_root is None:
        repo_root = Path.cwd()
    
    with RepoMapPackGenerator(repo_root) as gen:
        pack = gen.generate(budget_tokens=budget_tokens, focus=focus)
        return pack.to_text()


def zoom(target: str, repo_root: Optional[Path] = None, 
         budget_tokens: int = 4000) -> str:
    """
    Generate a ZoomPack as text.
    
    Args:
        target: Symbol ID, name, or file:line
        repo_root: Repository root (uses current directory if None)
        budget_tokens: Maximum tokens
    
    Returns:
        Formatted text representation
    """
    if repo_root is None:
        repo_root = Path.cwd()
    
    with ZoomPackGenerator(repo_root) as gen:
        pack = gen.generate(target, budget_tokens=budget_tokens)
        if pack is None:
            return f"# Error\n\nSymbol not found: {target}"
        return pack.to_text()


def impact(targets: Union[str, List[str]], repo_root: Optional[Path] = None,
           depth: int = 2, budget_tokens: int = 4000) -> str:
    """
    Generate an ImpactPack as text.
    
    Args:
        targets: Changed symbol(s) or file(s)
        repo_root: Repository root (uses current directory if None)
        depth: Traversal depth for impact analysis
        budget_tokens: Maximum tokens
    
    Returns:
        Formatted text representation
    """
    if repo_root is None:
        repo_root = Path.cwd()
    
    with ImpactPackGenerator(repo_root) as gen:
        pack = gen.generate(targets, depth=depth, budget_tokens=budget_tokens)
        return pack.to_text()
