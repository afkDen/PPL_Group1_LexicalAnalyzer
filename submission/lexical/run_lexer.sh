#!/bin/sh
set -eu
cd "$(dirname "$0")"
if [ "$#" -eq 0 ]; then
    exec python3 analyzer.py examples/complete.tfd
fi
exec python3 analyzer.py "$@"
