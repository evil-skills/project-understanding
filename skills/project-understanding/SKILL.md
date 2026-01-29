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
  Requires Python 3.10+; optional git for version control integration;
  local filesystem access required; optional internet for bootstrap dependencies
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

## Quick Start

```bash
# Generate repo map
opencode skill project-understanding repo-map

# Analyze specific file
opencode skill project-understanding analyze --file src/main.py

# Generate call graph
opencode skill project-understanding call-graph --symbol MyClass

# Impact analysis
opencode skill project-understanding impact --change "src/api/routes.py"
```

## Basic Commands

| Command | Description | Example |
|---------|-------------|---------|
| `repo-map` | Repository structure view | `repo-map --depth 3` |
| `analyze` | Deep file/symbol analysis | `analyze --target src/main.py` |
| `call-graph` | Generate call graphs | `call-graph --symbol MyClass` |
| `impact` | Change impact analysis | `impact --change src/api.py` |
| `index` | Manage incremental index | `index build` |

## References

- [REFERENCE.md](references/REFERENCE.md) - Complete command reference and configuration
- [ARCHITECTURE.md](references/ARCHITECTURE.md) - System design details
- [API.md](references/API.md) - API documentation
- [DEVELOPMENT.md](references/DEVELOPMENT.md) - Contribution guidelines

## License

MIT License - See repository LICENSE file
