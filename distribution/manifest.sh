#!/bin/sh
set -eu
scripts=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
cd "$1"
test -z "$(find . -type l -print)"
find . -type f | while IFS= read -r path; do
  path=${path#./}
  case "$path" in
    source/*) grep -Fqx "${path#source/}" "$scripts/../SOURCE_FILES.txt" ;;
    source-original.zip|Run-Windows.cmd|Run-Mac.command|RUN_OR_COMPILE.md|README.md|SHA256SUMS) ;;
    bin/windows-x64/ternfold-lexer.exe|bin/windows-x64/BUILD_INFO.txt) ;;
    bin/macos-arm64/ternfold-lexer|bin/macos-arm64/BUILD_INFO.txt|bin/macos-arm64/imports.txt) ;;
    bin/macos-x64/ternfold-lexer|bin/macos-x64/BUILD_INFO.txt|bin/macos-x64/imports.txt) ;;
    licenses/windows-x64/LLVM-LICENSE.txt|licenses/windows-x64/COPYING|licenses/windows-x64/COPYING.MinGW-w64.txt|licenses/windows-x64/COPYING.MinGW-w64-runtime.txt|licenses/windows-x64/COPYING.winpthreads.txt|licenses/windows-x64/COPYING.winstorecompat.txt) ;;
    *) echo "Unexpected payload file: $path" >&2; exit 1 ;;
  esac
done
if [ "${2-}" = validate ]; then exit 0; fi
test ! -e SHA256SUMS
# Use an external temporary file so neither it nor SHA256SUMS hashes itself.
manifest_tmp=$(mktemp)
trap 'rm -f "$manifest_tmp"' EXIT HUP INT TERM
find . -type f | LC_ALL=C sort | while IFS= read -r path; do
  digest=$(shasum -a 256 "$path" | cut -d ' ' -f 1)
  printf '%s  %s\n' "$digest" "${path#./}"
done > "$manifest_tmp"
cp "$manifest_tmp" SHA256SUMS
