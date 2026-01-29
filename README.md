# Project Understanding Skill

A powerful skill for LLM-based coding agents that provides on-demand, token-budgeted views of a repository's global architecture, enabling efficient code comprehension and navigation.

This skill maintains an incremental index of your codebase using Tree-sitter for parsing, along with a dependency graph for impact analysis. It allows agents to quickly understand repository structure without reading every file, zoom into specific components for detailed summaries, and analyze dependencies to understand the impact of changes.

## Installation

Install the skill using the skills CLI:

```bash
npx skills add project-understanding-skill/project-understanding-skill
```

Or with a specific skill name:

```bash
npx skills add project-understanding-skill/project-understanding-skill --skill project-understanding
```

## Quick Demo

Once installed, the skill provides several commands for exploring your codebase:

```bash
# Index the current repository (builds the codebase index)
project-understanding index

# Generate a repository map (global architecture view)
project-understanding repomap

# Zoom into a specific file or symbol for detailed view
project-understanding zoom path/to/file.py
project-understanding zoom --symbol MyClass

# Analyze impact of changes (dependency/call graph)
project-understanding impact path/to/file.py
project-understanding impact --symbol MyFunction
```

## Compatibility

**Required:**
- Python 3.8+

**Optional (for enhanced parsing):**
- Tree-sitter language grammars (auto-installed on first use)

## Features

- **Repository Map**: Get a high-level view of your codebase structure, organized by directories and modules
- **Zoom**: Drill down into specific files, classes, functions, or symbols for detailed information
- **Impact Analysis**: Understand dependencies and call graphs to assess the scope of changes
- **Incremental Indexing**: Only re-index changed files for fast updates
- **Token Budgeting**: Control how much context is returned to fit within LLM context windows

## Release Checklist

Before releasing a new version of this skill, ensure the following:

- [ ] **Skill Validation**: Skill passes `skills-ref validate skills/project-understanding`
- [ ] **Tests Pass**: All unit tests pass (`pytest`)
- [ ] **Linting**: Code passes ruff linting and formatting checks (`ruff check . && ruff format --check .`)
- [ ] **Version Bump**: Version updated in `skills/project-understanding/SKILL.md` frontmatter
- [ ] **Documentation**: README.md and SKILL.md are up to date
- [ ] **CHANGELOG**: CHANGELOG.md updated with new features and fixes (if applicable)
- [ ] **CI Passing**: All GitHub Actions checks are green
- [ ] **Manual Testing**: Skill tested locally with real repositories

## License

MIT License - see [LICENSE](LICENSE) for details.
