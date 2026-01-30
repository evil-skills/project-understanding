# Project Understanding Skill: Improvement Insights

Based on an analysis of the LeanBoost (C++) codebase, the following areas have been identified for improvement in the `project-understanding` skill.

## 1. Parser Accuracy & Language Support
*   **C++ Support:** The tool failed to extract symbols from C++ files, resulting in `None (file)` entries in the repository map. Tree-sitter queries for C/C++ need to be verified or implemented.
*   **False Positives in Framework Detection:** The tool hallucinated Python/Web frameworks (FastAPI, Django, pytest) in a native C++ Windows utility project. Heuristics for architecture detection must be strictly scoped to the detected language.

## 2. Context Isolation (Sandboxing)
*   **Internal Data Leakage:** The tool included its own test fixtures (Python/Rust/Go files) in the architectural analysis of the project. This led to a file count of 176 models when the project only had 83 files.
*   **Exclusion Logic:** The tool must automatically exclude its own skill directory, virtual environments (`.pui/venv`), and internal test directories from the indexing process.

## 3. CLI & Documentation Consistency
*   **Command Parity:** The skill's internal prompt instructions suggested commands like `index build` and flags like `--depth`, which are not supported by the actual `pui.sh` implementation.
*   **UX Alignment:** Ensure that the "Base Workflow" described in the skill metadata matches the current CLI arguments exactly.

## 4. Architectural Heuristics
*   **Static Categories:** The "Application Layers" analysis is currently biased toward Web/MVC patterns (routes, controllers). It should be updated to recognize native application patterns (core, UI, services, engines).
*   **Importance Scoring:** The "Top Files by Importance" list currently weights all files equally (1 symbol). Heuristics should be improved to weight files based on symbol density, cross-references, or central directory roles (e.g., `src/core`).

## 5. Metadata & Indexing
*   **Dependency Mapping:** The tool reported 0 edges despite the project having a clear library-based dependency structure in `CMakeLists.txt`. It should attempt to resolve local `#include` relationships to build a meaningful dependency graph.
