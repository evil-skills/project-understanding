# Sample Repository

This is a sample repository for integration testing the project-understanding skill.

## Structure

- `src/` - Source code files in multiple languages
  - Python files (main.py, utils.py, models.py)
  - JavaScript files (api.js, types.js)
  - Go files (server.go, store.go)
  - Rust files (main.rs, handlers.rs)
- `tests/` - Test files
- `docs/` - Documentation

## Purpose

This fixture repository is used to test:
- Multi-language parsing (Python, JavaScript, Go, Rust)
- Symbol extraction
- Import/call graph construction
- Pack generation (repomap, zoom, impact)
- Token budget enforcement

## Testing

Run integration tests:
```bash
pytest tests/test_integration.py -v
```
