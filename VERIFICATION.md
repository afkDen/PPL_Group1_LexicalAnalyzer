# Source-submission verification

This archive is source-complete. A compatible C17 compiler must already be
available; no compiler, binary, installer, Python, Node or hosted service is a
project dependency. The scanner itself is unchanged from the accepted C lexer.

## Observed local toolchain

Windows x64, official LLVM-MinGW Clang23.1.4. The integrated strict build passed
117201lexer assertions,27CLIcases,684classroomreport assertions,78sample-specific
checks and84lexicalaudit checks,zero failures. The main demo visibly contains all
seven arithmetic/nine Boolean operators, five literal categories and14distinct
reserved names. Tests also cover invalid rows, extension rejection before reading,
hyphen-leading output directories, atomic/source-safe reports and escaping.

One Windows symlink creation probe is unavailable for this account and is not
claimed passed. Integrated ASan/UBSan and optimized -O2 suites also passed the same assertions.
One attempted sanitizer launch hit a shared-build file lock; sequential reruns
completed successfully. Final freshZIP acceptance is recorded in the external
release manifest and release-supervisor evidence. No universal platform claim is made.

## Verified source platforms

Actual hosted run40835024229 at source commit
fbda8c066dc0db6ded125c80a07f70210895963a passed all three jobs:

| Platform | Compiler | Result |
|---|---|---|
| macOS15 Apple Silicon / arm64 | Apple Clang17.0.0 | environment, full native check, primary/invalid/extension demos and report comparison passed |
| macOS15 Intel / x86_64 | Apple Clang17.0.0 | same checks passed |
| Ubuntu24.04 x86_64 | GCC13.3.0 | same checks passed |

See https://github.com/afkDen/PPL_Group1_LexicalAnalyzer/actions/runs/40835024229 .
Each job extracted the exact lexical source commit outside its checkout before
building. Results:117201lexer assertions,27CLIcases,700classroom checks,
78sample checks and84audit checks; zero capability skips on these runners.
Windows x64 Clang23.1.4 also passed strict,optimized andASan/UBSan runs; its
unprivileged-symlink probe remains unavailable (one explicit capability skip).

Initial runs exposed two strict compiler warnings in operator/test formatting
and one audit-cleanup indentation warning. Those minimal portability defects
were fixed without changing recognition rules or weakening warnings/tests;
the successful run above supersedes their failed build attempts. The final
source differs only by README/verification/workflow evidence updates after that
code pass. A dispatch input also permits verifying the actual downloadable
source ZIP release asset, with its SHA256 printed in the workflow log.
No prebuilt macOS executable is included or required; compilation still needs
an installed compatible compiler. macOS/Linux sanitizer execution is not claimed
by this non-sanitized hosted source run.
## Submission boundaries

Only standalone lexical source, support, examples, reports, tests and concise
coursework instructions are included. No full compiler, private agents/skills,
roadmap, proposal, toolchain cache or development binaries belong in this source
submission. Original historical ZIPs are preserved separately. Optional binary
convenience archives, if verified later, are distinct from this official source ZIP.

## IDE guide update — 2026-10-29

IDE_QUICK_START.md supplies manual Dev-C++ and Xcode configuration, the exact four C source files, C17/header settings, explicit arguments and working directory, and no-argument/invalid/extension demonstrations. No .dev or .xcodeproj is included. Neither GUI was available for direct execution, and Dev-C++ bundled GCC compatibility remains unverified. The analyzer source, headers, tests, fixtures and scanner vocabulary are byte-identical to the preceding accepted release.

The source-verification workflow now additionally compiles the four files directly with cc, runs the guide's root-directory arguments, compares fresh valid/invalid reports, checks no-argument exit2, rejects README.md without changing the report and restores the complete report. This is equivalent compiler/CLI verification, not a claim of GUI execution. Current release evidence is linked from the GitHub release; prior verified source and archives remain preserved.
