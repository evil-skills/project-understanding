#!/usr/bin/env python3
"""
Project Understanding Interface (PUI) - CLI Entrypoint

Single entrypoint for the Project Understanding Skill with subcommands for:
- bootstrap: sets up local runtime deps
- index: builds/updates index database
- repomap: prints RepoMapPack (Markdown default)
- find: fuzzy symbol search (JSON default; Markdown option)
- zoom: prints ZoomPack for a file/symbol
- impact: prints ImpactPack for a changed set
- graph: exports dependency graph (Mermaid/DOT)
- watch: file watcher with auto-update
- depgraph: module dependency graph
"""

import argparse
import sys
from pathlib import Path


def cmd_bootstrap(args: argparse.Namespace) -> int:
    """Sets up local runtime dependencies."""
    print("Not implemented yet")
    return 0


def cmd_index(args: argparse.Namespace) -> int:
    """Builds/updates index database."""
    from scripts.lib.indexer import Indexer
    
    repo_root = Path.cwd()
    skill_root = Path(__file__).parent.parent
    
    with Indexer(repo_root, skill_root) as indexer:
        # Apply CLI include/exclude patterns
        if indexer.ignore_manager:
            for pattern in args.include:
                indexer.ignore_manager.add_include(pattern)
            for pattern in args.exclude:
                indexer.ignore_manager.add_exclude(pattern)
        
        # Run indexing
        stats = indexer.run(force=args.force)
        
        # Print stats if requested
        if args.stats:
            print(stats)
    
    return 0


def _resolve_budget_arg(budget_arg: str, pack_type: str, config_budget: int | None = None) -> int:
    """Resolve budget argument, handling 'auto' value."""
    if budget_arg == "auto":
        from scripts.lib.budget import resolve_budget
        return resolve_budget("auto", pack_type, config_budget)
    try:
        return int(budget_arg)
    except ValueError:
        return config_budget or 8000


def cmd_repomap(args: argparse.Namespace) -> int:
    """Prints RepoMapPack (Markdown default)."""
    from scripts.lib.packs import RepoMapPackGenerator
    from scripts.lib.budget import resolve_budget
    
    repo_root = Path.cwd()
    
    # Resolve budget (handles "auto" value)
    budget = resolve_budget(args.max_tokens, "repomap", config_budget=8000)
    
    with RepoMapPackGenerator(repo_root) as gen:
        pack = gen.generate(budget_tokens=budget, focus=getattr(args, 'focus', None))
        
        if args.format == "json":
            import json
            print(json.dumps({
                'directory_tree': pack.directory_tree,
                'top_files': pack.top_files,
                'file_symbols': pack.file_symbols,
                'dependency_summary': pack.dependency_summary,
            }, indent=2))
        else:
            print(pack.to_text())
    
    return 0


def cmd_find(args: argparse.Namespace) -> int:
    """Fuzzy symbol search (JSON default; Markdown option)."""
    from scripts.lib.db import Database, get_db_path
    
    repo_root = Path.cwd()
    db_path = get_db_path(repo_root)
    db = Database(db_path)
    db.connect()
    
    try:
        results = db.search_symbols(args.query, limit=args.limit)
        
        if args.format == "json":
            import json
            print(json.dumps(results, indent=2))
        else:
            print(f"# Search Results for '{args.query}'\n")
            for i, r in enumerate(results, 1):
                print(f"{i}. `{r['name']}` ({r['kind']}) in `{r.get('file_path', 'unknown')}:{r.get('line_start', 0)}`")
        
        return 0
    finally:
        db.close()


