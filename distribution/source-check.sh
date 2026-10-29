#!/bin/sh
set -eu
test "$#" -ge 2 && test "$#" -le 3 || { echo 'Usage: source-check.sh SOURCE.zip SHA256 [SOURCE_DIRECTORY]' >&2; exit 2; }
scripts=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
pin=$2
test "${#pin}" = 64
case "$pin" in *[!a-fA-F0-9]*) exit 2 ;; esac
pin=$(printf '%s' "$pin" | tr A-F a-f)
test "$(shasum -a 256 "$1" | cut -d ' ' -f 1)" = "$pin"
check_tmp=$(mktemp -d)
trap 'rm -rf "$check_tmp"' EXIT HUP INT TERM
tr -d '\r' < "$scripts/../SOURCE_FILES.txt" > "$check_tmp/expected"
# Compare before extraction: reject traversal, directories, duplicates and private paths.
unzip -Z1 "$1" | LC_ALL=C sort > "$check_tmp/entries"
LC_ALL=C sort "$check_tmp/expected" > "$check_tmp/sorted"
cmp "$check_tmp/entries" "$check_tmp/sorted"
test -z "$(zipinfo -l "$1" | awk '$1 ~ /^l/ {print}')"
unzip -p "$1" SOURCE_FILES.txt | tr -d '\r' > "$check_tmp/embedded"
cmp "$check_tmp/expected" "$check_tmp/embedded"
unzip -q "$1" -d "$check_tmp/source"
if [ "$#" = 3 ]; then
  test -z "$(find "$3" -type l -print)"
  (cd "$3" && find . -type f | sed 's|^\./||' | LC_ALL=C sort) > "$check_tmp/files"
  cmp "$check_tmp/files" "$check_tmp/sorted"
  diff -r "$3" "$check_tmp/source"
fi
printf 'PASS: pinned source ZIP and %s allowlisted files.\n' "$(wc -l < "$check_tmp/expected" | tr -d ' ')"
