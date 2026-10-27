# Codex project-local skills

Codex discovers skills under `.agents/skills/<name>/SKILL.md` (YAML name/description). These procedures are repository-authored, offline-capable and subordinate to the normative language specification. The external GitHub sources studied (with links and inspected blob SHA IDs) are recorded in `docs/github-skills-research.md`; no third-party code was vendored or installed.

| Skill | Use when | Primary users |
|---|---|---|
| `$ternfold-orchestration` | Nontrivial bounded delegation, safe parallelism | supervisor |
| `$ternfold-feature` | Cross-phase Ternfold feature implementation | compiler specialists |
| `$ternfold-spec-audit` | Specification/code invariants and milestone consistency | reviewer, semantic-auditor |
| `$ternfold-differential` | Interpreter vs C backend observable parity | quality, backend |
| `$ternfold-test-design` | Valid/invalid/boundary tests, diagnostics, Hypothesis/property coverage | all implementers, quality |
| `$ternfold-debugging` | Failures, wrong outputs, phase divergence | all implementers |
| `$ternfold-verified-completion` | Fresh evidence and task/course signoff | supervisor, reviewer |
| `$ternfold-lexical-conformance` | DFA, lexer, invalid tokens and `Symbol Table.txt` | frontend, quality |
| `$ternfold-native-safety` | C17 ABI, memory ownership, fault cleanup | backend, native-safety-auditor |

Each skill triggers only for its own repeated procedure; skip irrelevant skills. The two independent read-only auditors are *agents*, not skills. Agents must read relevant skills explicitly in bounded task instructions; auto-discovery is client-specific. Validate with `python scripts/validate_skills.py` and `python scripts/check_codex_workspace.py`. Live agent discovery/delegation must be checked inside a running Codex client; static validation is not evidence of actual spawning.
