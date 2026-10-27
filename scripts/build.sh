#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
TF_CC=${CC:-cc}
export TF_CC
mkdir -p build
"$TF_CC" -std=c17 -Wall -Wextra -Werror -pedantic -Wconversion -Wshadow tools/tfdev.c -o build/tfdev
exec ./build/tfdev "${1:-check}"
