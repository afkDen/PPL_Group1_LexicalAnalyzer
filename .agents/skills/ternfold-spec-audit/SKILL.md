---
name: ternfold-spec-audit
description: Audit Ternfold specification-to-implementation consistency across grammar, AST, semantics, types, machine plans, Core, executors, tests, and examples. Use after semantic changes, difficult reviews, and milestone readiness checks.
---

# Ternfold specification consistency audit

Read the task brief and only the normative documents/layers it affects. Treat `docs/language-spec.md`, `docs/grammar.md`, focused type/module/runtime documents, ADRs, and accepted task contracts as authoritative.

Build an affected-layer matrix covering: syntax/grammar; tokens/lexer; AST/parser; resolution/modules; types/coverage; machine plans; lowering/Core/verifier; interpreter; C backend/runtime; diagnostics; tests; examples; CLI/docs. Mark each row `affected`, `not affected`, or `not implemented yet` with a reason.

For affected rows, compare the normative rule to actual code/tests. Check especially source-span preservation, old versus candidate reads, lexical dependency collection before optimization, ASCII ready-name scheduling, candidate-before-guard ordering, first-false guard selection, delayed/private emissions, checked Int behavior, Unicode scalar semantics, verified-Core-only execution, and native ownership transfer rules.

Look for silent host-language leakage, missing invalid/boundary cases, inconsistent error codes/spans, tests that only prove two executors share the same bug, and documentation that claims an unimplemented capability. Do not repair by silently changing semantics.

Output a compact audit report with: scope; documents/code inspected; consistency findings ordered by severity; missing tests/evidence; whether an ADR/spec update is required; and a pass/block recommendation. A milestone passes only when contradictions are resolved or explicitly recorded as blockers.

## Authorized numerical/rubric amendment

Mandatory professor clarification: seven arithmetic + - / * % div ^ and nine logical/relational && || ! > < == != >= <= are required operator counts. Accepted ADR 0010 defines real / and finite Float, distinct from integer div. Preserve completed work and use C01 before M08; require executable eleven-item lexical evidence and actual UTF-8 Symbol Table.txt. Historical Int-only passes do not verify new Float or executor/native parity.
