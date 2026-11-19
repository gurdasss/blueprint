#!/usr/bin/env bash
# Gate for the standalone exe: run a fixed set of bp commands and record what they did.
#
#     gate.sh <bp command> <inputs dir> <out dir>
#
# The bp under test must include `bp mcp` (the exe always does; a pip install needs [mcp]).
#
# <inputs dir> holds guidelines/, sales-overview.yaml and report/ (a copy of
# fixtures/02-card-and-chart). It is copied, never changed. Each command's stdout, stderr
# and exit code land in <out dir>; the report the commands wrote is <out dir>/work/report.
#
# Run it twice -- once with the frozen exe on a PATH with no Python, once with the
# pip-installed `bp` -- then verify_gate.py compares the two. Uses only bash builtins, cp,
# mkdir, cat and sleep, so it runs on Git Bash with no Python. A non-zero exit from bp is recorded, not fatal:
# `check` exits 1 on the fixture's own hand-built page, and the reference run must agree.
set -u
bp="$1"; inputs="$2"; out="$3"
here="${0%/*}"; [[ "$here" == "$0" ]] && here=.
sessions="$(cd "$here" && pwd)"   # the recorded MCP sessions sit beside this script

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
run init     init starter
run describe-model describe --report report --guidelines guidelines/example.yaml --json --section model

# `bp mcp`: replay each recorded client session (record_mcp_sessions.py: the SDK client's own
# bytes, in both connection modes) and keep stdin open until every request has its reply,
# as a real client does -- the server stops reading at end of input and drops calls still
# running. Bash builtins plus cat and sleep only; gives up after 60 s.
for session in "$sessions"/mcp-session-*.jsonl; do
  mode="${session##*/mcp-session-}"; mode="${mode%.jsonl}"
  reply="../mcp-$mode.out"
  : >"$reply"
  want=0
  while IFS= read -r line; do [[ "$line" == *'"id":'* ]] && want=$((want + 1)); done <"$session"
  {
    cat "$session"
    for ((i = 0; i < 600; i++)); do
      mapfile -t got <"$reply"
      (( ${#got[@]} >= want )) && break
      sleep 0.1
    done
  } | "$bp" mcp >"$reply" 2>"../mcp-$mode.err"
  echo "$?" >"../mcp-$mode.code"
done
exit 0
