---
name: ternfold-feature
description: Implement or review a Ternfold compiler feature across its affected semantic phases. Use for Ternfold roadmap tasks or language changes, not unrelated maintenance.
---

Locate the repository root containing AGENTS.md. Read its operating instructions, docs/progress.md, the owning task brief, and only relevant normative documents. Treat examples as fixtures, not implemented capability claims.

Before editing, identify the semantic rule and build a short impact list covering specification, grammar, lexer/tokens, AST/parser, resolution, types, machine plans, Core lowering/verification, interpreter, C backend/runtime, diagnostics, tests and examples. Mark genuinely unaffected layers explicitly in the progress entry. Never infer completeness from a happy-path run.

For machine work, distinguish old-cell reads from candidate projections, collect dependencies before folding dead branches, preserve the lexical ready-name scheduler, and keep guard/emission fault order. For Core work, do not introduce a machine opcode or consult ASTs from executors. For native code, use the ABI's borrowed-input/owned-output discipline and one cleanup path.

Implement the smallest complete task slice consistent with these contracts. Include an invalid case and a boundary case where the feature admits them. Activate the owning example assertions at the milestone that promises them; skips do not establish completion. Run ./scripts/build.ps1 check (Windows) or sh scripts/build.sh check (POSIX, pending verification) and relevant source/native tests. If changing semantics, update the normative rule and ADR before relying on the changed result.

Update docs/progress.md with task ID, affected layers, changed files, commands and observed outcomes, known limitations, and the next eligible task. Update docs/tasks.json only when status actually changes. Keep environmental blockers distinct from failing assertions. Do not start a second redesign to avoid a difficult acceptance condition.

## Authorized numerical/rubric amendment

Mandatory professor clarification: seven arithmetic + - / * % div ^ and nine logical/relational && || ! > < == != >= <= are required operator counts. Accepted ADR 0010 defines real / and finite Float, distinct from integer div. Preserve completed work and use C01 before M08; require executable eleven-item lexical evidence and actual UTF-8 Symbol Table.txt. Historical Int-only passes do not verify new Float or executor/native parity.

## C17 migration workflow (ADR0011)

All implementation stages and native developer tools target ISO C17. Use explicit
ownership, checked allocation/size arithmetic, destroyable failure states, stable
IDs/spans and immutable published records. Run `./scripts/build.ps1 check` and
`sanitize`; intended POSIX equivalent is `sh scripts/build.sh check|sanitize`.
Record actual compiler/platform support. Preserve M00–M17/X01 and auxiliaries;
optional extensions never block class. Historical Python passes do not complete
C work. No Python/Node/AI runtime or build dependency. Independent review and
fresh extracted archive builds are required before acceptance.
