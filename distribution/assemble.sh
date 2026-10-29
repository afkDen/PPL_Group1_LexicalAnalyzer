#!/bin/sh
set -eu
test "$#" = 5 || { echo 'Usage: assemble.sh WINDOWS.zip ARM.zip INTEL.zip NEW_COMBINED.zip SOURCE_SHA256' >&2; exit 2; }
scripts=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
output=$(cd -- "$(dirname -- "$4")" && pwd)/$(basename -- "$4")
test ! -e "$output"
test ! -e "$output.sha256"
assembly_tmp=$(mktemp -d)
trap 'rm -rf "$assembly_tmp"' EXIT HUP INT TERM
unzip -q "$1" -d "$assembly_tmp/windows"
unzip -q "$2" -d "$assembly_tmp/arm"
unzip -q "$3" -d "$assembly_tmp/intel"
for payload in windows arm intel; do
  sh "$scripts/manifest.sh" "$assembly_tmp/$payload" validate
  (cd "$assembly_tmp/$payload" && shasum -a 256 -c SHA256SUMS)
  sh "$scripts/source-check.sh" "$assembly_tmp/$payload/source-original.zip" "$5" "$assembly_tmp/$payload/source"
done
for payload in arm intel; do
  diff -r "$assembly_tmp/windows/source" "$assembly_tmp/$payload/source"
  for name in source-original.zip Run-Windows.cmd Run-Mac.command RUN_OR_COMPILE.md README.md; do
    cmp "$assembly_tmp/windows/$name" "$assembly_tmp/$payload/$name"
  done
done
cp -pR "$assembly_tmp/arm/bin/macos-arm64" "$assembly_tmp/windows/bin/"
cp -pR "$assembly_tmp/intel/bin/macos-x64" "$assembly_tmp/windows/bin/"
cd "$assembly_tmp/windows"
rm SHA256SUMS
for executable in "$assembly_tmp/arm/Run-Mac.command" bin/macos-arm64/ternfold-lexer bin/macos-x64/ternfold-lexer; do
  test "$(stat -f %Lp "$executable")" = 755
done
# The Windows ZIP does not preserve the Mac launcher mode; use the verified Mac copy.
cp -p "$assembly_tmp/arm/Run-Mac.command" Run-Mac.command
sh "$scripts/manifest.sh" "$assembly_tmp/windows"
# Standard Unix zip records real Unix modes after chmod. Do not re-ZIP on Windows.
zip -q -r "$output" .
zipinfo -l "$output"
digest=$(shasum -a 256 "$output" | cut -d ' ' -f 1)
printf '%s  %s\n' "$digest" "$(basename -- "$output")" > "$output.sha256"
echo 'Prepared archive: fresh native Windows and both Mac verification jobs must pass before release.'
