#!/usr/bin/env bash
# Claude Code PreToolUse hook wrapper.
#
# Reads the PreToolUse JSON envelope from stdin, extracts the
# `tool_input.command` field, and — only when the command is a
# `git commit` invocation — delegates to check-review-decisions.sh
# for the disposition gate. Any other Bash command short-circuits
# to exit 0, leaving the tool call alone.
#
# Hooked via .claude/settings.local.json under PreToolUse / Bash.

set -euo pipefail

input="$(cat)"

# Extract the command via python (json on stdin → tool_input.command);
# python3 is universal, jq is not. One-liner so there's no
# backslash-continuation ambiguity inside the single-quoted source.
command="$(printf '%s' "$input" | python3 -c 'import json,sys; print(json.loads(sys.stdin.read()).get("tool_input",{}).get("command",""))')"

# Word-boundary match: fire only when "git commit" is the actual
# subcommand — at the start of the command, or immediately after a
# recognized shell separator (&&, ;, ||). Followed by whitespace or
# end-of-string so `git commit-tree` / `git commit-graph` plumbing
# does not match. Filters quoted-string false-positives like
# `echo "git commit"` (the leading `"` doesn't match any of the
# allowed prefixes) and argument false-positives like
# `grep "git commit" file`.
RE='(^|&&[[:space:]]+|;[[:space:]]+|\|\|[[:space:]]+)git[[:space:]]+commit([[:space:]]|$)'
if [[ ! "$command" =~ $RE ]]; then
    exit 0
fi

exec "$(dirname "$0")/check-review-decisions.sh"
