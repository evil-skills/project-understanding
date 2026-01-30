"""
Multi-repository federation for workspace-wide analysis.

Provides:
- Workspace configuration management
- Unified graph view across repositories
- Cross-repo dependency analysis
"""

import json
from typing import List, Dict, Any, Optional, Set
from pathlib import Path
from dataclasses import dataclass, field, asdict
import sqlite3


@dataclass
class RepoConfig:
    """Configuration for a single repository in the workspace."""
    path: str
    name: str
    enabled: bool = True
    exclude_patterns: List[str] = field(default_factory=list)
    priority: int = 0  # Higher = more important
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'path': self.path,
            'name': self.name,
            'enabled': self.enabled,
            'exclude_patterns': self.exclude_patterns,
            'priority': self.priority
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'RepoConfig':
        return cls(**data)


@dataclass
class WorkspaceConfig:
    """Configuration for a multi-repository workspace."""
    name: str
    repos: List[RepoConfig] = field(default_factory=list)
    unified_graph: bool = True
    cross_repo_analysis: bool = True
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'name': self.name,
            'repos': [r.to_dict() for r in self.repos],
            'unified_graph': self.unified_graph,
            'cross_repo_analysis': self.cross_repo_analysis
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'WorkspaceConfig':
        repos = [RepoConfig.from_dict(r) for r in data.get('repos', [])]
        return cls(
            name=data['name'],
            repos=repos,
            unified_graph=data.get('unified_graph', True),
            cross_repo_analysis=data.get('cross_repo_analysis', True)
        )
    
    def save(self, path: Path):
        """Save workspace configuration to file."""
        path.write_text(json.dumps(self.to_dict(), indent=2))
    
    @classmethod
    def load(cls, path: Path) -> 'WorkspaceConfig':
        """Load workspace configuration from file."""
        data = json.loads(path.read_text())
        return cls.from_dict(data)


@dataclass
class CrossRepoEdge:
    """Represents a dependency edge between repositories."""
    source_repo: str
    source_symbol: str
    target_repo: str
    target_symbol: str
    edge_type: str
    confidence: float
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'source_repo': self.source_repo,
            'source_symbol': self.source_symbol,
            'target_repo': self.target_repo,
            'target_symbol': self.target_symbol,
            'edge_type': self.edge_type,
            'confidence': round(self.confidence, 2)
        }


@dataclass
class UnifiedGraph:
    """Unified graph view across multiple repositories."""
    repos: List[str] = field(default_factory=list)
    total_symbols: int = 0
    total_edges: int = 0
    cross_repo_edges: List[CrossRepoEdge] = field(default_factory=list)
    repo_summaries: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'repos': self.repos,
            'total_symbols': self.total_symbols,
            'total_edges': self.total_edges,
            'cross_repo_edges': [e.to_dict() for e in self.cross_repo_edges],
            'repo_summaries': self.repo_summaries
        }
    
    def to_text(self) -> str:
        """Format as readable text."""
        lines = [
            "# Unified Workspace Graph",
            "",
            f"**Repositories**: {len(self.repos)}",
            f"**Total Symbols**: {self.total_symbols}",
            f"**Total Edges**: {self.total_edges}",
            f"**Cross-Repo Dependencies**: {len(self.cross_repo_edges)}",
            ""
        ]
        
        if self.repos:
            lines.append("## Repositories")
            lines.append("")
            for repo_name in self.repos:
                summary = self.repo_summaries.get(repo_name, {})
                symbols = summary.get('symbol_count', 0)
                edges = summary.get('edge_count', 0)
                lines.append(f"- **{repo_name}**: {symbols} symbols, {edges} edges")
            lines.append("")
        
        if self.cross_repo_edges:
            lines.append("## Cross-Repository Dependencies")
            lines.append("")
            for edge in self.cross_repo_edges[:20]:  # Limit output
                lines.append(
                    f"- `{edge.source_repo}.{edge.source_symbol}` → "
                    f"`{edge.target_repo}.{edge.target_symbol}` ({edge.edge_type})"
                )
            lines.append("")
        
        return '\n'.join(lines)


