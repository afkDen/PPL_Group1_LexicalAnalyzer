# What this Codex bootstrap will build

The repository implements the frontend through machine planning (M01–M07). C01 numerical amendments are active; Core/execution/native compilation remain pending. `scripts/dev.py build` creates the Python distribution; compiling .tfd programs begins at M11.

## Already included in the ZIP (available immediately)

- The normative Ternfold 0.2 language proposal/spec, grammar, type/module/standard-library/runtime/Core documents, 10 ADRs, and diagrams of token-recognizing finite automata.
- A source-first Python package with tokens/AST/check/plan and status/help/version capabilities and an independent transition semantics experiment (not the interpreter).
- `docs/tasks.json`, 21 task briefs, progress evidence files, a 25-item course-requirements ledger, sample `.tfd` **fixtures** (not yet executable), pinned development configuration and reproducible environment scripts.
- Codex/ChatGPT Work implementation-control files: root `AGENTS.md`, `MASTER_IMPLEMENTATION.md`, `docs/codex-handoff.md`, `.codex/config.toml`, seven focused `.codex/agents/*.toml` (including two read-only auditors), and nine `.agents/skills/*/SKILL.md` procedures. Codex availability and execution still depend on the user's client/account/workspace.

## After completing the core tasks M01–M14 (intended, not guaranteed today)

| Stage | Task(s) | Deliverable |
|---|---|---|
| Source and diagnostics | M01–M02 | Immutable UTF-8 source snapshots and byte spans; actionable text/JSON diagnostics |
| Real lexer and course token report | M03 | `.tfd` validation, lexer for all specified 0.2 categories, both comments, invalid token diagnostics, token inspection, deterministic `Symbol Table.txt`, automata-based recognition tests |
| Parser | M04 | Handwritten recursive-descent/Pratt AST with correct precedence, `^`, `div`, `Char`, `for`, conditional, input/output and machine clauses, recovery and AST inspection |
| Module and semantic analysis | M05–M07 | Root-contained imports; names/scopes/visibility; static types, exhaustive patterns and safety diagnostics; machine candidate scheduling with cycles and ordered guards, `check` and `plan` commands |
| Core interpreter | M08–M09 | Verified, inspectable Core IR; real `.tfd` execution with immutable state machines, pure loops, input snapshot and atomic staged output; `core` and `run` commands |
| C native execution | M10–M11 | Immutable C17 runtime, structured C generator, native compilation (`emit-c` and `build`), reference/native parity tests and ABI/ownership checks |
| Completeness and usability | M12–M14 | Standard prelude, executable examples/showcase, REPL, fixtures and all 25 rubric requirements verified by real tests/evidence; packaging, diagnostics, property/fuzz/conformance validation |

Example target CLI after its owning task passes: `ternfold tokens`, `ast`, `check`, `plan`, `core`, `run`, `emit-c`, `build`, `repl`. **Unavailable commands must fail honestly until implemented.**

### Explicitly included in Ternfold 0.2

- Original identity: pure, statically typed, expression-oriented programs and immutable `machine` transitions: propose all candidate cells, validate guards in order, publish all emissions only after success.
- Types and forms: checked 64-bit signed `Int`, finite binary64 `Float`, `Bool`, UTF-8 `Text`, `Char`, `Unit`, homogeneous `List`, `Option`, `Decision`, nominal records/enums/machines, functions/closures and exhaustive pattern matches.
- Arithmetic and logic: `+ - * / % ^ div`, six relational/equality operators (`< <= > >= == !=`), `&& || !`, checked errors, explicit precedence. `/` performs real division returning Float; `div` uses integer floor division (ADR 0010).
- Course requirements: ASCII source identifiers (including English/algebraic names), 10+ keywords and 10+ reserved names, finite automata examples, optional noise words `from`/`to` in entrypoint I/O, both line/block comments, punctuation/semicolon/free-field rules, at least four lexical constant families (five with Float), invalid tokens, `.tfd` extension, `Symbol Table.txt`, single and nested pure `for` loops and staged main-only input/output.
- Output semantics: main entry point returns `List[Text]`; explicit `output` values and returned lines commit together **only after successful full evaluation**. Machines retain no ambient I/O.

## Optional work not required to pass the core course target

- M15: transition traces and replay inspection.
- M16: semantics-preserving optimizer and ownership/lifetime improvements.
- M17: formatter/editor diagnostics tooling.
- X01: investigate composition/contracts; **not an approved new language feature** until separately accepted and specified.

## Boundaries and necessary verification

The language is **not** a mutable imperative scripting environment: `let` and `next` provide immutable binding and candidate writing; `for` is a pure list-producing expression; input/output exists only at the entry point. The compiler is **not** Python `eval` or a regex translator and the final native executable does not depend on an AI service. The handoff promises progressive implementation, **not a guarantee** that all roadmap tasks will autonomously succeed without intervention. Native stages require a verified GCC/Clang C17 toolchain. Before calling the course project complete, all acceptance ledger rows must be `verified` with real passing tests and independent review, not merely a static documentation audit.
