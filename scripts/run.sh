#!/bin/sh
# neverbor launcher: run a script with the first working Python 3.8+.
# Windows often has `python` or `py` but no real `python3` (only a Store stub),
# so try all three. No Python means "do nothing" (exit 0), never a broken session.
case "$0" in */*) dir=${0%/*} ;; *) dir=. ;; esac
script=$1
shift
for p in python3 python py; do
  if "$p" -c 'import sys; sys.exit(sys.version_info < (3, 8))' >/dev/null 2>&1; then
    exec "$p" "$dir/$script" "$@"
  fi
done
echo "neverbor: Python 3.8+ not found (tried python3, python, py)" >&2
exit 0
