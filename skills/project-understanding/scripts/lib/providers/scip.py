"""
SCIP (Source Code Index Protocol) Provider for semantic analysis.

SCIP is a protocol for indexing code that provides precise code intelligence.
This provider ingests .scip files and provides semantic analysis.

Reference: https://github.com/sourcegraph/scip
"""

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional
import gzip

try:
    # Try to import protobuf if available
    import importlib.util
    HAS_PROTOBUF = importlib.util.find_spec("google.protobuf.message") is not None
except ImportError:
    HAS_PROTOBUF = False

from .base import (
    SemanticProvider, Position, Range, Location, SymbolInfo,
    CallSite, ImportInfo, EdgeConfidence
)


@dataclass
class SCIPDocument:
    """Represents a document in SCIP format."""
    language: str
    relative_path: str
    occurrences: List[Dict[str, Any]] = field(default_factory=list)
    symbols: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class SCIPIterator:
    """Iterator for parsing SCIP index files."""
    file_path: Path
    _symbols: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    _documents: Dict[str, SCIPDocument] = field(default_factory=dict)
    _metadata: Dict[str, Any] = field(default_factory=dict)
    
    def parse(self) -> bool:
        """Parse the SCIP index file."""
        try:
            # SCIP files can be gzipped
            if self.file_path.suffix == '.gz':
                with gzip.open(self.file_path, 'rb') as f:
                    data = f.read()
            else:
                with open(self.file_path, 'rb') as f:
                    data = f.read()
            
            # Try protobuf parsing first
            if HAS_PROTOBUF:
                return self._parse_protobuf(data)
            else:
                # Fallback to JSON if available
                return self._parse_json(data)
                
        except Exception as e:
            print(f"Error parsing SCIP file: {e}")
            return False
    
    def _parse_protobuf(self, data: bytes) -> bool:
        """Parse protobuf-encoded SCIP index."""
        # This is a simplified parser - full protobuf support would require the scip proto definitions
        # For now, we extract basic information from the binary format
        
        try:
            # Check for gzip magic
            if data[:2] == b'\x1f\x8b':
                data = gzip.decompress(data)
            
            # Try to extract strings and build basic index
            # This is a heuristic approach for when protobuf isn't available
            offset = 0
            while offset < len(data):
                # Read varint for message length (simplified)
                if offset + 1 > len(data):
                    break
                
                # Look for document markers
                chunk = data[offset:offset + 1024]
                if b"document" in chunk or b"occurrence" in chunk:
                    # Extract path information
                    for line in chunk.split(b'\n'):
                        if b'relative_path' in line or b'language' in line:
                            try:
                                text = line.decode('utf-8', errors='ignore')
                                if ':' in text:
                                    key, value = text.split(':', 1)
                                    self._metadata[key.strip()] = value.strip()
                            except Exception:
                                pass
                
                offset += 1024
            
            return True
            
        except Exception as e:
            print(f"Error in protobuf parsing: {e}")
            return False
    
    def _parse_json(self, data: bytes) -> bool:
        """Parse JSON-encoded SCIP index."""
        try:
            json_data = json.loads(data.decode('utf-8'))
            
            # Extract metadata
            self._metadata = json_data.get('metadata', {})
            
            # Parse documents
            for doc in json_data.get('documents', []):
                scip_doc = SCIPDocument(
                    language=doc.get('language', 'unknown'),
                    relative_path=doc.get('relative_path', ''),
                    occurrences=doc.get('occurrences', []),
                    symbols=doc.get('symbols', [])
                )
                self._documents[scip_doc.relative_path] = scip_doc
            
            # Build symbol index
            for doc_path, doc in self._documents.items():
                for sym in doc.symbols:
                    symbol_id = sym.get('symbol', '')
                    if symbol_id:
                        self._symbols[symbol_id] = {
                            **sym,
                            'document': doc_path
                        }
            
            return True
            
        except json.JSONDecodeError as e:
            print(f"Error parsing JSON SCIP: {e}")
            return False
    
    def get_symbols(self) -> Dict[str, Dict[str, Any]]:
        """Get all symbols from the index."""
        return self._symbols
    
    def get_documents(self) -> Dict[str, SCIPDocument]:
        """Get all documents from the index."""
        return self._documents
    
    def get_metadata(self) -> Dict[str, Any]:
        """Get index metadata."""
        return self._metadata


