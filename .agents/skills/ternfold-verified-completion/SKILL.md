---
name: ternfold-verified-completion
description: Use before declaring any Ternfold task, review, milestone, course-rubric item or build complete or verified.
---

# Evidence before completion (repository-authored)

1. Identify the exact task brief, requested observable behavior, and the command(s) that establish it. Check that implementation and tests exist, not just a green static documentation audit.
2. Run fresh **focused tests**, **canonical quality gate**, **repository/course audits** and **native/differential gates** whenever the task actually requires them. Verify process exit codes, failure/skip counts, diagnostic outputs and whether all declared examples ran.
3. Inspect the diff, review findings, semantic spec and test amendments. Obtain independent read-only review for substantive semantic changes. No review by the sole code author passes as independent review.
4. If a gate cannot run, record command, error, environment, affected acceptance criteria, and next action. Never silently downgrade it to passed, mark tests skipped or claim success from an old transcript.
5. Only after all mandatory evidence passes, update `docs/tasks.json`, `docs/progress.md` and `docs/course-acceptance.json`. Put reproducible command lines and concise results in progress. A green lint/test run is not proof of feature completeness unless acceptance criteria are asserted.
6. For interruptions, keep task status incomplete with accurate partial-work notes; reassess unintegrated worktrees and subagents on continuation.

Do not use for generating new feature code. Reviewed upstream `obra/superpowers` verification-before-completion (2026-10-27); this is a new Ternfold-specific procedure: https://github.com/obra/superpowers/tree/main/skills/verification-before-completion

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
