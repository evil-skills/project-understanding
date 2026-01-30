# Project Understanding Skill

A powerful skill for LLM-based coding agents that provides on-demand, token-budgeted views of a repository's global architecture, enabling efficient code comprehension and navigation.

This skill maintains an incremental index of your codebase using Tree-sitter for parsing, along with a dependency graph for impact analysis. It allows agents to quickly understand repository structure without reading every file, zoom into specific components for detailed summaries, and analyze dependencies to understand the impact of changes.

## Installation

### Quick Install (via skills CLI)

Install the skill using the skills CLI:

```bash
npx skills add project-understanding-skill/project-understanding-skill
```

Verify the installation:

```bash
npx skills list
```

For a targeted install (specific skill only):

```bash
npx skills add project-understanding-skill/project-understanding-skill --skill project-understanding
```

#### Expected Folder Structure

After installation, the skill will be available at:

```
skills/project-understanding/
├── SKILL.md              # Skill specification and usage guide
├── scripts/              # Python scripts for indexing and analysis
│   ├── pui.py
│   ├── bootstrap.py
│   └── lib/
├── references/           # Extended documentation
│   ├── REFERENCE.md
│   ├── TROUBLESHOOTING.md
│   ├── PACK_FORMAT.md
│   ├── DB_SCHEMA.md
│   └── LANG_SUPPORT.md
└── assets/               # Configuration assets
    └── default-ignore.txt
```

### Manual Install (with bootstrap)

For development or offline environments, use the bootstrap script:

```bash
# Clone or navigate to the skill directory
cd project-understanding-skill

# Run bootstrap to create venv and install dependencies
python scripts/bootstrap.py

# Activate the virtual environment
source .pui/venv/bin/activate  # Linux/macOS
# OR
.pui/venv/Scripts/activate     # Windows
```

### Offline Mode

For air-gapped or offline environments:

```bash
# Step 1: On a machine with internet, download packages
pip download -r scripts/requirements.txt -d .pui/packages

# Step 2: Copy the entire project directory to the offline machine

# Step 3: On the offline machine, run bootstrap with --offline flag
python scripts/bootstrap.py --offline
```

**Note:** Offline mode requires pre-downloaded packages in `.pui/packages/`. The bootstrap script will verify existing packages before attempting installation.

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

### Agent Skill Activation Compatibility

| Platform | Activation | Status | Notes |
|----------|-----------|--------|-------|
| **Claude Code** | `project-understanding` | Supported | Full feature support |
| **OpenCode** | `opencode skill project-understanding` | Supported | Native integration |
| **Gemini CLI** | `@project-understanding` | Supported | Basic functionality |

**Activation Keywords:**
- "understand this codebase"
- "what does this project do"
- "analyze repository structure"
- "show me the architecture"

## Features

- **Repository Map**: Get a high-level view of your codebase structure, organized by directories and modules
- **Zoom**: Drill down into specific files, classes, functions, or symbols for detailed information
- **Impact Analysis**: Understand dependencies and call graphs to assess the scope of changes
- **Incremental Indexing**: Only re-index changed files for fast updates
- **Token Budgeting**: Control how much context is returned to fit within LLM context windows

## Performance Benchmarks

The following performance targets are expected when running on a typical development machine (2.5GHz CPU, SSD):

### Index Performance

| Metric | Target | Notes |
|--------|--------|-------|
| **Cold Start** | < 30s for 1000 files | Initial indexing of repository |
| **Incremental Update** | < 5s for 10 changed files | Updating after changes |
| **Files/sec** | 50+ files/second | Single-threaded parsing rate |

### Query Performance

| Metric | Target | Notes |
|--------|--------|-------|
| **Repomap Generation** | < 5s | Generate repository overview |
| **Zoom Query** | < 3s | Lookup specific symbol details |
| **Impact Analysis** | < 5s | Dependency graph traversal |
| **Search** | < 1s | Symbol search with FTS |

### Token Budget Compliance

All pack generators respect token budgets:
- **RepoMap Pack**: Default 8000 tokens, automatically truncates
- **Zoom Pack**: Default 4000 tokens, prioritizes code + docs
- **Impact Pack**: Default 6000 tokens, includes affected files

### Scaling Characteristics

- **Small repos** (< 100 files): Near-instant queries (< 1s)
- **Medium repos** (< 1000 files): Meets all targets above
- **Large repos** (> 10000 files): Recommend using `focus` option to subset analysis

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

### Spec Compliance Validation

To validate the skill meets the Agent Skills specification:

```bash
skills-ref validate skills/project-understanding
```

#### Expected Validation Output

A successful validation produces output similar to:

```
✓ Validating skill: project-understanding
✓ YAML frontmatter parsed successfully
✓ Required fields present (name, description, version, license)
✓ Directory structure compliant
✓ SKILL.md formatting valid (166 lines)
✓ Reference files accessible
✓ All validation checks passed
```

#### Common Fixes for Violations

| Violation | Cause | Fix |
|-----------|-------|-----|
| `Missing required field: version` | Frontmatter lacks version | Add `version: "x.y.z"` to metadata |
| `Invalid YAML syntax` | Malformed frontmatter | Check indentation and quote multi-line strings with `\|` |
| `SKILL.md exceeds 500 lines` | Documentation too long | Move extended content to `references/` files |
| `Missing references/ directory` | Required folder absent | Create `skills/project-understanding/references/` |
| `scripts/ directory missing` | No scripts folder | Create `skills/project-understanding/scripts/` |
| `Name mismatch` | Folder name ≠ skill name | Rename folder to match `name:` in frontmatter |

Fix any reported frontmatter naming, path, or formatting violations before release.

## Skills.sh

This skill is published on the [skills.sh](https://skills.sh) registry:

[![View on skills.sh](https://img.shields.io/badge/skills.sh-view-blue)](https://skills.sh/project-understanding-skill/project-understanding-skill/project-understanding)

**Direct URL:** `https://skills.sh/project-understanding-skill/project-understanding-skill/project-understanding`

The SKILL.md is rendered as a readable documentation page. Ensure it stays under 500 lines for optimal readability.

## License

MIT License - see [LICENSE](LICENSE) for details.
