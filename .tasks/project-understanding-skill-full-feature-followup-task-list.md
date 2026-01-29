# Project Understanding Skill — Follow‑up Task List for “Full Feature” Status

## Preamble (what “full feature” means)
This follow‑up plan takes the v1 “RepoMap/Zoom/Impact via Tree‑sitter + heuristic graph” skill and upgrades it into a **high‑precision, production-grade project intelligence skill** suitable for daily use on large, polyglot codebases.

**Full feature status** here means:
- **Semantic-accurate navigation** where possible (go-to-definition, references, call hierarchy).
- **Reliable impact analysis** based on resolved dependencies (plus explicit confidence fallbacks).
- **Multi-language support** with a scalable extension mechanism.
- **Fast incremental indexing** (watch mode, large repo performance).
- **Strong portability** across common agent hosts and developer machines.
- **Security hardening**, reproducibility, and CI quality gates.
- **Publish-ready polish** (docs, examples, compatibility matrix, versioning).

---

## Full Feature Definition of Done (DoD)
- [ ] **Semantic edges** (defs/refs/calls) are resolved via LSP/SCIP for supported languages; heuristic edges remain as fallback with clear confidence labels.
- [ ] **ImpactPack** includes: upstream callers, downstream callees, import/module deps, test selection candidates, and a ranked “next files” list with explanations.
- [ ] Skill supports **watch mode** and incremental updates under 2s for small diffs on medium repos.
- [ ] Supports at least **10+ major languages** (with a documented extension model).
- [ ] Provides **graph exports** (Mermaid + DOT) for call/module graphs.
- [ ] Runs on **Windows/macOS/Linux** with a single bootstrap and no manual grammar compilation for common languages.
- [ ] CI includes unit + integration + performance smoke tests; releases are tagged and changelogged.
- [ ] Security: path sandboxing, dependency pinning, safe execution, and clear threat model.
- [ ] Published and installable via `npx skills add org/repo`, with validated skill pages on skills.sh.

---

## Phase 1 — Semantic enrichment (turn “best‑effort” into “accurate”)

### 1.1 Provider architecture (mandatory)
- [ ] Create a `SemanticProvider` interface (in `scripts/lib/providers/`):
  - [ ] `get_definitions(file, position)` (optional)
  - [ ] `get_references(symbol_id)` (optional)
  - [ ] `get_call_hierarchy(symbol_id)` (optional)
  - [ ] `resolve_imports(file)` (optional)
- [ ] Implement provider registry + configuration:
  - [ ] `--semantic none|lsp|scip|auto`
  - [ ] `auto` prefers SCIP > LSP > heuristic

### 1.2 LSP provider (high value, medium complexity)
- [ ] Implement an LSP runner abstraction:
  - [ ] spawn language server
  - [ ] manage init/handshake
  - [ ] request: document symbols, references, call hierarchy, workspace symbols
- [ ] Add per-language LSP profiles:
  - [ ] TS/JS: `typescript-language-server`
  - [ ] Python: `pyright`/`pylsp` (choose one; document tradeoffs)
  - [ ] Go: `gopls`
  - [ ] Rust: `rust-analyzer`
  - [ ] Java: `jdtls` (optional)
- [ ] Cache LSP results in DB with source tag `source="lsp"` and `confidence=1.0`
- [ ] Add timeouts and fallbacks:
  - [ ] if LSP fails, degrade to heuristic edges with a warning section in packs

### 1.3 SCIP provider (highest precision where available)
- [ ] Implement SCIP ingestion:
  - [ ] detect `.scip` files in repo or configured path
  - [ ] parse and ingest definitions, references, and occurrences into DB edges
- [ ] Add “SCIP generation helpers”:
  - [ ] for repos already using Sourcegraph tooling
  - [ ] keep this optional; don’t require it for baseline usage
- [ ] Mark edges with `source="scip"` and `confidence=1.0`

### 1.4 Edge reconciliation and precedence
- [ ] Add edge merge rules:
  - [ ] resolved edges override heuristic edges when both exist
  - [ ] keep heuristic edges only if no resolved edges for that scope/symbol
- [ ] Add “edge provenance” in `meta` (provider, timestamp, query version)

---

