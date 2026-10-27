# Ternfold 0.2 — Codex / ChatGPT implementation control

This is the **active supervisor operating manual** for Codex (CLI, IDE, desktop or cloud when the repository is accessible) and repository-capable ChatGPT Work. The repository holds persistent truth; an ordinary ChatGPT text conversation without workspace access can review the files but cannot serve as a persistent local build agent. No OpenAI service is a compiler dependency.

## Startup: do this, then implement

1. Read root `AGENTS.md` and this manual. Read `docs/codex-handoff.md` and `docs/progress.md`.
2. Reconcile `git status`, branches/worktrees/diffs, current source/tests, unfinished agent handoffs, and `docs/tasks.json`; actual evidence overrides stale status prose. This source ZIP has no `.git` metadata: if not yet in a Git checkout, inspect files/task records directly and report Git/worktree features as unavailable until the user initializes or connects a repository. Do not invent commit identity.
3. Read `docs/implementation-plan.md`, the earliest eligible incomplete `docs/tasks/<ID>.md`, `docs/course-requirements.md`, ADR 0009 and only task-relevant normative documents and tests.
4. Run `python scripts/bootstrap.py` if required (offline mode allowed with cached wheels); identify venv Python as `.venv/Scripts/python.exe` (Windows) or `.venv/bin/python` (POSIX). Run `<venv-python> scripts/check_environment.py --phase frontend`, `<venv-python> scripts/check_codex_workspace.py`, and `<venv-python> scripts/dev.py check`. M10/M11 require `--phase native` and a verified C17 compiler.
5. Resume an interrupted eligible task, close completed-but-unverified work, or implement the next task. **Do not write another approval-gated implementation plan.** The task briefs authorize implementation; ask only at real authorization/destructive/irreducible semantic boundaries.

## Stage 1 delivered; Stage 2 resumed

Standalone lexical analyzer ZIP and lexical-only repository publication are
verified complete under S01. M08 is active again. S01 tracks the strict name-DFA correction,
exact two-column report, stdlib-only package and fresh isolated verification.
Preserve partial M08 and all full-project source/config/evidence; resume Stage 2
after verified lexical delivery. Do not package this orchestration manual or
unfinished compiler dependencies. See active handoff and docs/tasks/S01.md.

## Current source of truth

**Ternfold 0.2**, specified by `docs/language-spec.md`, `docs/grammar.md`, `docs/type-system.md`, `docs/module-system.md`, `docs/standard-library.md`, `docs/runtime.md`, `docs/core-ir.md` and ADRs 0001–0010. `docs/course-requirements.md`, `docs/automata.md` and `docs/course-acceptance.json` bind the classroom deliverables. The original immutable-machine semantics stay in force. **M00 and C00 are documentation/scaffold complete; M01–M07 source through machine planning are verified under the earlier numerical contract; C01 real-division/Float amendments are verified; M08 verified Core/lowering is complete; M09 interpreter is active.** The M01–M06 partially completed Antigravity session was intentionally **not** imported into this fresh restart.

## Active authorized correction (received during M07)

Professor clarification makes `/7` and `/9` required operator counts: seven
arithmetic `+ - / * % div ^` and nine logical/relational
`&& || ! > < == != >= <=`. Accepted ADR 0010 defines real `/` returning finite
binary64 Float and integer `div`, preserving immutable machines and the pipeline.
C01 has verified lexical/type/constant/report amendments; M08 now implements Core.
Preserve completed evidence and coordinated ownership. Reconcile all eleven
lexical rubric items with runnable tests and actual deterministic UTF-8
`Symbol Table.txt`; documentation and historical passes do not verify new rules.
Schema-2 acceptance metadata distinguishes specified, implemented, tested,
reviewed, verified and blocked. See active recovery context in the handoff.

## Implementation and delegation

The primary Codex supervisor owns tasks, integration, review, verification and progress. The project exposes bounded specialist agents in `.codex/agents/*.toml`: `frontend-engineer`, `semantics-core-engineer`, `backend-runtime-engineer`, `quality-engineer`, `reviewer`. Route substantial subsystem work to the matching agent when native subagent support is present and improves the outcome. The supervisor may directly implement small/integrative work. If subagents are unavailable (e.g., some ChatGPT surfaces), work sequentially and apply the same independent review checklist—do not pretend an unavailable agent was invoked. No overlapping writers to the same AST/type/Core/module/ABI contract; max three subagents configured in `.codex/config.toml`.