class SCIPProvider(SemanticProvider):
    """
    SCIP-based semantic provider.
    
    Provides high-precision code intelligence from pre-computed SCIP indices.
    """
    
    def __init__(self, repo_root: Path, verbose: bool = False, scip_path: Optional[Path] = None):
        super().__init__(repo_root, verbose)
        self.scip_path = scip_path
        self._name = "scip"
        self._index: Optional[SCIPIterator] = None
        self._symbol_cache: Dict[str, SymbolInfo] = {}
        self._location_cache: Dict[str, List[Location]] = {}
    
    def initialize(self) -> "SCIPProvider":
        """Load SCIP index file."""
        self._log("Initializing SCIP provider")
        
        # Find SCIP file if not specified
        if not self.scip_path:
            self.scip_path = self._find_scip_file()
        
        if self.scip_path and self.scip_path.exists():
            self._index = SCIPIterator(self.scip_path)
            if self._index.parse():
                self._log(f"Loaded SCIP index: {self.scip_path}")
                self._build_caches()
                self._initialized = True
            else:
                self._log("Failed to parse SCIP index")
        else:
            self._log("No SCIP index found")
        
        return self
    
    def shutdown(self) -> None:
        """Clear caches."""
        self._symbol_cache.clear()
        self._location_cache.clear()
        self._index = None
    
    def _find_scip_file(self) -> Optional[Path]:
        """Find SCIP index file in repository."""
        # Common locations for SCIP files
        candidates = [
            self.repo_root / "index.scip",
            self.repo_root / "index.scip.gz",
            self.repo_root / ".scip" / "index.scip",
            self.repo_root / ".scip" / "index.scip.gz",
            self.repo_root / "dist" / "index.scip",
        ]
        
        # Also check for language-specific SCIP files
        candidates.extend([
            self.repo_root / "index.scip",  # TypeScript
            self.repo_root / "index-python.scip",
            self.repo_root / "index-go.scip",
            self.repo_root / "index-rust.scip",
        ])
        
        for candidate in candidates:
            if candidate.exists():
                return candidate
        
        return None
    
    def _build_caches(self) -> None:
        """Build symbol and location caches from SCIP index."""
        if not self._index:
            return
        
        # Build symbol cache
        for symbol_id, sym_data in self._index.get_symbols().items():
            doc_path = sym_data.get('document', '')
            full_path = str(self.repo_root / doc_path) if doc_path else ''
            
            # Parse relationships for call hierarchy
            sym_data.get('relationships', [])
            
            self._symbol_cache[symbol_id] = SymbolInfo(
                id=symbol_id,
                name=sym_data.get('display_name', symbol_id.split('/')[-1] if '/' in symbol_id else symbol_id),
                kind=self._map_symbol_kind(sym_data.get('kind', 'unknown')),
                location=Location(
                    file=full_path,
                    range=Range(
                        start=Position(line=0, character=0),
                        end=Position(line=0, character=0)
                    )
                ),
                signature=sym_data.get('signature'),
                docstring=sym_data.get('documentation', [None])[0] if sym_data.get('documentation') else None
            )
        
        # Build location cache for references
        for doc_path, doc in self._index.get_documents().items():
            for occ in doc.occurrences:
                symbol_id = occ.get('symbol', '')
                if symbol_id:
                    if symbol_id not in self._location_cache:
                        self._location_cache[symbol_id] = []
                    
                    # Parse occurrence range
                    range_data = occ.get('range', [0, 0, 0])
                    if len(range_data) >= 2:
                        line, char = range_data[0], range_data[1]
                        self._location_cache[symbol_id].append(
                            Location(
                                file=str(self.repo_root / doc_path),
                                range=Range(
                                    start=Position(line=line, character=char),
                                    end=Position(line=line, character=char + (range_data[2] if len(range_data) > 2 else 1))
                                )
                            )
                        )
    
    def _map_symbol_kind(self, kind: str) -> str:
        """Map SCIP symbol kind to our kind."""
        kind_map = {
            'UnspecifiedKind': 'unknown',
            'Type': 'type',
            'Class': 'class',
            'Enum': 'enum',
            'Interface': 'interface',
            'Struct': 'struct',
            'TypeParameter': 'type_parameter',
            'Parameter': 'parameter',
            'Variable': 'variable',
            'Property': 'property',
            'EnumMember': 'enum_member',
            'Function': 'function',
            'Method': 'method',
            'Constructor': 'constructor',
            'Macro': 'macro',
            'Module': 'module',
            'Namespace': 'namespace',
            'Package': 'package',
        }
        return kind_map.get(kind, kind.lower())
    
    def get_definitions(self, file: Path, position: Position) -> List[SymbolInfo]:
        """Get symbol definitions at position from SCIP index."""
        if not self._index:
            return []
        
        # Find symbol at position
        relative_path = str(file.relative_to(self.repo_root)) if file.is_relative_to(self.repo_root) else str(file)
        doc = self._index.get_documents().get(relative_path)
        
        if not doc:
            return []
        
        # Find occurrence at position
        for occ in doc.occurrences:
            range_data = occ.get('range', [0, 0])
            if len(range_data) >= 2:
                line = range_data[0]
                char = range_data[1]
                
                # Check if position is within occurrence
                if line == position.line and abs(char - position.character) < 50:
                    symbol_id = occ.get('symbol', '')
                    if symbol_id and symbol_id in self._symbol_cache:
                        return [self._symbol_cache[symbol_id]]
        
        return []
    
    def get_references(self, symbol_id: str) -> List[Location]:
        """Get all references to a symbol from SCIP index."""
        return self._location_cache.get(symbol_id, [])
    
    def get_call_hierarchy(self, symbol_id: str, direction: str = "both") -> Dict[str, List[CallSite]]:
        """Get call hierarchy from SCIP relationships."""
        if not self._index or symbol_id not in self._symbol_cache:
            return {"incoming": [], "outgoing": []}
        
        incoming = []
        outgoing = []
        
        # Get symbol data
        sym_data = self._index.get_symbols().get(symbol_id, {})
        relationships = sym_data.get('relationships', [])
        
        for rel in relationships:
            rel_symbol = rel.get('symbol', '')
            rel_type = rel.get('is_reference', False)
            rel_def = rel.get('is_definition', False)
            
            if direction in ("incoming", "both") and rel_type and not rel_def:
                # Incoming reference
                if rel_symbol in self._symbol_cache:
                    caller = self._symbol_cache[rel_symbol]
                    callee = self._symbol_cache[symbol_id]
                    
                    # Get reference locations
                    locations = self._location_cache.get(rel_symbol, [])
                    for loc in locations[:5]:  # Limit to first 5
                        incoming.append(CallSite(
                            caller=caller,
                            callee=callee,
                            location=loc,
                            confidence=EdgeConfidence.RESOLVED
                        ))
            
            if direction in ("outgoing", "both") and rel_type:
                # Outgoing reference
                if rel_symbol in self._symbol_cache:
                    caller = self._symbol_cache[symbol_id]
                    callee = self._symbol_cache[rel_symbol]
                    
                    locations = self._location_cache.get(symbol_id, [])
                    for loc in locations[:5]:
                        outgoing.append(CallSite(
                            caller=caller,
                            callee=callee,
                            location=loc,
                            confidence=EdgeConfidence.RESOLVED
                        ))
        
        # Also check occurrences for call relationships
        for doc_path, doc in self._index.get_documents().items():
            for occ in doc.occurrences:
                occ_symbol = occ.get('symbol', '')
                if occ_symbol == symbol_id:
                    # This file references our symbol
                    pass
        
        return {"incoming": incoming, "outgoing": outgoing}
    
    def resolve_imports(self, file: Path) -> List[ImportInfo]:
        """Resolve imports from SCIP index."""
        if not self._index:
            return []
        
        relative_path = str(file.relative_to(self.repo_root)) if file.is_relative_to(self.repo_root) else str(file)
        doc = self._index.get_documents().get(relative_path)
        
        if not doc:
            return []
        
        imports = []
        
        # Look for import/export symbols
        for sym in doc.symbols:
            if sym.get('kind') == 'Module' or 'import' in sym.get('symbol', '').lower():
                symbol_id = sym.get('symbol', '')
                
                # Parse import information
                # SCIP format: scheme package manager name version descriptor
                parts = symbol_id.split(' ')
                if len(parts) >= 3:
                    manager = parts[1]
                    descriptor = ' '.join(parts[3:]) if len(parts) > 3 else parts[2]
                    
                    imports.append(ImportInfo(
                        source_file=str(file),
                        module=manager,
                        name=descriptor,
                        alias=None,
                        location=Location(
                            file=str(file),
                            range=Range(
                                start=Position(line=0, character=0),
                                end=Position(line=0, character=0)
                            )
                        ),
                        is_relative='.' in descriptor
                    ))
        
        return imports
    
    def get_document_symbols(self, file: Path) -> List[SymbolInfo]:
        """Get all symbols defined in a document."""
        if not self._index:
            return []
        
        relative_path = str(file.relative_to(self.repo_root)) if file.is_relative_to(self.repo_root) else str(file)
        doc = self._index.get_documents().get(relative_path)
        
        if not doc:
            return []
        
        symbols = []
        for sym_data in doc.symbols:
            symbol_id = sym_data.get('symbol', '')
            if symbol_id in self._symbol_cache:
                symbols.append(self._symbol_cache[symbol_id])
        
        return symbols
    
    @property
    def name(self) -> str:
        return self._name
    
    @property
    def supported_languages(self) -> List[str]:
        """Get languages from SCIP metadata."""
        if self._index:
            self._index.get_metadata()
            # Try to infer from documents
            docs = self._index.get_documents()
            languages = set(doc.language for doc in docs.values())
            return list(languages)
        return []
    
    def is_available(self) -> bool:
        return self._initialized and self._index is not None
    
    def get_metadata(self) -> Dict[str, Any]:
        """Get SCIP index metadata."""
        if self._index:
            return self._index.get_metadata()
        return {}
    
    def get_all_symbols(self) -> Dict[str, SymbolInfo]:
        """Get all symbols from the index."""
        return self._symbol_cache.copy()
    
    def get_statistics(self) -> Dict[str, int]:
        """Get index statistics."""
        if not self._index:
            return {"symbols": 0, "documents": 0}
        
        return {
            "symbols": len(self._index.get_symbols()),
            "documents": len(self._index.get_documents()),
            "cached_symbols": len(self._symbol_cache),
            "cached_locations": len(self._location_cache)
        }
