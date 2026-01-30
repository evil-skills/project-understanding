# Reference Documentation

Complete technical documentation for the Project Understanding Skill.

---

## Configuration

The skill automatically detects project structure and configures itself.
Optional `.project-understanding.yaml` for custom settings:

```yaml
index:
  exclude_dirs:
    - node_modules
    - .git
    - __pycache__
  max_file_size: 1048576  # 1MB
  ignore_file: .puiignore

parsing:
  languages:
    - python
    - javascript
    - typescript
    - rust
    - go

output:
  format: markdown
  max_tokens: 4000
  colors: true
```

### Configuration Locations

1. `.project-understanding.yaml` - Repository-specific settings
2. `~/.config/project-understanding/config.yaml` - User defaults
3. Environment variables (e.g., `PUI_MAX_FILE_SIZE`)

---

## Commands

### `bootstrap`

Set up runtime dependencies for the Project Understanding Skill.

```bash
pui bootstrap [--offline]
```

Options:
- `--offline`: Use only locally available packages

Creates:
- `.pui/venv` - Local virtual environment for dependencies

Installs:
- Required Python dependencies into `.pui/venv`

### `index`

Manage the incremental code index.

```bash
opencode skill project-understanding index [command] [options]
```

Commands:
- `build`: Build initial index from scratch
- `update`: Incrementally update changed files
- `clean`: Remove all index data
- `status`: Show index statistics and health
- `verify`: Check index integrity

Options:
- `--workers N`: Parallel parsing workers (default: CPU count)
- `--batch-size N`: Files per transaction (default: 100)
- `--force`: Re-index even if unchanged
- `--language LANG`: Only index specific language

Index Storage:
- Location: `.pui/index.sqlite`
- Format: SQLite with FTS5 for symbol search
- Size: ~10-50KB per 1000 lines of code

### `repo-map`

Generate a hierarchical view of the repository structure.

```bash
opencode skill project-understanding repo-map [options]
```

Options:
- `--depth N`: Maximum depth to traverse (default: 3, max: 10)
- `--focus PATH`: Focus on specific directory or file
- `--format {markdown,json,tree}`: Output format
- `--include-symbols`: Show top-level symbols in each file
- `--max-files N`: Limit number of files shown

Output Structure:
```
repo-root/
  src/
    main.py          # Entry point
    utils/
      helpers.py     # Utility functions
  tests/
    test_main.py
```

### `analyze`

Deep analysis of specific files, symbols, or functions.

```bash
opencode skill project-understanding analyze --target <path> [options]
```

Options:
- `--target PATH`: File, class, or function to analyze (required)
- `--context LINES`: Lines of context to include (default: 5)
- `--dependencies`: Include dependency information
- `--show-source`: Include source code in output
- `--format {markdown,json}`: Output format

Analysis Output:
- Symbol definitions with signatures
- Import dependencies
- Documentation strings
- Complexity metrics
- Call sites (with confidence scores)

### `call-graph`

Generate call graph for symbols or the entire codebase.

```bash
opencode skill project-understanding call-graph [options]
```

Options:
- `--symbol NAME`: Generate graph for specific symbol
- `--file PATH`: Generate graph for all symbols in file
- `--depth N`: Maximum call depth (default: 5)
- `--direction {incoming,outgoing,both}`: Relationship direction
- `--format {dot,json,markdown}`: Output format
- `--min-confidence N`: Filter by minimum confidence (0.0-1.0)

Call Graph Confidence:
- **1.0**: Qualified call (e.g., `obj.method()`, `module.func()`)
- **0.8**: Imported symbol with known origin
- **0.6**: Same-file symbol resolution
- **0.4**: Global symbol with name match
- **0.2**: Dynamic dispatch or callback

### `impact`

Analyze the impact of proposed changes.

```bash
pui impact [options]
```

Options:
- `--git-diff BASE..COMPARE`: Analyze changes from a git diff
- `--files PATH...`: Analyze changes for specific files
- `--format {markdown,json}`: Output format
- `--max-tokens N`: Token budget for output
- `--include-tests`: Include test impact analysis