class WorkspaceManager:
    """Manages multi-repository workspaces."""
    
    def __init__(self, config_path: Optional[Path] = None):
        self.config_path = config_path
        self.config: Optional[WorkspaceConfig] = None
        
        if config_path and config_path.exists():
            self.config = WorkspaceConfig.load(config_path)
    
    def create_workspace(self, name: str, repo_paths: List[Path]) -> WorkspaceConfig:
        """Create a new workspace from repository paths."""
        repos = []
        for i, path in enumerate(repo_paths):
            if path.exists():
                repos.append(RepoConfig(
                    path=str(path.resolve()),
                    name=path.name or f"repo_{i}",
                    priority=len(repo_paths) - i
                ))
        
        self.config = WorkspaceConfig(name=name, repos=repos)
        return self.config
    
    def add_repo(self, repo_path: Path, name: Optional[str] = None):
        """Add a repository to the workspace."""
        if self.config is None:
            raise ValueError("No workspace configured")
        
        repo = RepoConfig(
            path=str(repo_path.resolve()),
            name=name or repo_path.name,
            priority=len(self.config.repos)
        )
        self.config.repos.append(repo)
    
    def remove_repo(self, name: str):
        """Remove a repository from the workspace."""
        if self.config is None:
            raise ValueError("No workspace configured")
        
        self.config.repos = [r for r in self.config.repos if r.name != name]
    
    def save(self):
        """Save workspace configuration."""
        if self.config is None:
            raise ValueError("No workspace to save")
        
        if self.config_path is None:
            self.config_path = Path.cwd() / ".pui-workspace.json"
        
        self.config.save(self.config_path)
    
    def build_unified_graph(self) -> UnifiedGraph:
        """Build unified graph across all repos."""
        if self.config is None:
            raise ValueError("No workspace configured")
        
        graph = UnifiedGraph()
        
        # Aggregate data from all repos
        for repo in self.config.repos:
            if not repo.enabled:
                continue
            
            repo_path = Path(repo.path)
            db_path = repo_path / ".pui" / "index.sqlite"
            
            if not db_path.exists():
                continue
            
            try:
                summary = self._get_repo_summary(db_path)
                graph.repos.append(repo.name)
                graph.repo_summaries[repo.name] = summary
                graph.total_symbols += summary.get('symbol_count', 0)
                graph.total_edges += summary.get('edge_count', 0)
            except Exception as e:
                print(f"Warning: Could not analyze {repo.name}: {e}")
        
        # Detect cross-repo dependencies (simplified)
        if self.config.cross_repo_analysis:
            graph.cross_repo_edges = self._detect_cross_repo_deps()
        
        return graph
    
    def _get_repo_summary(self, db_path: Path) -> Dict[str, Any]:
        """Get summary statistics from repository database."""
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        summary = {}
        
        try:
            cursor.execute("SELECT COUNT(*) FROM files")
            summary['file_count'] = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM symbols")
            summary['symbol_count'] = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM edges")
            summary['edge_count'] = cursor.fetchone()[0]
        except sqlite3.OperationalError:
            pass
        finally:
            conn.close()
        
        return summary
    
    def _detect_cross_repo_deps(self) -> List[CrossRepoEdge]:
        """Detect dependencies between repositories."""
        edges = []
        
        # This is a simplified implementation
        # In practice, you'd look for:
        # - Import statements referencing other repos
        # - Package references in config files
        # - Symbol names that match across repos
        
        return edges
    
    def find_symbol_across_repos(self, symbol_name: str) -> List[Dict[str, Any]]:
        """Find a symbol across all repositories."""
        results = []
        
        if self.config is None:
            return results
        
        for repo in self.config.repos:
            if not repo.enabled:
                continue
            
            repo_path = Path(repo.path)
            db_path = repo_path / ".pui" / "index.sqlite"
            
            if not db_path.exists():
                continue
            
            try:
                conn = sqlite3.connect(db_path)
                cursor = conn.cursor()
                
                cursor.execute(
                    "SELECT name, kind, file_path, line_start FROM symbols WHERE name LIKE ?",
                    (f"%{symbol_name}%",)
                )
                
                for row in cursor.fetchall():
                    results.append({
                        'repo': repo.name,
                        'name': row[0],
                        'kind': row[1],
                        'file': row[2],
                        'line': row[3]
                    })
                
                conn.close()
            except Exception:
                pass
        
        return results


def init_workspace(name: str, repo_paths: List[Path], config_path: Optional[Path] = None) -> WorkspaceConfig:
    """Initialize a new workspace."""
    manager = WorkspaceManager(config_path)
    config = manager.create_workspace(name, repo_paths)
    manager.save()
    return config


def load_workspace(config_path: Path) -> WorkspaceManager:
    """Load an existing workspace."""
    return WorkspaceManager(config_path)