def cmd_zoom(args: argparse.Namespace) -> int:
    """Prints ZoomPack for a file/symbol."""
    from scripts.lib.packs import ZoomPackGenerator
    from scripts.lib.budget import resolve_budget
    
    repo_root = Path.cwd()
    
    # Resolve budget (handles "auto" value)
    budget = resolve_budget(args.max_tokens, "zoom", config_budget=4000)
    
    with ZoomPackGenerator(repo_root) as gen:
        pack = gen.generate(args.target, budget_tokens=budget)
        
        if pack is None:
            print(f"Symbol not found: {args.target}", file=sys.stderr)
            return 1
        
        if args.format == "json":
            import json
            print(json.dumps({
                'target_symbol': pack.target_symbol,
                'signature': pack.signature,
                'docstring': pack.docstring,
                'callers': pack.callers,
                'callees': pack.callees,
            }, indent=2))
        else:
            print(pack.to_text())
    
    return 0


def cmd_impact(args: argparse.Namespace) -> int:
    """Prints ImpactPack for a changed set."""
    from scripts.lib.packs import ImpactPackGenerator
    from scripts.lib.budget import resolve_budget
    
    repo_root = Path.cwd()
    
    # Resolve budget (handles "auto" value)
    budget = resolve_budget(args.max_tokens, "impact", config_budget=6000)
    
    with ImpactPackGenerator(repo_root) as gen:
        # Collect targets from various sources
        targets = []
        if hasattr(args, 'git_diff') and args.git_diff:
            # TODO: Implement git diff parsing
            print("Git diff parsing not yet implemented")
        elif hasattr(args, 'files') and args.files:
            targets = args.files
        
        pack = gen.generate(targets, budget_tokens=budget)
        
        if args.format == "json":
            import json
            print(json.dumps({
                'changed_items': pack.changed_items,
                'affected_files': pack.affected_files,
                'affected_tests': pack.affected_tests,
                'affected_symbols': pack.affected_symbols,
                'ranked_inspection': pack.ranked_inspection,
            }, indent=2))
        else:
            print(pack.to_text())
    
    return 0


def cmd_graph(args: argparse.Namespace) -> int:
    """Exports dependency graph in Mermaid or DOT format."""
    from scripts.lib.graph_export import GraphExporter
    from scripts.lib.db import Database, get_db_path
    
    repo_root = Path.cwd()
    db_path = get_db_path(repo_root)
    db = Database(db_path)
    db.connect()
    
    try:
        # Ensure connection is established
        if db._conn is None:
            print("Database connection failed", file=sys.stderr)
            return 1
        
        # Resolve symbol
        symbol_id = args.symbol
        if isinstance(symbol_id, str):
            try:
                symbol_id = int(symbol_id)
            except ValueError:
                # Try to find by name
                cursor = db._conn.execute(
                    "SELECT id FROM symbols WHERE name = ? LIMIT 1",
                    (symbol_id,)
                )
                row = cursor.fetchone()
                if row:
                    symbol_id = row[0]
                else:
                    print(f"Symbol not found: {args.symbol}", file=sys.stderr)
                    return 1
        
        exporter = GraphExporter(db)
        result = exporter.generate_graph_pack(
            symbol_id=symbol_id,
            depth=args.depth,
            format=args.format,
            title=args.title if hasattr(args, 'title') else None
        )
        
        print(result)
        return 0
    finally:
        db.close()


def cmd_watch(args: argparse.Namespace) -> int:
    """Watch mode for automatic index updates."""
    from scripts.lib.watcher import WatchMode
    from scripts.lib.platform import PlatformSupport, install_signal_handlers
    
    # Install signal handlers for clean shutdown
    install_signal_handlers()
    
    repo_root = Path.cwd()
    skill_root = Path(__file__).parent.parent
    
    # Print platform info
    if hasattr(args, 'verbose') and args.verbose:
        platform = PlatformSupport()
        platform.print_report()
        print()
    
    watcher = WatchMode(
        repo_root=repo_root,
        skill_root=skill_root,
        debounce_seconds=args.debounce,
        verbose=getattr(args, 'verbose', False)
    )
    
    try:
        watcher.start()
    except KeyboardInterrupt:
        watcher.stop()
    
    return 0


