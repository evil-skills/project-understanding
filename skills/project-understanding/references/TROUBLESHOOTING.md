# Troubleshooting Guide

Common issues and solutions for the Project Understanding Skill.

---

## Installation Issues

### Tree-sitter Build Failures

**Symptom:**
```
ERROR: Failed building wheel for tree-sitter
```

**Cause:** Missing C compiler or system dependencies.

**Solution:**

```bash
# Ubuntu/Debian
sudo apt-get install build-essential python3-dev

# macOS
xcode-select --install

# Windows (with Visual Studio Build Tools)
pip install --upgrade setuptools wheel
```

### Import Errors

**Symptom:**
```
ModuleNotFoundError: No module named 'tree_sitter'
```

**Solution:**

```bash
# Reinstall with dependencies
pip install --force-reinstall tree-sitter tree-sitter-languages

# Verify installation
python -c "import tree_sitter; print(tree_sitter.__version__)"
```

---

## Index Issues

### Index Build Hangs

**Symptom:** Indexing appears frozen or takes excessive time.

**Causes & Solutions:**

1. **Binary files being parsed**
   ```bash
   # Add to .puiignore
   *.png
   *.jpg
   *.pdf
   *.zip
   ```

2. **Large generated files**
   ```yaml
   # .project-understanding.yaml
   index:
     max_file_size: 524288  # 512KB limit
     exclude_dirs:
       - generated
       - dist
       - build
   ```

3. **Too many workers**
   ```yaml
   # Reduce parallelism
   index:
     workers: 2  # Default is CPU count
   ```

### "Database is locked" Error

**Symptom:**
```
sqlite3.OperationalError: database is locked
```

**Cause:** Multiple processes trying to access the index simultaneously.

**Solution:**

```bash
# Kill any hanging processes
pkill -f "project-understanding"

# Wait a moment, then retry
sleep 2
opencode skill project-understanding index build
```

### Corrupted Index

**Symptom:** Strange errors, missing data, or crashes during queries.

**Solution:**

```bash
# Clean and rebuild
opencode skill project-understanding index clean
opencode skill project-understanding index build

# Verify integrity
opencode skill project-understanding index verify
```

### Index Out of Date

**Symptom:** Analysis shows stale information or missing recently added code.

**Solution:**

```bash
# Update incrementally (fast)
opencode skill project-understanding index update

# Or force full rebuild (slower but thorough)
opencode skill project-understanding index clean && opencode skill project-understanding index build
```

---

## Parsing Issues

### Files Not Being Indexed

**Symptom:** Certain files don't appear in repo-map or analysis.

**Check:**

1. **File extension support**
   ```bash
   # Check if language is supported
   opencode skill project-understanding index status
   ```

2. **Ignore patterns**
   ```bash
   # Check .puiignore and default ignores
   cat .puiignore
   ```

3. **File size limit**
   ```bash
   # Check file size
   ls -lh path/to/file
   ```

**Solution:**

```yaml
# .project-understanding.yaml
index:
  max_file_size: 2097152  # Increase to 2MB
  include_extensions:
    - .mycustomext  # Add custom extensions
```

### Syntax Errors in Valid Files

**Symptom:** Files with valid syntax show parsing errors.

**Causes:**

1. **Language mismatch** - File extension doesn't match content
2. **Unusual syntax** - New language features not yet supported
3. **Encoding issues** - Non-UTF8 characters

**Solution:**

```bash
# Force specific language
opencode skill project-understanding index build --language python

# Check file encoding
file -i path/to/file

# Convert encoding if needed
iconv -f ISO-8859-1 -t UTF-8 path/to/file > path/to/file.utf8
```

### Partial Parse Results

**Symptom:** Some symbols missing from analysis.

**Cause:** Tree-sitter recovered from syntax errors but skipped some nodes.

**Solution:**
- Check `.pui/parsing_errors.log` for details
- Fix syntax errors if possible
- For complex macros/templates, consider using simpler syntax

---

## Query Issues

### "Symbol not found" Errors

**Symptom:**
```
Symbol 'MyClass' not found in index
```

**Causes & Solutions:**

1. **Symbol not yet indexed**
   ```bash
   opencode skill project-understanding index update
   ```

2. **Case sensitivity**
   ```bash
   # Try different cases
   opencode skill project-understanding analyze --target myclass
   opencode skill project-understanding analyze --target MyClass
   opencode skill project-understanding analyze --target MYCLASS
   ```

3. **Symbol in unindexed file**
   ```bash
   # Check file is indexed
   opencode skill project-understanding repo-map --focus path/to/file
   ```

