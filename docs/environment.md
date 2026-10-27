# C17 development environment

Normal builds/execution require a C17 compiler and the platform shell adapter,
not Python, Node, CMake, AI access or a network connection. The native tools are
C programs. GCC/Clang-compatible flags are used; MSVC is not currently supported.
CMake/CTest were unavailable locally; the small native tfdev driver is the
verified equivalent build/test path rather than an additional build dependency.

## Windows (verified)

`./scripts/build.ps1 environment`, `./scripts/build.ps1 build`,
`./scripts/build.ps1 test`, `./scripts/build.ps1 audit`,
`./scripts/build.ps1 check`, `./scripts/build.ps1 sanitize`.
`./scripts/build.ps1 release` builds with -O2 and runs the full native gate.
Clean builds use a fresh archive extraction; no generated binaries are shipped.
Pass `-Compiler PATH` or set CC for a compiler path (not shell flags).
`./build.bat check` is the convenience wrapper.
The wrapper detects Clang/GCC or the locally cached LLVM-MinGW toolchain and
adds its binary directory for runtime DLL discovery. Paths with spaces work.

Verified: official LLVM-MinGW 20261020 UCRT x86_64, Clang 23.1.4, Windows x64.
Archive SHA256 fd5462b7f5d93b2ff981fcd3f9c7e427e47f3203c64ea91c27bcc444eebd74cd.
Optional `./scripts/bootstrap.ps1` downloads this pinned official compiler only
if needed; it is not a normal build prerequisite. Installed compiler use is offline.

## POSIX (intended, not yet verified)

`CC=clang sh scripts/build.sh environment` and `sh scripts/build.sh check`.
The C source includes isolated POSIX adapters. No Linux/macOS/GCC result is claimed
without an actual platform run. Cross compilation alone is not such a run.

## Gates and limitations

Strict C17 flags: -Wall -Wextra -Werror -pedantic -Wconversion -Wshadow.
ASan/UBSan are verified in the Windows toolchain; LeakSanitizer is unsupported.
The native audit checks maintained files/configuration; independent code review
and allocation-failure counters supplement sanitizer coverage. Use clang --analyze
for static analysis; native debug symbols are retained in build outputs.
`build` builds all currently implemented components (the lexer); there is no
full compiler executable yet. Full compiler tests arrive with their owning tasks.

Package: `./scripts/package.ps1`; verify: `./scripts/verify-archives.ps1`.
Both ZIPs must compile/run tests after fresh extraction outside the checkout.
Do not bundle toolchains, binaries, caches, credentials or historical Python ZIPs.
