# Security Documentation

## Threat Model

This document outlines the security considerations for the Project Understanding Skill.

### Asset Inventory

| Asset | Sensitivity | Description |
|-------|-------------|-------------|
| Source Code | High | Repository source files being analyzed |
| Index Database | Medium | SQLite database with parsed symbols and relationships |
| Configuration | Low | Skill configuration files |

### Threat Actors

| Actor | Motivation | Capability |
|-------|------------|------------|
| Malicious Repository | Exploit parser vulnerabilities | Can craft malicious source files |
| Compromised Environment | Data exfiltration | System-level access |
| Malicious Skill Code | Privilege escalation | Code execution in skill context |

### Threat Scenarios

#### T1: Path Traversal via Malicious File Paths
- **Risk**: High
- **Description**: Malicious repository contains files with `../` paths
- **Impact**: Read files outside repository root
- **Mitigation**: Path sandboxing (see below)

#### T2: Parser Exploitation
- **Risk**: Medium
- **Description**: Malformed source triggers parser vulnerability
- **Impact**: Memory corruption or infinite loops
- **Mitigation**: Tree-sitter's safe parsing, timeouts

#### T3: Resource Exhaustion
- **Risk**: Medium
- **Description**: Extremely large files cause OOM
- **Impact**: Denial of service
- **Mitigation**: File size limits, memory monitoring

#### T4: Dependency Confusion
- **Risk**: Medium
- **Description**: Malicious package uploaded to PyPI with same name
- **Impact**: Supply chain attack
- **Mitigation**: Pinned dependencies, checksums

## Filesystem Access Scope

### Allowed Operations

The skill performs read-only access to:
- Source files within the repository root
- The `.pui/` directory for index storage
- Standard Python library modules

### Path Sandboxing

All file paths are validated to ensure they remain within the repository root:

```python
def validate_path(path: Path, repo_root: Path) -> Path:
    """Ensure path does not escape repository root."""
    resolved = (repo_root / path).resolve()
    if not str(resolved).startswith(str(repo_root.resolve())):
        raise SecurityError(f"Path escapes repository root: {path}")
    return resolved
```

### Implementation Details

1. **Path Resolution**: All paths are resolved to absolute paths before validation
2. **Symlink Handling**: Symlinks are followed but target must remain within repo root
3. **No Write Access**: The skill never modifies source files
4. **Database Location**: Index database is stored in `.pui/index.sqlite` only

## No Arbitrary Shell Execution

### Policy

The Project Understanding Skill **never** executes arbitrary shell commands. This includes:

- No `os.system()` calls
- No `subprocess.run()` with user input
- No `eval()` or `exec()` on untrusted data
- No compilation or execution of analyzed code

### Allowed Shell Usage

The only permitted shell interactions are:

1. **Git Integration**: Read-only git operations (status, log, diff)
2. **Bootstrap Script**: One-time setup with hardcoded commands

### Audit Trail

All file system operations are logged:
```
DEBUG: Reading file: src/main.py
DEBUG: Writing database: .pui/index.sqlite
DEBUG: Git operation: git diff --name-only
```

## Supply Chain Security

### Pinned Dependencies

All dependencies are pinned to exact versions in `requirements.txt`:

```
tree-sitter==0.20.4
tree-sitter-languages==1.10.2
# ... etc
```

### Hash Verification (Optional)

For high-security environments, dependencies can be verified with hashes:

```bash
pip install -r requirements.txt --require-hashes
```

### Dependabot Configuration

To enable automated security updates, add `.github/dependabot.yml`:

```yaml
version: 2
updates:
  - package-ecosystem: "pip"
    directory: "/"
    schedule:
      interval: "weekly"
    open-pull-requests-limit: 10
```

### Release Tagging

All releases follow semantic versioning with signed tags:

```bash
git tag -s v1.0.0 -m "Release v1.0.0"
git push origin v1.0.0
```

### Checksums

Release artifacts include SHA-256 checksums:

```bash
sha256sum project-understanding-skill.tar.gz > checksums.txt
```

## Security Checklist

### For Users

- [ ] Verify skill is from official source
- [ ] Check that `.pui/` directory is in `.gitignore`
- [ ] Review permissions before running in sensitive repositories

### For Contributors

- [ ] No shell execution added in PR
- [ ] Path traversal protection in place
- [ ] Dependencies pinned
- [ ] Security test added for new features

### For Maintainers

- [ ] Dependencies updated quarterly
- [ ] Security advisories monitored
- [ ] Release artifacts signed
- [ ] Security documentation updated

## Reporting Security Issues

If you discover a security vulnerability:

1. **DO NOT** open a public issue
2. Email security concerns to: security@example.com
3. Include reproduction steps and impact assessment
4. Allow 90 days for disclosure

## Security Testing

### Automated Tests

Run security-focused tests:

```bash
pytest tests/test_security.py -v
```

### Manual Testing

Verify path sandboxing:

```bash
# Attempt path traversal (should fail)
echo "test" > src/../../../etc/passwd
pui index  # Should not read outside repo
```

### Fuzzing

For parser security testing:

```bash
# Install fuzzing dependencies
pip install fuzzingbook

# Run fuzzer
python tests/fuzz_parser.py
```

## Compliance

### Data Protection

- No source code leaves the local machine
- No telemetry or analytics collected
- Index database contains only metadata (no full file contents)

### Audit Requirements

- All file access logged
- Database operations tracked
- Git operations recorded

---

**Last Updated**: 2026-01-30  
**Version**: 1.0.0  
**Next Review**: 2026-04-30