Effort routing (when supported): **low** mechanical/reconnaissance; **medium** bounded implementation under fixed contracts; **high** type/machine semantics, grammar ambiguity, Core/lowering, ABI/ownership, backend, cross-phase bugs, milestone or specification review. Keep agent role distinct from effort and avoid hard-coded models; use the selected model and available effort setting. For critical reviews, choose High. Use the skill `$ternfold-orchestration` for nontrivial routing, `$ternfold-feature` on language changes, `$ternfold-spec-audit` for cross-layer changes, and `$ternfold-differential` once dual execution paths exist (skills live in `.agents/skills/`).

Bounded delegation format: **task ID; goal; files/interfaces; normative sections/ADRs; invariants; explicit non-goals; acceptance and tests; verification commands; requested effort; expected handoff.** Handoff: actual diff/files, tests, command outcomes, risks, remaining actions. Read-only reviewer should not be the implementer. Confirm user approval only when required by permissions or meaningful unresolved design decisions.

## Task algorithm and milestone gates

Select the earliest eligible task in `docs/tasks.json` whose prerequisites have been verified; finish any interrupted owner task first. Do not advance the task graph to escape a failing test; in particular M05 resolution must remain independent of unimplemented M06 type checking. Keep phase interfaces honest.

After focused implementation, run targeted positive/invalid/boundary tests, canonical Ruff/mypy/pytest/course/doc/workspace gates, and an independent review when semantics or architecture is involved. Broader High review is required at M04, M07, M09, M11 and M14. Differential testing is required after interpreter M09 and backend M11. Do not mask failures with skips or weakened tests. A static course mapping audit is **not** executable course evidence. Record verified results and task acceptance criteria in `docs/tasks.json`, `docs/progress.md`, and the task brief; update `docs/course-acceptance.json` only when real tests support the claimed status. Continue to the next eligible task automatically if safe.

## Recovery and safety

For quota/session interruptions: inspect Git status, diffs, worktrees, existing agent outputs, tests, and progress before resuming. Preserve correct partial work; avoid duplicating live workers, overwriting unintegrated changes, or marking unverified work complete. Leave an honest exact next action. Do not delete worktrees without reviewing unmerged changes.

Language behavior changes require normative spec/grammar/ADR updates and tests; do not silently redesign Ternfold. No Python `eval`/`exec`, regex translation, host-semantic shortcuts, unsound C ownership, ambient filesystem access, secrets, hosted compile/runtime APIs, or fabricated verification. Use `sys.executable`, pathlib, and explicit UTF-8 for portable scripts. Compiler remains offline-capable after dependencies are installed.

At meaningful stopping points, report completed task, actual tests/review, blockers, and next task; do not require this conversation for resumption.

## Quality-enhanced coding protocol (Codex)

Preserve language scope and outputs: these additions improve implementation quality only. On nontrivial feature work invoke `$ternfold-test-design`, then use the owning existing specialist (frontend/semantics/backend) for bounded implementation; no generic planning approval gate. On defects activate `$ternfold-debugging` to reproduce and isolate the first wrong compiler phase. At acceptance invoke `$ternfold-verified-completion` **with fresh outputs**, not an old test summary. For M02–M04 use `$ternfold-lexical-conformance`; for M10/M11/M16 use `$ternfold-native-safety`.

Independent review: a distinct `reviewer` reads the diff and test evidence. For M05–M09 or semantic/core milestones, request the read-only `semantic-auditor` to find adversarial counterexamples when useful. For C17/runtime/memory changes, the read-only `native-safety-auditor` is mandatory before accepting M10/M11; these auditors do not write production code. Run read-only audits in parallel when appropriate, but **do not** spawn overlapping code writers. Agent caps stay at three. No hard-pinned model names; use High reasoning for semantic/native review and escalate after repeated errors.

Tests are evidence, not a performance: introduce focused failing regression cases first when practical, assert valid/invalid/boundary behavior, and retain provenance of concrete command results. If a task references a feature owned by a future phase, do not pull in that phase simply to green the current test suite. Course rubric acceptance is independently evidenced by runnable `.tfd` examples and `Symbol Table.txt` assertions, not simply DFA figures.

The research/provenance for the five project-specific quality skills is in `docs/github-skills-research.md`. These are **new locally authored procedures inspired by inspected public skills**; they are not falsely presented as exact vendored GitHub packages. They require no external service or installation. Verify via `python scripts/validate_skills.py`, `python scripts/check_codex_workspace.py`, and canonical project gates.

Per-agent High reasoning defaults are configured for semantic/backend specialists and reviewers/auditors through supported `model_reasoning_effort` keys, with explicit task-level effort taking precedence where Codex exposes it. No model ID is hard-pinned.
