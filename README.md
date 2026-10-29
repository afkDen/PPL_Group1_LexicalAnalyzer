# Ternfold — C17 Lexical Analyzer

Ternfold is our group's original programming language. This repository contains
its standalone, handwritten C17 lexical analyzer. It reads `.tfd` source,
recognizes tokens, and writes a classroom **Symbol Table.txt** report.
It performs lexical analysis only; it does not parse, type-check, or execute
Ternfold programs.

## Quick start

### Option A: Run without compiling

Download the **All-in-One ZIP** below and extract the whole archive. On Windows,
open `Run-Windows.cmd`; on a compatible Mac, open `Run-Mac.command`. The launcher
runs `complete.tfd` and writes **reports/Symbol Table.txt**. No compiler, Homebrew,
Python, Node, or additional project download is required.

The bundle includes Windows x64, macOS ARM64, and macOS Intel executables.
Mac binaries require macOS 15 or later and are not Developer ID signed or
notarized; Gatekeeper may prompt or block them. Read the bundle README first.

### Option B: Compile from source

Extract the **Source-only ZIP**, then open a terminal in its root directory.
A compatible C17 Clang or GCC compiler must already be installed.

**Mac / Linux:**

```sh
sh scripts/build.sh build
./build/ternfold-lexer examples/lexical/complete.tfd --classroom --output-dir build
```

**Windows PowerShell:**

```powershell
./scripts/build.ps1 build
./build/ternfold-lexer.exe examples/lexical/complete.tfd --classroom --output-dir build
```

Open **build/Symbol Table.txt**. The build command creates `build`; any other
output directory must already exist. For Dev-C++, Xcode, compiler selection,
and direct four-file compilation, see [the IDE guide](IDE_QUICK_START.md).

## Submission downloads

Choose one of the two packages in the
[current release](https://github.com/afkDen/PPL_Group1_LexicalAnalyzer/releases/tag/lexical-submission-clean-2026-10-30):

| Package | Use it to |
|---|---|
| [Source-only ZIP](https://github.com/afkDen/PPL_Group1_LexicalAnalyzer/releases/download/lexical-submission-clean-2026-10-30/Ternfold_Lexical_Source_2026-10-30_Clean.zip) | Inspect, compile, and test the source. Includes IDE instructions, examples, reference reports, and tests. |
| [All-in-One ZIP](https://github.com/afkDen/PPL_Group1_LexicalAnalyzer/releases/download/lexical-submission-clean-2026-10-30/Ternfold_Lexical_All_In_One_2026-10-30_Clean.zip) | Run a supplied executable, or compile the same source. Includes launchers and runtime notices. |

Checksums and file manifests accompany the ZIPs. Earlier releases remain
available as historical checkpoints.

## What it recognizes

The scanner recognizes 28 keyword spellings, 25 reserved names, identifiers,
Int/Float/Bool/Text/Char literals, operators, delimiters, contextual noise words,
and line/block comments. Invalid input produces diagnostics and `INVALID` rows
where a source report can be generated.

For example, this input:

```tfd
let total: Int = 17 + 2;
```

produces these classroom classifications, in source order:

```text
TOKEN TYPE         LEXEME
KEYWORD            let
IDENTIFIER         total
COLON              :
RESERVED_WORD      Int
ASSIGN             =
INT_LITERAL        17
PLUS               +
INT_LITERAL        2
SEMICOLON          ;
```

The report has exactly two columns: `TOKEN TYPE` and `LEXEME`. Whitespace and EOF
are omitted; comments and invalid tokens remain. Escapes keep multiline lexemes
on one row. Without `--classroom`, lexemes use lossless JSON quoting.

## Professor demonstration

Follow the [presentation guide](PROFESSOR_DEMO_GUIDE.md) and
[eleven-item rubric](RUBRIC.md). `complete.tfd` demonstrates the current vocabulary,
all seven arithmetic operators, all nine Boolean/relational operators, literals,
comments, noise words, and delimiters. [Report row references](DEMO_ROWS.md)
make each example easy to locate. [Invalid examples](INVALID_CASES.md) demonstrate
errors and recovery; they intentionally return exit code 1.

## Handwritten DFA implementation

[`src/name_dfa.inc`](src/name_dfa.inc) defines 215 immutable name states and their
character edges at compile time. [`src/lexer.c`](src/lexer.c) follows those edges;
it does not construct the production graph at runtime or compare completed
input words against a keyword list. Classification uses the accepting state at
the lexeme boundary, so `ifx` remains one identifier.

Numbers, quoted literals, comments, and operators use separate handwritten
state/switch logic. The include is part of `lexer.c`, **not a fifth compilation
unit**. See [DFA.md](DFA.md) and [the live walkthrough](DFA_LIVE_DEMO.md).
Add `--trace-dfa` to record actual transitions on standard error without
changing the Symbol Table.

## Project files

| File | Purpose |
|---|---|
| `src/main.c` | Command-line arguments, file handling, and exit status. |
| `src/lexer.c` | Active scanner and transition tracing. |
| `src/source.c` | Source bytes, UTF-8 validation, spans, and allocation support. |
| `src/report.c` | Classroom and lossless report output. |
| `include/ternfold/lexer.h`, `src/internal.h` | Public interface and internal declarations. |
| `src/name_dfa.inc` | Fixed name-state definitions included by the scanner. |
| `examples/lexical/` | Main demonstration, support file, vocabulary, trace, and invalid input. |
| `tests/`, `tools/`, `scripts/` | Regression fixtures and build/test support. |

Only the four `src/*.c` files form the application. The historical scanner in
`tests/baseline_lexer.c` is a frozen differential-test oracle, never linked into
the production executable. See [the test overview](tests/README.md).

## Testing

```sh
sh scripts/build.sh check
sh scripts/build.sh sanitize
```

On Windows, use `./scripts/build.ps1 check` and `./scripts/build.ps1 sanitize`.
These run strict C17 builds, lexical/CLI/report/DFA/trace tests, historical
comparisons, and the repository audit. Sanitizers require toolchain support.
[VERIFICATION.md](VERIFICATION.md) gives results, reproduction steps, CI links,
and the limits of platform checks.

## Documentation index

- [Start here](START_HERE.md): short source-build walkthrough.
- [IDE guide](IDE_QUICK_START.md): Dev-C++, Xcode, and manual compilation.
- [DFA explanation](DFA.md) and [live demonstration](DFA_LIVE_DEMO.md).
- [Presentation guide](PROFESSOR_DEMO_GUIDE.md), [rubric](RUBRIC.md), and [report rows](DEMO_ROWS.md).
- [Invalid-input matrix](INVALID_CASES.md).
- [Submitted-proposal alignment](SUBMITTED_PROPOSAL_ALIGNMENT.md) and [full vocabulary matrix](PROPOSAL_LEXICAL_RECONCILIATION.md).
- [Tests](tests/README.md) and [verification](VERIFICATION.md).

## Limitations

Input filenames must end in the exact, case-sensitive extension `.tfd`.
Lexical rejection returns 1; usage, allocation, file, or output failures return 2.
Source compilation requires an installed toolchain; MSVC is not a supported
workflow. Dev-C++ and Xcode GUI steps are documented but were not directly tested.
Unsigned executable warnings may occur. Token recognition does not establish
Ternfold program validity or runtime behavior.
