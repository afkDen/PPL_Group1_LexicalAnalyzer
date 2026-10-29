#!/bin/sh
set -eu
test "$#" = 3 || { echo 'Usage: finalize-repack.sh PREPARED.zip NEW_COMBINED.zip SOURCE_SHA256' >&2; exit 2; }
scripts=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
output=$(cd -- "$(dirname -- "$2")" && pwd)/$(basename -- "$2")
test ! -e "$output"
test ! -e "$output.sha256"
repack_tmp=$(mktemp -d)
trap 'rm -rf "$repack_tmp"' EXIT HUP INT TERM
unzip -q "$1" -d "$repack_tmp"
cd "$repack_tmp"
sh "$scripts/manifest.sh" "$PWD" validate
test "$(find . -type f | wc -l | tr -d ' ')" -eq "$(($(wc -l < SHA256SUMS) + 1))"
test "$(cut -c 67- SHA256SUMS | LC_ALL=C sort -u | wc -l | tr -d ' ')" -eq "$(wc -l < SHA256SUMS | tr -d ' ')"
! grep -Eq '  (SHA256SUMS|/|.*\.\./)' SHA256SUMS
shasum -a 256 -c SHA256SUMS
sh "$scripts/source-check.sh" source-original.zip "$3" source
test -f bin/windows-x64/ternfold-lexer.exe
chmod 755 Run-Mac.command bin/macos-arm64/ternfold-lexer bin/macos-x64/ternfold-lexer
# A Unix ZIP writer records executable modes; the file contents remain unchanged.
zip -q -r "$output" .
digest=$(shasum -a 256 "$output" | cut -d ' ' -f 1)
printf '%s  %s\n' "$digest" "$(basename -- "$output")" > "$output.sha256"
echo 'Prepared archive: fresh native Windows and both Mac verification jobs must pass before release.'
