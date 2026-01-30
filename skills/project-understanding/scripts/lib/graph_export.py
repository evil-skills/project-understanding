"""
Graph export utilities for Mermaid and DOT formats.

Provides:
- Mermaid diagram generation
- DOT (Graphviz) export
- Integration with PackGenerator for graph packs
"""

from typing import List, Dict, Optional, Set
from dataclasses import dataclass


@dataclass
class GraphNode:
    """Node for graph export."""
    id: str
    label: str
    kind: str
    file_path: str
    
    def mermaid_id(self) -> str:
        """Get safe Mermaid identifier."""
        # Replace special characters
        safe = self.id.replace(".", "_").replace("-", "_").replace(":", "_")
        return f"node_{safe}"
    
    def dot_id(self) -> str:
        """Get safe DOT identifier."""
        # Quote if needed
        if any(c in self.id for c in ['.', '-', ':', ' ']):
            return f'"{self.id}"'
        return self.id


@dataclass
class GraphEdge:
    """Edge for graph export."""
    source: str
    target: str
    kind: str
    label: Optional[str] = None


class GraphExporter:
    """Export dependency graphs to various formats."""
    
    def __init__(self, db=None):
        self.db = db
        self.nodes: Dict[str, GraphNode] = {}
        self.edges: List[GraphEdge] = []
    
    def export_symbol_subgraph(
        self,
        symbol_id: int,
        depth: int = 2,
        include_callers: bool = True,
        include_callees: bool = True
    ) -> None:
        """
        Export subgraph starting from a symbol.
        
        Args:
            symbol_id: Starting symbol ID
            depth: Traversal depth
            include_callers: Include upstream dependencies
            include_callees: Include downstream dependencies
        """
        if not self.db:
            return
        
        visited: Set[int] = set()
        
        def traverse(current_id: int, current_depth: int, direction: str) -> None:
            if current_depth > depth or current_id in visited:
                return
            
            visited.add(current_id)
            
            # Get symbol info
            cursor = self.db._conn.execute(
                """
                SELECT s.*, f.path as file_path
                FROM symbols s
                JOIN files f ON s.file_id = f.id
                WHERE s.id = ?
                """,
                (current_id,)
            )
            row = cursor.fetchone()
            if not row:
                return
            
            symbol = dict(row)
            node_id = str(current_id)
            
            # Add node
            if node_id not in self.nodes:
                self.nodes[node_id] = GraphNode(
                    id=node_id,
                    label=symbol['name'],
                    kind=symbol.get('kind', 'unknown'),
                    file_path=symbol.get('file_path', 'unknown')
                )
            
            # Traverse edges
            if direction in ('both', 'up') and include_callers:
                edges = self.db.get_incoming_edges(current_id)
                for edge in edges:
                    caller_id = edge['source_id']
                    if caller_id not in visited:
                        self.edges.append(GraphEdge(
                            source=str(caller_id),
                            target=node_id,
                            kind=edge.get('kind', 'call'),
                            label=edge.get('kind', 'call')
                        ))
                        traverse(caller_id, current_depth + 1, 'up')
            
            if direction in ('both', 'down') and include_callees:
                edges = self.db.get_outgoing_edges(current_id)
                for edge in edges:
                    callee_id = edge['target_id']
                    if callee_id not in visited:
                        self.edges.append(GraphEdge(
                            source=node_id,
                            target=str(callee_id),
                            kind=edge.get('kind', 'call'),
                            label=edge.get('kind', 'call')
                        ))
                        traverse(callee_id, current_depth + 1, 'down')
        
        traverse(symbol_id, 0, 'both')
    
    def to_mermaid(self, title: Optional[str] = None) -> str:
        """
        Export as Mermaid flowchart.
        
        Returns:
            Mermaid diagram string
        """
        lines = ["```mermaid", "flowchart TD"]
        
        if title:
            lines.append(f'    subgraph "{title}"')
        
        # Add nodes
        for node_id, node in sorted(self.nodes.items()):
            # Style based on kind
            style = ""
            if node.kind == 'class':
                style = f"[[{node.label}]]"  # Double bracket for class
            elif node.kind == 'function':
                style = f"[{node.label}]"
            elif node.kind == 'method':
                style = f"({node.label})"  # Rounded for methods
            else:
                style = f"[{node.label}]"
            
            mermaid_id = node.mermaid_id()
            lines.append(f'    {mermaid_id}{style}')
        
        # Add edges
        for edge in self.edges:
            if edge.source in self.nodes and edge.target in self.nodes:
                source_id = self.nodes[edge.source].mermaid_id()
                target_id = self.nodes[edge.target].mermaid_id()
                label = f'|{edge.label}|' if edge.label else ''
                lines.append(f'    {source_id} -->{label} {target_id}')
        
        if title:
            lines.append('    end')
        
        lines.append("```")
        return '\n'.join(lines)
    
    def to_dot(self, title: Optional[str] = None) -> str:
        """
        Export as Graphviz DOT.
        
        Returns:
            DOT graph string
        """
        lines = ['digraph DependencyGraph {']
        lines.append('    rankdir=TD;')
        lines.append('    node [shape=box, style=rounded];')
        
        if title:
            lines.append(f'    label="{title}";')
        
        # Add nodes
        for node_id, node in sorted(self.nodes.items()):
            # Shape based on kind
            shape = "box"
            if node.kind == 'class':
                shape = "box3d"
            elif node.kind == 'function':
                shape = "ellipse"
            elif node.kind == 'method':
                shape = "box"
            
            # Truncate label if too long
            label = node.label
            if len(label) > 40:
                label = label[:37] + "..."
            
            safe_id = node.dot_id()
            lines.append(f'    {safe_id} [label="{label}", shape={shape}];')
        
        # Add edges
        for edge in self.edges:
            if edge.source in self.nodes and edge.target in self.nodes:
                source_node = self.nodes[edge.source]
                target_node = self.nodes[edge.target]
                source_id = source_node.dot_id()
                target_id = target_node.dot_id()
                
                attrs = []
                if edge.label:
                    attrs.append(f'label="{edge.label}"')
                if edge.kind == 'import':
                    attrs.append('style=dashed')
                
                attr_str = f' [{", ".join(attrs)}]' if attrs else ''
                lines.append(f'    {source_id} -> {target_id}{attr_str};')
        
        lines.append('}')
        return '\n'.join(lines)
    
    def generate_graph_pack(
        self,
        symbol_id: int,
        depth: int = 2,
        format: str = "mermaid",
        title: Optional[str] = None
    ) -> str:
        """
        Generate a complete graph pack.
        
        Args:
            symbol_id: Starting symbol ID
            depth: Traversal depth
            format: Output format (mermaid, dot)
            title: Optional title
        
        Returns:
            Formatted graph pack
        """
        self.export_symbol_subgraph(symbol_id, depth=depth)
        
        if format == "mermaid":
            return self.to_mermaid(title=title)
        elif format == "dot":
            return self.to_dot(title=title)
        else:
            raise ValueError(f"Unknown format: {format}")


def export_symbol_graph(
    db,
    symbol_id: int,
    depth: int = 2,
    format: str = "mermaid",
    title: Optional[str] = None
) -> str:
    """
    Convenience function to export symbol graph.
    
    Args:
        db: Database instance
        symbol_id: Symbol ID to start from
        depth: Traversal depth
        format: Output format
        title: Optional title
    
    Returns:
        Formatted graph
    """
    exporter = GraphExporter(db)
    return exporter.generate_graph_pack(symbol_id, depth, format, title)
