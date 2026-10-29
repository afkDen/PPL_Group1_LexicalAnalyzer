# Start here

To run without installing a compiler, choose the All-in-One ZIP from
[the current release](https://github.com/afkDen/PPL_Group1_LexicalAnalyzer/releases/tag/lexical-submission-clean-2026-10-30).
Extract it and use its Windows or Mac launcher. Open `reports/Symbol Table.txt`.
Mac binaries require macOS 15 or later; Gatekeeper may prompt or block execution.
Read the bundle README for platform instructions.

For a source build:

1. Extract the complete Source-only ZIP and open a terminal in its root folder.
2. Check that a C17 Clang/GCC compiler is installed. For IDE setup, use
   [IDE_QUICK_START.md](IDE_QUICK_START.md).
3. Build: `sh scripts/build.sh build` on Mac/Linux, or
   `./scripts/build.ps1 build` in Windows PowerShell.
4. Run the main demonstration:

   ```sh
   ./build/ternfold-lexer examples/lexical/complete.tfd --classroom --output-dir build
   ```

   On Windows, use `./build/ternfold-lexer.exe` with the same arguments.
5. Open `build/Symbol Table.txt`. Success prints `Symbol Table.txt written` and
   returns 0. The root `Symbol Table.txt` is the supplied reference;
   this command creates a fresh report.
6. Repeat the command using `examples/lexical/invalid.tfd`. Exit code 1 and
   `INVALID` rows are expected. Rerun `complete.tfd` to restore the valid report.
7. Add `--trace-dfa` to see actual scanner transitions on standard error.
   Follow [DFA_LIVE_DEMO.md](DFA_LIVE_DEMO.md) to compare states to the source.

The report has two columns: `TOKEN TYPE` and `LEXEME`. The output directory
must exist. A run replaces the report in that directory; use separate directories
to retain several reports.

For presentation, follow [PROFESSOR_DEMO_GUIDE.md](PROFESSOR_DEMO_GUIDE.md),
[RUBRIC.md](RUBRIC.md), and [DEMO_ROWS.md](DEMO_ROWS.md). For errors and recovery,
see [INVALID_CASES.md](INVALID_CASES.md). [README.md](README.md) links to tests,
proposal alignment, and the documentation index.
