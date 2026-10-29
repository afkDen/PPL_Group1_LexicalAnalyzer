#!/bin/sh
set -eu
test "$#" = 3 || { echo 'Usage: build-mac.sh SOURCE.zip NEW_OUTPUT_DIRECTORY SHA256' >&2; exit 2; }
scripts=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
source_zip=$(cd -- "$(dirname -- "$1")" && pwd)/$(basename -- "$1")
sh "$scripts/source-check.sh" "$source_zip" "$3"
test ! -e "$2"
case "$(uname -sm)" in
  'Darwin arm64') target=macos-arm64; arch=arm64 ;;
  'Darwin x86_64') target=macos-x64; arch=x86_64 ;;
  *) echo 'Build this payload on its native Mac host.' >&2; exit 2 ;;
esac
mkdir -p "$2/source"
out=$(CDPATH= cd -- "$2" && pwd)
cp "$source_zip" "$out/source-original.zip"
unzip -q "$source_zip" -d "$out/source"
sh "$scripts/source-check.sh" "$source_zip" "$3" "$out/source"
for name in Run-Windows.cmd Run-Mac.command RUN_OR_COMPILE.md; do cp "$scripts/$name" "$out/$name"; done
cp "$scripts/RUN_OR_COMPILE.md" "$out/README.md"
printf '\nEmbedded source ZIP SHA-256: `%s`.\n' "$(printf '%s' "$3" | tr A-F a-f)" >> "$out/README.md"
mkdir -p "$out/bin/$target"
# Native gate outputs must not enter or mutate the source-preserving payload.
test ! -e "$out-check"
mkdir "$out-check"
cp -R "$out/source/." "$out-check/"
cd "$out-check"
export MACOSX_DEPLOYMENT_TARGET=15.0
sh scripts/build.sh environment
sh scripts/build.sh check
sh scripts/build.sh sanitize
cc -std=c17 -O2 -Wall -Wextra -Werror -pedantic -Wconversion -Wshadow -mmacosx-version-min=15.0 -arch "$arch" -Iinclude src/main.c src/lexer.c src/source.c src/report.c -o "$out/bin/$target/ternfold-lexer"
binary="$out/bin/$target/ternfold-lexer"
chmod 755 "$binary" "$out/Run-Mac.command"
file "$binary" | grep "Mach-O 64-bit executable $arch"
otool -L "$binary" > "$out/bin/$target/imports.txt"
# Fail closed for Homebrew/toolchain/runtime dylibs or rpath dependencies.
awk 'NR > 1 { if ($1 !~ /^\/usr\/lib\// && $1 !~ /^\/System\/Library\//) exit 1; n++ } END { if (!n) exit 1 }' "$out/bin/$target/imports.txt"
{
  uname -a
  cc --version
  printf 'Deployment target: macOS 15.0; native tested host above. No older-macOS claim.\nNo Developer ID signing; not notarized. Ad hoc signatures are possible.\n'
  file "$binary"
  otool -L "$binary"
  otool -l "$binary"
  codesign -dvv "$binary" 2>&1 || :
} > "$out/bin/$target/BUILD_INFO.txt"
# Only the fixed allowlisted runtime payload enters the archive; check outputs stay outside.
cd "$out"
sh "$scripts/manifest.sh" "$out"
printf 'Prepared %s payload: %s\n' "$target" "$out"
