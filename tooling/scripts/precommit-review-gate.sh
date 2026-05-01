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

# Permissive match: any command containing "git commit" anywhere
# (catches `cd ... && git commit ...`, `env X=Y git commit ...`, etc.).
# False-positives on `echo "git commit"` are tolerated — the gate
# refusal is loud enough that the user notices.
case "$command" in
    *"git commit"*) ;;
    *) exit 0 ;;
esac

exec "$(dirname "$0")/check-review-decisions.sh"
