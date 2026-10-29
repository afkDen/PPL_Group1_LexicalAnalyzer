# Ternfold static DFA all-in-one — October 30, 2026

Extract the ENTIRE ZIP to a writable folder first. Keep its folders together.
This analyzes tokens and produces a table; it does not execute Ternfold programs.
Includes the new static DFA source and Windows x64 / macOS ARM64 / Intel binaries.

## Run without compiling

**No compiler, IDE, Python, Node, Git or Internet connection is needed.**

Windows 10/11 x64: double-click **Run-Windows.cmd**. Press a key when finished.
Mac with Apple Silicon OR Intel: double-click **Run-Mac.command**. Press Return
when finished. The launcher selects the binary for the current Mac architecture.
Open **reports/Symbol Table.txt** for the newly generated result.
The file **source/Symbol Table.txt** is only the supplied reference.

Mac executables have **no Developer ID signing and are not notarized**. Apple
tools may apply an ad hoc signature; that does not establish a developer identity
or notarization. A download may be blocked by
Gatekeeper. After checking the download and its SHA256, use Finder's Open action
for the specific launcher; if macOS blocks the selected binary, use System
Settings > Privacy & Security > Open Anyway for that specific trusted item.
Availability and wording depend on macOS version and local administrator policy.
If policy disallows it, use the source instructions below. Do not disable
Gatekeeper globally. These launchers do not remove quarantine or change security
settings. Windows may also show an unsigned-download warning; use local policy.
Apple explains [opening a specific blocked app](https://support.apple.com/102445)
and [Developer ID signing and notarization](https://developer.apple.com/documentation/security/notarizing-macos-software-before-distribution).

To analyze your own file, open a terminal in the extracted folder:

Windows Command Prompt:

```bat
Run-Windows.cmd "C:\path with spaces\my-program.tfd"
Run-Windows.cmd source\examples\lexical\invalid-comprehensive.tfd
Run-Windows.cmd source\examples\lexical\trace.tfd --trace-dfa 2>trace.txt
```

Mac Terminal:

```sh
./Run-Mac.command "/path with spaces/my-program.tfd"
./Run-Mac.command source/examples/lexical/invalid-comprehensive.tfd
./Run-Mac.command source/examples/lexical/trace.tfd --trace-dfa 2>trace.txt
```

Both launchers always write **reports/Symbol Table.txt** beside the launcher,
including when given your own input path. Terminal runs with arguments finish
without pausing. If launching from another folder, supply an absolute input path.

Success exits 0. Invalid input exits 1 and writes INVALID rows to the report.
A wrong extension (for example README.md) exits 1 before opening that input and
leaves the report unchanged. Only the exact lowercase .tfd extension is accepted.
With no arguments the launchers analyze complete.tfd in classroom format.
The trace demo intentionally contains invalid tokens (exit 1); trace.txt records
actual scanner transitions, final decisions and diagnostics.
The launchers use classroom-readable output. To choose other CLI options, run
the appropriate executable under bin/ directly (see source/README.md).

## Compile from source

**This route DOES require an installed C17 compiler.** The complete standalone
source is in **source/**, byte for byte from the pinned static DFA source ZIP.
The exact original ZIP is also preserved as source-original.zip.

Open a terminal in **source/**, then:

Windows PowerShell with Clang or GCC installed:

```powershell
./scripts/build.ps1 check
./scripts/build.ps1 build
./build/ternfold-lexer.exe examples/lexical/complete.tfd --classroom --output-dir build
```

Mac Terminal with the Apple command line tools installed:

```sh
sh scripts/build.sh check
sh scripts/build.sh build
./build/ternfold-lexer examples/lexical/complete.tfd --classroom --output-dir build
```

Read source/IDE_QUICK_START.md for manual Dev-C++ and Xcode project setup.
Keep src/name_dfa.inc adjacent to src/lexer.c when compiling the four C files.
Read source/DFA_LIVE_DEMO.md and source/INVALID_CASES.md for the new demos.
Read source/RUBRIC.md and source/DEMO_ROWS.md for the classroom demonstration.

## Integrity and platform limits

SHA256SUMS covers every supplied regular file except SHA256SUMS itself.
On Mac, run `shasum -a 256 -c SHA256SUMS` from the extracted root.
The external .zip.sha256 hashes the whole archive and is kept outside it.
Windows contains statically linked LLVM/MinGW runtime portions; their license
notices are under licenses/windows-x64. Windows system DLLs are not bundled.
Mac builds target macOS 15.0 and link only Apple system libraries. The native
execution gate uses macOS 15 on each Mac architecture; older macOS is unverified
and below this bundle's deployment target. This bundle does not include an IDE
or compiler. See BUILD_INFO files for actual compiler, architecture and imports.
CI verifies a fresh extraction on Windows x64, Mac ARM64 and Mac Intel before
the supervisor may publish the combined ZIP. Other platforms remain unverified.
