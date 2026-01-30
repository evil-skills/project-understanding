"""
LSP (Language Server Protocol) Provider for semantic analysis.

Supports multiple language servers:
- TypeScript: typescript-language-server
- Python: pyright or pylsp
- Go: gopls
- Rust: rust-analyzer
- Java: jdtls (optional)
"""

import json
import subprocess
import time
from pathlib import Path
from typing import Any, Dict, List, Optional
import threading

from .base import (
    SemanticProvider, Position, Range, Location, SymbolInfo,
    CallSite, ImportInfo, EdgeConfidence
)


class LSPClient:
    """JSON-RPC client for communicating with LSP servers."""
    
    def __init__(self, command: List[str], workspace: Path, verbose: bool = False):
        self.command = command
        self.workspace = workspace
        self.verbose = verbose
        self.process: Optional[subprocess.Popen] = None
        self._message_id = 0
        self._responses: Dict[int, Any] = {}
        self._lock = threading.Lock()
        self._reader_thread: Optional[threading.Thread] = None
        self._initialized = False
    
    def _log(self, message: str) -> None:
        if self.verbose:
            print(f"[LSPClient] {message}")
    
    def start(self) -> bool:
        """Start the LSP server process."""
        try:
            self.process = subprocess.Popen(
                self.command,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=str(self.workspace)
            )
            
            # Start reader thread
            self._reader_thread = threading.Thread(target=self._read_responses, daemon=True)
            self._reader_thread.start()
            
            # Initialize handshake
            self._initialize()
            self._initialized = True
            return True
            
        except Exception as e:
            self._log(f"Failed to start LSP server: {e}")
            return False
    
    def stop(self) -> None:
        """Stop the LSP server."""
        if self.process and self._initialized:
            try:
                self._send_request("shutdown", {})
                self._send_notification("exit", {})
                self.process.wait(timeout=5)
            except Exception as e:
                self._log(f"Error stopping LSP: {e}")
                if self.process:
                    self.process.terminate()
        
        self._initialized = False
    
    def _send_request(self, method: str, params: Dict[str, Any]) -> Optional[Any]:
        """Send a JSON-RPC request and wait for response."""
        with self._lock:
            self._message_id += 1
            msg_id = self._message_id
        
        message = {
            "jsonrpc": "2.0",
            "id": msg_id,
            "method": method,
            "params": params
        }
        
        self._send_message(message)
        
        # Wait for response with timeout
        for _ in range(100):  # 10 second timeout
            with self._lock:
                if msg_id in self._responses:
                    return self._responses.pop(msg_id)
            time.sleep(0.1)
        
        return None
    
    def _send_notification(self, method: str, params: Dict[str, Any]) -> None:
        """Send a JSON-RPC notification (no response expected)."""
        message = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params
        }
        self._send_message(message)
    
    def _send_message(self, message: Dict[str, Any]) -> None:
        """Send a message to the LSP server."""
        if not self.process or not self.process.stdin:
            return
        
        content = json.dumps(message)
        headers = f"Content-Length: {len(content)}\r\n\r\n"
        full_message = headers + content
        
        try:
            self.process.stdin.write(full_message.encode('utf-8'))
            self.process.stdin.flush()
        except Exception as e:
            self._log(f"Error sending message: {e}")
    
    def _read_responses(self) -> None:
        """Read responses from LSP server."""
        while self.process and self.process.poll() is None:
            try:
                # Read headers
                headers = b""
                while True:
                    byte = self.process.stdout.read(1)
                    if not byte:
                        break
                    headers += byte
                    if headers.endswith(b"\r\n\r\n"):
                        break
                
                # Parse Content-Length
                content_length = 0
                for line in headers.decode('utf-8', errors='ignore').split('\r\n'):
                    if line.startswith('Content-Length:'):
                        content_length = int(line.split(':')[1].strip())
                
                # Read content
                if content_length > 0:
                    content = self.process.stdout.read(content_length)
                    message = json.loads(content.decode('utf-8'))
                    
                    if 'id' in message:
                        with self._lock:
                            self._responses[message['id']] = message.get('result')
                    
            except Exception as e:
                self._log(f"Error reading response: {e}")
    
    def _initialize(self) -> None:
        """Send initialize request."""
        params = {
            "processId": None,
            "rootUri": self.workspace.as_uri() if hasattr(self.workspace, 'as_uri') else f"file://{self.workspace}",
            "capabilities": {
                "textDocumentSync": {
                    "openClose": True,
                    "change": 1
                },
                "definitionProvider": True,
                "referencesProvider": True,
                "documentSymbolProvider": True,
                "workspaceSymbolProvider": True,
                "callHierarchyProvider": True
            }
        }
        
        result = self._send_request("initialize", params)
        if result:
            self._send_notification("initialized", {})
            self._log("LSP server initialized")
    
    def open_document(self, file_path: Path, language_id: str, content: str) -> None:
        """Open a document in the LSP server."""
        uri = f"file://{file_path}"
        params = {
            "textDocument": {
                "uri": uri,
                "languageId": language_id,
                "version": 1,
                "text": content
            }
        }
        self._send_notification("textDocument/didOpen", params)
    
    def get_definition(self, file_path: Path, line: int, character: int) -> List[Dict[str, Any]]:
        """Get definition locations."""
        uri = f"file://{file_path}"
        params = {
            "textDocument": {"uri": uri},
            "position": {"line": line, "character": character}
        }
        
        result = self._send_request("textDocument/definition", params)
        if not result:
            return []
        
        # Handle both single result and array
        if isinstance(result, list):
            return result
        return [result]
    
    def get_references(self, file_path: Path, line: int, character: int) -> List[Dict[str, Any]]:
        """Get reference locations."""
        uri = f"file://{file_path}"
        params = {
            "textDocument": {"uri": uri},
            "position": {"line": line, "character": character},
            "context": {"includeDeclaration": False}
        }
        
        result = self._send_request("textDocument/references", params)
        return result if result else []
    
    def get_document_symbols(self, file_path: Path) -> List[Dict[str, Any]]:
        """Get all symbols in a document."""
        uri = f"file://{file_path}"
        params = {"textDocument": {"uri": uri}}
        
        result = self._send_request("textDocument/documentSymbol", params)
        return result if result else []
    
    def get_workspace_symbols(self, query: str) -> List[Dict[str, Any]]:
        """Search workspace symbols."""
        params = {"query": query}
        result = self._send_request("workspace/symbol", params)
        return result if result else []
    
    def get_call_hierarchy(self, file_path: Path, line: int, character: int, direction: str) -> List[Dict[str, Any]]:
        """Get call hierarchy."""
        uri = f"file://{file_path}"
        
        # First, prepare call hierarchy
        params = {
            "textDocument": {"uri": uri},
            "position": {"line": line, "character": character}
        }
        
        items = self._send_request("textDocument/prepareCallHierarchy", params)
        if not items:
            return []
        
        if not isinstance(items, list):
            items = [items]
        
        results = []
        for item in items:
            if direction in ("incoming", "both"):
                incoming = self._send_request("callHierarchy/incomingCalls", {"item": item})
                if incoming:
                    results.extend(incoming if isinstance(incoming, list) else [incoming])
            
            if direction in ("outgoing", "both"):
                outgoing = self._send_request("callHierarchy/outgoingCalls", {"item": item})
                if outgoing:
                    results.extend(outgoing if isinstance(outgoing, list) else [outgoing])
        
        return results


