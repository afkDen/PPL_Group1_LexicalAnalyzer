# Ternfold 0.2 — C17 foundation

**Propose together. Validate in order. Publish together.**

Ternfold is a statically typed language built around immutable machine snapshots.
The entire compiler, interpreter, runtime and native development driver target
ISO C17. The currently implemented component is the standalone lexical analyzer;
parsing through execution remain future C milestones. No Python, Node, AI service
or network connection is needed for normal builds or execution.

## Build and run

Use a C17 Clang/GCC toolchain. On Windows, run:

```powershell
./scripts/build.ps1 environment
./scripts/build.ps1 check
./build/ternfold-lexer.exe examples/lexical/complete.tfd --output-dir build
./scripts/build.ps1 sanitize
```

On POSIX, the intended portable entry point is `sh scripts/build.sh check`, then
`./build/ternfold-lexer examples/lexical/complete.tfd --output-dir build`.
Windows LLVM-MinGW is verified; POSIX/GCC/MSVC are not yet verified here.
The report is `Symbol Table.txt`, with exactly TOKEN TYPE and LEXEME columns.
Exit codes: 0 success, 1 invalid source/lexemes, 2 host/usage/output failure.
See [environment](docs/environment.md) and [testing](docs/testing.md).

## Project contents

`include/ternfold` contains owning C APIs; `src` implements source, scanner,
reports and CLI; `tests` contains native tests/fixtures; `tools` contains the C
development driver/auditor; `scripts` contains platform build/package adapters.
`docs` holds normative specifications, ADRs, task graph and progress. `.codex`
and `.agents/skills` are optional development configuration, never dependencies.

The immediate submission is `Ternfold_C_Lexical_Analyzer_Submission.zip`;
`Ternfold_C17_Foundation_Final.zip` contains the whole current foundation.
See [progress](docs/progress.md) for verified status and archive evidence.
The full compiler is the finals target, not a claimed current capability.

## Continue implementation

Read [MASTER_IMPLEMENTATION.md](MASTER_IMPLEMENTATION.md), [AGENTS.md](AGENTS.md)
and [handoff](docs/codex-handoff.md). Preserve the M00–M17/X01 task graph and
optional extensions. [ADR 0011](docs/decisions/0011-c17-foundation.md) supersedes
the old Python-host architecture. Historical source and test evidence remain on
`history/python-full-2026-10-28`; proposal PDFs remain unchanged historical artifacts.
