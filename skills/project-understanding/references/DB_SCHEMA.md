# Database Schema

This document describes the SQLite database schema used by the Project Understanding Index (PUI).

## Overview

The database is stored at `<repo>/.pui/index.sqlite` and contains tables for:
- File metadata and content hashes
- Symbol definitions and references
- Call graph edges between symbols
- Call site information

## Tables

### files

Stores metadata about indexed source files.

| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER PRIMARY KEY | Unique file identifier |
| path | TEXT UNIQUE NOT NULL | Relative path from repo root |
| mtime | INTEGER NOT NULL | Last modification timestamp (Unix epoch) |
| size | INTEGER NOT NULL | File size in bytes |
| content_hash | TEXT NOT NULL | SHA256 hash of file content |
| indexed_at | INTEGER NOT NULL | When file was last indexed (Unix epoch) |
| language | TEXT | Detected programming language |

**Indices:**
- `idx_files_path` (path) - Fast lookup by path
- `idx_files_language` (language) - Filter by language

### symbols

Stores symbol definitions (functions, classes, variables, etc.).

| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER PRIMARY KEY | Unique symbol identifier |
| file_id | INTEGER NOT NULL | Reference to files.id |
| name | TEXT NOT NULL | Symbol name |
| kind | TEXT NOT NULL | Symbol type (function, class, method, variable, etc.) |
| line_start | INTEGER NOT NULL | Starting line number (1-indexed) |
| line_end | INTEGER | Ending line number (1-indexed) |
| column_start | INTEGER | Starting column (0-indexed) |
| column_end | INTEGER | Ending column |
| signature | TEXT | Function signature or type annotation |
| docstring | TEXT | Associated documentation |
| parent_id | INTEGER | Reference to parent symbol (for nested definitions) |

**Indices:**
- `idx_symbols_file` (file_id) - Find symbols in a file
- `idx_symbols_name` (name) - Lookup by name
- `idx_symbols_kind` (kind) - Filter by type
- `idx_symbols_parent` (parent_id) - Find children of a symbol

**Full-Text Search:**
- Virtual table `symbols_fts` for fuzzy name matching

### edges

Stores relationships between symbols (calls, inherits, contains, etc.).

| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER PRIMARY KEY | Unique edge identifier |
| source_id | INTEGER NOT NULL | Source symbol (caller, parent, etc.) |
| target_id | INTEGER NOT NULL | Target symbol (callee, child, etc.) |
| kind | TEXT NOT NULL | Relationship type (call, inherit, contain, import, etc.) |
| file_id | INTEGER NOT NULL | File where relationship occurs |

**Indices:**
- `idx_edges_source` (source_id) - Outgoing edges from a symbol
- `idx_edges_target` (target_id) - Incoming edges to a symbol
- `idx_edges_kind` (kind) - Filter by relationship type
- `idx_edges_file` (file_id) - Find edges in a file

### callsites

Stores specific call site information.

| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER PRIMARY KEY | Unique callsite identifier |
| edge_id | INTEGER NOT NULL | Reference to edges.id |
| line | INTEGER NOT NULL | Line number of call site |
| column | INTEGER | Column position |
| context | TEXT | Surrounding code context |

**Indices:**
- `idx_callsites_edge` (edge_id) - Find callsites for an edge
- `idx_callsites_line` (line) - Find callsites by location

### meta

Stores metadata about the index itself.

| Column | Type | Description |
|--------|------|-------------|
| key | TEXT PRIMARY KEY | Metadata key |
| value | TEXT | Metadata value |

**Standard Keys:**
- `schema_version` - Current schema version (integer)
- `created_at` - Index creation timestamp
- `last_indexed` - Last successful index run
- `indexed_files` - Count of indexed files
- `indexed_symbols` - Count of indexed symbols

## Schema Versioning

The schema uses semantic versioning:
- Major version changes require rebuild
- Minor version changes support migration
- Patch version changes are backwards compatible

### Migration Strategy

1. Check `meta.schema_version` on connection
2. If outdated, run migration scripts in sequence
3. Migrations are idempotent and transactional
4. Failed migrations rollback and report error

## FTS Index

The Full-Text Search index uses SQLite's FTS5 extension:

```sql
CREATE VIRTUAL TABLE symbols_fts USING fts5(
    name,
    content='symbols',
    content_rowid='id'
);
```

This enables efficient fuzzy matching for symbol search with:
- Prefix matching: `name:^prefix`
- Suffix matching: `name:suffix$`
- Boolean operators: `AND`, `OR`, `NOT`

## Performance Considerations

1. **Write Performance**: Use batched transactions (100-1000 files per batch)
2. **Read Performance**: All lookup columns are indexed
3. **Storage**: Content hashes prevent duplicate storage of unchanged files
4. **Incremental Updates**: Only modified files are re-parsed

## Example Queries

### Find all functions in a file
```sql
SELECT s.name, s.line_start, s.line_end
FROM symbols s
JOIN files f ON s.file_id = f.id
WHERE f.path = 'src/main.py' AND s.kind = 'function';
```

### Find all callers of a function
```sql
SELECT f.path, s.name, cs.line
FROM symbols s
JOIN edges e ON s.id = e.target_id
JOIN symbols caller ON e.source_id = caller.id
JOIN files f ON caller.file_id = f.id
LEFT JOIN callsites cs ON e.id = cs.edge_id
WHERE s.name = 'my_function' AND e.kind = 'call';
```

### Fuzzy symbol search
```sql
SELECT s.*, rank
FROM symbols_fts
JOIN symbols s ON symbols_fts.rowid = s.id
WHERE symbols_fts MATCH 'func*'
ORDER BY rank;
```

### Get call graph depth
```sql
WITH RECURSIVE call_chain AS (
    SELECT target_id, 0 as depth
    FROM edges
    WHERE source_id = ? AND kind = 'call'
    
    UNION ALL
    
    SELECT e.target_id, cc.depth + 1
    FROM edges e
    JOIN call_chain cc ON e.source_id = cc.target_id
    WHERE e.kind = 'call' AND cc.depth < 5
)
SELECT * FROM call_chain;
```
