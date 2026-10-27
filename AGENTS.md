# Ternfold 0.2 repository engineering rules — Codex / ChatGPT

**Read `MASTER_IMPLEMENTATION.md` for execution policy and `docs/codex-handoff.md` for current state.** `AGENTS.md` is auto-discovered by Codex. Do not restart the original language design. The target is course-aligned **Ternfold 0.2**, not the 0.1 proposal or interrupted M06 experiment.

## Non-negotiable correctness

- Immutable machine snapshots: old reads remain old; lexical `next.cell` reads create dependencies; one writer per cell; cycles reject; ready candidates schedule in ASCII name order. All candidates finish before guards; the first failed ordered guard determines a typed rejection; emissions only publish on success. Runtime faults are not typed rejection and cannot leak partial output.
- Source → tokens → AST → resolution → types → machine plan → verified Core → interpreter and structured C17 backend. Executables consume verified Core; no regex translation, Python `eval`/`exec`, direct AST interpretation after Core is canonical, or C undefined-behavior shortcuts.
- Ternfold 0.2 additions in ADRs 0009–0010: real `/`, finite binary64 Float, checked `^`, floor `div`, Char, `/*...*/`, optional `from`/`to` readability words, main-only staged input/output and pure single/nested `for` comprehensions. Preserve machine purity. For classroom compliance use `docs/course-requirements.md`, `docs/automata.md`, and `docs/course-acceptance.json`.
- Mandatory professor clarification received during M07: seven arithmetic `+ - / * % div ^` and nine logical/relational `&& || ! > < == != >= <=` are operator counts, not points. `/` must perform real division, distinct from integer `div`. Preserve completed work and active writers; follow accepted ADR 0010 and corrective C01 before Core interfaces. The full eleven-item lexical rubric requires executable tests and an actual UTF-8 `Symbol Table.txt`; documentation alone is not evidence.
- No dependency on ChatGPT, Codex, APIs, MCP or hosted services to compile/run Ternfold; no credentials/secrets in repo. Subprocesses use argv lists and safe path handling.

## Stage 1 lexical submission priority (2026-10-28)

S01 delivered the verified standalone Ternfold_Lexical_Analyzer_Submission.zip
and matching lexical-only GitHub content; M08 is now resumed. Preserve the
reviewed lexical artifact while implementing later compiler phases. Reuse the production scanner with explicit character
DFA/trie transitions for names/keywords/reserved/noise; no completed-word lookup,
spelling-set recognition, regex tokenization or premade analyzer/generator.
Classroom Symbol Table.txt has exactly TOKEN TYPE and LEXEME columns, source
order, comments/invalid rows and documented reversible escaping. Rich internal
APIs stay separate. Package stdlib-only dependencies, launchers/examples/tests/
DFA/evidence; exclude orchestration/config/compiler/caches from the submission.
Verify fresh extraction outside checkout and independently review before delivery.
Supplied lexical-only GitHub repository is authorized for update; inspect history,
use existing configured identity/access, no forcepush or invented attribution.

## Source of truth and discipline

Normative: `docs/language-spec.md`, `docs/grammar.md`, `docs/type-system.md`, `docs/module-system.md`, `docs/standard-library.md`, `docs/core-ir.md`, `docs/runtime.md`, `docs/architecture.md`, `docs/compiler-pipeline.md`, ADRs 0001–0010. Tasks/status: `docs/tasks.json`, `docs/tasks/*.md`, `docs/progress.md`; `docs/testing.md` governs quality. Specs and tests outrank agent summaries; contradictions require documented change procedure, not implicit reinterpretation.

A task is not complete with a happy path. Cover valid, invalid, boundary, diagnostics and execution, plus interpreter/native parity once both exist. Update affected syntax/AST/resolution/types/IR/interpreter/backend/runtime/docs coherently. Keep M05 resolution separate from unfinished M06 types. Run required focused and full checks; do not weaken assertions, hide failures, or prematurely mark a task/course requirement complete. Record actual files/commands/results and independent review evidence. No new approval-plan gate: existing roadmap authorizes work, subject to real permission/destructive/semantic blockers.

## Canonical commands (run from repository root)

`python scripts/bootstrap.py` then `<venv-python> scripts/check_environment.py --phase frontend` and `<venv-python> scripts/dev.py check`. `<venv-python>` is `.venv\Scripts\python.exe` on Windows or `.venv/bin/python` on POSIX. Additional checks: `<venv-python> scripts/check_codex_workspace.py`, `scripts/audit_docs.py`, `scripts/course_audit.py`, `scripts/dev.py build`. Native milestones: environment check `--phase native`. `dev.py build` builds Python packaging only until the real Ternfold compiler is implemented.

## Codex agents and skills

Project agents: `.codex/agents/` (`frontend-engineer`, `semantics-core-engineer`, `backend-runtime-engineer`, `quality-engineer`, `reviewer`). Skills: `.agents/skills/` (`$ternfold-feature`, `$ternfold-spec-audit`, `$ternfold-differential`, `$ternfold-orchestration`). Use specialist delegation for substantial work when available; supervisor integrates, verifies and reviews. A missing subagent facility is a capability limitation, not permission to pretend delegation happened. Use disjoint worktrees for parallel writers; do not overlap shared semantics contracts. For semantic/architecture changes invoke `$ternfold-spec-audit`; for interpreter/backend equivalence invoke `$ternfold-differential` once runnable.

## Files and safety

Use Python >=3.12,<3.15, strict typing, frozen slotted semantic records, structured spans/diagnostics, and the existing dependency boundaries. Never hand-edit `uv.lock` hashes. Generated C, wheels, coverage, venv/caches are ignored; maintained fixtures/tests/specs are committed. Never invent Git identity, publish or push without authorization. Historical Antigravity/Codex instructions in `docs/archive/` are not active. The output of a prior ChatGPT conversation cannot replace repository evidence.

## Code quality and independent audits

Do not optimize agent count or prompt length at the expense of correctness. Use `$ternfold-test-design` on substantive tasks, `$ternfold-debugging` on failures, and `$ternfold-verified-completion` before claiming completion; reserve `$ternfold-lexical-conformance` for lexer/automata/reporting and `$ternfold-native-safety` for C/ABI. Reviewer remains read-only; `semantic-auditor` and `native-safety-auditor` provide targeted adversarial audits. The supervisor integrates and owns evidence. No second approval-gated plan, no premature later-phase work, no repetition after quota interruption, no guessed tests. Project-local skill content is original and offline-capable; see `docs/github-skills-research.md` for researched upstream workflows.
