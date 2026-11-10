#!/usr/bin/env bash
# Run `bp check --github` over each report in $REPORTS (one per line) for the composite action in
# action.yml. Annotations go to the log, the text reports to $GITHUB_STEP_SUMMARY, and the step
# exits with the worst exit code (2 unreadable > 1 failing findings > 0).
#
#   REPORTS=$'a/Sales.Report\nb/Ops.pbip' GUIDELINES=guidelines/example.yaml STRICT=false \
#     bash scripts/ci_check.sh
#
# BP defaults to the action's venv; set it to run another bp (tests use the dev install).
set -uo pipefail

BP="${BP:-${RUNNER_TEMP:-/tmp}/blueprint-venv/bin/bp}"
args=(--github)
[ -n "${GUIDELINES:-}" ] && args+=(--guidelines "$GUIDELINES")
case "${STRICT:-false}" in
  true) args+=(--strict) ;;
  false|"") ;;
  *) echo "::error title=bp check::strict must be true or false, not '$STRICT'"; exit 2 ;;
esac

worst=0
checked=0
while IFS= read -r report || [ -n "$report" ]; do
  report="${report#"${report%%[![:space:]]*}"}"   # trim leading and trailing whitespace
  report="${report%"${report##*[![:space:]]}"}"
  [ -z "$report" ] && continue
  checked=$((checked + 1))
  out=$("$BP" check --report "$report" "${args[@]}" 2>&1)
  code=$?
  echo "::group::bp check $report (exit $code)"
  printf '%s\n' "$out"
  echo "::endgroup::"
  if [ -n "${GITHUB_STEP_SUMMARY:-}" ]; then
    {
      printf '### `%s`: exit %s\n\n```\n' "$report" "$code"
      printf '%s\n' "$out" | grep -v '^::'
      printf '```\n\n'
    } >> "$GITHUB_STEP_SUMMARY"
  fi
  if [ "$code" -ge 2 ]; then
    echo "::error title=bp check::$report could not be checked (exit $code): $(printf '%s' "$out" | grep -v '^::' | tail -n 1)"
  fi
  [ "$code" -gt "$worst" ] && worst=$code
done <<< "${REPORTS:-}"

if [ "$checked" -eq 0 ]; then
  echo "::error title=bp check::no reports given (set the 'reports' input)"
  worst=2
fi
[ -n "${GITHUB_OUTPUT:-}" ] && echo "exit-code=$worst" >> "$GITHUB_OUTPUT"
exit "$worst"
