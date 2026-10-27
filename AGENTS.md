# Ternfold 0.2 — C17 engineering rules

Read MASTER_IMPLEMENTATION.md first and docs/codex-handoff.md for current state.
The entire implementation targets ISO C17; the historical Python host is
superseded by ADR 0011, not silently relabeled as C completion.

## Correctness

Source → tokens → AST → resolution → types → machine plan → verified Core →
interpreter / structured C17 backend. Executors consume verified Core. No regex
translation, host eval, AST execution shortcuts or undefined behavior.
Immutable snapshots retain old reads. Lexical next.cell reads create dependencies;
one writer per cell; cycles reject; ready cells use ASCII name order. All
candidates finish before ordered guards; first false guard determines typed
rejection; emissions publish only on success. Faults never leak partial output.
Preserve ADRs 0009–0010, including real /, floor div, checked powers, Float,
Char, comments, readability words, pure comprehensions and staged main I/O.
I/O-bearing root main is entry-only E208; main without I/O remains callable.

## Workflow

Read normative specs, task graph/brief and course requirements. Retain M00–M17,
X01, C00/C01/S01, their dependencies and acceptance intent. M15–M17/X01 are
optional after M14. Immediate C lexer delivery is C-MIGRATION-01. Never restart
historical work or infer C success from Python passes. No second approval plan.
Use explicit ownership, checked size arithmetic, deterministic cleanup, stable
IDs/spans, immutable semantic records and well-defined evaluation order. No
mutable global compiler state. No hosted service or Python build/runtime dependency.
Subprocesses use safe argv and paths; never construct shell command text from input.

## Commands

`./scripts/build.ps1 environment`, `./scripts/build.ps1 check`,
`./scripts/build.ps1 sanitize` on Windows. Intended POSIX equivalents:
`sh scripts/build.sh environment`, `check`, `sanitize`. Full check includes
warning-clean compilation, native unit/integration tests and C repository audit.
Package with scripts/package.ps1 and verify fresh extraction with
scripts/verify-archives.ps1. Unsupported platform/compiler claims remain pending.

## Agents and skills

Configured roles in .codex/agents: frontend-engineer, semantics-core-engineer,
backend-runtime-engineer, quality-engineer, reviewer, semantic-auditor,
native-safety-auditor. Max three; high effort for ownership/semantic/native risk.
Delegate substantial bounded work when available; supervisor integrates/reviews.
Use disjoint worktrees for parallel writers. Reviewers/auditors remain read-only.
Use ternfold-orchestration, feature, test-design, spec-audit; lexical-conformance
for scanner/report work; debugging for failures; native-safety for C ownership;
differential once executors exist; verified-completion before acceptance.

Run valid, invalid, boundary, diagnostics, allocation-failure and sanitizer checks.
Obtain independent review; update task/progress/course metadata with actual
commands/results, not guessed passes. Preserve proposal PDFs unchanged. Never
invent attribution, credentials or Git identity. Existing GitHub foundation update
is authorized; retain history and inspect remote changes, never blind force-push.