## Phase 2 — Graph accuracy and richer dependency modeling

### 2.1 Module/package dependency graph
- [ ] Add module/package nodes (workspace-aware):
  - [ ] for JS/TS: packages via package.json workspaces
  - [ ] for Python: pyproject/requirements (best-effort)
  - [ ] for Go: go.mod modules
  - [ ] for Rust: Cargo workspace crates
- [ ] Add edges:
  - [ ] `MODULE_DEPENDS_ON`
  - [ ] `EXPORTS` / `IMPORTS_FROM`
- [ ] Provide `pui depgraph --format mermaid|dot --scope module|package`

### 2.2 Call graph improvements
- [ ] Distinguish call types:
  - [ ] direct function call
  - [ ] method dispatch (unknown receiver type → lower confidence unless resolved)
  - [ ] higher-order calls (callbacks) flagged explicitly
- [ ] Add call graph compression:
  - [ ] collapse trivial wrappers
  - [ ] group by module boundary in RepoMapPack

### 2.3 “Confidence semantics” (make uncertainty actionable)
- [ ] Define confidence bands:
  - [ ] `1.0` resolved
  - [ ] `0.7–0.9` strong heuristic (same module + unique match)
  - [ ] `0.3–0.6` weak heuristic (many matches)
- [ ] Update packs to:
  - [ ] show confidence by band
  - [ ] include “how to confirm” instructions when low confidence

---

## Phase 3 — Impact analysis v2 (change implications that hold up)

### 3.1 Diff-aware impact
- [ ] Add `pui impact --git-diff`:
  - [ ] compute changed files and symbol spans from git diff
  - [ ] map edits to affected symbols
  - [ ] compute blast radius (callers/callees + module deps)
- [ ] Add `pui impact --from <commit> --to <commit>`

### 3.2 Test selection intelligence
- [ ] Add “test mapping” signals:
  - [ ] reference edges to test files
  - [ ] naming conventions (Foo → FooTest)
  - [ ] directory adjacency heuristics
  - [ ] (Optional) coverage-informed mapping if coverage reports exist
- [ ] Output “candidate tests to run” ranked with explanation

### 3.3 API boundary and contract impact
- [ ] Identify “public API surface”:
  - [ ] exported symbols
  - [ ] public classes/interfaces
  - [ ] CLI commands / endpoints (framework heuristics)
- [ ] ImpactPack includes “API risk” section:
  - [ ] if a change touches public API, elevate severity

---

## Phase 4 — Pack UX upgrades (better zoom, better maps, less noise)

### 4.1 Budget negotiation and adaptive detail
- [ ] Add `--budget auto`:
  - [ ] detects model/context constraints when host provides them
  - [ ] otherwise uses config defaults
- [ ] Implement priority-based truncation:
  - [ ] keep headings + IDs
  - [ ] drop low-ranked sections first
  - [ ] always include “how to retrieve more” hints

### 4.2 Better “skeletonization”
- [ ] Language-aware skeleton strategies:
  - [ ] preserve function signature + doc + key branches
  - [ ] keep lines containing calls, exceptions, returns, logging
  - [ ] collapse loops/blocks with stable placeholders
- [ ] Add `--zoom full|skeleton|min` levels

### 4.3 Graph exports for human review
- [ ] Add `pui graph --symbol <id> --depth 2 --format mermaid|dot`
- [ ] Include a Mermaid block in packs when requested

---

## Phase 5 — Large repo performance & incremental indexing

### 5.1 Watch mode (developer-grade usability)
- [ ] Add `pui watch`:
  - [ ] file watcher (cross-platform)
  - [ ] debounced updates
  - [ ] prints update stats
- [ ] Add “index lock” and concurrent access handling

### 5.2 Parallel parsing and caching
- [ ] Add multi-process parsing (configurable)
- [ ] Cache Tree-sitter parse trees or intermediate artifacts (optional)
- [ ] Use WAL mode for SQLite and tuned indices

### 5.3 Scalability guardrails
- [ ] Add hard limits:
  - [ ] maximum symbols per file (with overflow notes)
  - [ ] maximum edges per symbol
- [ ] Add “topology compression”:
  - [ ] collapse auto-generated code directories by default

---

## Phase 6 — Portability and distribution hardening

