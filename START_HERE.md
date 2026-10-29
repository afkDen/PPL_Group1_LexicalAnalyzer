# Start here

**Compiling in Dev-C++ or Xcode? Follow [IDE_QUICK_START.md](IDE_QUICK_START.md).**
It lists the four C files, header path, program arguments and working directory.

1. Extract the entire ZIP.
2. Open a terminal in the extracted folder. A compatible C17 compiler must already
   be installed; no compiler or executable is required to be bundled here.
3. Mac/Linux: `sh scripts/build.sh build`.
   Windows PowerShell: `./scripts/build.ps1 build`.
4. Mac/Linux:
   `./build/ternfold-lexer examples/lexical/complete.tfd --classroom --output-dir build`
   Windows: use `./build/ternfold-lexer.exe` with the same arguments.
5. Open `build/Symbol Table.txt`. Follow the eleven rows in `RUBRIC.md`.
6. Run `examples/lexical/invalid.tfd` with the same options. Exit 1 is expected;
   INVALID rows must appear. Rerun the complete example to restore its report.
7. Run the analyzer on `README.md`: it must reject the extension before reading.

Expected success: `Symbol Table.txt written`, exit 0. Reports have TOKEN TYPE and
LEXEME columns. The provided root `Symbol Table.txt` is a generated reference;
step4 creates a NEW report, proving the analyzer produced it.

See README.md for choosing an existing compiler, test commands, path/permission
troubleshooting and verified versus unverified platforms. Do not grade runtime
semantics from this lexical-only submission.

For the full vocabulary/proposal comparison and oral defense, open PROFESSOR_DEMO_GUIDE.md, PROPOSAL_LEXICAL_RECONCILIATION.md and DFA_LIVE_DEMO.md. The name DFA is fixed in src/name_dfa.inc; --trace-dfa shows actual transitions on stderr. Run invalid-comprehensive.tfd and the byte fixtures described in INVALID_CASES.md for detailed error/recovery evidence. The separate versioned all-in-one package runs without compiling; previous binaries remain historical, not substitutes for this revision.
