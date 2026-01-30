"""
Module Dependency Analysis for Project Understanding.

Parses package manifests and creates module-level dependency graphs.
Supports:
- JavaScript/TypeScript: package.json workspaces
- Python: pyproject.toml, requirements.txt
- Go: go.mod
- Rust: Cargo.toml workspaces
"""

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple


@dataclass
class ModuleNode:
    """Represents a module/package in the dependency graph."""
    id: str
    name: str
    type: str  # 'package', 'workspace', 'crate', 'module'
    language: str
    path: Path
    version: Optional[str] = None
    description: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __hash__(self):
        return hash(self.id)
    
    def __eq__(self, other):
        if isinstance(other, ModuleNode):
            return self.id == other.id
        return False


@dataclass
class ModuleEdge:
    """Represents a dependency relationship between modules."""
    source: str
    target: str
    kind: str  # 'MODULE_DEPENDS_ON', 'EXPORTS_TO', 'IMPORTS_FROM', 'DEV_DEPENDS_ON'
    version_constraint: Optional[str] = None
    is_optional: bool = False
    is_dev: bool = False
    
    def __hash__(self):
        return hash((self.source, self.target, self.kind))
    
    def __eq__(self, other):
        if isinstance(other, ModuleEdge):
            return (self.source, self.target, self.kind) == (other.source, other.target, other.kind)
        return False


class ModuleParser:
    """Base class for module manifest parsers."""
    
    def __init__(self, repo_root: Path):
        self.repo_root = repo_root
    
    def can_parse(self, file_path: Path) -> bool:
        """Check if this parser can handle the given file."""
        raise NotImplementedError
    
    def parse(self, file_path: Path) -> Tuple[Optional[ModuleNode], List[ModuleEdge]]:
        """
        Parse a manifest file.
        
        Returns:
            Tuple of (module_node, edges) where edges are dependencies
        """
        raise NotImplementedError


class JavaScriptModuleParser(ModuleParser):
    """Parser for package.json files."""
    
    def can_parse(self, file_path: Path) -> bool:
        return file_path.name == "package.json"
    
    def parse(self, file_path: Path) -> Tuple[Optional[ModuleNode], List[ModuleEdge]]:
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except (json.JSONDecodeError, IOError):
            return None, []
        
        # Check if it's a workspace root
        is_workspace = 'workspaces' in data
        
        module = ModuleNode(
            id=f"js:{data.get('name', file_path.parent.name)}",
            name=data.get('name', file_path.parent.name),
            type='workspace' if is_workspace else 'package',
            language='javascript',
            path=file_path.parent,
            version=data.get('version'),
            description=data.get('description'),
            metadata={
                'main': data.get('main'),
                'scripts': list(data.get('scripts', {}).keys()),
                'is_workspace': is_workspace,
                'private': data.get('private', False)
            }
        )
        
        edges = []
        module_id = module.id
        
        # Parse dependencies
        for dep_type, is_dev in [('dependencies', False), ('devDependencies', True), ('peerDependencies', False)]:
            deps = data.get(dep_type, {})
            for dep_name, version in deps.items():
                edges.append(ModuleEdge(
                    source=module_id,
                    target=f"js:{dep_name}",
                    kind='DEV_DEPENDS_ON' if is_dev else 'MODULE_DEPENDS_ON',
                    version_constraint=version,
                    is_dev=is_dev
                ))
        
        # Parse workspaces
        if is_workspace:
            workspaces = data.get('workspaces', [])
            if isinstance(workspaces, dict):
                workspaces = workspaces.get('packages', [])
            
            for pattern in workspaces:
                # Resolve workspace patterns
                workspace_paths = self._resolve_workspace_pattern(file_path.parent, pattern)
                for ws_path in workspace_paths:
                    ws_module, ws_edges = self.parse(ws_path / "package.json")
                    if ws_module:
                        # Add workspace relationship
                        edges.append(ModuleEdge(
                            source=module_id,
                            target=ws_module.id,
                            kind='EXPORTS_TO'
                        ))
                        edges.append(ModuleEdge(
                            source=ws_module.id,
                            target=module_id,
                            kind='IMPORTS_FROM'
                        ))
                        edges.extend(ws_edges)
        
        return module, edges
    
    def _resolve_workspace_pattern(self, root: Path, pattern: str) -> List[Path]:
        """Resolve a workspace glob pattern to actual paths."""
        import fnmatch
        
        results = []
        # Handle simple glob patterns like "packages/*"
        if '*' in pattern:
            base = pattern.split('*')[0].rstrip('/')
            base_path = root / base
            if base_path.exists():
                for item in base_path.iterdir():
                    if item.is_dir() and (item / "package.json").exists():
                        results.append(item)
        else:
            # Direct path
            direct = root / pattern
            if direct.exists() and direct.is_dir():
                results.append(direct)
        
        return results


