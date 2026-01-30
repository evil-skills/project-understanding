"""
Graph Query API for Project Understanding.

Provides graph traversal and impact analysis capabilities:
- Query callers (upstream dependencies)
- Query callees (downstream dependencies)
- Impact analysis for change propagation

Features:
- Cycle detection to avoid infinite loops
- Stable ordering of results
- Confidence aggregation for uncertain edges
- BFS traversal with configurable depth
"""

from typing import List, Dict, Any, Optional, Set, Tuple, Union
from pathlib import Path
from dataclasses import dataclass, field
from collections import deque, defaultdict
import json

from scripts.lib.db import Database, get_db_path


@dataclass
class GraphNode:
    """Represents a node in the dependency graph."""
    symbol_id: int
    name: str
    kind: str
    file_path: str
    line_start: int
    confidence: float = 1.0
    path_depth: int = 0  # Distance from start node
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            'symbol_id': self.symbol_id,
            'name': self.name,
            'kind': self.kind,
            'file_path': self.file_path,
            'line_start': self.line_start,
            'confidence': round(self.confidence, 3),
            'depth': self.path_depth
        }


@dataclass
class GraphEdge:
    """Represents an edge in the dependency graph."""
    source_id: int
    target_id: int
    kind: str
    confidence: float
    metadata: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            'source_id': self.source_id,
            'target_id': self.target_id,
            'kind': self.kind,
            'confidence': round(self.confidence, 3),
            'metadata': self.metadata
        }


@dataclass
class ImpactResult:
    """Result of impact analysis."""
    affected_symbols: List[GraphNode] = field(default_factory=list)
    affected_files: List[str] = field(default_factory=list)
    affected_tests: List[str] = field(default_factory=list)
    ranked_inspection: List[Dict[str, Any]] = field(default_factory=list)
    total_fan_in: Dict[int, int] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            'affected_symbols': [s.to_dict() for s in self.affected_symbols],
            'affected_files': self.affected_files,
            'affected_tests': self.affected_tests,
            'ranked_inspection': self.ranked_inspection,
            'summary': {
                'symbol_count': len(self.affected_symbols),
                'file_count': len(self.affected_files),
                'test_count': len(self.affected_tests)
            }
        }


