#!/bin/sh
set -eu
test "$#" = 2
printf '%s\n' "$1" | LC_ALL=C grep -Eq '^https://github\.com/afkDen/PPL_Group1_LexicalAnalyzer/releases/download/[A-Za-z0-9][A-Za-z0-9._-]*/[A-Za-z0-9][A-Za-z0-9._-]*\.zip$'
test "${#2}" = 64
case "$2" in *[!a-fA-F0-9]*) exit 2 ;; esac
