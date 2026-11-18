#!/usr/bin/env bash
# Gate for the standalone exe: run a fixed set of bp commands and record what they did.
#
#     gate.sh <bp command> <inputs dir> <out dir>
#
# <inputs dir> holds guidelines/, sales-overview.yaml and report/ (a copy of
# fixtures/02-card-and-chart). It is copied, never changed. Each command's stdout, stderr
# and exit code land in <out dir>; the report the commands wrote is <out dir>/work/report.
#
# Run it twice -- once with the frozen exe on a PATH with no Python, once with the
# pip-installed `bp` -- then verify_gate.py compares the two. Uses only bash builtins, cp and
# mkdir, so it runs on Git Bash with no Python. A non-zero exit from bp is recorded, not fatal:
# `check` exits 1 on the fixture's own hand-built page, and the reference run must agree.
set -u
bp="$1"; inputs="$2"; out="$3"

mkdir -p "$out" || exit 2
cp -r "$inputs" "$out/work" || exit 2
cd "$out/work" || exit 2

export SOURCE_DATE_EPOCH=0   # the manifest's generated_at, so the two runs can match byte for byte

run() {
  local name="$1"; shift
  "$bp" "$@" >"../$name.out" 2>"../$name.err"
  echo "$?" >"../$name.code"
}

run version  --version
run describe describe --guidelines guidelines/example.yaml --json
run describe-report describe --report report --guidelines guidelines/example.yaml --json
run apply    apply sales-overview.yaml --report report --guidelines guidelines/example.yaml
run reapply  apply sales-overview.yaml --report report --guidelines guidelines/example.yaml
run check    check --report report --guidelines guidelines/example.yaml
run inspect  inspect --report report
exit 0
