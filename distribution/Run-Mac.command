#!/bin/sh
set -eu
cd "$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
case "$(uname -m)" in
  arm64) target=macos-arm64 ;;
  x86_64) target=macos-x64 ;;
  *) echo 'Supported Macs: Apple Silicon or Intel.' >&2; exit 2 ;;
esac
mkdir -p reports
status=0
if [ "$#" -eq 0 ]; then
  "./bin/$target/ternfold-lexer" source/examples/lexical/complete.tfd --classroom --output-dir reports || status=$?
  printf 'Report: %s/reports/Symbol Table.txt\nPress Return to close.\n' "$PWD"
  read -r unused || :
else
  "./bin/$target/ternfold-lexer" "$@" --classroom --output-dir reports || status=$?
fi
exit "$status"
