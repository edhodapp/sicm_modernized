#!/usr/bin/env bash
# Install the SICM-Modernized git pre-commit hook into .git/hooks/.
#
# Composes:
#   1. ~/tools/code-review/pre-commit-hook.sh (quality gates +
#      Gemini review; shared across Ed's projects)
#   2. tooling/scripts/check-review-decisions.sh (SICM-specific
#      no-unilateral-deferral discipline gate)
#
# The shared script flows code into the SICM project per the global
# "principles transfer; processes do not" rule — we use it as a
# *tool* (clean interface), not by copying its content.

set -euo pipefail

REPO_ROOT="$(git rev-parse --show-toplevel)"
HOOK_PATH="$REPO_ROOT/.git/hooks/pre-commit"
SHARED_HOOK="$HOME/tools/code-review/pre-commit-hook.sh"
LOCAL_GATE="$REPO_ROOT/tooling/scripts/check-review-decisions.sh"

if [ ! -x "$SHARED_HOOK" ]; then
    echo "ERROR: shared hook missing or not executable: $SHARED_HOOK" >&2
    exit 1
fi
if [ ! -x "$LOCAL_GATE" ]; then
    echo "ERROR: local gate missing or not executable: $LOCAL_GATE" >&2
    exit 1
fi

cat > "$HOOK_PATH" <<'HOOK'
#!/usr/bin/env bash
# SICM-Modernized git pre-commit hook (managed by
# tooling/scripts/install-pre-commit-hook.sh — re-run after edits).
#
# Order: shared quality gates + Gemini review first (block on
# quality failures; advisory on Gemini), then the SICM-specific
# review-decisions discipline gate (blocks on undispositioned
# findings).
set -euo pipefail
"$HOME/tools/code-review/pre-commit-hook.sh"
"$(git rev-parse --show-toplevel)/tooling/scripts/check-review-decisions.sh"
HOOK
chmod +x "$HOOK_PATH"

echo "Installed: $HOOK_PATH"
echo "Composes:"
echo "  1. $SHARED_HOOK"
echo "  2. $LOCAL_GATE"