### Empty Call Graphs

**Symptom:** Call graph returns no results.

**Check:**

1. **Symbol has no calls**
   - Verify the symbol is actually called elsewhere

2. **Low confidence filtered out**
   ```bash
   # Lower confidence threshold
   opencode skill project-understanding call-graph --symbol MyFunc --min-confidence 0.3
   ```

3. **Direction mismatch**
   ```bash
   # Try all directions
   opencode skill project-understanding call-graph --symbol MyFunc --direction both
   ```

### Slow Queries

**Symptom:** Commands take too long to return.

**Solutions:**

1. **Limit scope**
   ```bash
   # Focus on specific directory
   opencode skill project-understanding repo-map --focus src/core/
   ```

2. **Reduce depth**
   ```bash
   # Limit call graph depth
   opencode skill project-understanding call-graph --symbol X --depth 2
   ```

3. **Rebuild index with optimizations**
   ```yaml
   # .project-understanding.yaml
   index:
     batch_size: 200
   ```

---

## Output Issues

### Garbled or Truncated Output

**Symptom:** Markdown tables broken, Unicode errors.

**Cause:** Terminal encoding issues.

**Solution:**

```bash
# Set UTF-8 encoding
export LANG=en_US.UTF-8
export PYTHONIOENCODING=utf-8

# Or use JSON output
opencode skill project-understanding repo-map --format json
```

### Too Much Output

**Symptom:** Output exceeds screen buffer or token limits.

**Solution:**

```bash
# Limit depth
opencode skill project-understanding repo-map --depth 2

# Focus on specific area
opencode skill project-understanding repo-map --focus src/

# Limit files shown
opencode skill project-understanding repo-map --max-files 50
```

### Colors Not Showing

**Symptom:** Output lacks syntax highlighting.

**Solution:**

```yaml
# .project-understanding.yaml
output:
  colors: true
  force_color: true  # Even when piping
```

Or use environment variable:
```bash
export FORCE_COLOR=1
```

---

## Configuration Issues

### Configuration Not Applied

**Symptom:** Changes to `.project-understanding.yaml` have no effect.

**Check:**

1. **File location** - Must be in repository root
2. **YAML syntax** - Validate with:
   ```bash
   python -c "import yaml; yaml.safe_load(open('.project-understanding.yaml'))"
   ```
3. **Cache** - Configuration may be cached:
   ```bash
   opencode skill project-understanding index clean
   ```

### Wrong Language Detection

**Symptom:** Files parsed as wrong language.

**Solution:**

```yaml
# .project-understanding.yaml
parsing:
  language_overrides:
    *.h: c
    *.hpp: cpp
    *.pyx: python
```

---

## Performance Issues

### High Memory Usage

**Symptom:** System runs out of memory during indexing.

**Solutions:**

```yaml
# Reduce batch size
index:
  batch_size: 50
  workers: 1

# Exclude large directories
  exclude_dirs:
    - node_modules
    - .venv
    - venv
    - __pycache__
```

### Slow Initial Index

**Symptom:** First index takes hours on large codebases.

**Solutions:**

1. **Index by language**
   ```bash
   # Index only priority languages first
   opencode skill project-understanding index build --language python
   opencode skill project-understanding index build --language javascript
   ```

2. **Exclude non-essential files**
   ```yaml
   index:
     exclude_dirs:
       - tests
       - docs
       - examples
   ```

3. **Use SSD for index storage**
   - SQLite performance is significantly better on SSD

---

## Integration Issues

### Git Hook Failures

**Symptom:** Pre-commit hooks fail when skill runs.

**Solution:**

```bash
# Skip hooks during indexing
opencode skill project-understanding index build --no-hooks

# Or disable git integration
export PUI_SKIP_GIT=1
```

### CI/CD Timeouts

**Symptom:** Index build times out in CI.

**Solution:**

```bash
# Use shallower analysis in CI
opencode skill project-understanding repo-map --depth 1 --max-files 100

# Or skip index and use file scanning
opencode skill project-understanding repo-map --no-index
```

---

## Getting Help

If issues persist:

1. **Check logs:**
   ```bash
   cat .pui/parsing_errors.log
   cat .pui/index.log
   ```

2. **Run diagnostics:**
   ```bash
   opencode skill project-understanding index status --verbose
   ```

3. **Enable debug output:**
   ```bash
   export PUI_DEBUG=1
   opencode skill project-understanding <command>
   ```

4. **Report issues:**
   - Include error messages
   - Provide minimal reproduction steps
   - Attach `.pui/parsing_errors.log` if relevant
