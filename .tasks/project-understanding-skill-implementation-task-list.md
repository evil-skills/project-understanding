# Project Understanding Skill — Implementation Task List

## Preamble (motivation + expected outcome)

### Motivation
Modern coding agents struggle to build and maintain a **global mental model** of a repository without flooding the model context window with raw code. This causes repeated “re-discovery” of architecture and fragile edits that miss hidden dependencies. The goal of this project is to ship a **publishable Agent Skill** that gives any LLM-based coding agent an **on-demand, token-budgeted view** of:
- the repo’s **global architecture** (“repo map”),
- the ability to **zoom** to a file/symbol/function-level summary,
- a **dependency/call graph** view (callers/callees) to support **impact analysis** before changes.

### Expected outcome
A public GitHub repository containing a skill directory that:
- follows the **Agent Skills specification** (`SKILL.md` w/ YAML frontmatter + progressive disclosure layout),
- is discoverable by the Skills CLI and installable via:

  ```bash
  npx skills add org/repo
  ```

- is “marketplace-ready” (renderable on https://skills.sh/ and usable across Claude Code, OpenCode, Gemini CLI, and other skill-compatible agents),
- ships a **local code-intelligence engine** (Tree-sitter–based) that maintains an incremental index + dependency graph and emits **strictly token-budgeted context packs**: `RepoMapPack`, `ZoomPack`, `ImpactPack`.

### Non-goals (v1)
- Perfect semantic call resolution for highly dynamic languages (Python/JS reflection/DI). v1 will provide **best-effort** call graphs with confidence annotations and clear limitations.
- Building a full IDE-grade language server. We will integrate optional semantic enrichers later (LSP/SCIP) behind provider interfaces.

### Constraints and design principles
- **Progressive disclosure:** keep `SKILL.md` concise; move large docs into `references/`.
- **Deterministic outputs:** packs must be stable, bounded, and easy for LLMs to parse.
- **Low friction:** indexing must be incremental, fast, and runnable from a single command.
- **Portable execution:** scripts must run on typical dev machines; dependencies must be clearly bootstrapped.

---

## Repository layout (target)

> The Skills CLI discovers skills in standard locations (including `skills/`), so we will ship a single-skill repo with one directory: `skills/project-understanding/`.

```
repo-root/
  README.md
  LICENSE
  .gitignore
  .github/
    workflows/
      ci.yml
  skills/
    project-understanding/
      SKILL.md
      scripts/
        pui.py
        bootstrap.py
        lib/
          __init__.py
          config.py
          ignore.py
          tokens.py
          db.py
          indexer.py
          queries/
            python.scm
            javascript.scm
            typescript.scm
            go.scm
            rust.scm
          graph.py
          packs.py
      references/
        REFERENCE.md
        PACK_FORMAT.md
        DB_SCHEMA.md
        LANG_SUPPORT.md
        TROUBLESHOOTING.md
      assets/
        default-ignore.txt
```

---

## Definition of Done (DoD)

- [ ] `npx skills add org/repo` installs the skill and it appears in `npx skills list`
- [ ] Skill passes `skills-ref validate` (and CI enforces it)
- [ ] `SKILL.md` frontmatter `name` matches the directory name (`project-understanding`)
- [ ] `SKILL.md` ≤ 500 lines and uses progressive disclosure with `references/`
- [ ] Running the skill scripts on a medium repo produces:
  - [ ] `repomap` output under the requested token budget
  - [ ] `zoom` output under budget and includes callers/callees (best-effort)
  - [ ] `impact` output under budget with ranked affected symbols/files
- [ ] The repo is public and renderable at `https://skills.sh/<org>/<repo>/project-understanding`

---

## Phase 0 — Project setup & scaffolding

### 0.1 Create the Git repository
- [ ] Create a new GitHub repo (public) named e.g. `project-understanding-skill`
- [ ] Add a permissive license (`MIT` or `Apache-2.0`) as `LICENSE`
- [ ] Add `README.md` (repo-level) including:
  - [ ] what the skill does (1–2 paragraphs)
  - [ ] install command(s): `npx skills add org/repo` and optional `--skill project-understanding`
  - [ ] quick demo commands (index → repomap → zoom → impact)
  - [ ] compatibility (Python required; optional tools)
- [ ] Add `.gitignore` (Python + SQLite + caches)

### 0.2 Scaffold the skill directory
- [ ] Create `skills/project-understanding/`
- [ ] Create `skills/project-understanding/SKILL.md` with required YAML frontmatter:
  - [ ] `name: project-understanding`
  - [ ] `description: ...` (include keywords: repo map, architecture, Tree-sitter, call graph, impact analysis)
  - [ ] Optional (recommended):
    - [ ] `license: MIT` (or reference the repo LICENSE)
    - [ ] `compatibility: Requires Python 3.10+; optional git; local filesystem access; optional internet for bootstrap`
    - [ ] `metadata: { author: <org>, version: "0.1.0" }`
- [ ] Create subdirectories:
  - [ ] `skills/project-understanding/scripts/`
  - [ ] `skills/project-understanding/references/`
  - [ ] `skills/project-understanding/assets/`

### 0.3 Add validation & CI early
- [ ] Add `skills/project-understanding/references/REFERENCE.md` (placeholder) and keep `SKILL.md` concise
- [ ] Add GitHub Action `.github/workflows/ci.yml` that runs:
  - [ ] `python -m pip install skills-ref` (or the official install per skills-ref docs)
  - [ ] `skills-ref validate skills/project-understanding`
  - [ ] basic Python linting (ruff) and formatting checks
  - [ ] unit tests (pytest)
- [ ] Add a “release checklist” section to the repo README

---

## Phase 1 — UX contract: commands + pack formats

### 1.1 Decide the user-facing CLI contract (single entrypoint)
- [ ] Implement a single command runner:
  - [ ] `python skills/project-understanding/scripts/pui.py <subcommand> [args]`
- [ ] Define subcommands and required output formats:
  - [ ] `bootstrap` — sets up local runtime deps (if needed)
  - [ ] `index` — builds/updates index database
  - [ ] `repomap` — prints RepoMapPack (Markdown default)
  - [ ] `find` — fuzzy symbol search (JSON default; Markdown option)
  - [ ] `zoom` — prints ZoomPack for a file/symbol
  - [ ] `impact` — prints ImpactPack for a changed set

### 1.2 Specify pack schemas (write docs first)
- [ ] Create `references/PACK_FORMAT.md` defining:
  - [ ] `RepoMapPack` structure (sections + fields)
  - [ ] `ZoomPack` structure (signature, doc, skeleton, callers/callees, code slice)
  - [ ] `ImpactPack` structure (changed items, upstream/downstream, tests, ranked files)
  - [ ] Budgeting rules (hard truncation + “more available via zoom” pointers)
- [ ] Add “example outputs” for each pack (small, medium)
- [ ] Define a stable machine-readable footer block in each pack:
  - [ ] e.g., `<!-- PUI: {...json...} -->` containing ids + hashes (optional)

### 1.3 Token budgeting strategy
- [ ] Implement `scripts/lib/tokens.py`:
  - [ ] `estimate_tokens(text) -> int` (simple heuristic, documented)
  - [ ] `truncate_to_budget(text, budget_tokens) -> text` (preserve section boundaries)
- [ ] Add unit tests for deterministic truncation

---

## Phase 2 — Index DB + incremental scanning

### 2.1 Database schema
- [ ] Create `references/DB_SCHEMA.md` documenting tables and indices
- [ ] Implement `scripts/lib/db.py` to manage SQLite DB at:
  - [ ] `<repo>/.pui/index.sqlite` (default)
- [ ] Tables (minimum v1):
  - [ ] `files(path TEXT PRIMARY KEY, lang TEXT, sha1 TEXT, mtime INT, size INT)`
  - [ ] `symbols(id TEXT PRIMARY KEY, path TEXT, kind TEXT, name TEXT, qualname TEXT, start_line INT, end_line INT, signature TEXT)`
  - [ ] `edges(src_id TEXT, dst_id TEXT, kind TEXT, confidence REAL, meta JSON)`
  - [ ] `callsites(id TEXT PRIMARY KEY, path TEXT, line INT, callee_text TEXT, scope_symbol_id TEXT, meta JSON)`
  - [ ] FTS index for symbol search (`symbols_fts` on `name`, `qualname`, `signature`)
- [ ] Add migrations/versioning:
  - [ ] `meta(key TEXT PRIMARY KEY, value TEXT)` with `schema_version`

### 2.2 File discovery and ignore rules
- [ ] Implement `scripts/lib/ignore.py`:
  - [ ] merge `.gitignore` + `assets/default-ignore.txt`
  - [ ] allow CLI `--include` / `--exclude` overrides
- [ ] Implement `scripts/lib/config.py` to store defaults in `.pui/config.json`:
  - [ ] budgets
  - [ ] languages enabled
  - [ ] ignore patterns

### 2.3 Incremental indexing loop
- [ ] Implement `scripts/lib/indexer.py`:
  - [ ] scan candidate files
  - [ ] determine language by extension
  - [ ] compute hash/mtime; skip unchanged
  - [ ] delete stale symbols/edges for removed files
  - [ ] (re)parse changed files → update `files`, `symbols`, `callsites`, and candidate `edges`

### 2.4 Make it fast enough
- [ ] Add batching transactions (one transaction per N files)
- [ ] Add timing logs (optional, behind `--verbose`)
- [ ] Add a `pui index --stats` summary (files scanned, parsed, skipped, time)

---

## Phase 3 — Tree-sitter parsing: symbols, imports, call-sites

### 3.1 Choose Tree-sitter runtime + grammars
- [ ] Implement in Python using Tree-sitter bindings.
- [ ] Decide grammar source strategy:
  - [ ] Option A (recommended): `tree_sitter_languages` for prebuilt grammars
  - [ ] Option B: vendor selected grammars in-repo and build locally
- [ ] Document required system deps (if any) in `compatibility`

### 3.2 Language query files
- [ ] Add `scripts/lib/queries/<lang>.scm` Tree-sitter queries for:
  - [ ] function/method definitions (name + parameters span)
  - [ ] class definitions
  - [ ] import declarations
  - [ ] call expressions (callee identifier/member expression)
- [ ] Start with these languages in v1:
  - [ ] Python
  - [ ] JavaScript
  - [ ] TypeScript
  - [ ] Go
  - [ ] Rust
- [ ] Add `references/LANG_SUPPORT.md` documenting:
  - [ ] supported languages
  - [ ] known limitations per language (dynamic dispatch, macros, etc.)
  - [ ] fallbacks (regex outline if no grammar)

### 3.3 Build symbol extraction
- [ ] Implement `scripts/lib/indexer.py::extract_symbols(ast, path, lang)`
  - [ ] compute stable `symbol_id` (e.g., `path:kind:qualname:start_line`)
  - [ ] extract signature text (best-effort, language-specific)
  - [ ] store spans for later `zoom`
- [ ] Implement unit tests using small fixture files for each language

### 3.4 Build import graph extraction
- [ ] Implement `extract_imports(...)` → edges:
  - [ ] `edges(kind="IMPORTS", src=file_node, dst=module/file node when resolvable)`
  - [ ] store raw import text when not resolvable (meta)

### 3.5 Build call-site extraction + candidate call edges
- [ ] Implement `extract_callsites(...)`:
  - [ ] capture `callee_text` (e.g., `foo`, `obj.foo`, `pkg.Foo`)
  - [ ] attach containing symbol (`scope_symbol_id`)
- [ ] Implement candidate edge construction:
  - [ ] resolve `foo` → all symbols with `name=foo` (within same file/module preferred)
  - [ ] resolve `obj.foo` → symbols with `name=foo` (lower confidence)
  - [ ] use import hints to boost confidence
- [ ] Store candidate `CALLS` edges with `confidence` and `meta` explaining heuristic

---

## Phase 4 — Graph engine: callers, callees, impact analysis

### 4.1 Graph query API
- [ ] Implement `scripts/lib/graph.py` functions:
  - [ ] `callers(symbol_id, depth=1, min_conf=0.0) -> list`
  - [ ] `callees(symbol_id, depth=1, min_conf=0.0) -> list`
  - [ ] `impact(changed_symbol_ids|paths, depth=2) -> ranked results`
- [ ] Ensure graph traversals:
  - [ ] avoid cycles (visited set)
  - [ ] output stable ordering (deterministic)
  - [ ] include confidence aggregation (min/avg)

### 4.2 Impact ranking
- [ ] Ranking heuristic (v1):
  - [ ] primary: number of upstream callers (fan-in)
  - [ ] secondary: test proximity (edges to test files)
  - [ ] tertiary: file centrality (import fan-in/out)
- [ ] Implement test file detection:
  - [ ] language-aware patterns (`test_*.py`, `*_test.go`, `*.spec.ts`, etc.)
- [ ] Add `--explain` mode to show why an item is ranked

---

## Phase 5 — Pack generators (the real “context-efficient view”)

### 5.1 RepoMapPack generator
- [ ] Implement `scripts/lib/packs.py::repomap(budget_tokens, focus_paths=None)`
  - [ ] emit:
    - [ ] collapsed directory tree (depth-limited)
    - [ ] top files list (ranked)
    - [ ] per-file top symbols (signature-only)
    - [ ] “major dependency edges” summary
  - [ ] enforce token budget (truncate)
- [ ] Add an option `--focus <path|glob>` to prioritize a subtree
- [ ] Add snapshot tests (“golden files”) for deterministic output

### 5.2 ZoomPack generator
- [ ] Implement `zoom(symbol_id|path, budget_tokens, include_code_slice=true)`
  - [ ] locate symbol span and load code slice
  - [ ] produce a “skeleton body”:
    - [ ] keep signature + docstring/comments
    - [ ] keep lines containing calls/imports/returns/raises
    - [ ] collapse long blocks with `…`
  - [ ] attach callers/callees (depth=1)
  - [ ] enforce token budget (truncate lower-priority sections first)
- [ ] Add tests for:
  - [ ] correct span extraction
  - [ ] skeletonization determinism

### 5.3 ImpactPack generator
- [ ] Implement `impact(changed_paths|symbol_ids, depth, budget_tokens)`
  - [ ] identify changed symbols (by file or explicit ids)
  - [ ] traverse callers/callees
  - [ ] list affected tests + files
  - [ ] output “next files to inspect” ranked list
  - [ ] enforce token budget

---

## Phase 6 — Skill authoring: SKILL.md content & progressive disclosure

### 6.1 Write the SKILL.md body (keep it short)
- [ ] Sections to include (recommended):
  - [ ] **When to use** (activation keywords)
  - [ ] **Quick start** (bootstrap → index → repomap → zoom → impact)
  - [ ] **Common workflows** (refactor, add feature, fix bug)
  - [ ] **How to interpret confidence** (call graph quality)
  - [ ] **Where to read more** (links to `references/*.md`)
- [ ] Keep `SKILL.md` under 500 lines; push details into `references/` files

### 6.2 Add reference docs
- [ ] `references/REFERENCE.md`: deep technical overview + troubleshooting pointers
- [ ] `references/TROUBLESHOOTING.md`: common failures (missing Python, grammar install, permissions)
- [ ] `references/LANG_SUPPORT.md`: supported languages and known gaps
- [ ] `references/DB_SCHEMA.md`: DB design, edges, confidence
- [ ] `references/PACK_FORMAT.md`: stable schemas and examples

### 6.3 Add assets
- [ ] `assets/default-ignore.txt`: ignore patterns (node_modules, dist, build, vendor, .git, etc.)

---

## Phase 7 — Bootstrapping and portability

### 7.1 Bootstrap strategy (choose one and implement)
- [ ] Strategy A (recommended): create a local venv under `.pui/venv/` and install deps on-demand
  - [ ] `python scripts/bootstrap.py`:
    - [ ] create venv if missing
    - [ ] install pinned deps (requirements lock)
    - [ ] print the exact command the agent should run next (no ambiguity)
- [ ] Strategy B: require user-managed environment and fail with actionable instructions

### 7.2 Dependency management
- [ ] Add `skills/project-understanding/scripts/requirements.txt` (pinned)
- [ ] Document “offline” behavior:
  - [ ] if no internet, bootstrap should degrade gracefully and explain required packages

---

## Phase 8 — Testing & quality gates

### 8.1 Unit tests (fast)
- [ ] Add `tests/` (repo root or skill-local) for:
  - [ ] token budgeting + truncation
  - [ ] symbol extraction correctness on fixtures
  - [ ] deterministic pack output ordering
  - [ ] DB migration/version checks

### 8.2 Integration tests (real repos)
- [ ] Add a small fixture repo under `tests/fixtures/sample-repo/`
- [ ] Add a CI job that:
  - [ ] runs `pui bootstrap` (if applicable)
  - [ ] runs `pui index` on the fixture
  - [ ] runs `repomap/zoom/impact` and checks output is non-empty and within budgets

### 8.3 Performance smoke test
- [ ] Add a `pui index --stats` benchmark mode
- [ ] Document expected baseline times on a medium repo (informational)

---

## Phase 9 — Publish readiness: install + render on skills.sh

### 9.1 Verify Skills CLI discovery and install
- [ ] From a clean machine (or CI), run:
  - [ ] `npx skills add <org>/<repo>`
  - [ ] Confirm the skill is installed and visible:
    - [ ] `npx skills list`
  - [ ] Optionally verify targeted install:
    - [ ] `npx skills add <org>/<repo> --skill project-understanding`
- [ ] Confirm the installed folder contains:
  - [ ] `SKILL.md`
  - [ ] `scripts/` and `references/` present

### 9.2 Validate spec compliance
- [ ] Run:
  - [ ] `skills-ref validate skills/project-understanding`
- [ ] Fix any frontmatter naming, path, or formatting violations

### 9.3 skills.sh rendering check
- [ ] Confirm the skill page renders:
  - [ ] `https://skills.sh/<org>/<repo>/project-understanding`
- [ ] Ensure the SKILL.md is readable and not excessively long

---

## Phase 10 — Optional v2: semantic enrichment (LSP/SCIP)

> Keep this out of v1. Only start after v1 DoD is met.

- [ ] Define a provider interface `SemanticProvider`:
  - [ ] `definitions()`, `references()`, `call_hierarchy()`
- [ ] Add optional LSP-based resolver (per language) behind `--semantic lsp`
- [ ] Add optional SCIP ingestion behind `--semantic scip`
- [ ] Store resolved edges with `confidence=1.0`, keep candidate edges as fallback
- [ ] Update packs to prefer resolved edges and show “source: resolved|heuristic”

---

## Deliverables checklist (what should exist in the final repo)

- [ ] `skills/project-understanding/SKILL.md` (spec-compliant)
- [ ] `skills/project-understanding/scripts/pui.py` with subcommands:
  - [ ] `bootstrap`, `index`, `repomap`, `find`, `zoom`, `impact`
- [ ] `skills/project-understanding/references/` complete docs set
- [ ] `assets/default-ignore.txt`
- [ ] CI workflow validates the skill and runs tests
- [ ] Repo README explains install + usage and links to the skills.sh page

