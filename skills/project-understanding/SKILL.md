---
name: project-understanding
description: Use when you need to understand the architecture, dependencies, or impact of changes in a large, unfamiliar repository.
---

# Project Understanding

## Overview
Automated repository intelligence using Tree-sitter parsing to generate maps, dependency graphs, and impact analysis.

## When to Use
- **Entering new codebase:** Rapidly map structure and patterns
- **Planning refactors:** Find all callers and assess "blast radius"
- **Budgeting context:** Fit repository summaries into LLM token limits
- **Verification:** Ensure changes don't violate architectural boundaries

## Core Workflow
1. **Auto-Bootstrap:** The skill automatically sets up its dependencies on the first call.
2. **Index:** `./scripts/pui.sh index`
3. **Map:** `./scripts/pui.sh repomap`
4. **Impact:** `./scripts/pui.sh impact --files path/to/changed_file.py`

## Installation
The skill works "out of the box". On the first invocation, it automatically installs a shared virtual environment in `~/.local/share/pui/venv` (or a local fallback). Repository-specific data (index database) is stored in the `.pui/` directory of your project root.

## Quick Reference

| Command | Purpose | Key Flag |
|---------|---------|----------|
| `repo-map` | High-level overview | `--depth` |
| `zoom` | Deep file/symbol dive | `--target` |
| `graph` | Call/dependency visualization | `--symbol` |
| `impact` | Blast radius analysis | `--git-diff` |

## Impact Analysis Confidence
| Score | Meaning | Action |
|-------|---------|--------|
| **0.9+** | Definite match | Trust & proceed |
| **0.7-0.9** | Likely (imports) | Verify manually |
| **<0.7** | Heuristic/Dynamic | Treat as hints |

## Common Mistakes
- **Skipping index:** Commands will fail or show stale data. Always `index build` after large changes.
- **Vague zoom:** Zooming on a generic term (e.g., `utils`) returns too much noise. Use specific symbols.
- **Ignoring Budget:** Large repo-maps can burn 20k+ tokens. Use `--depth` to constrain.

## Rationalization Table

| Excuse | Reality |
|--------|---------|
| "I can just grep for imports" | Grep misses dynamic imports and indirect dependencies. `impact` is more accurate. |
| "Structure is obvious from file names" | File names lie. `repo-map` shows actual symbol relationships. |
| "Indexing takes too long" | Manual tracing takes longer and is error-prone. Indexing is incremental. |
| "I'll just read the large files" | Reading 600+ line files burns tokens and focus. `zoom` isolates the essential logic. |

## Red Flags - STOP and Index
- You are manually following imports through more than 2 files.
- You are guessing the architecture based on folder names alone.
- You are providing "Impact Analysis" based on simple keyword search.
- You are hitting context window limits with large code blocks.

**All of these mean: Run `index build` and use the proper analysis tools.**
