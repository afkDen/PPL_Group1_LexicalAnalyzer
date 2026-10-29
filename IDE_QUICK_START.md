# Compile and demonstrate in a C IDE

A lexical analyzer reads source text and identifies tokens such as names,
numbers and operators. This application reads a Ternfold `.tfd` file and writes
the two-column `Symbol Table.txt` report. It does not execute the Ternfold program.

Extract the whole ZIP first. Keep its folders together. A compatible existing
C17 compiler is required; this submission bundles neither an IDE nor a compiler.

## Files to compile

Add exactly these four implementation files to one **C console application**:

| File | Purpose |
|---|---|
| `src/main.c` | Application entry point, filename/options and exit status |
| `src/source.c` | Source loading, UTF-8 and source positions |
| `src/lexer.c` | Handwritten scanner and token recognition |
| `src/report.c` | Diagnostics and safe Symbol Table publication |

They call each other, so compiling only `lexer.c` or only `main.c` is insufficient.
`include/ternfold/lexer.h` declares their shared interface; `src/internal.h`
declares private helpers. Headers may be added for browsing; do not compile
them as separate programs. Add the **`include` directory**, not `include/ternfold`,
to the compiler's header search path. The private header is found beside the C files.
Keep `.c` files in C mode, not C++ mode.

Do not add `tests/*.c`, `tools/*.c`, or a template-generated `main.c` to this
application: those contain separate entry points. `.tfd` files are analyzer input,
not C compilation units. No external project libraries are needed.

## Windows: Dev-C++ manual project setup

The following settings are checked against Embarcadero Dev-C++ documentation
and source. Dev-C++ and its GCC toolchain were **not run in our verification**;
menu labels vary between versions. No untested `.dev` project is supplied.
Dev-C++ is a Windows IDE; use Xcode or Apple Clang on macOS.

1. Choose **File > New > Project**, select **Console Application** and **C Project**.
   Save the project in the extracted folder containing this guide. Remove the
   auto-created source file from the project to avoid a second `main()`.
2. Use **Project > Add to Project** to add the four `.c` files listed above.
3. Open **Project > Project Options**. Under **Directories > Include Directories**,
   add `include`, relative to the project folder. Under **Options > C Compiler**
   (called **Parameters** in some versions), add `-std=c17 -Wall -Wextra -pedantic`.
   These are compiler options, not program arguments. Select an installed
   compatible GCC C compiler under **Compiler**. Older bundled compilers may
   lack C17 or required Windows APIs; their compatibility is unverified. If the
   build rejects a flag/API, use the verified Clang workflow in README rather
   than changing the scanner or compiling it as C++.
4. In **Output**, choose an executable name such as `ternfold-lexer.exe` and the
   project root as its executable output directory. Compile the **project** (F9
   in Embarcadero Dev-C++); inspect the build log for all four `.c` files.
5. Open **Execute > Parameters** and put this in the program-parameters field;
   leave **Host Application** empty:

   ```text
   examples/lexical/complete.tfd --classroom --output-dir .
   ```

6. If your version offers a working-directory setting, explicitly select the
   extracted root folder. Saving a project there alone does not prove the run
   directory. Run the executable (F10 in Embarcadero Dev-C++). Check that a fresh
   root `Symbol Table.txt` was produced and compare it with
   `tests/fixtures/lexer/Classroom Symbol Table.txt`.

If the IDE cannot set the working directory reliably, use **absolute paths** in
the same program-parameters field, quoting both paths if they contain spaces:

```text
"C:/path/to/extracted/examples/lexical/complete.tfd" --classroom --output-dir "C:/path/to/extracted"
```

Replace both paths with your actual extraction folder. This removes dependence
on the IDE's current directory. Alternatively, open PowerShell in that folder
and run `./ternfold-lexer.exe` followed by the relative demonstration arguments.

## Mac: Xcode manual project setup

These settings follow Apple's scheme/build documentation. **Direct Xcode GUI
execution is unverified.** Apple Clang source builds and report comparisons
have been run on actual Apple Silicon and Intel Macs; see VERIFICATION.md.

1. In Xcode choose **File > New > Project > macOS > Command Line Tool**; select
   **C** as the language. Save it outside the extracted folder if you wish.
2. Remove the generated `main.c` from the target. Choose **File > Add Files**
   and add the four original `.c` files from the extracted folder, with your
   command-line target selected under **Add to targets**. Keep references to the
   original files (do not copy them individually away from `src/internal.h`).
