# Ternfold

**Propose together. Validate in order. Publish together.**

Ternfold is a statically typed language for inspectable state transitions. Its machines are immutable snapshots: try an input, compute a candidate state, then return either an accepted new snapshot with emissions or the unchanged snapshot with a typed rejection. Old state remains available for replay and independent branches.

**Current status: source through machine planning verified; C01 real-division/Float frontend verified; M08 Core verified; M09 interpreter active.**
The CLI supports `--help`, `--version`, `status`, `tokens`, `ast`, full-frontend `check`, `plan`, and `core`, including real
`--symbol-table` output. Frontend validation/planning is available. ADR 0010 adds finite Float and real `/`; its C01 frontend/constants are verified. Source execution remains pending.
Execution begins in M09; native compilation in M11. No source program below
is claimed to run yet. See [verified progress](docs/progress.md).

```tfd
machine Counter(delta: Int) yields Int rejects Text {
    state count: Int = 0;
    state doubled: Int = 0;
    next doubled = next.count * 2;
    next count = count + delta;
    guard next.count >= 0 else "count cannot be negative";
    emit next.doubled;
}
```

`count` always reads the old snapshot. `next.count` reads its proposed value. The compiler checks one writer per cell, rejects candidate dependency cycles, schedules the writers, and lowers guards into explicit control flow. A rejection skips every emission. Runtime faults are distinct from typed rejections.

The design draws on synchronous dataflow, pure update functions and transactional validation; its identity is their deliberate integration. See [the six candidate designs and research](docs/design-exploration.md). Intended uses include local simulations, rule-driven workflows, and replayable application models. It has no ambient filesystem access or remote runtime dependency; Ternfold 0.2 explicitly supports constrained, staged entrypoint input/output.

## Continue in Codex / ChatGPT Work

This repository uses **Codex / repository-capable ChatGPT Work** for implementation orchestration (not for compiler execution). Open the extracted repository in Codex CLI/IDE/desktop, or provide it to a code-capable ChatGPT Work session; paste [`docs/codex-init-prompt.txt`](docs/codex-init-prompt.txt). The supervisor follows [`MASTER_IMPLEMENTATION.md`](MASTER_IMPLEMENTATION.md), reconciles task state, invokes project agents/skills where supported, verifies changes and updates progress. Ordinary ChatGPT chat can discuss an uploaded ZIP but is not automatically connected to the local checkout. This ZIP does not include `.git` history; for branch/worktree workflows, extract into or initialize a Git repository before starting Codex.

Codex custom agents: `.codex/agents/`; reusable project skills: `.agents/skills/`. Choose a currently offered model/reasoning setting rather than using hard-coded historical model names. No AI account/API is needed to compile or run Ternfold once built.

## Start developing

Requirements: Python 3.12–3.14, uv 0.12.11, and GCC >=12 or Clang >=16 for native work. The bootstrap supports Windows and POSIX; frontend work does not require GCC. Native M10/M11/final verification requires a C17 compiler.

```sh
python3 scripts/bootstrap.py
.venv/bin/python scripts/check_environment.py
.venv/bin/python scripts/dev.py check
.venv/bin/ternfold status
```

On Windows use `python scripts/bootstrap.py` and `.venv\Scripts\python.exe scripts/dev.py check` instead of the POSIX example above. Bootstrap creates/updates `.venv` and uses locked dependencies. After the initial download, `python3 scripts/bootstrap.py --offline` uses the project cache. A fresh offline machine needs a prepopulated package cache/wheelhouse; the source archive does not bundle third-party binaries. See [environment setup and verification](docs/environment.md).

For project-local Windows x64 C17 tooling, use
`python scripts/bootstrap.py --install-native`. It installs a hash-pinned portable
Clang and runs the native probe; add `--offline` for subsequent cached setup.

```sh
.venv/bin/python scripts/dev.py test
.venv/bin/python scripts/dev.py lint
.venv/bin/python scripts/dev.py types
.venv/bin/python scripts/dev.py build
.venv/bin/python scripts/smoke_wheel.py
```

`dev.py build` builds the **Python distribution**, not a Ternfold program. It works offline after setup. Install the built wheel with `python3 -m pip install dist/ternfold_lang-0.0.1-py3-none-any.whl` in a target environment. Its present capabilities include lexical/AST inspection, reports, module resolution, type validation and machine plans.

## Language toolchain target

Source → tokens → surface AST → resolved/typed program → machine plan → verified Core → reference interpreter **or** structured C17 → native executable.

The Python frontend owns syntax, types, scheduling, lowering and diagnostics. The C compiler is only the final machine-code stage. The language is never translated by regex substitution or executed with Python `eval`/`exec`. Immutable reference-counted runtime values support snapshots and closures.

Toolchain commands, available after their owning milestones:

```sh
ternfold tokens examples/intro/counter.tfd
ternfold ast examples/intro/counter.tfd
ternfold check examples/intro/counter.tfd
ternfold plan examples/features/dependency_order.tfd
ternfold core examples/intro/counter.tfd
ternfold run examples/showcase/branching_inventory.tfd
ternfold emit-c examples/intro/counter.tfd -o build/counter.c
ternfold build examples/intro/counter.tfd -o build/counter
ternfold repl
```

Command details and exit codes are in [compiler pipeline](docs/compiler-pipeline.md). The [showcase](examples/showcase/branching_inventory.tfd) demonstrates accepted state, rejected input, delayed output, and branching from an unchanged original. The [example manifest](examples/manifest.json) contains exact expected outputs and error codes.