class PythonModuleParser(ModuleParser):
    """Parser for Python pyproject.toml and requirements.txt files."""
    
    def can_parse(self, file_path: Path) -> bool:
        return file_path.name in ("pyproject.toml", "requirements.txt", "setup.py")
    
    def parse(self, file_path: Path) -> Tuple[Optional[ModuleNode], List[ModuleEdge]]:
        if file_path.name == "pyproject.toml":
            return self._parse_pyproject(file_path)
        elif file_path.name == "requirements.txt":
            return self._parse_requirements(file_path)
        elif file_path.name == "setup.py":
            return self._parse_setup_py(file_path)
        return None, []
    
    def _parse_pyproject(self, file_path: Path) -> Tuple[Optional[ModuleNode], List[ModuleEdge]]:
        try:
            import tomllib
        except ImportError:
            try:
                import tomli as tomllib
            except ImportError:
                # Fallback to basic parsing
                return self._parse_pyproject_fallback(file_path)
        
        try:
            with open(file_path, 'rb') as f:
                data = tomllib.load(f)
        except Exception:
            return None, []
        
        # Get project info
        project = data.get('project', {})
        tool_poetry = data.get('tool', {}).get('poetry', {})
        
        # Try poetry first, then standard
        name = tool_poetry.get('name') or project.get('name')
        version = tool_poetry.get('version') or project.get('version')
        description = project.get('description')
        
        if not name:
            name = file_path.parent.name
        
        module = ModuleNode(
            id=f"py:{name}",
            name=name,
            type='package',
            language='python',
            path=file_path.parent,
            version=version,
            description=description,
            metadata={
                'build_system': list(data.get('build-system', {}).get('requires', [])),
                'is_poetry': bool(tool_poetry)
            }
        )
        
        edges = []
        
        # Parse dependencies from project
        deps = project.get('dependencies', [])
        if isinstance(deps, list):
            for dep in deps:
                dep_name = dep.split(';')[0].strip() if ';' in dep else dep
                version_spec = None
                if any(c in dep_name for c in '<>=!'):
                    match = re.match(r'^([a-zA-Z0-9_-]+)\s*(.*)$', dep_name)
                    if match:
                        dep_name = match.group(1)
                        version_spec = match.group(2).strip()
                
                edges.append(ModuleEdge(
                    source=module.id,
                    target=f"py:{dep_name}",
                    kind='MODULE_DEPENDS_ON',
                    version_constraint=version_spec
                ))
        
        # Parse poetry dependencies
        poetry_deps = tool_poetry.get('dependencies', {})
        for dep_name, version in poetry_deps.items():
            if dep_name == 'python':
                continue
            version_str = str(version) if not isinstance(version, dict) else None
            edges.append(ModuleEdge(
                source=module.id,
                target=f"py:{dep_name}",
                kind='MODULE_DEPENDS_ON',
                version_constraint=version_str
            ))
        
        # Parse dev dependencies
        dev_deps = project.get('optional-dependencies', {})
        for group, group_deps in dev_deps.items():
            for dep in group_deps:
                dep_name = dep.split(';')[0].strip() if ';' in dep else dep
                edges.append(ModuleEdge(
                    source=module.id,
                    target=f"py:{dep_name}",
                    kind='DEV_DEPENDS_ON',
                    is_dev=True
                ))
        
        return module, edges
    
    def _parse_pyproject_fallback(self, file_path: Path) -> Tuple[Optional[ModuleNode], List[ModuleEdge]]:
        """Fallback parser when tomllib is not available."""
        try:
            content = file_path.read_text()
        except IOError:
            return None, []
        
        name_match = re.search(r'^name\s*=\s*"([^"]+)"', content, re.MULTILINE)
        version_match = re.search(r'^version\s*=\s*"([^"]+)"', content, re.MULTILINE)
        
        name = name_match.group(1) if name_match else file_path.parent.name
        
        module = ModuleNode(
            id=f"py:{name}",
            name=name,
            type='package',
            language='python',
            path=file_path.parent,
            version=version_match.group(1) if version_match else None
        )
        
        edges = []
        
        # Extract dependencies with simple regex
        for match in re.finditer(r'^([a-zA-Z0-9_-]+)\s*[=<>!]+\s*([^\s,]+)', content, re.MULTILINE):
            dep_name = match.group(1)
            version = match.group(2)
            edges.append(ModuleEdge(
                source=module.id,
                target=f"py:{dep_name}",
                kind='MODULE_DEPENDS_ON',
                version_constraint=version
            ))
        
        return module, edges
    
    def _parse_requirements(self, file_path: Path) -> Tuple[Optional[ModuleNode], List[ModuleEdge]]:
        try:
            with open(file_path, 'r') as f:
                lines = f.readlines()
        except IOError:
            return None, []
        
        # Create a virtual module for requirements.txt
        module = ModuleNode(
            id=f"py:req:{file_path.parent.name}",
            name=file_path.parent.name,
            type='requirements',
            language='python',
            path=file_path.parent,
            metadata={'source': str(file_path)}
        )
        
        edges = []
        
        for line in lines:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            
            # Parse requirement spec
            # Handle: package>=1.0, package==1.0, -r other.txt, git+https://...
            if line.startswith('-'):
                continue  # Skip options
            
            # Match package name and version
            match = re.match(r'^([a-zA-Z0-9_.-]+)\s*([<>=!~]+.+)?$', line)
            if match:
                dep_name = match.group(1)
                version = match.group(2).strip() if match.group(2) else None
                edges.append(ModuleEdge(
                    source=module.id,
                    target=f"py:{dep_name}",
                    kind='MODULE_DEPENDS_ON',
                    version_constraint=version
                ))
        
        return module, edges
    
    def _parse_setup_py(self, file_path: Path) -> Tuple[Optional[ModuleNode], List[ModuleEdge]]:
        try:
            content = file_path.read_text()
        except IOError:
            return None, []
        
        # Extract name and version with regex
        name_match = re.search(r'name\s*=\s*["\']([^"\']+)["\']', content)
        version_match = re.search(r'version\s*=\s*["\']([^"\']+)["\']', content)
        
        name = name_match.group(1) if name_match else file_path.parent.name
        
        module = ModuleNode(
            id=f"py:{name}",
            name=name,
            type='package',
            language='python',
            path=file_path.parent,
            version=version_match.group(1) if version_match else None
        )
        
        edges = []
        
        # Try to find install_requires
        install_requires_match = re.search(
            r'install_requires\s*=\s*\[([^\]]+)\]',
            content,
            re.DOTALL
        )
        
        if install_requires_match:
            deps_str = install_requires_match.group(1)
            for match in re.finditer(r'["\']([a-zA-Z0-9_.-]+)([<>=!~][^"\']*)?["\']', deps_str):
                dep_name = match.group(1)
                version = match.group(2)
                edges.append(ModuleEdge(
                    source=module.id,
                    target=f"py:{dep_name}",
                    kind='MODULE_DEPENDS_ON',
                    version_constraint=version
                ))
        
        return module, edges