class GraphEngine:
    """
    Graph traversal engine for dependency queries.
    
    Provides efficient BFS traversal with cycle detection,
    confidence scoring, and stable result ordering.
    """
    
    def __init__(self, db: Database):
        """
        Initialize graph engine.
        
        Args:
            db: Connected database instance
        """
        self.db = db
        self._symbol_cache: Dict[int, Dict[str, Any]] = {}
        self._file_cache: Dict[int, str] = {}
    
    def _get_symbol(self, symbol_id: int) -> Optional[Dict[str, Any]]:
        """Get symbol info with caching."""
        if symbol_id not in self._symbol_cache:
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
            self._symbol_cache[symbol_id] = dict(row) if row else None
        return self._symbol_cache[symbol_id]
    
    def _get_file_path(self, file_id: int) -> Optional[str]:
        """Get file path with caching."""
        if file_id not in self._file_cache:
            cursor = self.db._conn.execute(
                "SELECT path FROM files WHERE id = ?",
                (file_id,)
            )
            row = cursor.fetchone()
            self._file_cache[file_id] = row[0] if row else None
        return self._file_cache[file_id]
    
    def callers(self, symbol_id: Union[int, str], depth: int = 1, 
                min_conf: float = 0.0) -> List[GraphNode]:
        """
        Get symbols that call/depend on the given symbol (upstream).
        
        Traverses incoming edges (CALLS, IMPORTS) to find symbols
        that reference the target symbol.
        
        Args:
            symbol_id: Symbol ID to query (int) or qualified name (str)
            depth: Maximum traversal depth (default 1 = direct callers)
            min_conf: Minimum confidence threshold for edges
        
        Returns:
            List of GraphNode objects representing callers, sorted by
            confidence (descending) and then by name
        
        Example:
            >>> graph.callers(42, depth=2)
            [GraphNode(symbol_id=10, name="main", ...), ...]
        """
        # Resolve symbol_id if string
        if isinstance(symbol_id, str):
            symbol_id = self._resolve_symbol(symbol_id)
            if symbol_id is None:
                return []
        
        results: Dict[int, GraphNode] = {}
        
        # BFS traversal - track (node_id, depth, confidence, path)
        queue: deque[Tuple[int, int, float]] = deque([(symbol_id, 0, 1.0)])
        
        while queue:
            current_id, current_depth, current_conf = queue.popleft()
            
            if current_depth >= depth:
                continue
            
            # Get incoming edges (callers)
            edges = self.db.get_incoming_edges(current_id)
            
            for edge in edges:
                caller_id = edge['source_id']
                
                # Skip the original target to avoid self-reference in cycles
                if caller_id == symbol_id:
                    continue
                
                # Skip if already processed with higher or equal confidence
                if caller_id in results:
                    continue
                
                # Parse metadata for confidence
                edge_conf = self._extract_confidence(edge)
                aggregated_conf = current_conf * edge_conf
                
                # Skip if below confidence threshold
                if aggregated_conf < min_conf:
                    continue
                
                # Get symbol info
                symbol = self._get_symbol(caller_id)
                if symbol:
                    node = GraphNode(
                        symbol_id=caller_id,
                        name=symbol['name'],
                        kind=symbol['kind'],
                        file_path=symbol.get('file_path', 'unknown'),
                        line_start=symbol['line_start'],
                        confidence=aggregated_conf,
                        path_depth=current_depth + 1
                    )
                    
                    results[caller_id] = node
                    
                    # Continue traversal
                    queue.append((caller_id, current_depth + 1, aggregated_conf))
        
        # Sort results: by confidence desc, then by name
        sorted_results = sorted(
            results.values(),
            key=lambda n: (-n.confidence, n.name)
        )
        
        return sorted_results
    
    def callees(self, symbol_id: Union[int, str], depth: int = 1,
                min_conf: float = 0.0) -> List[GraphNode]:
        """
        Get symbols that are called/depended on by the given symbol (downstream).
        
        Traverses outgoing edges (CALLS, IMPORTS) to find symbols
        that are referenced by the source symbol.
        
        Args:
            symbol_id: Symbol ID to query (int) or qualified name (str)
            depth: Maximum traversal depth (default 1 = direct callees)
            min_conf: Minimum confidence threshold for edges
        
        Returns:
            List of GraphNode objects representing callees, sorted by
            confidence (descending) and then by name
        
        Example:
            >>> graph.callees(42, depth=2)
            [GraphNode(symbol_id=15, name="helper_func", ...), ...]
        """
        # Resolve symbol_id if string
        if isinstance(symbol_id, str):
            symbol_id = self._resolve_symbol(symbol_id)
            if symbol_id is None:
                return []
        
        results: Dict[int, GraphNode] = {}
        
        # BFS traversal
        queue: deque[Tuple[int, int, float]] = deque([(symbol_id, 0, 1.0)])
        
        while queue:
            current_id, current_depth, current_conf = queue.popleft()
            
            if current_depth >= depth:
                continue
            
            # Get outgoing edges (callees)
            edges = self.db.get_outgoing_edges(current_id)
            
            for edge in edges:
                callee_id = edge['target_id']
                
                # Skip the original target to avoid self-reference in cycles
                if callee_id == symbol_id:
                    continue
                
                # Skip if already processed
                if callee_id in results:
                    continue
                
                # Parse metadata for confidence
                edge_conf = self._extract_confidence(edge)
                aggregated_conf = current_conf * edge_conf
                
                # Skip if below confidence threshold
                if aggregated_conf < min_conf:
                    continue
                
                # Get symbol info
                symbol = self._get_symbol(callee_id)
                if symbol:
                    node = GraphNode(
                        symbol_id=callee_id,
                        name=symbol['name'],
                        kind=symbol['kind'],
                        file_path=symbol.get('file_path', 'unknown'),
                        line_start=symbol['line_start'],
                        confidence=aggregated_conf,
                        path_depth=current_depth + 1
                    )
                    
                    results[callee_id] = node
                    
                    # Continue traversal
                    queue.append((callee_id, current_depth + 1, aggregated_conf))
        
        # Sort results
        sorted_results = sorted(
            results.values(),
            key=lambda n: (-n.confidence, n.name)
        )
        
        return sorted_results
    
    def impact(self, targets: Union[List[int], List[str], int, str],
               depth: int = 2) -> ImpactResult:
        """
        Analyze impact of changes to given symbols or files.
        
        Traverses the dependency graph to find all symbols that could be
        affected by changes to the target symbols. Returns ranked results
        based on fan-in (number of upstream callers).
        
        Args:
            targets: Symbol IDs, symbol names, file paths, or mixed list
            depth: Maximum traversal depth for impact propagation (default 2)
        
        Returns:
            ImpactResult containing:
            - affected_symbols: All symbols reachable from targets
            - affected_files: Unique files containing affected symbols
            - affected_tests: Test files among affected files
            - ranked_inspection: Files ranked by importance for inspection
        
        Example:
            >>> graph.impact(["auth.login", "auth.logout"], depth=3)
            ImpactResult(affected_symbols=[...], affected_files=[...], ...)
        """
        result = ImpactResult()
        
        # Normalize targets to list
        if not isinstance(targets, list):
            targets = [targets]
        
        # Resolve all targets to symbol IDs
        start_ids: Set[int] = set()
        changed_files: Set[str] = set()
        
        for target in targets:
            if isinstance(target, int):
                start_ids.add(target)
                symbol = self._get_symbol(target)
                if symbol:
                    changed_files.add(symbol.get('file_path', 'unknown'))
            elif isinstance(target, str):
                # Could be symbol name or file path
                symbol_id = self._resolve_symbol(target)
                if symbol_id:
                    start_ids.add(symbol_id)
                    symbol = self._get_symbol(symbol_id)
                    if symbol:
                        changed_files.add(symbol.get('file_path', 'unknown'))
                elif '/' in target or '\\' in target or target.endswith('.py'):
                    # Looks like a file path
                    changed_files.add(target)
                    # Add all symbols from this file
                    file_symbols = self._get_symbols_in_file_by_path(target)
                    start_ids.update(file_symbols)
        
        if not start_ids:
            return result
        
        # Track all affected symbols with their fan-in
        affected_symbols: Dict[int, GraphNode] = {}
        fan_in_counts: Dict[int, int] = defaultdict(int)
        
        # Traverse from each starting symbol
        visited_global: Set[int] = set()
        
        for start_id in start_ids:
            # BFS for impact propagation
            queue: deque[Tuple[int, int]] = deque([(start_id, 0)])
            visited: Set[int] = {start_id}
            
            while queue:
                current_id, current_depth = queue.popleft()
                
                if current_depth >= depth:
                    continue
                
                # Get symbol info
                symbol = self._get_symbol(current_id)
                if not symbol:
                    continue
                
                # Track affected symbol
                if current_id not in affected_symbols:
                    affected_symbols[current_id] = GraphNode(
                        symbol_id=current_id,
                        name=symbol['name'],
                        kind=symbol['kind'],
                        file_path=symbol.get('file_path', 'unknown'),
                        line_start=symbol['line_start'],
                        path_depth=current_depth
                    )
                
                # Count fan-in (callers)
                callers = self.db.get_incoming_edges(current_id)
                fan_in_counts[current_id] = len(callers)
                
                # Propagate to callers (upstream impact)
                for edge in callers:
                    caller_id = edge['source_id']
                    if caller_id not in visited:
                        visited.add(caller_id)
                        queue.append((caller_id, current_depth + 1))
                        visited_global.add(caller_id)
        
        # Populate result
        result.affected_symbols = list(affected_symbols.values())
        result.total_fan_in = dict(fan_in_counts)
        
        # Collect affected files
        affected_files_set: Set[str] = set()
        for symbol in result.affected_symbols:
            affected_files_set.add(symbol.file_path)
        result.affected_files = sorted(affected_files_set)
        
        # Identify test files
        result.affected_tests = self._filter_test_files(result.affected_files)
        
        # Rank files for inspection
        result.ranked_inspection = self._rank_for_inspection(
            result.affected_files,
            result.affected_symbols,
            fan_in_counts,
            changed_files
        )
        
        return result
    
    def _resolve_symbol(self, qualified_name: str) -> Optional[int]:
        """Resolve a symbol name to its ID."""
        # Try exact match first
        cursor = self.db._conn.execute(
            "SELECT id FROM symbols WHERE name = ? LIMIT 1",
            (qualified_name,)
        )
        row = cursor.fetchone()
        if row:
            return row[0]
        
        # Try partial match (for qualified names)
        parts = qualified_name.split('.')
        if len(parts) > 1:
            cursor = self.db._conn.execute(
                "SELECT id FROM symbols WHERE name = ? LIMIT 1",
                (parts[-1],)
            )
            row = cursor.fetchone()
            if row:
                return row[0]
        
        return None
    
    def _get_symbols_in_file_by_path(self, file_path: str) -> List[int]:
        """Get all symbol IDs in a file by path."""
        cursor = self.db._conn.execute(
            """
            SELECT s.id
            FROM symbols s
            JOIN files f ON s.file_id = f.id
            WHERE f.path = ?
            """,
            (file_path,)
        )
        return [row[0] for row in cursor.fetchall()]
    
    def _extract_confidence(self, edge: Dict[str, Any]) -> float:
        """Extract confidence from edge metadata."""
        # Default confidence
        confidence = 0.8
        
        # Parse metadata JSON
        metadata = edge.get('metadata')
        if metadata:
            try:
                if isinstance(metadata, str):
                    metadata = json.loads(metadata)
                if isinstance(metadata, dict):
                    confidence = metadata.get('confidence', confidence)
            except (json.JSONDecodeError, TypeError):
                pass
        
        # Edge kind affects confidence
        kind = edge.get('kind', '')
        if kind == 'call':
            confidence = max(confidence, 0.9)  # Direct calls are high confidence
        elif kind == 'import':
            confidence = max(confidence, 0.85)
        
        return min(confidence, 1.0)
    
    def _filter_test_files(self, files: List[str]) -> List[str]:
        """Identify test files from a list of paths."""
        test_patterns = [
            'test_',
            '_test.',
            '_spec.',
            '.spec.',
            'tests/',
            '/tests/',
            '__tests__/',
            '/__tests__/',
        ]
        
        test_files = []
        for f in files:
            f_lower = f.lower()
            if any(pattern in f_lower for pattern in test_patterns):
                test_files.append(f)
        
        return sorted(test_files)
    
    def _rank_for_inspection(self, files: List[str],
                            symbols: List[GraphNode],
                            fan_in: Dict[int, int],
                            changed_files: Set[str]) -> List[Dict[str, Any]]:
        """
        Rank files by importance for inspection.
        
        Ranking heuristic:
        1. Primary: Number of upstream callers (fan-in)
        2. Secondary: Test proximity (test files ranked higher)
        3. Tertiary: File centrality (number of affected symbols)
        """
        # Build file-level metrics
        file_metrics: Dict[str, Dict[str, Any]] = {}
        
        for f in files:
            file_metrics[f] = {
                'path': f,
                'total_fan_in': 0,
                'symbol_count': 0,
                'is_test': False,
                'is_changed': f in changed_files
            }
        
        # Aggregate symbol-level metrics to file level
        for symbol in symbols:
            if symbol.file_path in file_metrics:
                file_metrics[symbol.file_path]['symbol_count'] += 1
                file_metrics[symbol.file_path]['total_fan_in'] += fan_in.get(symbol.symbol_id, 0)
        
        # Mark test files
        test_files = set(self._filter_test_files(files))
        for f in test_files:
            if f in file_metrics:
                file_metrics[f]['is_test'] = True
        
        # Calculate composite score
        scored_files = []
        for f, metrics in file_metrics.items():
            # Skip changed files (already known)
            if metrics['is_changed']:
                continue
            
            # Primary: fan-in (normalized, higher is better)
            fan_in_score = min(metrics['total_fan_in'] / 10.0, 1.0)
            
            # Secondary: test proximity (binary boost)
            test_score = 0.3 if metrics['is_test'] else 0.0
            
            # Tertiary: centrality
            centrality_score = min(metrics['symbol_count'] / 5.0, 1.0) * 0.2
            
            composite_score = fan_in_score + test_score + centrality_score
            
            scored_files.append({
                'path': f,
                'score': round(composite_score, 3),
                'fan_in': metrics['total_fan_in'],
                'symbol_count': metrics['symbol_count'],
                'is_test': metrics['is_test'],
                'reason': self._rank_reason(metrics['is_test'], fan_in_score)
            })
        
        # Sort by score descending
        scored_files.sort(key=lambda x: (-x['score'], x['path']))
        
        return scored_files
    
    def _rank_reason(self, is_test: bool, fan_in_score: float) -> str:
        """Generate human-readable ranking reason."""
        if is_test:
            return "test_file"
        elif fan_in_score > 0.7:
            return "high_fan_in"
        elif fan_in_score > 0.3:
            return "moderate_fan_in"
        else:
            return "low_fan_in"


