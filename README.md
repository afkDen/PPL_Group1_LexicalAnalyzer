# Ternfold lexical analyzer — official source submission

**Using an IDE? Start with [IDE_QUICK_START.md](IDE_QUICK_START.md)** for Dev-C++ and Xcode setup, run arguments and report location.

## 1. Introduction

Ternfold is our group's original programming language. This submission contains
its handwritten C17 lexical analyzer. A compatible C compiler must already be
available to build the source; a compiler, installer and executable are not
bundled in this official source ZIP.

## 2. What it does

The analyzer reads only `.tfd` files, separates their contents into tokens, and
recognizes identifiers, keywords, reserved words, five literal categories,
operators, comments, delimiters and invalid lexemes. It writes `Symbol Table.txt`
with exactly two columns: `TOKEN TYPE` and `LEXEME`. This is lexical analysis,
not the complete parser, type checker or executable Ternfold compiler.

## 3. Files included

- `src/main.c`, `lexer.c`, `source.c`, `report.c`, `internal.h`: complete analyzer.
- `include/ternfold/lexer.h`: the shared C interface.
- `examples/lexical/complete.tfd`: the primary grading demonstration.
- `examples/lexical/invalid.tfd`: intentionally invalid tokens and recovery.
- `examples/lexical/vocabulary.tfd`: separately labeled lexical-only inventory.
- `tests/`: C tests and expected report files.
- `scripts/build.sh`, `scripts/build.ps1`, `build.bat`, `tools/`: build/test support.
- `Symbol Table.txt`: generated classroom report for the primary demonstration.
- `RUBRIC.md`, `DFA.md`: demonstration checklist and scanner explanation.

## 4. Quick start — compile and run

Open a terminal in the extracted directory. Paths containing spaces are supported.

**Mac / Linux / POSIX:** a C17 compiler (`cc`, Apple Clang or GCC) and a standard
shell must already be installed. On a Mac, check `cc --version` first; command
line developer tools are not installed on every Mac. Homebrew is not required.

```sh
sh scripts/build.sh build
./build/ternfold-lexer examples/lexical/complete.tfd --classroom --output-dir build
```

To choose an existing compiler, use `CC=clang sh scripts/build.sh build`.

**Windows:** install or select a compatible Clang/GCC compiler, then use PowerShell:

```powershell
./scripts/build.ps1 build
./build/ternfold-lexer.exe examples/lexical/complete.tfd --classroom --output-dir build
```

If the compiler is not on PATH, pass `-Compiler 'C:/path/to/clang.exe'` to the
build script. `build.bat build` is an alternative launcher.

Success prints `Symbol Table.txt written` and returns exit code 0. The report
begins with `TOKEN TYPE` and `LEXEME`, followed by rows such as `KEYWORD` / `let`
and `INT_LITERAL` / `17`. Classroom mode does not add quotes around ordinary
lexemes; the original quotes in a Text or Char literal are part of that lexeme.

## 5. Demonstration

Run the primary example first, then read the report and `RUBRIC.md`. It visibly
contains all seven arithmetic operators, all nine Boolean/relational operators,
five literal categories, both comment forms, noise words and brackets/delimiters.

Run the invalid example next:

```sh
./build/ternfold-lexer examples/lexical/invalid.tfd --classroom --output-dir build
```

On Windows use `./build/ternfold-lexer.exe` for the executable name. Exit code 1
is EXPECTED for this example. The report is still generated, including `INVALID`
rows for `@`, `09`, `1e+`, an invalid Text escape, an invalid Char and an
unfinished block comment. This run replaces the previous report in `build`;
rerun the primary example to restore its report.

To demonstrate filetype rejection, run the analyzer on `README.md`. It must
return 1 and explain that only `.tfd` is accepted, before opening the input.
The automated tests additionally use a missing non-`.tfd` path to check this order.

## 6. Where is Symbol Table.txt?

`--output-dir build` writes `build/Symbol Table.txt`. The directory must exist
(the build command creates it). Without that option, the report is written into
the current working directory. Select a different existing directory to keep
multiple reports. The source file is never a report destination.

Classroom mode keeps each lexeme on one row: newline, carriage return, tab and
backslash are shown as `\n`, `\r`, `\t`, `\\`; other controls use `\u00XX`.
Unicode text remains UTF-8. Original quote characters are retained, so `"hello"`
is a Text lexeme and `'A'` is a Char lexeme. Without `--classroom`, the compatible
lossless report encloses each lexeme in JSON quotes. Both preserve token order,
comments and invalids; whitespace and EOF are omitted. Unit is two parentheses.

## 7. Professor criteria

All eleven criteria are mapped to actual sample lexemes and generated rows in
[RUBRIC.md](RUBRIC.md). The valid main sample and separate invalid sample are the
visible grading demonstrations; recognition hidden in scanner code is not proof.

## 8. Source implementation

The scanner advances explicit character-driven states and trie edges. It does
not use a lexer generator, premade analyzer, regex tokenization or whole-word
keyword matching. The token classification comes from the accepting state at
an identifier boundary. `letx` is one identifier, not `let` plus `x`.
See [DFA.md](DFA.md) for comments, literals, operators and recovery.

## 9. Troubleshooting and tested platforms

- **Compiler missing:** source compilation needs an existing C17 Clang/GCC compiler.
  This ZIP contains all project source dependencies, not a compiler installation.
- **Wrong extension:** `.tfd` is exact and case-sensitive; `.txt` / `.TFD` reject.
- **Invalid source:** exit 1 and `INVALID` report rows are expected; inspect stderr.
- **Output failure:** create the output directory and check write permissions.
  Usage, allocation, file-read and output failures return 2.
- **Report/input alias:** choose a different directory; source protection rejects it.
- **Platforms:** Windows x64 Clang23.1.4, macOS15 Apple Silicon and Intel AppleClang17,
  and Ubuntu24.04 GCC13.3 source builds are verified. Actual results are in
  `VERIFICATION.md`; other platforms remain unverified.
  MSVC is not currently a supported build workflow.

## 10. Advanced testing

```sh
sh scripts/build.sh check
sh scripts/build.sh sanitize
```

Windows equivalents are `./scripts/build.ps1 check` and `sanitize`. Sanitizers
require compiler support; an unavailable sanitizer is not a passed check.
The tests exercise vocabulary, spans/UTF-8, allocation failures, invalid recovery,
report bytes, filetype policy, safe publication and CLI failures. The public
header documents memory ownership. Compiler/runtime execution is outside this
lexical submission. No Python, Node, AI service or network is needed to build
or run it once a compatible C toolchain is installed.
