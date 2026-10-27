# C17 implementation progress

The authoritative 2026-10-28 migration replaces the Python-host architecture.
Immediate owner task: C-MIGRATION-01. Standalone lexer is staged by the frontend
specialist; native report/CLI acceptance, integration, archive verification and
publication are still pending until fresh evidence is recorded below.

## Historical achievements (not C completion)

Python M00–M08 were accepted; partial M09 was not accepted. Full maintained
snapshot: history/python-full-2026-10-28 commit
cbffadf00548a5d1a66b9eb369c1e4437f7408f2, pushed before active source removal.
Previous lexical publication: history/python-lexical-2026-10-28 commit
389030efe8e852b319fe87ea2fd243d58cac1859. Both histories remain preserved.
See historical-artifacts.md for backup hashes. Canonical task IDs/dependencies
remain; current C status is separate in tasks.json.

## Current observed environment

Portable official LLVM-MinGW Clang 23.1.4 compiles/runs C17 on Windows x64.
Native environment check passed after fixing Windows CRT argv quoting for paths
with spaces. ASan/UBSan detect deliberate probes; leak sanitizer is unavailable.
Source/scanner adversarial preflight passed, not final report/CLI acceptance.
No Python build dependency. Updated evidence will be recorded in verification/.

## Verified C17 foundation and lexical scope

M00 and C00 accepted for their stated foundation scope after independent review.
M01 is the next canonical task, in progress: source/span lexer subset exists;
SourceManager canonical-path caching and no-reread guarantees remain unfinished.
M02 rich text/JSON diagnostics and M03 full token inspection remain pending their
prerequisites. Optional M15–M17/X01 retain M14 prerequisites and never block class.
The historical M00 semantic experiment remains design evidence, not C execution.

Integrated include/ternfold/lexer.h, src/source.c/lexer.c/report.c/main.c, native
unit/integration tests and C tools. check/release/sanitize pass112457 lexer
assertions plus18 CLI cases; final native audit669 zero failures before positive
ledger evidence was recorded. The JSON EOF and nested-ledger review findings,
Python egg-info packaging leakage and Unit wording are fixed and independently
closed. Both corrected ZIPs passed fresh external builds/tests/new-report matching.
Meitner independently confirmed closure and recommended foundation acceptance;
Boole reviewed source/scanner/report/CLI lifetime and file safety. See the detailed
[eleven-item matrix and evidence](verification/C-MIGRATION-01-2026-10-28.md).

Windows symlink creation is unavailable (one explicit capability skip); hardlinks,
closed pipes and failed publication are tested. LeakSanitizer/POSIX/GCC/MSVC are
not claimed verified. Complete compiler/runtime/interpreter remain planned C work.
C-MIGRATION-01 remains active only for publication/final evidence closure.