3. Select the project, then the command-line target, **Build Settings > All**.
   Set **C Language Dialect** (`GCC_C_LANGUAGE_STANDARD`) to **C17**. Set
   **Header Search Paths** (`HEADER_SEARCH_PATHS`) to the extracted folder's
   `include` directory; quote a path containing spaces. If the `.xcodeproj` is
   saved directly in the extracted root, `"$(SRCROOT)/include"` is suitable.
4. In **Build Phases > Compile Sources**, verify exactly the four `.c` files.
5. Choose **Product > Scheme > Edit Scheme > Run > Arguments**. Add these four
   enabled **Arguments Passed On Launch** entries, one per row:
   `examples/lexical/complete.tfd`, `--classroom`, `--output-dir`, `.`.
6. Under **Run > Options**, enable **Use custom working directory** and select
   the extracted root containing `examples`, `src`, and this guide. Build and
   run with **Product > Run**. Inspect the Xcode console for success and open
   `Symbol Table.txt` in that extracted root using Finder or a text editor.

If a menu differs in your Xcode version, use Apple's scheme help linked below.
The verified Terminal fallback needs no Xcode project or internal build driver:
open Terminal in the extracted root and run:

```sh
cc -std=c17 -Wall -Wextra -pedantic -Iinclude src/main.c src/lexer.c src/source.c src/report.c -o ternfold-lexer
./ternfold-lexer examples/lexical/complete.tfd --classroom --output-dir .
cmp 'Symbol Table.txt' 'tests/fixtures/lexer/Classroom Symbol Table.txt'
```

An existing Apple Clang installation is required. The README also retains the
verified `sh scripts/build.sh build` workflow. No Homebrew, Python or Node is needed.

## Demonstration and expected results

**Run with a filename argument.** Clicking Run with no arguments deliberately
returns usage error 2 (`expected source.tfd ...`); it does not prompt for input.
Set the run arguments above, rebuild if needed, and run again. No demo mode or
second launcher is required.

With the working directory explicitly set to the extracted root, use:

| Program arguments | Expected result |
|---|---|
| `examples/lexical/complete.tfd --classroom --output-dir .` | Exit 0; `Symbol Table.txt written`; fresh classroom report |
| `examples/lexical/invalid.tfd --classroom --output-dir .` | Exit 1; lexical diagnostics and report with `INVALID` rows; `Symbol Table.txt written` still appears |
| `README.md --classroom --output-dir .` | Exit 1; `source file extension must be exactly .tfd`; previous report stays unchanged |

Exit 2 indicates usage, input-read, allocation or output failure. If the IDE
closes the console immediately, inspect its run output or launch the executable
from Terminal/PowerShell; do not add `system("pause")` to the source.

The invalid run **replaces** the report. Rerun the complete example to restore
the normal report. A supplied report is only a reference: generate a new one
and compare it with the maintained expected file. `cmp` above prints nothing
and returns 0 when they agree. In PowerShell, compare the two files' SHA256
values with `Get-FileHash 'Symbol Table.txt'` and
`Get-FileHash 'tests/fixtures/lexer/Classroom Symbol Table.txt'`.

Open [RUBRIC.md](RUBRIC.md) and [DEMO_ROWS.md](DEMO_ROWS.md) beside the complete
sample and report. The sample visibly demonstrates all seven arithmetic and
nine Boolean/relational operators, five literal categories, keywords, reserved
and noise words, comments and delimiters. The separate invalid sample supplies
the invalid-token demonstration. Only sample-visible lexemes establish this proof.

## Configuration references and verification limits

- [Embarcadero project compilation](https://github.com/Embarcadero/Dev-Cpp/wiki/Compiling)
  and [project options UI](https://github.com/Embarcadero/Dev-Cpp/blob/master/Source/ProjectOptionsFrm.dfm).
  Its [project reader](https://github.com/Embarcadero/Dev-Cpp/blob/master/Source/Project.pas)
  uses an INI-style `.dev` format with per-file units and saved command-line
  parameters; compiler-set indices and old-version handling prevent promising
  a portable preconfigured file without testing the IDE.
- [Apple build settings](https://developer.apple.com/documentation/xcode/build-settings-reference)
  and [scheme launch configuration](https://developer.apple.com/documentation/xcode/customizing-the-build-schemes-for-a-project).

No `.dev` or `.xcodeproj` file is claimed tested or included. Equivalent compiler
commands and source lists are tested separately; successful compiler execution
does not establish GUI execution. See [VERIFICATION.md](VERIFICATION.md) for exact
platform evidence and limits. All previous CLI/build procedures remain available.