def create_graph_engine(repo_root: Path) -> GraphEngine:
    """
    Create a graph engine for a repository.
    
    Args:
        repo_root: Path to repository root
    
    Returns:
        Connected GraphEngine instance
    
    Example:
        >>> graph = create_graph_engine(Path("/path/to/repo"))
        >>> callers = graph.callers("main")
    """
    db_path = get_db_path(repo_root)
    db = Database(db_path)
    db.connect()
    return GraphEngine(db)


# Convenience functions for standalone usage
def get_callers(symbol_id: Union[int, str], repo_root: Optional[Path] = None,
                depth: int = 1, min_conf: float = 0.0) -> List[GraphNode]:
    """
    Get callers for a symbol (standalone convenience function).
    
    Args:
        symbol_id: Symbol ID or qualified name
        repo_root: Repository root (uses current directory if None)
        depth: Traversal depth
        min_conf: Minimum confidence threshold
    
    Returns:
        List of GraphNode callers
    """
    if repo_root is None:
        repo_root = Path.cwd()
    
    engine = create_graph_engine(repo_root)
    try:
        return engine.callers(symbol_id, depth, min_conf)
    finally:
        engine.db.close()


def get_callees(symbol_id: Union[int, str], repo_root: Optional[Path] = None,
                depth: int = 1, min_conf: float = 0.0) -> List[GraphNode]:
    """
    Get callees for a symbol (standalone convenience function).
    
    Args:
        symbol_id: Symbol ID or qualified name
        repo_root: Repository root (uses current directory if None)
        depth: Traversal depth
        min_conf: Minimum confidence threshold
    
    Returns:
        List of GraphNode callees
    """
    if repo_root is None:
        repo_root = Path.cwd()
    
    engine = create_graph_engine(repo_root)
    try:
        return engine.callees(symbol_id, depth, min_conf)
    finally:
        engine.db.close()


def get_impact(targets: Union[List[int], List[str], int, str],
               repo_root: Optional[Path] = None,
               depth: int = 2) -> ImpactResult:
    """
    Get impact analysis (standalone convenience function).
    
    Args:
        targets: Symbol IDs, names, or file paths
        repo_root: Repository root (uses current directory if None)
        depth: Traversal depth
    
    Returns:
        ImpactResult with analysis
    """
    if repo_root is None:
        repo_root = Path.cwd()
    
    engine = create_graph_engine(repo_root)
    try:
        return engine.impact(targets, depth)
    finally:
        engine.db.close()