## Repository guide

| Location | Purpose |
|---|---|
| [AGENTS.md](AGENTS.md) | Operating manual for coding agents |
| [Master implementation](MASTER_IMPLEMENTATION.md), [Codex handoff](docs/codex-handoff.md) | Supervisor control flow, continuation state and invariants |
| [Language spec](docs/language-spec.md), [grammar](docs/grammar.md), [types](docs/type-system.md) | Normative language rules |
| [Architecture](docs/architecture.md), [Core IR](docs/core-ir.md), [runtime](docs/runtime.md) | Phase interfaces and execution design |
| [Implementation plan](docs/implementation-plan.md), [progress](docs/progress.md) | Dependency-aware tasks and actual status |
| [ADRs](docs/decisions/README.md) | Why architectural commitments were made |
| `src/ternfold/` | Production compiler package and bounded future phase locations |
| `runtime/`, `stdlib/` | Native runtime and source library work boundaries |
| `tests/`, `examples/`, `experiments/` | Test infrastructure, language fixtures, independent semantic probe |
| [Agent orchestration](docs/agent-orchestration.md), [skills](docs/agent-skills.md) | Codex agents, reasoning routing, review and reusable procedures |

Read [testing requirements](docs/testing.md) before implementing a language feature. Happy-path execution is not completion: invalid inputs, boundaries, diagnostics, lowering and both executors must agree as their milestones become available.

## Project scope and licensing

The roadmap progresses from a documented foundation and independent transition probe to a functioning interpreter/native toolchain, then tracing, optimization and editor support. Experimental semantics are separate ADR-gated work. No hosted infrastructure, accounts or secrets are required.

No public software license has been selected for this newly created project. Do not publish it under an invented owner or license; internal development can proceed. Third-party development tools keep their own licenses and are not vendored in this source tree.

## New course-aligned language target (Ternfold 0.2)

This **restart archive** retains the Ternfold 0.1 machine identity but now targets the enumerated course requirements. It **does not** contain the later M01–M06 working tree from other sessions. New language syntax includes checked `^`, `div` floor quotient, `Char` literals, both `//` and `/*...*/` comments, `for ... in ...` list comprehensions (nested naturally), and main-only captured `input`/staged `output` clauses with optional `from stdin` / `to stdout` noise words. See [course contract](docs/course-requirements.md), [lexical automata](docs/automata.md), [ADR 0009](docs/decisions/0009.md), and [course examples](examples/course/).

A revised proposal PDF is delivered separately with the original 11 pages untouched and new diagrammatic amendment pages. The static course checker `python scripts/course_audit.py` checks documentation, not compiler feature readiness. **M01 is the next real implementation task.** In Codex/ChatGPT Work, read `MASTER_IMPLEMENTATION.md` and start the task directly without another approval-plan gate. For Windows prefer `python scripts/bootstrap.py`, `.venv\\Scripts\\python.exe scripts/dev.py check`; on POSIX use `.venv/bin/python scripts/dev.py check`. The full environment includes a C17 compiler for native milestones; Python frontend phases can be advanced independently if compiler unavailable.


See the detailed [planned deliverables and current-versus-future status](docs/what-codex-builds.md).

## What the complete roadmap builds

**Scaffold today:** documented 0.2 syntax/semantics, lexical DFA diagrams, task graph, course-acceptance crosswalk, examples as specifications, packaging/status CLI and development tools. **Not yet present:** lexer/parser/type checker, functional interpreter, C native compiler, REPL, formatter or editor integration.

**Core finished goal (M01–M14):** a real `.tfd` language frontend with source spans, actionable diagnostics, lexer (`tokens` and deterministic `Symbol Table.txt`), AST introspection, module graph/name resolution, static typing and pattern coverage, machine dependency scheduling, verified Core IR, `run` interpreter, structured C17 emitter/native `build`, standard prelude, REPL, sample/showcase programs, course demos, and independent interpreter/native conformance/property tests. Course-aligned 0.2 includes Char, block comments, exponentiation, floor `div`, noise words, pure loops, staged entrypoint input/output. **Optional advanced M15–M17:** transition traces, safe optimizations, formatter/editor diagnostics. **Experimental X01:** investigation only unless separately approved and specified.


Codex control-plane conversion verification and limitations: [docs/verification/codex-migration.md](docs/verification/codex-migration.md).

## Enhanced Codex quality workflows

This bootstrap includes 7 project-local Codex agents (five original roles plus two read-only semantic/native safety auditors) and 9 focused skills. Source design, compiler output and course acceptance targets are unchanged. See `docs/github-skills-research.md`, `docs/agent-skills.md`, and `docs/agent-orchestration.md`. Run `python scripts/validate_skills.py` and `python scripts/check_codex_workspace.py` to check project configuration; static validation does not demonstrate live subagent execution.

The professor's lexical rubric requires seven arithmetic operations
`+ - / * % div ^` and nine logical/relational operations
`&& || ! > < == != >= <=`; the counts are not points. `/` is real division and
`div` integer division. [ADR 0010](docs/decisions/0010.md) defines Float,
conversions, rounding and faults. The [course contract](docs/course-requirements.md)
and [C01 brief](docs/tasks/C01.md) track executable evidence for all eleven
lexical items, including a real UTF-8 `Symbol Table.txt`. Historical passes are
preserved; they do not establish the newly amended numerical behavior.
