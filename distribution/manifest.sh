#!/bin/sh
set -eu
cd "$1"
test ! -e SHA256SUMS
# Use an external temporary file so neither it nor SHA256SUMS hashes itself.
manifest_tmp=$(mktemp)
trap 'rm -f "$manifest_tmp"' EXIT HUP INT TERM
find . -type f | LC_ALL=C sort | while IFS= read -r path; do
  digest=$(shasum -a 256 "$path" | cut -d ' ' -f 1)
  printf '%s  %s\n' "$digest" "${path#./}"
done > "$manifest_tmp"
cp "$manifest_tmp" SHA256SUMS
