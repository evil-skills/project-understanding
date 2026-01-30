# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Architecture inference for framework detection (web routes, CLI commands)
- Dataflow heuristics for effect analysis (DB, file, network operations)
- Multi-repo federation with `--workspace` config
- Benchmark command for performance testing
- Golden snapshot tests for pack outputs
- Security documentation (SECURITY.md)
- Compatibility matrix for Claude Code, OpenCode, and Gemini CLI

### Changed
- Improved token budget enforcement across all pack types
- Enhanced impact analysis with transitive dependency tracking

### Fixed
- Path traversal vulnerability in file access
- Race condition in incremental indexing

## [0.1.0] - 2026-01-30

### Added
- Initial release of Project Understanding Skill
- Repository Map (RepoMapPack) for global architecture view
- ZoomPack for symbol-level detailed analysis
- ImpactPack for change impact assessment
- Tree-sitter based parsing for Python, JavaScript, TypeScript, Go, Rust
- Incremental indexing with file hash tracking
- Dependency graph construction with confidence scoring
- Token budget management for LLM context windows
- CLI interface with `pui` command
- Bootstrap script for environment setup
- Comprehensive test suite (unit and integration tests)
- Git integration for change detection
- Ignore patterns (.gitignore, .puiignore support)
- Language support documentation
- Pack format specification
- Database schema documentation
- Troubleshooting guide

### Security
- Path sandboxing to prevent directory traversal
- No arbitrary shell execution
- Pinned dependencies in requirements.txt

---

## Upgrade Notes

### Upgrading to 0.2.0 (Upcoming)

**Prerequisites:**
- Re-index your repositories: `pui index --force`
- Update workspace config for multi-repo support

**Breaking Changes:**
- Database schema updated (auto-migration on first run)
- New required field in config: `architecture_detection`

**Migration Steps:**
1. Backup existing `.pui/` directories
2. Run `pui index --force` in each repository
3. Update any custom ignore patterns

### Upgrading to 0.1.0

Initial installation - no upgrade steps required.

---

## Release Checklist Template

Use this checklist when preparing a release:

```markdown
## Release X.Y.Z

### Pre-Release
- [ ] Version bumped in SKILL.md frontmatter
- [ ] CHANGELOG.md updated
- [ ] All tests passing (`pytest`)
- [ ] Linting clean (`ruff check .`)
- [ ] Security review completed
- [ ] Documentation updated

### Release
- [ ] Git tag created: `git tag -s vX.Y.Z`
- [ ] Tag pushed: `git push origin vX.Y.Z`
- [ ] GitHub release created
- [ ] Release notes published
- [ ] Checksums generated

### Post-Release
- [ ] Skills registry updated
- [ ] Announcement published
- [ ] Migration guide updated (if breaking changes)
```

---

**View all releases:** https://github.com/project-understanding-skill/releases