def cmd_depgraph(args: argparse.Namespace) -> int:
    """Generate module dependency graph."""
    from scripts.lib.modules import ModuleDependencyAnalyzer
    
    repo_root = Path.cwd()
    analyzer = ModuleDependencyAnalyzer(repo_root, verbose=args.verbose)
    
    modules, edges = analyzer.analyze()
    
    if args.format == "mermaid":
        output = analyzer.to_mermaid(scope=args.scope)
    elif args.format == "dot":
        output = analyzer.to_dot(scope=args.scope)
    else:  # json
        import json
        output = json.dumps(analyzer.get_dependency_graph(), indent=2)
    
    if args.output:
        Path(args.output).write_text(output)
        print(f"Dependency graph written to {args.output}")
    else:
        print(output)
    
    return 0


def cmd_benchmark(args: argparse.Namespace) -> int:
    """Run performance benchmarks."""
    print("Not implemented yet")
    return 0



def cmd_architecture(args: argparse.Namespace) -> int:
    """Analyze repository architecture."""
    from scripts.lib.architecture import analyze_architecture
    
    repo_root = Path.cwd()
    
    # Load files from repository
    files_content = {}
    for ext in ["*.py", "*.js", "*.ts", "*.go", "*.rs"]:
        for file_path in repo_root.rglob(ext):
            try:
                rel_path = str(file_path.relative_to(repo_root))
                files_content[rel_path] = file_path.read_text()
            except Exception:
                pass
    
    pack = analyze_architecture(repo_root, files_content)
    
    if args.format == "json":
        import json
        print(json.dumps(pack.to_dict(), indent=2))
    else:
        print(pack.to_text())
    
    return 0


def cmd_workspace(args: argparse.Namespace) -> int:
    """Manage multi-repository workspaces."""
    from scripts.lib.workspace import WorkspaceManager, init_workspace
    from pathlib import Path
    
    if args.workspace_command == "init":
        repo_paths = [Path(p) for p in args.repos]
        config = init_workspace(args.name, repo_paths)
        print(f"Created workspace '{args.name}' with {len(config.repos)} repositories")
        return 0
    
    elif args.workspace_command == "graph":
        manager = WorkspaceManager(Path(".pui-workspace.json"))
        if not manager.config:
            print("No workspace configured. Run 'pui workspace init' first.")
            return 1
        
        graph = manager.build_unified_graph()
        print(graph.to_text())
        return 0
    
    elif args.workspace_command == "find":
        manager = WorkspaceManager(Path(".pui-workspace.json"))
        if not manager.config:
            print("No workspace configured. Run 'pui workspace init' first.")
            return 1
        
        results = manager.find_symbol_across_repos(args.symbol)
        if results:
            print(f"Found '{args.symbol}' in {len(results)} locations:")
            for r in results:
                print(f"  {r['repo']}: {r['name']} ({r['kind']}) in {r['file']}:{r['line']}")
        else:
            print(f"Symbol '{args.symbol}' not found in workspace")
        return 0
    
    return 0

