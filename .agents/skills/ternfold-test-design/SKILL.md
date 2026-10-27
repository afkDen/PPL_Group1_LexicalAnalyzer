---
name: ternfold-test-design
description: Use when implementing a Ternfold language feature, designing regression tests, or evaluating missing negative, boundary, property and differential coverage.
---

# Ternfold test design (repository-authored)

## When and where
Read the assigned task, `docs/testing.md`, affected language rules, `docs/course-requirements.md` and source/test modules. Not for prose-only edits. Do not add new test infrastructure without a failed requirement that justifies it.

## Procedure
1. List each observable rule and its source/AST/Core span, error code, type/runtime outcome and order-sensitive effects. Identify phase ownership and whether the implementation should succeed or diagnose the case.
2. Build a behavior matrix: ordinary valid, invalid input, boundary value, weird-but-valid, multiple errors/recovery, and regressions for previously fixed defects. For machine operations include old vs `next` reads, writer permutation, cycles, guard failure order, emission leakage, and faults. For arithmetic include checked Int64 endpoints, negative division, exponent overflow and power-zero cases.
3. Write a focused failing test (or a not-yet-implemented, explicitly pending conformance fixture) before implementation when practical. Observe the failure for the intended reason rather than an unrelated missing import. Never make existing tests pass by weakening assertions.
4. Add table-driven/golden diagnostic tests with stable error codes and byte spans. Use Hypothesis for finite composable invariants; constrain inputs and shrink counterexamples. Treat timeouts and resource failures explicitly, not as passing outcomes.
5. Run focused tests first, then canonical full check when dependencies are installed. At M09/M11 compare interpreter/native observable outcomes and distinguish semantic agreement from resource-limit differences.
6. Handoff a matrix and exact commands/results with files changed, missing cases, and the current task's phase boundary. Keep fixtures in the owning tests/examples directories.

## Done
Each named rule has at least one verifying assertion or an explicit tracked deferred acceptance criterion. False positives, broad skips, and expected-error swallowing are not completion evidence.

Inspired by GitHub `obra/superpowers` test-driven-development, reviewed 2026-10-27; this is a new Ternfold-specific procedure, not a copy. https://github.com/obra/superpowers/tree/main/skills/test-driven-development

## Authorized numerical/rubric amendment

Mandatory professor clarification: seven arithmetic + - / * % div ^ and nine logical/relational && || ! > < == != >= <= are required operator counts. Accepted ADR 0010 defines real / and finite Float, distinct from integer div. Preserve completed work and use C01 before M08; require executable eleven-item lexical evidence and actual UTF-8 Symbol Table.txt. Historical Int-only passes do not verify new Float or executor/native parity.
