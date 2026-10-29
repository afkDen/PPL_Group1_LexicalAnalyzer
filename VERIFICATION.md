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

## macOS and Linux

The included lexical-only GitHub Actions workflow extracts the exact source
commit, compiles with the runner's available C17 compiler, runs the included
native tests, regenerates both demonstration reports and checks invalid/extension
exit codes. It targets macOS15AppleSilicon,macOS15Intel andUbuntu24.04.
A configured workflow alone is NOT proof those runs succeeded. Until an actual
completed run is recorded, these platforms remain unverified. See the repository's
Actions results for the exact commit. No prebuilt macOS executable is included.

## Submission boundaries

Only standalone lexical source, support, examples, reports, tests and concise
coursework instructions are included. No full compiler, private agents/skills,
roadmap, proposal, toolchain cache or development binaries belong in this source
submission. Original historical ZIPs are preserved separately. Optional binary
convenience archives, if verified later, are distinct from this official source ZIP.
