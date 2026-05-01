#!/usr/bin/env bash
# Refuse the commit if any line in tooling/.review-decisions.md
# under a `## YYYY-MM-DD ...` session header lacks an explicit
# disposition keyword (**fix** / **defer** / **reject**) and a
# YYYY-MM-DD approval date.
#
# This is the Day 2a.5 mechanization of Ed's no-unilateral-deferral
# rule (project CLAUDE.md "Code-review discipline"): every code-
# review finding must be explicitly dispositioned by Ed before any
# commit proceeds.
#
# Bypass: SICM_BYPASS_REVIEW_DISPOSITIONS=1 skips the gate. The
# bypass is logged on use; no silent skip.
#
# Exit codes:
#   0 — all logged findings dispositioned (or file empty / bypassed)
#   1 — at least one finding undispositioned or malformed; commit blocked
#   2 — review-decisions file missing (must be present even if empty)

set -euo pipefail

REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
DECISIONS_FILE="${SICM_REVIEW_DECISIONS_FILE:-$REPO_ROOT/tooling/.review-decisions.md}"

if [ "${SICM_BYPASS_REVIEW_DISPOSITIONS:-}" = "1" ]; then
    echo "review-decisions gate: BYPASSED via SICM_BYPASS_REVIEW_DISPOSITIONS=1" >&2
    exit 0
fi

if [ ! -f "$DECISIONS_FILE" ]; then
    echo "review-decisions gate: ERROR: file not found: $DECISIONS_FILE" >&2
    echo "Create it (even empty with the standard preamble) before committing." >&2
    exit 2
fi

undispositioned=0
malformed=0
total=0
in_session=0
in_codefence=0
problems=()

# Parse the markdown line-by-line. Disposition checks apply only to
# `- ` bullets that appear AFTER the first `## YYYY-MM-DD …` header
# (so the preamble's prose is untouched) and OUTSIDE fenced code
# blocks (so example bullets in documentation aren't enforced as
# real findings).
#
# A valid disposition entry has the keyword IMMEDIATELY followed by
# whitespace and a YYYY-MM-DD date, so prose mentions of the
# keyword (e.g. "do not **defer** review findings") cannot
# accidentally satisfy the gate.
while IFS= read -r line; do
    if [[ "$line" == '```'* ]]; then
        in_codefence=$((1 - in_codefence))
        continue
    fi
    if (( in_codefence == 1 )); then
        continue
    fi
    if [[ "$line" =~ ^##[[:space:]]+[0-9]{4}-[0-9]{2}-[0-9]{2} ]]; then
        in_session=1
        continue
    fi
    if (( in_session == 0 )); then
        continue
    fi
    if [[ "$line" =~ ^-[[:space:]] ]]; then
        total=$((total + 1))
        if [[ "$line" =~ \*\*(fix|defer|reject)\*\*[[:space:]]+[0-9]{4}-[0-9]{2}-[0-9]{2} ]]; then
            continue
        fi
        if [[ "$line" =~ \*\*(fix|defer|reject)\*\* ]]; then
            problems+=("MALFORMED (keyword not followed by date): $line")
            malformed=$((malformed + 1))
        else
            problems+=("UNDISPOSITIONED:    $line")
            undispositioned=$((undispositioned + 1))
        fi
    fi
done < "$DECISIONS_FILE"

if (( undispositioned > 0 || malformed > 0 )); then
    echo "" >&2
    echo "review-decisions gate: COMMIT BLOCKED" >&2
    echo "  undispositioned findings: $undispositioned" >&2
    echo "  malformed entries:        $malformed" >&2
    echo "  total findings checked:   $total" >&2
    echo "" >&2
    for p in "${problems[@]}"; do
        echo "  $p" >&2
    done
    echo "" >&2
    echo "Every '- ' bullet under a '## YYYY-MM-DD ...' session" >&2
    echo "header in $DECISIONS_FILE must carry:" >&2
    echo "  - one disposition keyword: **fix**, **defer**, or **reject**" >&2
    echo "  - a YYYY-MM-DD approval date" >&2
    echo "" >&2
    echo "If you genuinely need to bypass this gate (file repair, log" >&2
    echo "refactor), set SICM_BYPASS_REVIEW_DISPOSITIONS=1 for the" >&2
    echo "single git commit invocation." >&2
    exit 1
fi

echo "review-decisions gate: OK ($total findings, all dispositioned)"
exit 0
