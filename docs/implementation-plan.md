# Implementation roadmap

Phase 1 completed M00. The active development control plane has been adapted to Codex/ChatGPT while preserving the 0.2 spec and compiler-task status. M01–M07 are verified for their recorded contracts; C01 real-division/Float amendments are verified; M08 is complete and M09 is active. The graph and routing hints are machine-readable in [tasks.json](tasks.json); each [task brief](tasks/M01.md) contains objective, contracts, files, tests, acceptance criteria and commands. Actual status/evidence belongs to [progress.md](progress.md).

| Task | Deliverable | Requires | Suggested agent | Default effort | Independent review |
|---|---|---|---|---|---|
| M00 | Architecture foundation | — | `reviewer` | High | High |
| C00 | Course-scope freeze / automata / crosswalk | M00 | `reviewer` | High | High |
| M01 | Source snapshots and byte spans | M00 | `frontend-engineer` | Medium | Medium |
| M02 | Structured diagnostics and renderers | M01 | `frontend-engineer` | Medium | Medium |
| M03 | Lexer and token introspection | M01, M02 | `frontend-engineer` | Medium | Medium |
| M04 | AST, handwritten parser and recovery | M03 | `frontend-engineer` | High | High |
| M05 | Module graph and name resolution | M04 | `semantics-core-engineer` | High | High |
| M06 | Types, constants and pattern coverage | M05 | `semantics-core-engineer` | High | High |
| M07 | Machine dependency analysis and plan command | M06 | `semantics-core-engineer` | High | High |
| C01 | Authorized real division and lexical-rubric correction | M07 | `semantics-core-engineer` | High | High |
| S01 | Standalone lexical analyzer delivery | C01 | `frontend-engineer` | High | High |
| M08 | Core IR, lowering and verifier | M07, C01, S01 | `semantics-core-engineer` | High | High |
| M09 | Reference Core interpreter and run command | M08 | `semantics-core-engineer` | High | High |
| M10 | C17 immutable runtime and ownership tests | M06, M08 | `backend-runtime-engineer` | High | High |
| M11 | Structured C backend and native differential execution | M09, M10 | `backend-runtime-engineer` | High | High |
| M12 | Library, examples and complete-language integration | M11 | `quality-engineer` | Medium | Medium |
| M13 | Transactional REPL and usability polish | M12 | `frontend-engineer` | Medium | Medium |
| M14 | Conformance, fuzzing and release readiness | M12, M13 | `quality-engineer` | High | High |
| M15 | Transition traces and replay inspection | M14 | `semantics-core-engineer` | High | High |
| M16 | Safe optimization and lifetime shortening | M14 | `backend-runtime-engineer` | High | High |
| M17 | Formatter and editor diagnostics | M14 | `frontend-engineer` | Medium | Medium |
| X01 | Evaluate composition and static transition contracts | M14 | `semantics-core-engineer` | High | High |

Routing metadata is guidance, not a caste system. The primary supervisor may choose a different project agent or reasoning level when the actual task warrants it; important uncertainty should move upward to High.

## Phase gates

**Foundational core (M00–M09 plus C01):** a checked source program demonstrates immutable snapshots, candidate scheduling, rejection and delayed emissions through real Core interpretation. A minimal arithmetic interpreter alone does not satisfy this gate. High milestone reviews occur at M04, M07 and M09.

**Complete language target (M10–M14):** native runtime/backend, interpreter/native conformance, full prelude and examples, practical REPL, packaged distribution, meaningful diagnostics and bounded fuzz/property evidence. All accepted 0.2 syntax and semantics must be implemented and verified before the complete-language gate passes. No online services required. High milestone reviews occur at M11 and M14.

**Advanced depth (M15–M17):** inspect actual execution, optimize with preservation evidence, improve editing. These deepen the same semantic model; they do not justify extra language features.

**Experimental extensions (X01):** proposals/probes only until an explicit design outcome. Production implementation needs accepted specification changes and ADR/task updates; speculative syntax must not leak into the parser.

## Dependency and orchestration policy

Critical path: M01 → M02 → M03 → M04 → M05 → M06 → M07 → C01 → S01 → M08 → M09 → M11 → M12 → M13 → M14. M10 may run alongside M09 only after Core/ABI contracts are stable and prerequisites are actually complete. M15–M17 are independent advanced branches with shared-code ownership coordination.

Strictly sequential/architecture-sensitive contracts: source/span representation, grammar/AST shape, type representation, namespace resolution, candidate fault scheduling, Core operation schema, ownership ABI. One owner at a time. Safely parallel work: disjoint fixture/test families, examples/docs, read-only research/review, native runtime versus interpreter after interface freeze, advanced branches with explicit file ownership.

Use Codex worktrees for concurrent writers and inherited workspace for read-only review/research. The supervisor integrates and reruns verification. Follow `MASTER_IMPLEMENTATION.md` and `docs/agent-orchestration.md` rather than maximizing concurrency.

## Autonomous continuation algorithm

1. Read `MASTER_IMPLEMENTATION.md`, root `AGENTS.md`, handoff and progress; inspect git/source/tests.
2. Bootstrap/check the development environment and run `scripts/check_codex_workspace.py`.
3. Reconcile `tasks.json`/progress against actual evidence and choose the earliest eligible incomplete task.
4. Read its brief and relevant normative contracts; classify reasoning and decide direct/delegated execution using `$ternfold-orchestration`.
5. Implement with valid/invalid/boundary evidence; use safe parallelism only after interfaces freeze.
6. Run focused tests then task/canonical gates. Obtain independent review and spec audit when required.
7. Fix findings; update brief checkboxes, task status and progress with exact commands/results.
8. Continue with the next eligible task while environment and contracts remain clear.

A passing prior milestone remains a regression gate. If an environment boundary blocks one task, record it and continue only independent authorized work. Never skip a prerequisite by relabeling its acceptance criterion.

## Course-aligned target revision 2: additive implementation scope

**New prerequisite C00 is complete for *specification/bootstrap only*.** M01–M07 source through planning are complete for their historical contract; C01 numerical/rubric correction is verified; M08 is complete and M09 is active. Read ADR 0009 and `docs/course-requirements.md` alongside each owning brief. M03 must implement finite-state-recognized lexical categories, both comment forms, four lexical literal families, extension policing and a real `Symbol Table.txt` emitter; M04 handles ^/div/for/main clauses; M06 types; M08/M09 Core/interpreter; M10/M11 C/ABI equivalence; M14 executed course acceptance. M05 `check` is explicitly phase-bounded: unfinished M06 types must not contaminate its verification. Do not paper over a missing feature by changing the proposal without corresponding compiler/tests.
