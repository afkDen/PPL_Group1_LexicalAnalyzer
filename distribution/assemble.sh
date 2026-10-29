#!/bin/sh
set -eu
test "$#" = 4 || { echo 'Usage: assemble.sh WINDOWS.zip ARM.zip INTEL.zip NEW_COMBINED.zip' >&2; exit 2; }
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
  (cd "$assembly_tmp/$payload" && shasum -a 256 -c SHA256SUMS)
done
for payload in arm intel; do
  diff -r "$assembly_tmp/windows/source" "$assembly_tmp/$payload/source"
  for name in source-original.zip Run-Windows.cmd Run-Mac.command RUN_OR_COMPILE.md README.md; do
    cmp "$assembly_tmp/windows/$name" "$assembly_tmp/$payload/$name"
  done
done
cp -R "$assembly_tmp/arm/bin/macos-arm64" "$assembly_tmp/windows/bin/"
cp -R "$assembly_tmp/intel/bin/macos-x64" "$assembly_tmp/windows/bin/"
cd "$assembly_tmp/windows"
rm SHA256SUMS
chmod 755 Run-Mac.command bin/macos-arm64/ternfold-lexer bin/macos-x64/ternfold-lexer
sh "$scripts/manifest.sh" "$assembly_tmp/windows"
# Standard Unix zip records real Unix modes after chmod. Do not re-ZIP on Windows.
zip -q -r "$output" .
zipinfo -l "$output"
digest=$(shasum -a 256 "$output" | cut -d ' ' -f 1)
printf '%s  %s\n' "$digest" "$(basename -- "$output")" > "$output.sha256"
echo 'Candidate only: fresh native Windows + both Mac verification jobs must pass before supervisor publication.'
