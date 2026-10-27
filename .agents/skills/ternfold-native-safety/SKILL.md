---
name: ternfold-native-safety
description: Use for C17 code generation, runtime ABI, reference counting, memory lifetime, error unwinding, emission publication, and interpreter/native differential correctness.
---

# Ternfold native ABI and lifetime review

1. Read ADR 0006, `docs/runtime.md`, `docs/core-ir.md`, current backend design and M10/M11/M16 brief. Do not infer semantics from Python reference counting or C integer overflow.
2. For every generated operation, record **borrowed inputs**, **owned outputs**, temporary references, heap-child ownership, capture lifetime, exceptional exits and cleanup actions; all paths (including early return/error) must be accounted for.
3. Review integer operations for overflow and division faults; UTF-8 storage must be length-aware and Unicode-scalar correct (including embedded NUL). Verify stable semantics independent of C undefined behavior.
4. Trace guards and emissions: all candidate writers before guards, first failed guard stops ordered checks, no partial main output, and no leaked emission before acceptance.
5. Add focused memory/lifetime tests, negative-path tests, stress conditions, and interpreter/native differential cases. Use sanitizers where installed and report their availability; never claim sanitizers ran unless command logs show it.
6. Produce findings with severity, source/IR operation, ownership timeline, reproducible test and required fix. Fail critical lifetime issues; do not provide a positive signoff on unverified code.

Not for frontend-only work or generic documentation.

## Authorized numerical/rubric amendment

Mandatory professor clarification: seven arithmetic + - / * % div ^ and nine logical/relational && || ! > < == != >= <= are required operator counts. Accepted ADR 0010 defines real / and finite Float, distinct from integer div. Preserve completed work and use C01 before M08; require executable eleven-item lexical evidence and actual UTF-8 Symbol Table.txt. Historical Int-only passes do not verify new Float or executor/native parity.
