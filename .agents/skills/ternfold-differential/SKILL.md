---
name: ternfold-differential
description: Design and debug Ternfold interpreter versus C conformance tests, including transition properties and runtime ownership. Use once the relevant executors exist, or when planning their conformance fixtures.
---

Read docs/runtime.md, docs/testing.md, and the owning task. Determine what executes today before running commands: bootstrap status and a Python semantic probe are not a language interpreter or C backend.

Define an observation as stdout bytes, exit status, and deterministic language-fault code plus original source span; use a debug value serializer only when explicitly part of the test harness. Exclude timing, object identity, allocation counts, and exact resource-limit coincidence. Never normalize away program output or a different first arithmetic fault.

Generate small well-typed terminating programs with bounded size, then run the same source through reference interpretation and native compilation. Keep arithmetic boundary generators and expected-fault generators separate from safe-value generators. Run compiler subprocesses with argv arrays, timeouts, private output paths and captured bytes. Do not execute source through Python eval/exec.

For machines, include old-state swap, dependency edges in dead branches, writer permutation, rejection preserving state, multiple failing guards, and faulting emissions after successful validation. Add hand-derived expected results so two executors sharing incorrect lowering cannot agree unnoticed. Minimize failures to a committed regression fixture, preserving fault order while shrinking.

For C lifetime changes, run sanitizer and allocation-failure tests on shared children, projections, branch-result retains, closure captures, and cleanup on every early exit. Record unavailable sanitizer support honestly. A successful unsanitized binary does not establish leak freedom. Stop optional stress expansion once the concrete defect or milestone gate is resolved.

## Authorized numerical/rubric amendment

Mandatory professor clarification: seven arithmetic + - / * % div ^ and nine logical/relational && || ! > < == != >= <= are required operator counts. Accepted ADR 0010 defines real / and finite Float, distinct from integer div. Preserve completed work and use C01 before M08; require executable eleven-item lexical evidence and actual UTF-8 Symbol Table.txt. Historical Int-only passes do not verify new Float or executor/native parity.
