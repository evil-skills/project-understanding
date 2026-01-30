"""
Semantic Providers for Project Understanding.

Provides code intelligence through:
- LSP (Language Server Protocol)
- SCIP (Source Code Index Protocol)
- Tree-sitter heuristics
"""

from .base import (
    SemanticProvider,
    CompositeProvider,
    HeuristicProvider,
    Position,
    Range,
    Location,
    SymbolInfo,
    CallSite,
    ImportInfo,
    EdgeConfidence,
    EdgeProvenance,
    create_provider
)

from .lsp import LSPProvider, get_default_lsp_configs, LSPClient
from .scip import SCIPProvider, SCIPIterator

__all__ = [
    # Base
    'SemanticProvider',
    'CompositeProvider',
    'HeuristicProvider',
    'create_provider',
    
    # Data types
    'Position',
    'Range',
    'Location',
    'SymbolInfo',
    'CallSite',
    'ImportInfo',
    'EdgeConfidence',
    'EdgeProvenance',
    
    # Providers
    'LSPProvider',
    'SCIPProvider',
    
    # Utilities
    'get_default_lsp_configs',
    'LSPClient',
    'SCIPIterator',
]
