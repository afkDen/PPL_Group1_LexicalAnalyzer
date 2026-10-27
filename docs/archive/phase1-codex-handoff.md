# Codex handoff — Ternfold architecture foundation

Intended next environment: Codex, GPT-5.6 Sol Medium. This repository contains all context needed without the original conversation. Start at its root and inspect before changing files.

## Identity and current state

Ternfold `.tfd`: **propose together, validate in order, publish together**. It is a pure, static, nominally typed language whose immutable machines expose old-state reads, compiler-scheduled candidate dependencies, ordered typed rejection and delayed emissions. Its purpose is inspectable/replayable application and simulation state transitions. It is not a claim of new transactional/synchronous concepts, hard real-time execution, or static proofs of arbitrary guards.

The architectural phase created six candidate designs, selected this one, froze a detailed 0.1 target, and created 19 task briefs (including foundation, advanced and experimental work), eight ADRs, example fixtures, test/tooling configuration and two project skills. Production source currently implements only the package entrypoint and status/help/version CLI. `experiments/transition_model.py` is a small independent semantic probe; it is **not** a Ternfold interpreter. Lexer/parser/types/Core/runtime/backend/REPL are unimplemented. Directory purpose files identify future code ownership without fake implementations.

M00 is the architectural foundation; check [progress](progress.md) for actual completion/evidence. **Next incomplete implementation task: M01 — source snapshots and byte spans.** If future sessions have advanced the repository, tasks.json/progress and actual source take precedence over this initial pointer.

## Read in this order

1. Root `AGENTS.md`, then this handoff and `docs/progress.md`.
2. `docs/language-spec.md` and `docs/grammar.md`.
3. `docs/type-system.md`, `docs/module-system.md`, `docs/standard-library.md` as relevant.
4. `docs/architecture.md`, `docs/compiler-pipeline.md`, `docs/core-ir.md`, `docs/runtime.md`.
5. `docs/decisions/README.md` and relevant ADRs; `docs/testing.md`.
6. `docs/implementation-plan.md`, `docs/tasks.json`, next task brief, existing source/tests/examples.
7. `docs/agent-skills.md` and the relevant installed repository skill.

## Exact setup and current executable commands

```sh
python3 scripts/bootstrap.py
.venv/bin/python scripts/check_environment.py
.venv/bin/python scripts/dev.py check
.venv/bin/python scripts/audit_docs.py
.venv/bin/ternfold status
```

For cached/offline setup use `python3 scripts/bootstrap.py --offline`. Requirements and official missing-tool installation routes are in `docs/environment.md`. Bootstrap verifies Python/uv/development tools/GCC; no accounts or API keys required. Project-local skills are plain checked-in instructions under `.agents/skills`; current Work catalog registration is not needed to read them.

Focused commands:

```sh
.venv/bin/python scripts/dev.py test
.venv/bin/python scripts/dev.py lint
.venv/bin/python scripts/dev.py types
.venv/bin/python scripts/dev.py format
.venv/bin/python scripts/dev.py build
.venv/bin/python scripts/smoke_wheel.py
.venv/bin/python -m coverage run -m pytest
.venv/bin/python -m coverage report
```

`dev.py build` packages Python source into sdist/wheel. It does not compile Ternfold. Today `.venv/bin/ternfold run ...` deliberately fails as an unavailable command. After M09 use `.venv/bin/ternfold run examples/intro/counter.tfd`; after M11 use `.venv/bin/ternfold build examples/intro/counter.tfd -o build/counter` and `./build/counter`; after M13 use `.venv/bin/ternfold repl`. Do not claim these future commands work until their tasks pass. Full CLI contract is in compiler-pipeline.md.

## Architecture commitments

Source snapshots → tokens → AST → resolved/typed program → machine plans → verified structured ANF Core → interpreter or structured C17 backend/runtime → native artifact. Python host with zero third-party production dependencies. Handwritten recursive descent/Pratt parser. One executable Core, with machines and matching lowered away. C runtime uses immutable acyclic boxed values, checked reference counting and borrowed-input/owned-output calls. Whole-program local module compilation; explicit root-contained imports. Main returns List[Text] and the host writes it only after successful evaluation.

Important ADRs: 0002 machine semantics, 0003 static type budget, 0005 Core/execution, 0006 C/ownership, 0007 scheduler, 0008 modules/output. Do not independently redesign them while implementing a task.

## Invariants that must survive refactoring

- Every cell has exactly one writer. Retention is an explicit old-value writer.
- Bare cell reads always use the old snapshot; lexical `next.cell` reads create graph edges even in dead branches.
- Cycles reject statically; ready writers execute by smallest ASCII cell name, one at a time. Declaration permutation does not change scheduling.
- All candidates finish before guards. First false guard chooses only its error; later work is skipped. Emissions happen only after all guards pass and remain private until Accept returns.
- Runtime faults are not typed rejections. Pure code may fault/diverge. No partial main output on evaluation failure.
- Checked signed Int semantics are independent of Python/C behavior; text is Unicode scalars with length-aware UTF-8 storage.
- Core has no unresolved types/names/machine syntax; both executors use only verified Core and runtime metadata.
- Heap children/captures are immutable; every native ownership transfer follows runtime.md.
- No eval/exec, regex translation, shell interpolation, hosted runtime dependency, ambient filesystem access or secrets.

## Roadmap and progress convention

- [ ] M01–M04: sources, diagnostics, tokens, full parser/AST.
- [ ] M05–M07: resolution/modules, types/coverage, machine graph and check/plan CLI.
- [ ] M08–M09: verified Core and real interpreter demonstrating identity.
- [ ] M10–M11: native runtime, structural C backend and differential tests.
- [ ] M12–M14: complete library/examples, REPL and conformance/packaging quality.
- [ ] M15–M17: optional advanced traces, safe optimization, formatter/editor tooling.
- [ ] X01: experimental composition/contracts, explicit design outcome before syntax.

These are initial high-level pointers; task checkboxes/statuses are authoritative. Select the earliest eligible incomplete task from tasks.json, read its brief, assess affected layers, implement it fully, run/fix checks, then update progress and continue. Record date, task, actual files, semantic impact, commands/outcomes, limitations, and next eligible task. Avoid restarting completed work merely because this handoff still describes the initial architecture phase.

## Known risks and change authority

The main risks are C lifetime correctness on failure edges, accidental candidate fault reordering, source spans through lowering, builtin inference/first-class wrappers, pattern coverage and misleading milestone status. Resource exhaustion need not coincide between Python and C. The working name is not legally cleared; no public software license or remote repository was selected. Neither is a blocker for local compiler implementation.

Freely refactor private helpers/node layouts where behavior and interfaces remain coherent. Any accepted-syntax or observable-semantics change updates the normative spec, grammar and tests. New generics/effects/recursive data, a new backend/IR, altered scheduling or memory/module model needs an ADR. Experimental directions are not permission to destabilize 0.1. Use evidence from real programs when proposing changes; record rationale and consequences.

If a tool cannot run, preserve the failure and choose only independent work. Do not replace a failed test with a skip, ask the user to do ordinary local work, or claim environment success without command evidence. Continue autonomously through ordinary tasks while preserving these contracts.