class GoModuleParser(ModuleParser):
    """Parser for Go go.mod files."""
    
    def can_parse(self, file_path: Path) -> bool:
        return file_path.name == "go.mod"
    
    def parse(self, file_path: Path) -> Tuple[Optional[ModuleNode], List[ModuleEdge]]:
        try:
            content = file_path.read_text()
        except IOError:
            return None, []
        
        # Extract module name
        module_match = re.search(r'^module\s+(\S+)', content, re.MULTILINE)
        if not module_match:
            return None, []
        
        module_name = module_match.group(1)
        go_version_match = re.search(r'^go\s+(\S+)', content, re.MULTILINE)
        
        module = ModuleNode(
            id=f"go:{module_name}",
            name=module_name,
            type='module',
            language='go',
            path=file_path.parent,
            metadata={'go_version': go_version_match.group(1) if go_version_match else None}
        )
        
        edges = []
        
        # Parse require blocks
        require_pattern = re.compile(r'require\s*\((.*?)\)', re.DOTALL)
        for match in require_pattern.finditer(content):
            block = match.group(1)
            for line in block.split('\n'):
                line = line.strip()
                if not line or line.startswith('//'):
                    continue
                
                parts = line.split()
                if len(parts) >= 2:
                    dep_name = parts[0]
                    version = parts[1]
                    is_indirect = '// indirect' in line
                    
                    edges.append(ModuleEdge(
                        source=module.id,
                        target=f"go:{dep_name}",
                        kind='MODULE_DEPENDS_ON',
                        version_constraint=version,
                        is_optional=is_indirect
                    ))
        
        # Parse single-line requires
        single_require_pattern = re.compile(r'^require\s+(\S+)\s+(\S+)', re.MULTILINE)
        for match in single_require_pattern.finditer(content):
            dep_name = match.group(1)
            version = match.group(2)
            
            edges.append(ModuleEdge(
                source=module.id,
                target=f"go:{dep_name}",
                kind='MODULE_DEPENDS_ON',
                version_constraint=version
            ))
        
        return module, edges


