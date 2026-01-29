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


def cmd_repomap(args: argparse.Namespace) -> int:
    """Prints RepoMapPack (Markdown default)."""
    print("Not implemented yet")
    return 0


def cmd_find(args: argparse.Namespace) -> int:
    """Fuzzy symbol search (JSON default; Markdown option)."""
    print("Not implemented yet")
    return 0


def cmd_zoom(args: argparse.Namespace) -> int:
    """Prints ZoomPack for a file/symbol."""
    print("Not implemented yet")
    return 0


def cmd_impact(args: argparse.Namespace) -> int:
    """Prints ImpactPack for a changed set."""
    print("Not implemented yet")
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
  pui repomap                # Print RepoMapPack (Markdown)
  pui find "auth*"           # Fuzzy search for symbols matching "auth*"
  pui zoom src/auth.py       # Print ZoomPack for file
  pui impact --diff HEAD~1   # Print ImpactPack for recent changes
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
        "--watch", "-w",
        action="store_true",
        help="Watch for changes and auto-update"
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
        type=int,
        default=8000,
        help="Maximum tokens in output (default: 8000)"
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
        type=int,
        default=4000,
        help="Maximum tokens in output (default: 4000)"
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
        "--diff",
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
        type=int,
        default=6000,
        help="Maximum tokens in output (default: 6000)"
    )
    impact_parser.add_argument(
        "--include-tests",
        action="store_true",
        help="Include test impact analysis"
    )
    impact_parser.set_defaults(func=cmd_impact)
    
    args = parser.parse_args(argv)
    
    if args.command is None:
        parser.print_help()
        return 1
    
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
