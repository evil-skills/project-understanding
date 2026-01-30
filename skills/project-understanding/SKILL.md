---
name: project-understanding
description: |
  Provides on-demand, token-budgeted repository intelligence including:
  - Global architecture view (repo map) with zoom capabilities to file/symbol/function-level summaries
  - Dependency and call graph visualization for impact analysis
  - Incremental indexing powered by Tree-sitter parsing

  Use this skill to rapidly understand codebase structure, analyze dependencies,
  and assess the impact of changes before implementation.
license: MIT
compatibility: |
  Requires Python 3.10+, tree-sitter and tree-sitter-languages packages;
  System deps: C compiler (for building tree-sitter if prebuilt wheels unavailable);
  Optional: git for version control integration; local filesystem access required
metadata:
  author: project-understanding-skill
  version: "0.1.0"
---

# Project Understanding Skill

## Overview

The Project Understanding Skill provides intelligent repository analysis capabilities,
designed to help developers quickly grasp codebase architecture and dependencies.

### Key Features

- **Repository Map**: Global view of codebase structure with drill-down capabilities
- **Architecture Analysis**: High-level system design and component relationships
- **Tree-sitter Integration**: Fast, accurate parsing of multiple programming languages
- **Call Graph Generation**: Visualize function/method dependencies and relationships
- **Impact Analysis**: Assess the scope and effect of proposed changes

## When to Use

**Activation Keywords:**
- "understand this codebase"
- "what does this project do"
- "find where X is defined"
- "who calls this function"
- "impact of changing Y"
- "repository structure"
- "code architecture"
- "dependency analysis"

Use this skill when you need to:
- Explore an unfamiliar codebase
- Plan refactoring or feature additions
- Assess the impact of changes
- Navigate complex dependency relationships
- Generate documentation from code

## Quick Start

The typical workflow follows this pattern: **bootstrap → index → repomap → zoom → impact**

```bash
# 1. Bootstrap: Set up dependencies (.pui/venv)
pui bootstrap

# 2. Index: Build the searchable code index
opencode skill project-understanding index build

# 3. Repo Map: Get a high-level view of the codebase
opencode skill project-understanding repo-map

# 4. Zoom: Drill down into specific areas
opencode skill project-understanding zoom --target src/main.py
opencode skill project-understanding graph --symbol MyClass

# 5. Impact: Assess change effects
pui impact --git-diff HEAD~1..HEAD
pui impact --files "src/api/routes.py"
```

## Basic Commands

| Command | Description | Example |
|---------|-------------|---------|
| `bootstrap` | Set up dependencies (.pui/venv) | `pui bootstrap` |
| `index` | Manage incremental index | `pui index` |
| `repomap` | Repository structure view | `pui repomap` |
| `zoom` | Deep file/symbol analysis | `pui zoom --target src/main.py` |
| `graph` | Generate call graphs | `pui graph --symbol MyClass` |
| `impact` | Change impact analysis | `pui impact --files src/api.py` |
| `benchmark` | Run performance benchmarks | `pui benchmark` |

## Common Workflows

### Refactoring Workflow

```bash
# 1. Identify the target for refactoring
opencode skill project-understanding zoom --target src/old_module.py

# 2. Find all dependencies and callers
opencode skill project-understanding graph --symbol OldClass --depth 2

# 3. Assess impact of the change
pui impact --files src/old_module.py

# 4. After changes, update the index
opencode skill project-understanding index
```

### Add Feature Workflow

```bash
# 1. Understand existing architecture
opencode skill project-understanding repomap

# 2. Find similar features to use as templates
opencode skill project-understanding zoom --target src/features/existing_feature.py

# 3. Check where to integrate the new feature
opencode skill project-understanding graph --symbol FeatureManager

# 4. Verify no breaking changes
pui impact --files src/features/new_feature.py
```

### Fix Bug Workflow

```bash
# 1. Locate the problematic code
opencode skill project-understanding zoom --target src/buggy_module.py

# 2. Trace the execution path
opencode skill project-understanding graph --symbol buggy_function --depth 3

# 3. Understand the root cause
opencode skill project-understanding zoom --target src/buggy_module.py

# 4. Check for similar issues elsewhere
opencode skill project-understanding graph --symbol related_function
```

## How to Interpret Confidence

Call graph edges and impact analysis include confidence scores:

| Confidence | Meaning | Action |
|------------|---------|--------|
| **0.9-1.0** | Definite match (qualified names) | High trust, proceed with confidence |
| **0.7-0.9** | Likely match (import context) | Verify visually before major decisions |
| **0.5-0.7** | Possible match (limited context) | Manual review recommended |
| **0.3-0.5** | Uncertain (dynamic dispatch) | Treat as hints, not facts |
| **< 0.3** | Very uncertain | Likely false positive, ignore |

**Factors affecting confidence:**
- **Qualified names** (`obj.method`, `pkg.function`) = Higher confidence
- **Import statements** present = Medium confidence
- **Simple identifiers** without context = Lower confidence
- **Dynamic dispatch** (callbacks, duck typing) = Lowest confidence

## Where to Read More

- [REFERENCE.md](references/REFERENCE.md) - Complete command reference and technical details
- [TROUBLESHOOTING.md](references/TROUBLESHOOTING.md) - Common failures and solutions
- [DB_SCHEMA.md](references/DB_SCHEMA.md) - Database schema documentation
- [LANG_SUPPORT.md](references/LANG_SUPPORT.md) - Language support details

## License

MIT License - See repository LICENSE file
