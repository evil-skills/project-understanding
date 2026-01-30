"""
Semantic Provider Interface for Project Understanding.

Provides abstract interface for semantic code analysis through
LSP (Language Server Protocol) and SCIP (Source Code Index Protocol).
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional
from enum import Enum


class EdgeConfidence(Enum):
    """Confidence levels for semantic edges."""
    RESOLVED = 1.0
    STRONG_HEURISTIC = 0.85
    MEDIUM_HEURISTIC = 0.65
    WEAK_HEURISTIC = 0.45
    UNCERTAIN = 0.25
    UNKNOWN = 0.0


@dataclass
class Position:
    """Source code position."""
    line: int
    character: int
    
    def __repr__(self) -> str:
        return f"Position(line={self.line}, char={self.character})"


@dataclass
class Range:
    """Source code range."""
    start: Position
    end: Position
    
    def __repr__(self) -> str:
        return f"Range({self.start} to {self.end})"


@dataclass
class Location:
    """Symbol location in codebase."""
    file: str
    range: Range
    
    def __repr__(self) -> str:
        return f"Location({self.file}:{self.range.start.line})"


@dataclass
class SymbolInfo:
    """Information about a symbol."""
    id: str
    name: str
    kind: str
    location: Location
    signature: Optional[str] = None
    docstring: Optional[str] = None
    
    def __repr__(self) -> str:
        return f"SymbolInfo({self.name} [{self.kind}])"


@dataclass
class CallSite:
    """Information about a function/method call."""
    caller: SymbolInfo
    callee: SymbolInfo
    location: Location
    call_type: str = "direct"  # direct, method_dispatch, higher_order
    confidence: EdgeConfidence = EdgeConfidence.RESOLVED


@dataclass
class ImportInfo:
    """Information about an import statement."""
    source_file: str
    module: Optional[str]
    name: Optional[str]
    alias: Optional[str]
    location: Location
    is_relative: bool = False


@dataclass
class EdgeProvenance:
    """Metadata about where an edge came from."""
    provider: str
    timestamp: float
    query_version: str
    confidence: EdgeConfidence


class SemanticProvider(ABC):
    """
    Abstract base class for semantic code analysis providers.
    
    Implementations may use:
    - LSP (Language Server Protocol) for live analysis
    - SCIP (Source Code Index Protocol) for pre-computed indices
    - Tree-sitter heuristics as fallback
    """
    
    def __init__(self, repo_root: Path, verbose: bool = False):
        """
        Initialize provider.
        
        Args:
            repo_root: Repository root directory
            verbose: Enable verbose logging
        """
        self.repo_root = Path(repo_root)
        self.verbose = verbose
        self._initialized = False
    
    def _log(self, message: str) -> None:
        """Log message if verbose mode enabled."""
        if self.verbose:
            print(f"[{self.__class__.__name__}] {message}")
    
    @abstractmethod
    def initialize(self) -> "SemanticProvider":
        """Initialize the provider (start LSP, load SCIP, etc.)."""
        pass
    
    @abstractmethod
    def shutdown(self) -> None:
        """Shutdown the provider gracefully."""
        pass
    
    def __enter__(self) -> "SemanticProvider":
        """Context manager entry."""
        return self.initialize()
    
    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Context manager exit."""
        self.shutdown()
    
    @abstractmethod
    def get_definitions(self, file: Path, position: Position) -> List[SymbolInfo]:
        """
        Get symbol definitions at a given position.
        
        Args:
            file: Source file path
            position: Cursor position
            
        Returns:
            List of symbol definitions
        """
        pass
    
    @abstractmethod
    def get_references(self, symbol_id: str) -> List[Location]:
        """
        Get all references to a symbol.
        
        Args:
            symbol_id: Unique symbol identifier
            
        Returns:
            List of reference locations
        """
        pass
    
    @abstractmethod
    def get_call_hierarchy(self, symbol_id: str, direction: str = "both") -> Dict[str, List[CallSite]]:
        """
        Get call hierarchy for a symbol.
        
        Args:
            symbol_id: Unique symbol identifier
            direction: "incoming" (callers), "outgoing" (callees), or "both"
            
        Returns:
            Dictionary with 'incoming' and 'outgoing' call sites
        """
        pass
    
    @abstractmethod
    def resolve_imports(self, file: Path) -> List[ImportInfo]:
        """
        Resolve all imports in a file.
        
        Args:
            file: Source file path
            
        Returns:
            List of resolved import information
        """
        pass
    
    @abstractmethod
    def get_document_symbols(self, file: Path) -> List[SymbolInfo]:
        """
        Get all symbols defined in a document.
        
        Args:
            file: Source file path
            
        Returns:
            List of symbol information
        """
        pass
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Provider name for identification."""
        pass
    
    @property
    @abstractmethod
    def supported_languages(self) -> List[str]:
        """List of supported language identifiers."""
        pass
    
    def is_available(self) -> bool:
        """Check if provider is available (LSP server installed, SCIP file exists, etc.)."""
        return True


class CompositeProvider(SemanticProvider):
    """
    Composite provider that tries multiple providers in order.
    
    Used for 'auto' mode: SCIP > LSP > heuristic
    """
    
    def __init__(self, providers: List[SemanticProvider], repo_root: Path, verbose: bool = False):
        """
        Initialize composite provider.
        
        Args:
            providers: Ordered list of providers to try
            repo_root: Repository root directory
            verbose: Enable verbose logging
        """
        super().__init__(repo_root, verbose)
        self.providers = providers
    
    def initialize(self) -> "CompositeProvider":
        """Initialize all providers."""
        for provider in self.providers:
            try:
                provider.initialize()
            except Exception as e:
                self._log(f"Failed to initialize {provider.name}: {e}")
        return self
    
    def shutdown(self) -> None:
        """Shutdown all providers."""
        for provider in self.providers:
            try:
                provider.shutdown()
            except Exception as e:
                self._log(f"Error shutting down {provider.name}: {e}")
    
    def _first_successful(self, method_name: str, *args, **kwargs):
        """Try each provider until one succeeds."""
        for provider in self.providers:
            if not provider.is_available():
                continue
            try:
                method = getattr(provider, method_name)
                result = method(*args, **kwargs)
                if result:  # Return first non-empty result
                    self._log(f"Using {provider.name} for {method_name}")
                    return result
            except Exception as e:
                self._log(f"{provider.name}.{method_name} failed: {e}")
        return [] if not args else None
    
    def get_definitions(self, file: Path, position: Position) -> List[SymbolInfo]:
        return self._first_successful("get_definitions", file, position) or []
    
    def get_references(self, symbol_id: str) -> List[Location]:
        return self._first_successful("get_references", symbol_id) or []
    
    def get_call_hierarchy(self, symbol_id: str, direction: str = "both") -> Dict[str, List[CallSite]]:
        for provider in self.providers:
            if not provider.is_available():
                continue
            try:
                result = provider.get_call_hierarchy(symbol_id, direction)
                if result and (result.get("incoming") or result.get("outgoing")):
                    self._log(f"Using {provider.name} for call_hierarchy")
                    return result
            except Exception as e:
                self._log(f"{provider.name}.get_call_hierarchy failed: {e}")
        return {"incoming": [], "outgoing": []}
    
    def resolve_imports(self, file: Path) -> List[ImportInfo]:
        return self._first_successful("resolve_imports", file) or []
    
    def get_document_symbols(self, file: Path) -> List[SymbolInfo]:
        return self._first_successful("get_document_symbols", file) or []
    
    @property
    def name(self) -> str:
        return "composite"
    
    @property
    def supported_languages(self) -> List[str]:
        languages = set()
        for provider in self.providers:
            languages.update(provider.supported_languages)
        return list(languages)
    
    def is_available(self) -> bool:
        return any(p.is_available() for p in self.providers)


class HeuristicProvider(SemanticProvider):
    """
    Fallback provider using Tree-sitter heuristics.
    
    This is the baseline provider that always works but has lower confidence.
    """
    
    def __init__(self, repo_root: Path, verbose: bool = False):
        super().__init__(repo_root, verbose)
        self._name = "heuristic"
    
    def initialize(self) -> "HeuristicProvider":
        """Initialize heuristic provider."""
        self._initialized = True
        self._log("Heuristic provider initialized")
        return self
    
    def shutdown(self) -> None:
        """No-op for heuristic provider."""
        pass
    
    def get_definitions(self, file: Path, position: Position) -> List[SymbolInfo]:
        """Get definitions using Tree-sitter parsing."""
        # This is a placeholder - would integrate with existing parser
        self._log(f"Heuristic definition lookup: {file}:{position}")
        return []
    
    def get_references(self, symbol_id: str) -> List[Location]:
        """Get references using text search heuristics."""
        self._log(f"Heuristic reference lookup: {symbol_id}")
        return []
    
    def get_call_hierarchy(self, symbol_id: str, direction: str = "both") -> Dict[str, List[CallSite]]:
        """Get call hierarchy using Tree-sitter."""
        self._log(f"Heuristic call hierarchy: {symbol_id}")
        return {"incoming": [], "outgoing": []}
    
    def resolve_imports(self, file: Path) -> List[ImportInfo]:
        """Resolve imports using Tree-sitter parsing."""
        self._log(f"Heuristic import resolution: {file}")
        return []
    
    def get_document_symbols(self, file: Path) -> List[SymbolInfo]:
        """Get symbols from Tree-sitter parser."""
        self._log(f"Heuristic document symbols: {file}")
        return []
    
    @property
    def name(self) -> str:
        return self._name
    
    @property
    def supported_languages(self) -> List[str]:
        return ["*"]  # Supports all languages via Tree-sitter
    
    def is_available(self) -> bool:
        return True


def create_provider(
    mode: str,
    repo_root: Path,
    verbose: bool = False,
    lsp_configs: Optional[Dict[str, Any]] = None
) -> SemanticProvider:
    """
    Factory function to create appropriate provider.
    
    Args:
        mode: Provider mode ('none', 'lsp', 'scip', 'auto')
        repo_root: Repository root directory
        verbose: Enable verbose logging
        lsp_configs: Optional LSP server configurations
        
    Returns:
        Configured SemanticProvider instance
    """
    from .scip import SCIPProvider
    from .lsp import LSPProvider, get_default_lsp_configs
    
    if mode == "none":
        return HeuristicProvider(repo_root, verbose)
    
    elif mode == "lsp":
        configs = lsp_configs or get_default_lsp_configs()
        return LSPProvider(repo_root, configs, verbose)
    
    elif mode == "scip":
        return SCIPProvider(repo_root, verbose)
    
    elif mode == "auto":
        # Auto mode: SCIP > LSP > heuristic
        providers = []
        
        # Try SCIP first (highest precision)
        scip = SCIPProvider(repo_root, verbose)
        providers.append(scip)
        
        # Then LSP
        configs = lsp_configs or get_default_lsp_configs()
        lsp = LSPProvider(repo_root, configs, verbose)
        providers.append(lsp)
        
        # Finally heuristic fallback
        heuristic = HeuristicProvider(repo_root, verbose)
        providers.append(heuristic)
        
        return CompositeProvider(providers, repo_root, verbose)
    
    else:
        raise ValueError(f"Unknown provider mode: {mode}")