def main(argv: list[str] | None = None) -> int:
    """Main entrypoint for the PUI CLI."""
    parser = argparse.ArgumentParser(
        prog="pui",
        description="Project Understanding Interface - analyze and navigate codebases",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  pui bootstrap              # Set up local runtime dependencies
  pui index                  # Build/update index database
  pui index --watch          # Build index and start watching for changes
  pui repomap                # Print RepoMapPack (Markdown)
  pui repomap --budget auto  # Auto-detect token budget for model
  pui find "auth*"           # Fuzzy search for symbols matching "auth*"
  pui zoom src/auth.py       # Print ZoomPack for file
  pui impact --git-diff HEAD~1..HEAD  # Print ImpactPack for recent changes
  pui graph -s auth_login -d 2 --format mermaid  # Export dependency graph
  pui watch                  # Watch files and auto-update index
  pui depgraph --format mermaid       # Generate module dependency graph
        """
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    # bootstrap subcommand
    bootstrap_parser = subparsers.add_parser(
        "bootstrap",
        help="Set up local runtime dependencies"
    )
    bootstrap_parser.set_defaults(func=cmd_bootstrap)
    
    # index subcommand
    index_parser = subparsers.add_parser(
        "index",
        help="Build/update index database"
    )
    index_parser.add_argument(
        "--force", "-f",
        action="store_true",
        help="Force full reindex (ignore existing)"
    )
    index_parser.add_argument(
        "--include", "-i",
        action="append",
        default=[],
        help="Include pattern (can be specified multiple times)"
    )
    index_parser.add_argument(
        "--exclude", "-e",
        action="append",
        default=[],
        help="Exclude pattern (can be specified multiple times)"
    )
    index_parser.add_argument(
        "--stats", "-s",
        action="store_true",
        help="Show indexing statistics"
    )
    index_parser.set_defaults(func=cmd_index)
    
    # repomap subcommand
    repomap_parser = subparsers.add_parser(
        "repomap",
        help="Print RepoMapPack (Markdown default)"
    )
    repomap_parser.add_argument(
        "--format", "-f",
        choices=["markdown", "json"],
        default="markdown",
        help="Output format (default: markdown)"
    )
    repomap_parser.add_argument(
        "--max-tokens", "-t",
        type=str,
        default="8000",
        help="Maximum tokens in output (default: 8000, use 'auto' for auto-detection)"
    )
    repomap_parser.add_argument(
        "--focus",
        help="Focus on specific subdirectory"
    )
    repomap_parser.set_defaults(func=cmd_repomap)
    
    # find subcommand
    find_parser = subparsers.add_parser(
        "find",
        help="Fuzzy symbol search (JSON default; Markdown option)"
    )
    find_parser.add_argument(
        "query",
        help="Search query (supports wildcards *)"
    )
    find_parser.add_argument(
        "--format", "-f",
        choices=["json", "markdown"],
        default="json",
        help="Output format (default: json)"
    )
    find_parser.add_argument(
        "--limit", "-l",
        type=int,
        default=50,
        help="Maximum results (default: 50)"
    )
    find_parser.set_defaults(func=cmd_find)
    
    # zoom subcommand
    zoom_parser = subparsers.add_parser(
        "zoom",
        help="Print ZoomPack for a file/symbol"
    )
    zoom_parser.add_argument(
        "target",
        help="File path or symbol identifier to zoom into"
    )
    zoom_parser.add_argument(
        "--format", "-f",
        choices=["markdown", "json"],
        default="markdown",
        help="Output format (default: markdown)"
    )
    zoom_parser.add_argument(
        "--max-tokens", "-t",
        type=str,
        default="4000",
        help="Maximum tokens in output (default: 4000, use 'auto' for auto-detection)"
    )
    zoom_parser.add_argument(
        "--context", "-c",
        type=int,
        default=10,
        help="Lines of context around references (default: 10)"
    )
    zoom_parser.set_defaults(func=cmd_zoom)
    
    # impact subcommand
    impact_parser = subparsers.add_parser(
        "impact",
        help="Print ImpactPack for a changed set"
    )
    impact_parser.add_argument(
        "--git-diff",
        metavar="REF",
        help="Git reference range (e.g., HEAD~1..HEAD)"
    )
    impact_parser.add_argument(
        "--files",
        nargs="+",
        help="Specific files to analyze for impact"
    )
    impact_parser.add_argument(
        "--format", "-f",
        choices=["markdown", "json"],
        default="markdown",
        help="Output format (default: markdown)"
    )
    impact_parser.add_argument(
        "--max-tokens", "-t",
        type=str,
        default="6000",
        help="Maximum tokens in output (default: 6000, use 'auto' for auto-detection)"
    )
    impact_parser.add_argument(
        "--include-tests",
        action="store_true",
        help="Include test impact analysis"
    )
    impact_parser.set_defaults(func=cmd_impact)
    
    # graph subcommand
    graph_parser = subparsers.add_parser(
        "graph",
        help="Export dependency graph (Mermaid/DOT)"
    )
    graph_parser.add_argument(
        "--symbol", "-s",
        required=True,
        help="Symbol ID or name to start from"
    )
    graph_parser.add_argument(
        "--depth", "-d",
        type=int,
        default=2,
        help="Traversal depth (default: 2)"
    )
    graph_parser.add_argument(
        "--format", "-f",
        choices=["mermaid", "dot"],
        default="mermaid",
        help="Output format (default: mermaid)"
    )
    graph_parser.set_defaults(func=cmd_graph)
    
    # watch subcommand
    watch_parser = subparsers.add_parser(
        "watch",
        help="Watch files and auto-update index"
    )
    watch_parser.add_argument(
        "--debounce",
        type=float,
        default=1.0,
        help="Debounce delay in seconds (default: 1.0)"
    )
    watch_parser.set_defaults(func=cmd_watch)
    
    # depgraph subcommand
    depgraph_parser = subparsers.add_parser(
        "depgraph",
        help="Generate module dependency graph"
    )
    depgraph_parser.add_argument(
        "--format", "-f",
        choices=["mermaid", "dot", "json"],
        default="mermaid",
        help="Output format (default: mermaid)"
    )
    depgraph_parser.add_argument(
        "--scope", "-s",
        choices=["module", "package"],
        default="module",
        help="Graph scope (default: module)"
    )
    depgraph_parser.add_argument(
        "--output", "-o",
        help="Output file (default: stdout)"
    )
    depgraph_parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose logging"
    )
    depgraph_parser.set_defaults(func=cmd_depgraph)
    
    # benchmark subcommand
    benchmark_parser = subparsers.add_parser(
        "benchmark",
        help="Run performance benchmarks"
    )
    benchmark_parser.add_argument(
        "--format", "-f",
        choices=["markdown", "json"],
        default="markdown",
        help="Output format (default: markdown)"
    )
    benchmark_parser.add_argument(
        "--output", "-o",
        help="Output file (default: stdout)"
    )
    benchmark_parser.set_defaults(func=cmd_benchmark)
    
    # architecture subcommand
    arch_parser = subparsers.add_parser(
        "architecture",
        help="Analyze repository architecture and frameworks"
    )
    arch_parser.add_argument(
        "--format", "-f",
        choices=["markdown", "json"],
        default="markdown",
        help="Output format (default: markdown)"
    )
    arch_parser.set_defaults(func=cmd_architecture)
    
    # workspace subcommand
    workspace_parser = subparsers.add_parser(
        "workspace",
        help="Manage multi-repository workspaces"
    )
    workspace_subparsers = workspace_parser.add_subparsers(
        dest="workspace_command",
        help="Workspace commands"
    )
    
    # workspace init
    ws_init_parser = workspace_subparsers.add_parser(
        "init",
        help="Initialize a new workspace"
    )
    ws_init_parser.add_argument(
        "name",
        help="Workspace name"
    )
    ws_init_parser.add_argument(
        "repos",
        nargs="+",
        help="Repository paths to include"
    )
    
    # workspace graph
    ws_graph_parser = workspace_subparsers.add_parser(
        "graph",
        help="Show unified workspace graph"
    )
    
    # workspace find
    ws_find_parser = workspace_subparsers.add_parser(
        "find",
        help="Find symbol across all workspace repos"
    )
    ws_find_parser.add_argument(
        "symbol",
        help="Symbol name to search for"
    )
    
    workspace_parser.set_defaults(func=cmd_workspace)
    
    args = parser.parse_args(argv)
    
    if args.command is None:
        parser.print_help()
        return 1
    
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
