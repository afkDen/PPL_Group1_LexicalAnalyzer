#!/bin/sh
set -eu
test "$#" = 3 || { echo 'Usage: verify-mac.sh COMBINED.zip NEW_EXTRACTION_DIRECTORY SHA256' >&2; exit 2; }
scripts=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
test ! -e "$2"
mkdir -p "$2"
unzip -q "$1" -d "$2"
cd "$2"
export PATH=/usr/bin:/bin:/usr/sbin:/sbin
sh "$scripts/manifest.sh" "$PWD" validate
printf 'Clean PATH: %s\n' "$PATH"
test -z "$(find . -type l -print)"
test "$(find . -type f | wc -l | tr -d ' ')" -eq "$(($(wc -l < SHA256SUMS) + 1))"
test "$(cut -c 67- SHA256SUMS | LC_ALL=C sort -u | wc -l | tr -d ' ')" -eq "$(wc -l < SHA256SUMS | tr -d ' ')"
! grep -Eq '  (SHA256SUMS|/|.*\.\./)' SHA256SUMS
shasum -a 256 -c SHA256SUMS
sh "$scripts/source-check.sh" source-original.zip "$3" source
for target in macos-arm64 macos-x64; do
  test "$(stat -f %Lp "bin/$target/ternfold-lexer")" = 755
done
test -f bin/windows-x64/ternfold-lexer.exe
test "$(stat -f %Lp Run-Mac.command)" = 755
case "$(uname -m)" in
  arm64) target=macos-arm64; arch=arm64 ;;
  x86_64) target=macos-x64; arch=x86_64 ;;
  *) exit 2 ;;
esac
file "bin/$target/ternfold-lexer" | grep "Mach-O 64-bit executable $arch"
otool -L "bin/$target/ternfold-lexer" | awk 'NR > 1 { if ($1 !~ /^\/usr\/lib\// && $1 !~ /^\/System\/Library\//) exit 1; n++ } END { if (!n) exit 1 }'
otool -l "bin/$target/ternfold-lexer" | awk '$1 == "minos" { if ($2 !~ /^15\.0(\.0)?$/) exit 1; seen=1 } END { if (!seen) exit 1 }'
printf '\n' | ./Run-Mac.command
cmp 'reports/Symbol Table.txt' 'source/tests/fixtures/invalid/complete.classroom.txt'
status=0
./Run-Mac.command source/examples/lexical/invalid.tfd || status=$?
test "$status" = 1
cmp 'reports/Symbol Table.txt' 'source/tests/fixtures/lexer/Invalid Classroom Symbol Table.txt'
before=$(shasum -a 256 'reports/Symbol Table.txt')
status=0
./Run-Mac.command missing-do-not-open.txt 2>extension.txt || status=$?
test "$status" = 1
grep 'extension must be exactly .tfd' extension.txt
test "$(shasum -a 256 'reports/Symbol Table.txt')" = "$before"
status=0
"./bin/$target/ternfold-lexer" 2>usage.txt || status=$?
test "$status" = 2
cp source/examples/lexical/complete.tfd 'path with spaces.tfd'
./Run-Mac.command "$PWD/path with spaces.tfd"
cmp 'reports/Symbol Table.txt' 'source/tests/fixtures/invalid/complete.classroom.txt'
sh "$scripts/verify-cases.sh" "$PWD" "$target"
echo 'PASS: fresh combined ZIP, all hashes/binaries/executable bits, exact source, native launcher valid/invalid/extension/usage/spaces, clean PATH.'