class RustModuleParser(ModuleParser):
    """Parser for Rust Cargo.toml files."""
    
    def can_parse(self, file_path: Path) -> bool:
        return file_path.name == "Cargo.toml"
    
    def parse(self, file_path: Path) -> Tuple[Optional[ModuleNode], List[ModuleEdge]]:
        try:
            import tomllib
        except ImportError:
            try:
                import tomli as tomllib
            except ImportError:
                return self._parse_cargo_fallback(file_path)
        
        try:
            with open(file_path, 'rb') as f:
                data = tomllib.load(f)
        except Exception:
            return None, []
        
        package = data.get('package', {})
        workspace = data.get('workspace', {})
        
        is_workspace = bool(workspace)
        name = package.get('name') or (file_path.parent.name if not is_workspace else None)
        
        if not name:
            # Check for workspace root
            if is_workspace:
                name = file_path.parent.name
        
        if not name:
            return None, []
        
        module = ModuleNode(
            id=f"rs:{name}",
            name=name,
            type='workspace' if is_workspace else 'crate',
            language='rust',
            path=file_path.parent,
            version=package.get('version'),
            description=package.get('description'),
            metadata={
                'edition': package.get('edition'),
                'authors': package.get('authors', []),
                'is_workspace': is_workspace
            }
        )
        
        edges = []
        
        # Parse workspace members
        if is_workspace:
            members = workspace.get('members', [])
            for member in members:
                member_paths = self._resolve_workspace_member(file_path.parent, member)
                for member_path in member_paths:
                    member_module, member_edges = self.parse(member_path / "Cargo.toml")
                    if member_module:
                        edges.append(ModuleEdge(
                            source=module.id,
                            target=member_module.id,
                            kind='EXPORTS_TO'
                        ))
                        edges.append(ModuleEdge(
                            source=member_module.id,
                            target=module.id,
                            kind='IMPORTS_FROM'
                        ))
                        edges.extend(member_edges)
            
            # Workspace dependencies
            workspace_deps = workspace.get('dependencies', {})
            for dep_name, dep_spec in workspace_deps.items():
                version = None
                if isinstance(dep_spec, str):
                    version = dep_spec
                elif isinstance(dep_spec, dict):
                    version = dep_spec.get('version')
                
                edges.append(ModuleEdge(
                    source=module.id,
                    target=f"rs:{dep_name}",
                    kind='MODULE_DEPENDS_ON',
                    version_constraint=version
                ))
        
        # Parse package dependencies
        deps = data.get('dependencies', {})
        for dep_name, dep_spec in deps.items():
            version = None
            is_optional = False
            
            if isinstance(dep_spec, str):
                version = dep_spec
            elif isinstance(dep_spec, dict):
                version = dep_spec.get('version')
                is_optional = dep_spec.get('optional', False)
            
            edges.append(ModuleEdge(
                source=module.id,
                target=f"rs:{dep_name}",
                kind='MODULE_DEPENDS_ON',
                version_constraint=version,
                is_optional=is_optional
            ))
        
        # Parse dev-dependencies
        dev_deps = data.get('dev-dependencies', {})
        for dep_name, dep_spec in dev_deps.items():
            version = dep_spec if isinstance(dep_spec, str) else dep_spec.get('version')
            edges.append(ModuleEdge(
                source=module.id,
                target=f"rs:{dep_name}",
                kind='DEV_DEPENDS_ON',
                version_constraint=version,
                is_dev=True
            ))
        
        return module, edges
    
    def _parse_cargo_fallback(self, file_path: Path) -> Tuple[Optional[ModuleNode], List[ModuleEdge]]:
        """Fallback parser when tomllib is not available."""
        try:
            content = file_path.read_text()
        except IOError:
            return None, []
        
        # Extract package name
        name_match = re.search(r'^\s*name\s*=\s*"([^"]+)"', content, re.MULTILINE)
        version_match = re.search(r'^\s*version\s*=\s*"([^"]+)"', content, re.MULTILINE)
        
        name = name_match.group(1) if name_match else file_path.parent.name
        
        module = ModuleNode(
            id=f"rs:{name}",
            name=name,
            type='crate',
            language='rust',
            path=file_path.parent,
            version=version_match.group(1) if version_match else None
        )
        
        edges = []
        
        # Extract dependencies
        in_deps = False
        for line in content.split('\n'):
            if '[dependencies]' in line:
                in_deps = True
                continue
            if '[' in line and 'dependencies' not in line:
                in_deps = False
                continue
            
            if in_deps:
                match = re.match(r'^\s*([a-zA-Z0-9_-]+)\s*=\s*"?([^"\s]+)"?', line)
                if match:
                    dep_name = match.group(1)
                    version = match.group(2)
                    edges.append(ModuleEdge(
                        source=module.id,
                        target=f"rs:{dep_name}",
                        kind='MODULE_DEPENDS_ON',
                        version_constraint=version
                    ))
        
        return module, edges
    
    def _resolve_workspace_member(self, root: Path, pattern: str) -> List[Path]:
        """Resolve a workspace member pattern."""
        import fnmatch
        
        if '*' in pattern:
            base = pattern.split('*')[0].rstrip('/')
            base_path = root / base
            if base_path.exists():
                return [p for p in base_path.iterdir() if p.is_dir()]
        else:
            direct = root / pattern
            if direct.exists():
                return [direct]
        
        return []