### 6.1 Cross-platform bootstrap improvements
- [ ] Support:
  - [ ] Python-only install path
  - [ ] optional “single binary” releases (PyInstaller) for users without Python
- [ ] Add OS detection + clear error messaging

### 6.2 Dependency pinning & reproducibility
- [ ] Add lockfiles:
  - [ ] `requirements.txt` pinned
  - [ ] optional `requirements.lock` generated
- [ ] Add “offline mode” instructions and vendored grammar fallback (if needed)

### 6.3 Host adapters (optional, keep skill portable)
- [ ] Provide optional wrappers:
  - [ ] `scripts/pui` shell shim
  - [ ] `scripts/pui.ps1` PowerShell shim
- [ ] Ensure outputs are deterministic across shells

---

## Phase 7 — Security and safety (must for “publishable”)

### 7.1 Threat model + sandboxing
- [ ] Write `references/SECURITY.md`:
  - [ ] filesystem access scope
  - [ ] what is executed (and what is not)
- [ ] Enforce path allowlisting:
  - [ ] only read under repo root (no `..` traversal)
- [ ] No arbitrary shell execution from skill scripts unless explicitly invoked by the user

### 7.2 Supply chain hygiene
- [ ] Pin dependencies
- [ ] Add dependabot (optional)
- [ ] Release tagging + checksums for binaries (if provided)

---

## Phase 8 — Quality gates, benchmarks, and real-world validation

### 8.1 Golden outputs and regression suite
- [ ] Add golden tests for packs on fixture repos:
  - [ ] repomap stable ordering
  - [ ] zoom stable skeleton
  - [ ] impact stable ranking given fixed inputs
- [ ] Add versioned fixtures for multiple languages

### 8.2 Performance benchmarks
- [ ] Add `pui benchmark`:
  - [ ] index cold start time
  - [ ] incremental update time
  - [ ] query latency (repomap/zoom/impact)
- [ ] CI performance smoke test (non-flaky thresholds)

### 8.3 Agent-host compatibility checks
- [ ] Document and test:
  - [ ] Claude Code skill activation + script execution
  - [ ] OpenCode skill activation
  - [ ] Gemini CLI skill activation
- [ ] Add a “compat matrix” in README:
  - [ ] required permissions
  - [ ] known limitations per host

---

## Phase 9 — Marketplace polish (skills.sh excellence)

### 9.1 Documentation upgrades
- [ ] Add a concise, user-first `SKILL.md` quickstart:
  - [ ] 3-command onboarding
  - [ ] “How to use in refactors”
  - [ ] “How to use before edits”
- [ ] Add animated GIF/screencast links in repo README (optional)
- [ ] Add “FAQ” section

### 9.2 Versioning and changelog
- [ ] Add `CHANGELOG.md` (Keep a Changelog format)
- [ ] Tag releases `vX.Y.Z`
- [ ] Add “upgrade notes” for schema migrations

---

## Phase 10 — Optional “advanced intelligence” (only after stability)

### 10.1 Dataflow & side-effect heuristics
- [ ] Add a lightweight “effect summary” per function:
  - [ ] writes to db/files/network
  - [ ] mutates globals
  - [ ] throws/raises
- [ ] Include in ZoomPack/ImpactPack when available

### 10.2 Architecture inference
- [ ] Detect frameworks and layers:
  - [ ] web routes/controllers/services/repositories
  - [ ] CLI commands
  - [ ] event handlers
- [ ] Add an “ArchitecturePack” (optional) summarizing layers and key entrypoints

### 10.3 Multi-repo / workspace federation
- [ ] Support indexing multiple repos and linking dependencies between them
- [ ] Add `--workspace` config and a unified graph view

---

## Deliverables checklist (full feature)
- [ ] `SemanticProvider` implemented with `auto` mode
- [ ] LSP provider integrated for major languages
- [ ] SCIP ingestion integrated
- [ ] Graph exports (Mermaid + DOT)
- [ ] Diff-aware ImpactPack with test selection
- [ ] Watch mode + performance tuning
- [ ] Security doc + sandboxing
- [ ] Benchmarks and regression suite
- [ ] Release process + changelog
- [ ] skills.sh page shows clean docs and examples

