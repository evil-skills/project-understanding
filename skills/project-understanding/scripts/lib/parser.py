"""
Tree-sitter parser integration for Project Understanding.

Provides language-aware parsing using tree-sitter with prebuilt grammars.
Supports Python, JavaScript, TypeScript, Go, and Rust.
"""

import re
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field

try:
    from tree_sitter import Parser, Tree, Node, Query
    TREE_SITTER_AVAILABLE = True
except ImportError:
    TREE_SITTER_AVAILABLE = False

# Try to import tree_sitter_languages, fallback to manual loading
try:
    from tree_sitter_languages import get_language, get_parser
    HAS_LANGUAGE_BINDINGS = True
except ImportError:
    HAS_LANGUAGE_BINDINGS = False


@dataclass
class Symbol:
    """Represents a symbol definition."""
    name: str
    kind: str
    line_start: int
    line_end: Optional[int] = None
    column_start: Optional[int] = None
    column_end: Optional[int] = None
    signature: Optional[str] = None
    docstring: Optional[str] = None
    parent_name: Optional[str] = None
    calls: List[Dict[str, Any]] = field(default_factory=list)
    
    @property
    def symbol_id(self) -> str:
        """Compute stable symbol ID."""
        # Format: path:kind:qualname:start_line
        return f"{self.name}:{self.kind}:{self.line_start}"


@dataclass
class Import:
    """Represents an import statement."""
    module: Optional[str]
    name: Optional[str]
    alias: Optional[str]
    line: int
    raw_text: str
    is_resolved: bool = False
    resolved_path: Optional[str] = None


@dataclass
class Callsite:
    """Represents a function/method call site."""
    callee_text: str
    line: int
    column: Optional[int] = None
    scope_symbol_id: Optional[str] = None
    confidence: float = 0.0
    context: Optional[str] = None


@dataclass
class ParseResult:
    """Result of parsing a file."""
    symbols: List[Symbol]
    imports: List[Import]
    callsites: List[Callsite]
    language: str
    errors: List[str] = field(default_factory=list)


class LanguageSupport:
    """Manages language support and query files."""
    
    SUPPORTED_LANGUAGES = {
        'python': ['.py'],
        'javascript': ['.js', '.jsx', '.mjs'],
        'typescript': ['.ts', '.tsx'],
        'go': ['.go'],
        'rust': ['.rs'],
        'cpp': ['.cpp', '.cc', '.cxx', '.h', '.hpp', '.c'],
    }
    
    def __init__(self, queries_dir: Optional[Path] = None):
        """
        Initialize language support.
        
        Args:
            queries_dir: Directory containing .scm query files
        """
        self.queries_dir = queries_dir or Path(__file__).parent / 'queries'
        self._languages: Dict[str, Any] = {}
        self._parsers: Dict[str, Parser] = {}
        self._queries: Dict[str, Dict[str, Any]] = {}
        
        if not TREE_SITTER_AVAILABLE:
            raise ImportError(
                "tree-sitter and tree-sitter-languages are required. "
                "Install with: pip install tree-sitter tree-sitter-languages"
            )
    
    def get_language_for_file(self, path: Path) -> Optional[str]:
        """Determine language from file extension."""
        ext = path.suffix.lower()
        for lang, exts in self.SUPPORTED_LANGUAGES.items():
            if ext in exts:
                return lang
        return None
    
    def is_supported(self, language: str) -> bool:
        """Check if a language is supported."""
        return language in self.SUPPORTED_LANGUAGES
    
    def _load_language(self, language: str) -> Any:
        """Load tree-sitter language."""
        if language not in self._languages:
            if not HAS_LANGUAGE_BINDINGS:
                raise RuntimeError(
                    f"Language '{language}' not available. "
                    "tree-sitter-languages package not installed."
                )
            try:
                self._languages[language] = get_language(language)
            except Exception as e:
                raise RuntimeError(f"Failed to load language '{language}': {e}")
        return self._languages[language]

    def _load_parser(self, language: str) -> Parser:
        """Load tree-sitter parser."""
        if language not in self._parsers:
            if not HAS_LANGUAGE_BINDINGS:
                raise RuntimeError(
                    f"Parser for '{language}' not available. "
                    "tree-sitter-languages package not installed."
                )
            try:
                self._parsers[language] = get_parser(language)
            except Exception as e:
                raise RuntimeError(f"Failed to load parser for '{language}': {e}")
        return self._parsers[language]
    
    def _load_query(self, language: str, query_name: str) -> Optional[Any]:
        """Load a query from .scm file."""
        if language not in self._queries:
            self._queries[language] = {}
        
        if query_name not in self._queries[language]:
            query_path = self.queries_dir / f"{language}.scm"
            if not query_path.exists():
                return None
            
            try:
                query_text = query_path.read_text()
                lang = self._load_language(language)
                if not TREE_SITTER_AVAILABLE:
                    return None
                self._queries[language][query_name] = Query(lang, query_text)
            except Exception:
                # Log error but don't crash - some queries may not be available
                return None
        
        return self._queries[language].get(query_name)


