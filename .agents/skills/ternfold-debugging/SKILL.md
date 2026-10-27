---
name: ternfold-debugging
description: Use for failing Ternfold tests, inconsistent diagnostics, incorrect compiler pass results, interpreter/native mismatches or broken environment commands.
---

# Root-cause debugging (repository-authored)

1. **Reproduce** the exact command and preserve the first concrete exception, input fixture and span. Distinguish missing tools/dependencies from defective compiler logic. Do not claim a failure is environmental without evidence.
2. **Trace the real phase**: Source → lexer → parser → resolution → typing → machine planning → verified Core → interpreter or C runtime. Identify where expected and actual first diverge. Do not modify a later phase to conceal an earlier failure.
3. **Hypothesize** one root cause and write the smallest counterexample. Use minimal print/debug trace *outside* production compiler passes if temporary instrumentation is necessary. Never insert permanent ad-hoc print statements or swallow diagnostics.
4. **Fail first**: add a regression assertion for the defect; observe that it catches the intended wrong behavior. Make the smallest spec-consistent correction. Review source-span propagation and architecture invariants.
5. **Verify** the reproducer, neighboring negative/boundary cases, and required full gate. If two attempts fail to confirm a root cause, escalate to High reviewer/supervisor rather than thrash.
6. **Report** actual fix, tests, command output and any unresolved uncertainty; do not change specifications to match a buggy implementation.

Do not invoke for stylistic refactors without a concrete defect. Inspired by reviewed upstream `obra/superpowers` systematic-debugging (2026-10-27); new Ternfold adaptation: https://github.com/obra/superpowers/tree/main/skills/systematic-debugging

## C17 migration workflow (ADR0011)

All implementation stages and native developer tools target ISO C17. Use explicit
ownership, checked allocation/size arithmetic, destroyable failure states, stable
IDs/spans and immutable published records. Run `./scripts/build.ps1 check` and
`sanitize`; intended POSIX equivalent is `sh scripts/build.sh check|sanitize`.
Record actual compiler/platform support. Preserve M00–M17/X01 and auxiliaries;
optional extensions never block class. Historical Python passes do not complete
C work. No Python/Node/AI runtime or build dependency. Independent review and
fresh extracted archive builds are required before acceptance.