class ModuleDependencyAnalyzer:
    """Analyzes module dependencies across the entire repository."""
    
    def __init__(self, repo_root: Path, verbose: bool = False):
        self.repo_root = Path(repo_root)
        self.verbose = verbose
        self.parsers: List[ModuleParser] = [
            JavaScriptModuleParser(repo_root),
            PythonModuleParser(repo_root),
            GoModuleParser(repo_root),
            RustModuleParser(repo_root)
        ]
        self.modules: Dict[str, ModuleNode] = {}
        self.edges: List[ModuleEdge] = []
    
    def _log(self, message: str) -> None:
        if self.verbose:
            print(f"[ModuleAnalyzer] {message}")
    
    def analyze(self) -> Tuple[Dict[str, ModuleNode], List[ModuleEdge]]:
        """Analyze all module manifests in the repository."""
        self._log("Starting module dependency analysis")
        
        manifest_files = self._find_manifest_files()
        self._log(f"Found {len(manifest_files)} manifest files")
        
        # First pass: parse all manifests
        for file_path in manifest_files:
            self._log(f"Parsing {file_path}")
            for parser in self.parsers:
                if parser.can_parse(file_path):
                    module, edges = parser.parse(file_path)
                    if module:
                        self.modules[module.id] = module
                        self.edges.extend(edges)
                    break
        
        # Second pass: resolve internal dependencies
        self._resolve_internal_dependencies()
        
        self._log(f"Found {len(self.modules)} modules and {len(self.edges)} dependencies")
        
        return self.modules, self.edges
    
    def _find_manifest_files(self) -> List[Path]:
        """Find all manifest files in the repository."""
        manifests = []
        
        for parser in self.parsers:
            if isinstance(parser, JavaScriptModuleParser):
                for path in self.repo_root.rglob("package.json"):
                    if "node_modules" not in str(path):
                        manifests.append(path)
            
            elif isinstance(parser, PythonModuleParser):
                for path in self.repo_root.rglob("pyproject.toml"):
                    manifests.append(path)
                for path in self.repo_root.rglob("requirements.txt"):
                    manifests.append(path)
                for path in self.repo_root.rglob("setup.py"):
                    if "node_modules" not in str(path):
                        manifests.append(path)
            
            elif isinstance(parser, GoModuleParser):
                for path in self.repo_root.rglob("go.mod"):
                    manifests.append(path)
            
            elif isinstance(parser, RustModuleParser):
                for path in self.repo_root.rglob("Cargo.toml"):
                    if "target" not in str(path):
                        manifests.append(path)
        
        return manifests
    
    def _resolve_internal_dependencies(self) -> None:
        """Mark dependencies that point to modules in the same repo."""
        internal_module_names = {m.name: m.id for m in self.modules.values()}
        
        for edge in self.edges:
            # Extract package name from target (remove language prefix)
            target_name = edge.target.split(":", 1)[-1]
            
            if target_name in internal_module_names:
                # This is an internal dependency
                edge.metadata = edge.metadata or {}
                edge.metadata['is_internal'] = True
                edge.metadata['resolved_target'] = internal_module_names[target_name]
    
    def get_module_dependencies(self, module_id: str) -> Dict[str, List[ModuleEdge]]:
        """Get dependencies for a specific module."""
        direct_deps = [e for e in self.edges if e.source == module_id]
        reverse_deps = [e for e in self.edges if e.target == module_id]
        
        return {
            'depends_on': direct_deps,
            'depended_by': reverse_deps
        }
    
    def get_dependency_graph(self) -> Dict[str, Any]:
        """Get the full dependency graph."""
        return {
            'nodes': {k: {
                'name': v.name,
                'type': v.type,
                'language': v.language,
                'path': str(v.path),
                'version': v.version
            } for k, v in self.modules.items()},
            'edges': [
                {
                    'source': e.source,
                    'target': e.target,
                    'kind': e.kind,
                    'version': e.version_constraint
                }
                for e in self.edges
            ]
        }
    
    def to_mermaid(self, scope: str = "module") -> str:
        """Generate Mermaid diagram of module dependencies."""
        lines = ["graph TD"]
        
        # Group by language
        by_language: Dict[str, List[str]] = {}
        for module_id, module in self.modules.items():
            lang = module.language
            if lang not in by_language:
                by_language[lang] = []
            by_language[lang].append(module_id)
        
        # Add nodes
        for lang, module_ids in by_language.items():
            lines.append(f"    subgraph {lang.upper()}")
            for module_id in module_ids:
                module = self.modules[module_id]
                safe_id = module_id.replace(":", "_").replace("-", "_")
                lines.append(f"        {safe_id}[{module.name}]")
            lines.append("    end")
        
        # Add edges
        for edge in self.edges:
            if edge.kind == 'MODULE_DEPENDS_ON':
                src = edge.source.replace(":", "_").replace("-", "_")
                tgt = edge.target.replace(":", "_").replace("-", "_")
                label = edge.version_constraint or ""
                if label:
                    lines.append(f"    {src} -->|{label}| {tgt}")
                else:
                    lines.append(f"    {src} --> {tgt}")
        
        return "\n".join(lines)
    
    def to_dot(self, scope: str = "module") -> str:
        """Generate DOT (GraphViz) format of module dependencies."""
        lines = ["digraph modules {"]
        lines.append("    rankdir=TB;")
        lines.append("")
        
        # Group by language
        by_language: Dict[str, List[str]] = {}
        for module_id, module in self.modules.items():
            lang = module.language
            if lang not in by_language:
                by_language[lang] = []
            by_language[lang].append(module_id)
        
        # Add nodes with color coding by language
        colors = {
            'javascript': '#f7df1e',
            'python': '#3776ab',
            'go': '#00add8',
            'rust': '#dea584'
        }
        
        for lang, module_ids in by_language.items():
            color = colors.get(lang, '#cccccc')
            lines.append(f"    subgraph cluster_{lang} {{")
            lines.append(f"        label=\"{lang.upper()}\";")
            lines.append(f"        style=filled;")
            lines.append(f"        color=\"{color}40\";")
            
            for module_id in module_ids:
                module = self.modules[module_id]
                safe_id = module_id.replace(":", "_").replace("-", "_")
                lines.append(f'        {safe_id} [label="{module.name}", fillcolor="{color}"];')
            
            lines.append("    }")
            lines.append("")
        
        # Add edges
        for edge in self.edges:
            if edge.kind == 'MODULE_DEPENDS_ON':
                src = edge.source.replace(":", "_").replace("-", "_")
                tgt = edge.target.replace(":", "_").replace("-", "_")
                if edge.version_constraint:
                    lines.append(f'    {src} -> {tgt} [label="{edge.version_constraint}"];')
                else:
                    lines.append(f'    {src} -> {tgt};')
        
        lines.append("}")
        
        return "\n".join(lines)
