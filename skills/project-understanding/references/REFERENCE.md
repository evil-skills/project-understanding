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
```

---

## Commands

### `repo-map`

Generate a hierarchical view of the repository structure.

```bash
opencode skill project-understanding repo-map [options]
```

Options:
- `--depth N`: Maximum depth to traverse (default: 3)
- `--focus PATH`: Focus on specific directory or file
- `--format {markdown,json}`: Output format

### `analyze`

Deep analysis of specific files, symbols, or functions.

```bash
opencode skill project-understanding analyze --target <path> [options]
```

Options:
- `--target PATH`: File, class, or function to analyze
- `--context LINES`: Lines of context to include (default: 5)
- `--dependencies`: Include dependency information

### `call-graph`

Generate call graph for symbols or the entire codebase.

```bash
opencode skill project-understanding call-graph [options]
```

Options:
- `--symbol NAME`: Generate graph for specific symbol
- `--depth N`: Maximum call depth (default: 5)
- `--direction {incoming,outgoing,both}`: Relationship direction

### `impact`

Analyze the impact of proposed changes.

```bash
opencode skill project-understanding impact --change <path> [options]
```

Options:
- `--change PATH`: Path to the changed file
- `--type {add,modify,delete}`: Type of change
- `--downstream`: Show downstream dependencies

### `index`

Manage the incremental index.

```bash
opencode skill project-understanding index [command]
```

Commands:
- `build`: Build initial index
- `update`: Update index incrementally
- `clean`: Remove index and rebuild
- `status`: Show index status

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Project Understanding Skill                │
├─────────────────────────────────────────────────────────────┤
│  CLI Interface  │  Core Engine  │  Tree-sitter Parser        │
├─────────────────┼───────────────┼────────────────────────────┤
│  repo-map       │  Indexer      │  Language Parsers          │
│  analyze        │  Analyzer     │  AST Extraction            │
│  call-graph     │  Graph Builder│  Symbol Resolution         │
│  impact         │  Query Engine │  Incremental Updates       │
└─────────────────┴───────────────┴────────────────────────────┘
                              │
                    ┌─────────┴─────────┐
                    ▼                   ▼
            ┌──────────────┐    ┌──────────────┐
            │  Index Store │    │  Output      │
            │  (SQLite)    │    │  (Markdown/  │
            │              │    │   JSON)      │
            └──────────────┘    └──────────────┘
```

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

---

## Indexing

The skill maintains an incremental index stored in `.project-understanding/`:

- `index.db`: SQLite database with symbol and reference information
- `checksums.json`: File checksums for incremental updates
- `config.yaml`: Skill configuration

The index is automatically updated when files change.

---

## Token Budgeting

All outputs are designed to fit within token limits:

- **Repo map**: Summarized structure, expandable on demand
- **Analysis**: Focused summaries with drill-down capability
- **Call graphs**: Pruned to most relevant paths
- **Impact reports**: Prioritized by significance

---

## References

- `ARCHITECTURE.md` - System design details
- `API.md` - Command reference
- `INDEXING.md` - Index management
- `LANGUAGES.md` - Language support details

---

## Development

See `DEVELOPMENT.md` for contribution guidelines.

---

## License

MIT License - See repository LICENSE file
