#!/bin/sh
set -eu
test "$#" = 2
root=$(CDPATH= cd -- "$1" && pwd)
binary=$root/bin/$2/ternfold-lexer
mkdir "$root/oracle-output"
cd "$root/source"
for case_name in complete vocabulary invalid-comprehensive trace; do
  expected=1
  case "$case_name" in complete|vocabulary) expected=0 ;; esac
  for mode in classroom lossless trace; do
    set -- "examples/lexical/$case_name.tfd" --output-dir "$root/oracle-output"
    fixture_mode=classroom
    if [ "$mode" = lossless ]; then fixture_mode=lossless; else set -- "$@" --classroom; fi
    if [ "$mode" = trace ]; then set -- "$@" --trace-dfa; fi
    status=0
    "$binary" "$@" > "$root/oracle-output/stdout" 2> "$root/oracle-output/stderr" || status=$?
    test "$status" = "$expected"
    cmp "$root/oracle-output/Symbol Table.txt" "tests/fixtures/invalid/$case_name.$fixture_mode.txt"
    if [ "$mode" = trace ]; then
      grep -Eq '^DFA [a-z]+ offset=[0-9]+ end=[0-9]+ state=' "$root/oracle-output/stderr"
      grep -q ' FINAL \[' "$root/oracle-output/stderr"
      sed '/^DFA /d' "$root/oracle-output/stderr" > "$root/oracle-output/diagnostics"
    else cp "$root/oracle-output/stderr" "$root/oracle-output/diagnostics"; fi
    cmp "$root/oracle-output/diagnostics" "tests/fixtures/invalid/$case_name.diagnostics.txt"
  done
done
echo 'PASS: 12 packaged-binary cases, exact reports/diagnostics/spans and actual trace transitions.'