Impact Scoring:
- **Critical**: Core functionality, many dependents
- **High**: Important module, moderate dependents
- **Medium**: Standard module, few dependents
- **Low**: Utility code, isolated usage

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Project Understanding Skill                │
├─────────────────────────────────────────────────────────────┤
│  CLI Interface  │  Core Engine  │  Tree-sitter Parser        │
├─────────────────┼───────────────┼────────────────────────────┤
│  bootstrap      │  Indexer      │  Language Parsers          │
│  index          │  Analyzer     │  AST Extraction            │
│  repo-map       │  Graph Builder│  Symbol Resolution         │
│  analyze        │  Query Engine │  Incremental Updates       │
│  call-graph     │  Impact Engine│  Error Recovery            │
│  impact         │               │                            │
└─────────────────┴───────────────┴────────────────────────────┘
                              │
                    ┌─────────┴─────────┐
                    ▼                   ▼
            ┌──────────────┐    ┌──────────────┐
            │  Index Store │    │  Output      │
            │  (SQLite)    │    │  (Markdown/  │
            │  - files     │    │   JSON/DOT)  │
            │  - symbols   │    │              │
            │  - edges     │    │              │
            │  - callsites │    │              │
            └──────────────┘    └──────────────┘
```

### Core Components

**Indexer**
- Discovers source files
- Manages incremental updates via content hashing
- Orchestrates parallel parsing
- Handles database transactions

**Analyzer**
- Queries the index for symbols and relationships
- Builds contextual views
- Generates summaries with token budgeting

**Graph Builder**
- Constructs call graphs from edge data
- Applies confidence scoring
- Handles cyclic dependencies
- Prunes by depth and relevance

**Impact Engine**
- Traverses dependency graphs
- Calculates risk scores
- Identifies test coverage gaps

---

## Supported Languages

- Python
- JavaScript / TypeScript
- Rust
- Go
- Java
- C / C++
- Ruby
- And more via Tree-sitter grammars

See [LANG_SUPPORT.md](LANG_SUPPORT.md) for detailed language capabilities.

---

## Indexing

The skill maintains an incremental index stored in `.pui/`:

### Index Files

- `index.sqlite`: SQLite database with:
  - `files` - File metadata and content hashes
  - `symbols` - Symbol definitions with locations
  - `edges` - Relationships (calls, imports, inherits)
  - `callsites` - Specific call locations
  - `meta` - Index version and statistics

- `parsing_errors.log`: Files that failed to parse
- `config.yaml`: Cached configuration

### Incremental Updates

1. Check file modification times against index
2. Compute SHA256 hash of changed files
3. Parse only files with new/changed hashes
4. Update database in batched transactions
5. Record new hashes and timestamps

### Performance

- Initial index: ~100-500 files/second
- Incremental update: Near-instant for small changes
- Storage: ~10-50KB per 1000 lines of code
- Memory: ~100MB for 100K LOC codebase

---

## Token Budgeting

All outputs are designed to fit within token limits:

### Budget Allocation

| Output Type | Default Budget | Strategy |
|-------------|----------------|----------|
| **Repo map** | 2000 tokens | Tree pruning, file summaries |
| **Analysis** | 3000 tokens | Symbol selection, context trimming |
| **Call graphs** | 2500 tokens | Depth limiting, edge filtering |
| **Impact** | 3000 tokens | Prioritization by severity |

### Budget Controls

```yaml
output:
  max_tokens: 4000        # Total output limit
  summary_ratio: 0.3      # % for file summaries
  detail_ratio: 0.7       # % for detailed output
```

---

## Error Handling

### Parse Errors

- Syntax errors don't crash indexing
- Partial parses are used when available
- Errors logged to `.pui/parsing_errors.log`
- Failed files skipped in analysis

### Database Errors

- Transactions are atomic
- Corruption triggers automatic rebuild
- Backups created before migrations

### Recovery

```bash
# Force index rebuild
opencode skill project-understanding index clean
opencode skill project-understanding index build

# Verify index integrity
opencode skill project-understanding index verify
```

---

## Performance Tuning

### For Large Codebases (>100K LOC)

```yaml
index:
  batch_size: 500        # Larger batches
  workers: 8             # More parallel workers
  exclude_dirs:
    - vendor
    - third_party
    - generated
```

### For CI/CD Integration

```bash
# Quick check mode (no full analysis)
opencode skill project-understanding index status

# Fail on impact threshold
opencode skill project-understanding impact --change src/ --fail-on critical
```

---

## References

- [TROUBLESHOOTING.md](TROUBLESHOOTING.md) - Common issues and solutions
- [DB_SCHEMA.md](DB_SCHEMA.md) - Database schema documentation
- [LANG_SUPPORT.md](LANG_SUPPORT.md) - Language support details
- [PACK_FORMAT.md](PACK_FORMAT.md) - Pack file format specification

---

## License

MIT License - See repository LICENSE file