class TreeSitterParser:
    """Parser using tree-sitter for multiple languages."""
    
    def __init__(self, queries_dir: Optional[Path] = None):
        """
        Initialize parser.
        
        Args:
            queries_dir: Directory containing .scm query files
        """
        self.language_support = LanguageSupport(queries_dir)
    
    def parse_file(self, path: Path, content: Optional[str] = None) -> Optional[ParseResult]:
        """
        Parse a file and extract symbols, imports, and callsites.
        
        Args:
            path: Path to the file
            content: Optional file content (reads from disk if not provided)
        
        Returns:
            ParseResult or None if parsing failed
        """
        language = self.language_support.get_language_for_file(path)
        if not language:
            return None
        
        if content is None:
            try:
                content = path.read_text(encoding='utf-8', errors='replace')
            except Exception as e:
                return ParseResult(
                    symbols=[], imports=[], callsites=[],
                    language=language, errors=[f"Failed to read file: {e}"]
                )
        
        try:
            parser = self.language_support._load_parser(language)
            tree = parser.parse(bytes(content, 'utf8'))
            
            symbols = self.extract_symbols(tree, path, language, content)
            imports = self.extract_imports(tree, path, language, content)
            callsites = self.extract_callsites(tree, path, language, content, symbols)
            
            return ParseResult(
                symbols=symbols,
                imports=imports,
                callsites=callsites,
                language=language
            )
        except Exception as e:
            # Fallback to regex-based extraction if tree-sitter fails
            return self._regex_parse_fallback(path, content, language, [f"Tree-sitter failed: {e}"])

    def _regex_parse_fallback(self, path: Path, content: str, language: str, errors: List[str]) -> ParseResult:
        """Fallback to regex-based extraction when tree-sitter is unavailable."""
        symbols = []
        imports = []
        callsites = []
        
        # If content is empty, return early to satisfy tests expecting 0 symbols
        if not content.strip():
            return ParseResult(
                symbols=[],
                imports=[],
                callsites=[],
                language=language,
                errors=errors
            )

        lines = content.split('\n')
        
        if language == 'python':
            # Basic Python regexes
            func_re = re.compile(r'^\s*(?:async\s+)?def\s+([a-zA-Z_]\w*)')
            class_re = re.compile(r'^\s*class\s+([a-zA-Z_]\w*)')
            import_re = re.compile(r'^\s*(?:from\s+([\w\.]+)\s+)?import\s+(.+)')
            call_re = re.compile(r'([a-zA-Z_]\w*(?:\.[a-zA-Z_]\w*)*)\s*\(')
            
            current_class = None
            for i, line in enumerate(lines):
                line_num = i + 1
                
                # Classes
                m = class_re.match(line)
                if m:
                    current_class = m.group(1)
                    symbols.append(Symbol(
                        name=current_class,
                        kind='class',
                        line_start=line_num,
                        column_start=line.find('class'),
                        signature=line.strip()
                    ))
                    continue
                
                # Functions/Methods
                m = func_re.match(line)
                if m:
                    kind = 'method' if current_class and line.startswith('    ') else 'function'
                    symbols.append(Symbol(
                        name=m.group(1),
                        kind=kind,
                        line_start=line_num,
                        column_start=line.find('def'),
                        signature=line.strip(),
                        parent_name=current_class if kind == 'method' else None
                    ))
                    continue
                
                # Imports
                m = import_re.match(line)
                if m:
                    module = m.group(1) or m.group(2).split(',')[0].split(' as ')[0].strip()
                    if 'import' in line and not m.group(1):
                        module = m.group(2).split(',')[0].split(' as ')[0].strip()
                    
                    imports.append(Import(
                        module=module,
                        name=None,
                        alias=None,
                        line=line_num,
                        raw_text=line.strip()
                    ))
                
                # Calls (simple heuristic)
                for call_match in call_re.finditer(line):
                    callee = call_match.group(1)
                    confidence = 0.6 if '.' in callee else 0.3
                    callsites.append(Callsite(
                        callee_text=callee,
                        line=line_num,
                        confidence=confidence
                    ))
                    
        elif language in ['javascript', 'typescript']:
            # Basic JS/TS regexes
            func_re = re.compile(r'(?:function\s+([a-zA-Z_]\w*)|([a-zA-Z_]\w*)\s*=\s*(?:async\s+)?(?:\([^)]*\)|[a-zA-Z_]\w*)\s*=>)')
            class_re = re.compile(r'class\s+([a-zA-Z_]\w*)')
            import_re = re.compile(r'import\s+.*from\s+[\'"](.+)[\'"]')
            
            for i, line in enumerate(lines):
                line_num = i + 1
                m = func_re.search(line)
                if m:
                    name = m.group(1) or m.group(2)
                    symbols.append(Symbol(name=name, kind='function', line_start=line_num, column_start=line.find(name), signature=line.strip()))
                
                m = class_re.search(line)
                if m:
                    symbols.append(Symbol(name=m.group(1), kind='class', line_start=line_num, column_start=line.find(m.group(1)), signature=line.strip()))
                    
                m = import_re.search(line)
                if m:
                    imports.append(Import(module=m.group(1), name=None, alias=None, line=line_num, raw_text=line.strip()))

        elif language == 'rust':
            func_re = re.compile(r'fn\s+([a-zA-Z_]\w*)')
            struct_re = re.compile(r'(?:struct|enum|trait)\s+([a-zA-Z_]\w*)')
            use_re = re.compile(r'use\s+([^;]+);')
            
            for i, line in enumerate(lines):
                line_num = i + 1
                m = func_re.search(line)
                if m:
                    symbols.append(Symbol(name=m.group(1), kind='function', line_start=line_num, column_start=line.find(m.group(1))))
                m = struct_re.search(line)
                if m:
                    symbols.append(Symbol(name=m.group(1), kind='class', line_start=line_num, column_start=line.find(m.group(1))))
                m = use_re.search(line)
                if m:
                    imports.append(Import(module=m.group(1).strip(), name=None, alias=None, line=line_num, raw_text=line.strip()))

        # Extract docstrings (very simple heuristic for Python)
        if language == 'python':
            for i in range(len(symbols)):
                sym = symbols[i]
                start_line = sym.line_start
                if start_line < len(lines):
                    next_line = lines[start_line].strip()
                    if next_line.startswith(('"""', "'''")):
                        sym.docstring = next_line.strip('"\'')

        # If still no symbols and NOT empty, add file-level symbol
        if not symbols and content.strip():
            symbols = [Symbol(
                name=path.stem,
                kind='file',
                line_start=1
            )]
            
        return ParseResult(
            symbols=symbols,
            imports=imports,
            callsites=callsites,
            language=language,
            errors=errors
        )
    
    def extract_symbols(self, tree: Tree, path: Path, language: str, content: str) -> List[Symbol]:
        """
        Extract symbol definitions from AST.
        
        Args:
            tree: Parsed AST
            path: File path
            language: Programming language
            content: File content
        
        Returns:
            List of symbols
        """
        symbols = []
        query = self.language_support._load_query(language, 'symbols')
        
        if query:
            root_node = tree.root_node
            captures = query.captures(root_node) # type: ignore
            
            # Group captures by node
            node_captures: Dict[int, Dict[str, Any]] = {}
            for capture in captures:
                node = capture[0]
                capture_name = capture[1]
                node_id = id(node)
                
                if node_id not in node_captures:
                    node_captures[node_id] = {'node': node, 'captures': {}}
                node_captures[node_id]['captures'][capture_name] = node
            
            # Process each captured definition
            for node_data in node_captures.values():
                node = node_data['node']
                caps = node_data['captures']
                
                # Determine kind
                kind = 'unknown'
                if 'function' in caps:
                    kind = 'function'
                elif 'method' in caps:
                    kind = 'method'
                elif 'class' in caps:
                    kind = 'class'
                
                # Get name
                name_node = caps.get('name', node)
                name = name_node.text.decode('utf8') if isinstance(name_node.text, bytes) else str(name_node.text)
                
                # Get signature text
                sig_node = caps.get('signature', node)
                signature = None
                if sig_node != node:
                    sig_text = sig_node.text.decode('utf8') if isinstance(sig_node.text, bytes) else str(sig_node.text)
                    signature = sig_text
                
                # Get docstring
                docstring = None
                if 'docstring' in caps:
                    doc_node = caps['docstring']
                    doc_text = doc_node.text.decode('utf8') if isinstance(doc_node.text, bytes) else str(doc_node.text)
                    docstring = doc_text.strip('"\'\n ')
                
                symbol = Symbol(
                    name=name,
                    kind=kind,
                    line_start=node.start_point[0] + 1,  # 1-indexed
                    line_end=node.end_point[0] + 1,
                    column_start=node.start_point[1],
                    column_end=node.end_point[1],
                    signature=signature,
                    docstring=docstring
                )
                symbols.append(symbol)
        
        # Fallback: use tree traversal for languages without queries
        if not symbols:
            symbols = self._fallback_symbol_extraction(tree, language, content)
        
        # Build parent-child relationships
        self._build_symbol_hierarchy(symbols, content)
        
        return symbols
    
    def _fallback_symbol_extraction(self, tree: Tree, language: str, content: str) -> List[Symbol]:
        """Fallback symbol extraction using tree traversal."""
        symbols = []
        content_bytes = bytes(content, 'utf8')
        
        # Language-specific node types
        definition_types = {
            'python': ['function_definition', 'class_definition', 'method_definition'],
            'javascript': ['function_declaration', 'method_definition', 'class_declaration', 'arrow_function'],
            'typescript': ['function_declaration', 'method_definition', 'class_declaration', 'arrow_function'],
            'go': ['function_declaration', 'method_declaration', 'type_declaration'],
            'rust': ['function_item', 'impl_item', 'trait_item', 'struct_item', 'enum_item'],
        }
        
        target_types = definition_types.get(language, [])
        
        def traverse(node: Node):
            if node.type in target_types:
                # Find name node
                name_node = None
                for child in node.children:
                    if child.type in ['identifier', 'name', 'type_identifier']:
                        name_node = child
                        break
                
                if name_node:
                    name = content_bytes[name_node.start_byte:name_node.end_byte].decode('utf8')
                    kind = 'function'
                    if 'class' in node.type or 'struct' in node.type or 'enum' in node.type or 'trait' in node.type:
                        kind = 'class'
                    elif 'method' in node.type:
                        kind = 'method'
                    
                    # Extract signature (first line of definition)
                    start_line = node.start_point[0]
                    lines = content.split('\n')
                    signature = None
                    if start_line < len(lines):
                        line = lines[start_line]
                        # Extract up to 200 chars for signature
                        signature = line[:200].strip()
                    
                    symbol = Symbol(
                        name=name,
                        kind=kind,
                        line_start=node.start_point[0] + 1,
                        line_end=node.end_point[0] + 1,
                        column_start=node.start_point[1],
                        column_end=node.end_point[1],
                        signature=signature
                    )
                    symbols.append(symbol)
            
            for child in node.children:
                traverse(child)
        
        traverse(tree.root_node)
        return symbols
    
    def _build_symbol_hierarchy(self, symbols: List[Symbol], content: str) -> None:
        """Build parent-child relationships between symbols based on line ranges."""
        content.split('\n')
        
        for i, symbol in enumerate(symbols):
            # Find potential parent (enclosing symbol)
            for j in range(i - 1, -1, -1):
                parent = symbols[j]
                if (parent.line_start <= symbol.line_start and 
                    parent.line_end and symbol.line_end and
                    parent.line_end >= symbol.line_end and
                    parent.kind in ['class', 'function', 'method']):
                    symbol.parent_name = parent.name
                    break
    
    def extract_imports(self, tree: Tree, path: Path, language: str, content: str) -> List[Import]:
        """
        Extract import statements.
        
        Args:
            tree: Parsed AST
            path: File path
            language: Programming language
            content: File content
        
        Returns:
            List of imports
        """
        imports = []
        query = self.language_support._load_query(language, 'imports')
        
        if query:
            captures = query.captures(tree.root_node) # type: ignore
            
            for capture in captures:
                node = capture[0]
                capture[1]
                
                raw_text = node.text.decode('utf8') if isinstance(node.text, bytes) else str(node.text)
                
                # Parse import based on capture name and language
                module, name, alias = self._parse_import_node(node, raw_text, language)
                
                imp = Import(
                    module=module,
                    name=name,
                    alias=alias,
                    line=node.start_point[0] + 1,
                    raw_text=raw_text.strip()
                )
                imports.append(imp)
        else:
            # Fallback import extraction
            imports = self._fallback_import_extraction(tree, language, content)
        
        return imports
    
    def _parse_import_node(self, node: Node, raw_text: str, language: str) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        """Parse import node into module, name, alias components."""
        module = None
        name = None
        alias = None
        
        if language == 'python':
            # Handle: import X, from X import Y, import X as Y, from X import Y as Z
            if 'import' in raw_text:
                if raw_text.startswith('from'):
                    # from X import Y [as Z]
                    parts = raw_text.replace('from', '').strip().split(' import ')
                    if len(parts) == 2:
                        module = parts[0].strip()
                        rest = parts[1].strip()
                        if ' as ' in rest:
                            name_part, alias = rest.split(' as ')
                            name = name_part.strip()
                        else:
                            name = rest.strip()
                else:
                    # import X [as Y]
                    rest = raw_text.replace('import', '').strip()
                    if ' as ' in rest:
                        name_part, alias = rest.split(' as ')
                        module = name_part.strip()
                    else:
                        module = rest.strip()
        
        elif language in ['javascript', 'typescript']:
            # Handle: import X from 'Y', import { X } from 'Y', import * as X from 'Y'
            match = re.search(r"from\s+['\"](.+?)['\"]", raw_text)
            if match:
                module = match.group(1)
            
            match = re.search(r"import\s+(\{[^}]+\}|\*\s+as\s+\w+|\w+)", raw_text)
            if match:
                name = match.group(1).strip()
        
        elif language == 'go':
            # Handle: import "X", import alias "X", import ( ... )
            match = re.search(r'import\s+(?:\(\s*)?(\w+\s+)?["`]([^"`]+)', raw_text)
            if match:
                alias = match.group(1).strip() if match.group(1) else None
                module = match.group(2)
        
        elif language == 'rust':
            # Handle: use X::Y, use X::Y as Z, use X::*
            if raw_text.startswith('use '):
                rest = raw_text[4:].strip()
                if ' as ' in rest:
                    path, alias = rest.split(' as ')
                    module = path.strip()
                else:
                    module = rest.strip()
        
        elif language == 'cpp':
            # Handle: #include "file.h" or #include <lib.h>
            # The raw_text will be the full #include line or the captured path
            match = re.search(r'#include\s+["<]([^">]+)[">]', raw_text)
            if match:
                module = match.group(1)
            elif not raw_text.startswith('#'):
                # If we captured just the path
                module = raw_text.strip('">< ')
        
        return module, name, alias
    
    def _fallback_import_extraction(self, tree: Tree, language: str, content: str) -> List[Import]:
        """Fallback import extraction using tree traversal."""
        imports = []
        content_bytes = bytes(content, 'utf8')
        
        # Language-specific import patterns
        import_types = {
            'python': ['import_statement', 'import_from_statement'],
            'javascript': ['import_statement'],
            'typescript': ['import_statement'],
            'go': ['import_declaration'],
            'rust': ['use_declaration'],
        }
        
        target_types = import_types.get(language, [])
        
        def traverse(node: Node):
            if node.type in target_types:
                raw_text = content_bytes[node.start_byte:node.end_byte].decode('utf8')
                module, name, alias = self._parse_import_node(node, raw_text, language)
                
                imports.append(Import(
                    module=module,
                    name=name,
                    alias=alias,
                    line=node.start_point[0] + 1,
                    raw_text=raw_text.strip()
                ))
            
            for child in node.children:
                traverse(child)
        
        traverse(tree.root_node)
        return imports
    
    def extract_callsites(self, tree: Tree, path: Path, language: str, content: str, symbols: List[Symbol]) -> List[Callsite]:
        """
        Extract function/method call sites.
        
        Args:
            tree: Parsed AST
            path: File path
            language: Programming language
            content: File content
            symbols: Extracted symbols (for scope determination)
        
        Returns:
            List of callsites
        """
        callsites = []
        query = self.language_support._load_query(language, 'calls')
        
        if query:
            captures = query.captures(tree.root_node) # type: ignore
            
            for capture in captures:
                node = capture[0]
                capture[1]
                
                callee_text = node.text.decode('utf8') if isinstance(node.text, bytes) else str(node.text)
                line = node.start_point[0] + 1
                column = node.start_point[1]
                
                # Determine containing symbol (scope)
                scope_symbol_id = self._find_containing_symbol(line, symbols)
                
                # Calculate confidence based on what we know
                confidence = self._calculate_call_confidence(callee_text, language)
                
                callsite = Callsite(
                    callee_text=callee_text,
                    line=line,
                    column=column,
                    scope_symbol_id=scope_symbol_id,
                    confidence=confidence
                )
                callsites.append(callsite)
        else:
            # Fallback callsite extraction
            callsites = self._fallback_callsite_extraction(tree, language, content, symbols)
        
        return callsites
    
    def _find_containing_symbol(self, line: int, symbols: List[Symbol]) -> Optional[str]:
        """Find the symbol that contains the given line."""
        # Find innermost containing symbol
        best_match = None
        for symbol in symbols:
            if symbol.line_start <= line:
                if symbol.line_end is None or symbol.line_end >= line:
                    # Prefer more specific (later starting) symbols
                    if best_match is None or symbol.line_start > best_match.line_start:
                        best_match = symbol
        
        return best_match.symbol_id if best_match else None
    
    def _calculate_call_confidence(self, callee_text: str, language: str) -> float:
        """Calculate confidence score for a call target."""
        confidence = 0.5  # Base confidence
        
        # Boost confidence for qualified names (obj.method, pkg.Function)
        if '.' in callee_text:
            confidence += 0.2
        
        # Boost for simple identifiers
        if re.match(r'^[a-zA-Z_]\w*$', callee_text):
            confidence += 0.1
        
        # Cap at 1.0
        return min(confidence, 1.0)
    
    def _fallback_callsite_extraction(self, tree: Tree, language: str, content: str, symbols: List[Symbol]) -> List[Callsite]:
        """Fallback callsite extraction using tree traversal."""
        callsites = []
        content_bytes = bytes(content, 'utf8')
        
        # Language-specific call patterns
        call_types = {
            'python': ['call'],
            'javascript': ['call_expression'],
            'typescript': ['call_expression'],
            'go': ['call_expression'],
            'rust': ['call_expression'],
        }
        
        target_types = call_types.get(language, [])
        
        def traverse(node: Node):
            if node.type in target_types:
                # Find the function being called
                callee_node = None
                for child in node.children:
                    if child.type not in ['(', ')', 'argument_list', 'arguments']:
                        callee_node = child
                        break
                
                if callee_node:
                    callee_text = content_bytes[callee_node.start_byte:callee_node.end_byte].decode('utf8')
                    line = node.start_point[0] + 1
                    column = node.start_point[1]
                    scope_symbol_id = self._find_containing_symbol(line, symbols)
                    confidence = self._calculate_call_confidence(callee_text, language)
                    
                    callsites.append(Callsite(
                        callee_text=callee_text,
                        line=line,
                        column=column,
                        scope_symbol_id=scope_symbol_id,
                        confidence=confidence
                    ))
            
            for child in node.children:
                traverse(child)
        
        traverse(tree.root_node)
        return callsites


# Convenience function for indexer integration
def parse_file(path: Path, content: Optional[str] = None, queries_dir: Optional[Path] = None) -> Optional[ParseResult]:
    """
    Parse a file and extract symbols, imports, and callsites.
    
    This is a convenience function for the indexer module.
    
    Args:
        path: Path to the file
        content: Optional file content
        queries_dir: Directory containing .scm query files
    
    Returns:
        ParseResult or None if parsing failed/unsupported
    """
    parser = TreeSitterParser(queries_dir)
    return parser.parse_file(path, content)
