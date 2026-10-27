# ADR 0011 — Entire Ternfold implementation in ISO C17

Status: **Accepted, 2026-10-28**, authoritative professor/user migration directive.
Supersedes ADR 0001's Python-host decision and incompatible build instructions.
ADRs 0002–0010 retain language semantics unless explicitly amended here.

## Context

The original architecture used Python frontend/analysis/Core/interpreter tooling
with a C17 backend/runtime. Python M00–M08 acceptance and partial M09 are genuine
historical work. The professor now requires the entire implementation in C.
The standalone C lexical analyzer is the immediate class submission; the full
compiler/interpreter is the finals deliverable. Historical proposals are unchanged.

## Decision and alternatives

Choose C17 throughout. Keeping Python with a C wrapper violates the requirement;
a line-for-line port preserves accidental host dependencies; redesigning the
language discards useful semantics. Instead rebuild bounded C phase interfaces
against the existing normative specifications and behavioral fixtures.
No Python/Node/AI/network dependency is allowed for normal builds or execution.
Platform shell adapters drive the native C development tool. Use strict warnings,
native tests, fault injection, sanitizers and independent audits.

## Ownership and interfaces

Sources own raw UTF-8 snapshots and coordinate indexes. Tokens borrow stable
source spans; decoded literal storage belongs to the lexical result. Destruction
order is results then sources. Constructors require fresh output and leave a
safe destroyable state on failure. Allocation callbacks must outlive their owners.
Later phase contexts own arenas/tables; stable integer IDs cross phase boundaries.
Do not return stack pointers or mutate accepted semantic records. Core verification
produces a separate executable handle; execution cannot consume unverified Core.
Runtime ownership/reference counting and fault unwinding remain M10/M11 work,
not scanner features. No signed overflow or unspecified C evaluation shortcuts.

## Migration and roadmap

Preserve Python code/evidence before removal, in both historical Git and ZIP.
Retain M00–M17/X01 plus C00/C01/S01, responsibilities, dependencies, acceptance
intent and optionality. Re-evaluate each brief for C memory ownership and native
checks; Python passes are history only. C-MIGRATION-01 tracks this narrowly scoped
foundation and lexical delivery without making later phases class prerequisites.
Do not preimplement parser/Core/runtime placeholders just to populate directories.

## Consequences and verification

C increases ownership, allocation, UTF-8, integer/Float and ABI risk. Cover failed
allocation positions, malformed encodings, spans, report aliasing, failed writes,
maximal munch and deterministic bytes. The native backend must preserve all
specified arithmetic and machine semantics; interpreter/native parity waits for
both executors. Windows LLVM-MinGW is the current verified toolchain; untested
GCC/POSIX/MSVC support is not claimed. Preserve historical proposals and original
ADR reasoning. Clean-extract, compile and test both separate archives before
acceptance. Publish the coherent foundation without erasing either Git history.
