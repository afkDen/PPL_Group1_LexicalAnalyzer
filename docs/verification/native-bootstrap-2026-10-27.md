# Authorized native toolchain setup — 2026-10-27

The human explicitly authorized necessary project dependencies and build tools,
including GCC/Clang setup and bootstrap integration. This authorization is
recorded in the active handoff and persists across milestones.

## Installed toolchain

Official LLVM-MinGW release
[20261020](https://github.com/mstorsjo/llvm-mingw/releases/tag/20261020), asset
`llvm-mingw-20261020-ucrt-x86_64.zip`, 190,612,575 bytes. GitHub's official release
API published SHA-256:

```text
fd5462b7f5d93b2ff981fcd3f9c7e427e47f3203c64ea91c27bcc444eebd74cd
```

The downloaded bytes matched that digest before extraction. The portable
toolchain resides under `.uv-cache/native-toolchains/`; no machine-wide PATH,
registry, administrator install or shell startup file was changed. The
[upstream README](https://github.com/mstorsjo/llvm-mingw#releases) documents native
Windows ZIP distributions that work by unpacking them.

Clang reports **23.1.4**, target `x86_64-w64-windows-gnu`. The real C17 probe
compiled with `-std=c17 -Wall -Wextra -Werror -pedantic` and ran successfully.
This removes the prior missing-compiler environment blocker; it is not evidence
that the Ternfold native runtime/backend is implemented.

## Bootstrap integration

`scripts/native_tools.py` pins the asset/hash, discovers the local compiler or
PATH GCC/Clang, validates archives before staging extraction, and supports an
offline repeat. Explicit `--cc` never silently falls back to another compiler.
`bootstrap.py --install-native` opts into project-local Windows x64 installation
and native verification; `--offline` reuses the cached archive/install.
`check_environment.py` auto-discovers the cached compiler. Other platforms may
use installed GCC/Clang or an explicit compiler path.

## Fresh evidence

- `scripts/check_environment.py --phase native --output
  docs/verification/native-environment-2026-10-27.json`: passed, including actual
  C17 compile/run. Exact versions and outcomes are in that JSON.
- `python scripts/bootstrap.py --offline --install-native`: passed with the
  cached Clang and native probe, without network or administrator access.
- `tests/test_native_tools.py`: **15 passed**. Cases cover archive traversal,
  drive/backslash/NUL spellings, link entries, digest mismatch, offline extraction,
  idempotent reuse, preservation of incomplete installs, explicit compiler
  selection and unsupported hosts.
- Scoped Ruff lint/format and strict mypy passed for helper/bootstrap/checker
  and tests. Full integration and independent tooling review remain pending
  alongside active M06 work.

The archive tests exposed Windows ZipInfo normalization of backslashes/NULs;
validation now examines `orig_filename` before normalization. Test fixtures are
never executed as binaries. Downloaded tools and archives remain ignored cache
artifacts, not maintained source or runtime/network dependencies.

## Independent tooling review

Read-only reviewer Meitner accepted the tooling change without blockers after
independently running 15 tests and scoped Ruff/mypy across four files,
validating 9,299 real archive members and the cached SHA-256, and passing the
actual Clang C17 compile/run. An explicitly missing `--cc` correctly fails the
native gate even when cached Clang is available. The supervisor observed offline
bootstrap with `--install-native` pass; upstream asset metadata/digest provenance
came from the official release API. Final full integration passed in the M06
954-test gate, recorded in [M06 acceptance](M06-2026-10-27.md).