def get_default_lsp_configs() -> Dict[str, Dict[str, Any]]:
    """Get default LSP server configurations."""
    return {
        "typescript": {
            "command": ["typescript-language-server", "--stdio"],
            "language_id": "typescript",
            "extensions": [".ts", ".tsx", ".js", ".jsx"]
        },
        "python": {
            "command": ["pyright-langserver", "--stdio"],
            "language_id": "python",
            "extensions": [".py"]
        },
        "go": {
            "command": ["gopls"],
            "language_id": "go",
            "extensions": [".go"]
        },
        "rust": {
            "command": ["rust-analyzer"],
            "language_id": "rust",
            "extensions": [".rs"]
        },
        "java": {
            "command": ["jdtls"],
            "language_id": "java",
            "extensions": [".java"]
        }
    }


class LSPProvider(SemanticProvider):
    """
    LSP-based semantic provider.
    
    Manages multiple LSP clients for different languages.
    """
    
    def __init__(self, repo_root: Path, configs: Dict[str, Dict[str, Any]], verbose: bool = False):
        super().__init__(repo_root, verbose)
        self.configs = configs
        self.clients: Dict[str, LSPClient] = {}
        self._name = "lsp"
    
    def initialize(self) -> "LSPProvider":
        """Initialize all LSP clients."""
        self._log("Initializing LSP provider")
        
        for lang, config in self.configs.items():
            client = LSPClient(
                command=config["command"],
                workspace=self.repo_root,
                verbose=self.verbose
            )
            
            if client.start():
                self.clients[lang] = client
                self._log(f"Started LSP server for {lang}")
            else:
                self._log(f"Failed to start LSP server for {lang}")
        
        self._initialized = True
        return self
    
    def shutdown(self) -> None:
        """Shutdown all LSP clients."""
        for lang, client in self.clients.items():
            self._log(f"Stopping LSP server for {lang}")
            client.stop()
        self.clients.clear()
    
    def _get_client_for_file(self, file: Path) -> Optional[LSPClient]:
        """Get appropriate LSP client for a file."""
        ext = file.suffix.lower()
        
        for lang, config in self.configs.items():
            if ext in config.get("extensions", []):
                return self.clients.get(lang)
        
        return None
    
    def _lsp_location_to_location(self, loc: Dict[str, Any]) -> Optional[Location]:
        """Convert LSP location to our Location type."""
        try:
            uri = loc.get("uri", "")
            if uri.startswith("file://"):
                file_path = uri[7:]
            else:
                file_path = uri
            
            rng = loc.get("range", {})
            start = rng.get("start", {})
            end = rng.get("end", {})
            
            return Location(
                file=file_path,
                range=Range(
                    start=Position(line=start.get("line", 0), character=start.get("character", 0)),
                    end=Position(line=end.get("line", 0), character=end.get("character", 0))
                )
            )
        except Exception as e:
            self._log(f"Error converting LSP location: {e}")
            return None
    
    def _lsp_symbol_to_symbol_info(self, sym: Dict[str, Any]) -> Optional[SymbolInfo]:
        """Convert LSP symbol to our SymbolInfo type."""
        try:
            loc = sym.get("location", {})
            uri = loc.get("uri", "")
            if uri.startswith("file://"):
                file_path = uri[7:]
            else:
                file_path = uri
            
            rng = loc.get("range", {})
            start = rng.get("start", {})
            end = rng.get("end", {})
            
            # Build unique ID
            symbol_id = f"{file_path}:{sym.get('name')}:{start.get('line', 0)}"
            
            return SymbolInfo(
                id=symbol_id,
                name=sym.get("name", ""),
                kind=sym.get("kind", "unknown"),
                location=Location(
                    file=file_path,
                    range=Range(
                        start=Position(line=start.get("line", 0), character=start.get("character", 0)),
                        end=Position(line=end.get("line", 0), character=end.get("character", 0))
                    )
                ),
                signature=sym.get("detail"),
                docstring=None  # LSP doesn't always provide this directly
            )
        except Exception as e:
            self._log(f"Error converting LSP symbol: {e}")
            return None
    
    def get_definitions(self, file: Path, position: Position) -> List[SymbolInfo]:
        """Get symbol definitions at position."""
        client = self._get_client_for_file(file)
        if not client:
            return []
        
        # Open document if not already open
        try:
            content = file.read_text()
            lang = None
            for lang_key, config in self.configs.items():
                if file.suffix.lower() in config.get("extensions", []):
                    lang = config["language_id"]
                    break
            
            if lang:
                client.open_document(file, lang, content)
        except Exception as e:
            self._log(f"Error opening document: {e}")
        
        locations = client.get_definition(file, position.line, position.character)
        
        results = []
        for loc in locations:
            symbol = self._lsp_symbol_to_symbol_info({
                "location": loc,
                "name": "definition",
                "kind": "unknown"
            })
            if symbol:
                results.append(symbol)
        
        return results
    
    def get_references(self, symbol_id: str) -> List[Location]:
        """Get all references to a symbol."""
        # Parse symbol_id to get file and position
        parts = symbol_id.rsplit(":", 2)
        if len(parts) < 2:
            return []
        
        try:
            file_path = Path(parts[0])
            line = int(parts[-1])
        except (ValueError, IndexError):
            return []
        
        client = self._get_client_for_file(file_path)
        if not client:
            return []
        
        locations = client.get_references(file_path, line, 0)
        
        results = []
        for loc in locations:
            location = self._lsp_location_to_location(loc)
            if location:
                results.append(location)
        
        return results
    
    def get_call_hierarchy(self, symbol_id: str, direction: str = "both") -> Dict[str, List[CallSite]]:
        """Get call hierarchy for a symbol."""
        # Parse symbol_id
        parts = symbol_id.rsplit(":", 2)
        if len(parts) < 2:
            return {"incoming": [], "outgoing": []}
        
        try:
            file_path = Path(parts[0])
            line = int(parts[-1])
        except (ValueError, IndexError):
            return {"incoming": [], "outgoing": []}
        
        client = self._get_client_for_file(file_path)
        if not client:
            return {"incoming": [], "outgoing": []}
        
        calls = client.get_call_hierarchy(file_path, line, 0, direction)
        
        incoming = []
        outgoing = []
        
        for call in calls:
            from_ranges = call.get("fromRanges", [])
            from_ = call.get("from", {})
            to = call.get("to", {})
            
            # Convert to CallSite objects
            if direction in ("incoming", "both") and from_:
                caller = self._lsp_symbol_to_symbol_info(from_)
                callee = self._lsp_symbol_to_symbol_info(to) if to else None
                if caller:
                    for rng in from_ranges:
                        loc = self._lsp_location_to_location({"uri": from_.get("uri"), "range": rng})
                        if loc:
                            incoming.append(CallSite(
                                caller=caller,
                                callee=callee or caller,  # Fallback
                                location=loc,
                                confidence=EdgeConfidence.RESOLVED
                            ))
            
            if direction in ("outgoing", "both") and to:
                caller = self._lsp_symbol_to_symbol_info(from_) if from_ else None
                callee = self._lsp_symbol_to_symbol_info(to)
                if callee:
                    for rng in from_ranges if from_ranges else [{}]:
                        loc = self._lsp_location_to_location({"uri": from_.get("uri", ""), "range": rng})
                        if loc:
                            outgoing.append(CallSite(
                                caller=caller or callee,  # Fallback
                                callee=callee,
                                location=loc,
                                confidence=EdgeConfidence.RESOLVED
                            ))
        
        return {"incoming": incoming, "outgoing": outgoing}
    
    def resolve_imports(self, file: Path) -> List[ImportInfo]:
        """Resolve imports using LSP."""
        # LSP doesn't have a direct "get imports" method
        # This would need to be done via Tree-sitter parsing
        self._log("Import resolution via LSP not directly supported")
        return []
    
    def get_document_symbols(self, file: Path) -> List[SymbolInfo]:
        """Get all symbols in a document."""
        client = self._get_client_for_file(file)
        if not client:
            return []
        
        symbols = client.get_document_symbols(file)
        
        results = []
        for sym in symbols:
            info = self._lsp_symbol_to_symbol_info(sym)
            if info:
                results.append(info)
        
        return results
    
    @property
    def name(self) -> str:
        return self._name
    
    @property
    def supported_languages(self) -> List[str]:
        return list(self.configs.keys())
    
    def is_available(self) -> bool:
        return len(self.clients) > 0
