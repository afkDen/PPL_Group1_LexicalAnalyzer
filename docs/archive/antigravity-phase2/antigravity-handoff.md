# Antigravity handoff — Ternfold implementation control

This repository is prepared for Antigravity with an **available user-selected Gemini supervisor, preferably High reasoning**. Gemini 3.8 Flash is a historical Phase-2 reference, not a hard requirement. It contains all required project context without the original conversation. Start at repository root; do not restart language design.

## Identity and current state

Ternfold `.tfd`: **propose together, validate in order, publish together**. It is a pure, static, nominally typed language whose immutable machines expose old-state reads, compiler-scheduled candidate dependencies, ordered typed rejection and delayed emissions. Its purpose is inspectable/replayable application and simulation state transitions.

Phase 1 froze the 0.1 language/architecture and created the task graph. Production source still implements only the package entrypoint/status CLI; the transition experiment is not a language interpreter. **M00 is complete; M01 — source snapshots and byte spans — is the next eligible implementation task.** Phase 2 changed implementation orchestration only; it did not alter Ternfold semantics or complete any compiler task.

## Read and run in this order

1. `MASTER_IMPLEMENTATION.md`.
2. Root `AGENTS.md`, this handoff, `docs/progress.md`.
3. `docs/tasks.json`, `docs/implementation-plan.md`, and the next task brief.
4. Relevant normative language/grammar/type/module/runtime/architecture/ADR documents.
5. Existing source/tests/examples plus relevant `.agents/skills/` procedure.

```sh
python3 scripts/bootstrap.py
.venv/bin/python scripts/check_environment.py
.venv/bin/python scripts/check_antigravity_workspace.py
.venv/bin/python scripts/dev.py check
.venv/bin/python scripts/audit_docs.py
.venv/bin/ternfold status
```

A fresh machine needs normal dependency access once unless its uv cache/wheelhouse is already populated. No account/API key/MCP/cloud service is required by the compiler.

## Antigravity setup

Root `AGENTS.md` is the persistent engineering ruleset. Workspace custom agents are in `.agents/agents/`; project skills are in `.agents/skills/`. No new legacy `.agents/workflows/` are used because current Antigravity documentation is migrating workflows to skills.

Custom agents: `frontend-engineer`, `semantics-core-engineer`, `backend-runtime-engineer`, `quality-engineer`, `reviewer`. All use `model: inherit` so the current user-selected supervisor remains the model source. The supervisor dynamically requests Low/Medium/High reasoning according to `MASTER_IMPLEMENTATION.md`; exact per-subagent effort is not a current custom-agent frontmatter field.

Skills: `ternfold-orchestration`, `ternfold-feature`, `ternfold-spec-audit`, `ternfold-differential`.

`docs/agent-orchestration.md` records platform assumptions, delegation format, worktree/parallelism policy, review/escalation, and current limitations. `docs/agent-skills.md` records actual skills and rejected external candidates.

## Core architecture commitments

Source snapshots → tokens → AST → resolved/typed program → machine plans → verified structured ANF Core → interpreter or structured C17 backend/runtime → native artifact. Python host with zero third-party production dependencies. Handwritten recursive descent/Pratt parser. One executable Core; machines/matching lower away. C runtime uses immutable acyclic boxed values, checked reference counting, borrowed-input/owned-output calls. Whole-program local module compilation and explicit root-contained imports.

Preserve: one writer per cell; bare cell reads use old snapshot; lexical `next.cell` dependencies are collected even in dead branches; static cycles reject; ready writers execute by smallest ASCII cell name; all candidates precede guards; first false guard alone selects its error; emissions occur only after all guards pass and remain private until Accept; runtime faults are distinct from typed rejections; checked Int and Unicode semantics are host-independent; executors consume verified Core only; native ownership follows `docs/runtime.md`.

## Reasoning and review defaults

Supervisor: High. Mechanical work: Low. Normal bounded implementation/review: Medium. Types/machines/Core/lowering/backend/runtime/architecture/spec contradictions/milestone readiness: High. Important work gets an independent reviewer; milestone gates after M04, M07, M09, M11, and M14 use High review plus specification audit.

## Progress mechanism

`docs/tasks.json` contains status, dependencies and routing hints. `docs/progress.md` contains command evidence and blockers. Update both together when status changes; keep task-brief acceptance checkboxes synchronized. Do not infer implementation from examples or roadmap prose.

## Known risks / limitations

Primary technical risks remain native lifetime cleanup, accidental candidate-fault reordering, span preservation through lowering, builtin inference/wrappers, pattern coverage, and misleading milestone status. The working name is not legally cleared; no public license/remote repository is selected.

Phase 2 was prepared outside an installed Antigravity desktop/CLI environment. Official current schemas/paths were researched and repository configuration is statically validated, but actual `/agents`/skill UI discovery and asynchronous delegation must be confirmed in the user's installed Antigravity build. Run `scripts/check_antigravity_workspace.py --require-cli` only if `agy` is expected to be installed; IDE usage does not require the compiler to depend on the CLI.

The preparation container also cannot resolve PyPI, and the uploaded source archive intentionally omits the Phase 1 uv cache, so the pinned development environment could not be reinstalled here. Static checks and the available seven-test subset pass; `docs/verification/antigravity-phase2.md` and `environment-phase2.json` preserve the failed bootstrap/environment evidence. A normal machine with dependency access must run the canonical bootstrap/full quality gates before implementing M01.

## Next action

Select an available preferred Gemini supervisor — High when supported, use `docs/antigravity-init-prompt.txt`, verify the environment, then implement M01 completely. Continue autonomously through later eligible tasks while preserving these contracts.

## CRITICAL course-alignment update — 2026-10-15

Supersedes 0.1 references earlier in this historical file: the new target is Ternfold 0.2, ADR 0009. First read docs/course-requirements.md, docs/automata.md, latest progress entry, and relevant scope expansion of each task. C00 finished as source-of-truth documentation; actual compiler next task remains M01. This archive is the Phase-2 scaffold rather than the later M06 partial Antigravity workspace. The original proposal plus explicit illustrated amendment is external to the repo ZIP. Do not claim the new language constructs are implemented. Resume with `MASTER_IMPLEMENTATION.md`; no plan-approval gate, delegate substantive specialist implementation, review independently, keep M05 separate from incomplete M06 typing, and use the model actually offered by Antigravity (do not assume a future model exists).
