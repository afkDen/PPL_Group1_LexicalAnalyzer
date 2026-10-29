# Verification and reproduction

This submission contains a handwritten C17 scanner with a fixed 215-state name
graph and optional actual-transition tracing. The current packaging revision
improves documentation and standalone test support; production C source, headers,
state definitions, examples, and expected reports retain their accepted bytes.

## Run the checks

From the extracted source directory, with a compatible Clang/GCC compiler:

```sh
sh scripts/build.sh environment
sh scripts/build.sh check
sh scripts/build.sh sanitize
```

Windows PowerShell equivalents:

```powershell
./scripts/build.ps1 environment
./scripts/build.ps1 check
./scripts/build.ps1 sanitize
```

Use `CC=clang` with the shell script, or `-Compiler 'path/to/clang.exe'` with
PowerShell, to select an installed compiler. Sanitizer support is a prerequisite
for `sanitize`; an unavailable sanitizer is not a passing result.

For the direct four-file command used by IDE projects, see
[IDE_QUICK_START.md](IDE_QUICK_START.md). The application compiles only
`src/main.c`, `src/lexer.c`, `src/source.c`, and `src/report.c`, with `-Iinclude`.
Keep `src/internal.h` and `src/name_dfa.inc` beside the implementation files.
The fixed include is not compiled separately.

## Regression coverage

| Suite | Accepted checks or cases |
|---|---:|
| Lexer | 117,201 checks |
| CLI integration | 31 cases; assertion totals vary by host and sanitizer diagnostics |
| Classroom report | 684 checks on Windows; 700 on POSIX |
| Demonstration | 78 checks |
| Fixed name DFA | 58,087 checks |
| Actual transition trace | 994 checks |
| Differential comparison | 13,464,314 comparisons across 3,010 cases |
| Independent vocabulary and invalid coverage | 289,723 checks, including 618 frozen historical cases |

The repository audit additionally checks scanner structure and local
documentation links. Its count varies with the documentation's link inventory.
See [tests/README.md](tests/README.md) for each suite's purpose and the distinction
between production code and the frozen historical test oracle.

Tests cover tokens, decoded values, UTF-8 and byte spans, invalid recovery,
allocation failures, report escaping, output publication, file aliases, extension
policy, DFA edges, accepting metadata, trace continuity, and exactly-once byte
consumption. Independent correctness and native-safety reviews found no remaining
blocking findings in the accepted scanner.

## Demonstrate the output

```sh
./build/ternfold-lexer examples/lexical/complete.tfd --classroom --output-dir build
./build/ternfold-lexer examples/lexical/complete.tfd --classroom --output-dir build --trace-dfa 2> build/dfa-trace.txt
```

On Windows, use `./build/ternfold-lexer.exe`. Both commands return 0 and generate
the same report as the supplied root `Symbol Table.txt`. Tracing changes standard
error only. Run `invalid.tfd`, `invalid-comprehensive.tfd`, or `trace.tfd` with the
same options to demonstrate lexical errors; those fixtures intentionally return
1. [INVALID_CASES.md](INVALID_CASES.md) describes separate source-encoding errors.
An invalid run replaces the report, so rerun `complete.tfd` afterward.

The [rubric](RUBRIC.md), [row index](DEMO_ROWS.md), and
[proposal matrix](PROPOSAL_LEXICAL_RECONCILIATION.md) map the demonstration to
actual classifications. Lexical success does not establish syntactic validity,
type correctness, or execution behavior.

## Platform evidence

The accepted production source passed strict warnings-as-errors, AddressSanitizer,
and UndefinedBehaviorSanitizer checks on these actual environments:

| Environment | Toolchain |
|---|---|
| Windows x64 | LLVM-MinGW Clang 23.1.4 |
| macOS 15 ARM64 and Intel | Apple Clang 17.0.0 |
| Ubuntu 24.04 x64 | GCC 13.3 |

Reproducible CI records for the accepted scanner and executable bytes:

- [Extracted source checks on macOS ARM64, macOS Intel, and Ubuntu](https://github.com/afkDen/PPL_Group1_LexicalAnalyzer/actions/runs/40910788344).
- [Native executable builds and fresh combined-ZIP checks](https://github.com/afkDen/PPL_Group1_LexicalAnalyzer/actions/runs/40911363510).
- [Published executable ZIP downloaded and tested on Windows and both Mac architectures](https://github.com/afkDen/PPL_Group1_LexicalAnalyzer/actions/runs/40912544533).

These records establish the unchanged scanner and binary baseline. The
[current release](https://github.com/afkDen/PPL_Group1_LexicalAnalyzer/releases/tag/lexical-submission-clean-2026-10-30)
records the refreshed source-archive and all-in-one verification runs and their
exact hashes. Executables are reused only after every production source/header
byte is compared with the accepted package; documentation changes do not require
rebuilding identical executable code.

## Archive verification

`SOURCE_FILES.txt` lists the source package contents. Release sidecars record the
ZIP SHA-256 and every included file hash. The all-in-one package includes the
exact source ZIP as `source-original.zip`, its extracted `source/` tree, platform
executables, runtime notices, launchers, and an internal `SHA256SUMS` manifest.

Fresh extraction checks compare the source ZIP to the extracted files, verify
manifests, inspect executable architectures and linked libraries, and run the
launchers outside the source checkout. Twelve binary cases per target compare
classroom, lossless, and trace output for the complete, vocabulary, expanded
invalid, and trace demonstrations. Permissions and paths containing spaces are
included. Current release assets are downloaded again for post-publication checks.

## Limits of the evidence

The standalone analyzer does not check or execute language semantics. Dev-C++ and
Xcode GUI steps were not directly exercised; equivalent four-file compiler
commands were. One local Windows symlink capability probe was unavailable and
was reported as such. LeakSanitizer was not verified.

Windows binaries use system DLLs with the non-system runtime linked statically.
Both Mac binaries link the system library and require macOS 15 or later. They
have no Developer ID signature or notarization; Gatekeeper may prompt or block
execution. GUI quarantine behavior and prompt-free launching are not claimed.

The submitted 20-page `Group-1_Project_Proposal-1 (1).pdf` remains unchanged and
is not redistributed. Its SHA-256 is
`d7c6bb63ca5ff4d7d627591375029e2f943cd6e3ce02cc4ada2f54fc7415c827`.
[Proposal alignment](SUBMITTED_PROPOSAL_ALIGNMENT.md) explicitly distinguishes
the submitted vocabulary from later lexical adjustments.
