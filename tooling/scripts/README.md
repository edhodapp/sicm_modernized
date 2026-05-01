# tooling/scripts — Day 2a.5 review-decisions automation

## What this is

Mechanizes Ed's no-unilateral-deferral rule (project CLAUDE.md
"Code-review discipline"). The gate refuses every commit until
each code-review finding logged in `tooling/.review-decisions.md`
carries an explicit Ed-approved disposition (`**fix**`,
`**defer**`, or `**reject**`) and a `YYYY-MM-DD` approval date.

Built 2026-04-30 in response to the 2026-04-26 incident where
Claude unilaterally triaged seven LOW review findings without
Ed's approval. The hook structurally prevents that failure mode
from recurring.

## Files

- **`tooling/.review-decisions.md`** — committed, append-only log.
  Per-session blocks with `## YYYY-MM-DD …` headers; per-finding
  lines as `- ` bullets carrying disposition + date. New review
  sessions append; old entries never edit. Mirrors DECISIONS.md's
  immutability convention.
- **`tooling/scripts/check-review-decisions.sh`** — the gate. Walks
  `.review-decisions.md`, classifies each finding-line as `OK`,
  `UNDISPOSITIONED`, or `MALFORMED`. Exits non-zero if any
  finding is undispositioned or malformed. Prints a clear blocked-
  commit explanation on failure.
- **`tooling/scripts/precommit-review-gate.sh`** — Claude Code
  PreToolUse wrapper. Reads the JSON tool envelope from stdin;
  delegates to `check-review-decisions.sh` only when the Bash
  command contains `git commit`. Other Bash commands pass through
  unchanged.
- **`tooling/scripts/install-pre-commit-hook.sh`** — installer for
  the git-side hook. Composes the shared
  `~/tools/code-review/pre-commit-hook.sh` (quality gates + Gemini
  review) with this project's local gate. Re-run after editing
  the hook composition.
- **`.claude/settings.local.json`** — Claude Code settings hooking
  `precommit-review-gate.sh` into the PreToolUse / Bash matcher.

## Two-layer enforcement

The gate runs at two layers, both calling
`check-review-decisions.sh`:

1. **Claude Code PreToolUse hook** — fires before Claude's
   `git commit` invocation. Refuses the tool call entirely;
   Claude never reaches the git layer.
2. **Git pre-commit hook** — fires on any `git commit` (Claude
   or Ed's terminal). Catches commits that bypass Claude entirely.

`git commit --no-verify` skips layer 2 (per git's design); per
global CLAUDE.md, Claude must not pass `--no-verify` without Ed's
explicit authorization. The bypass env var (below) is the
sanctioned escape hatch for both layers.

## Disposition format

Every `- ` bullet under a `## YYYY-MM-DD …` session header must
contain:

1. exactly one disposition keyword: `**fix**`, `**defer**`, or
   `**reject**`
2. a `YYYY-MM-DD` approval date (typically the date Ed approved
   the disposition)

Example entries:

```markdown
- F1 (HIGH) DecisionRef self-supersession: **fix** 2026-04-29
- F8 (LOW) per-helper name-set rebuild: **defer** 2026-04-29 — premature optimization
- F9 (LOW) _iter_node_kinds type erasure: **reject** 2026-04-29 — Pydantic+tuple covariance idiom
```

The post-keyword text after the date is free-form prose (rationale,
short explanation). Not parsed.

## Bypass

```bash
SICM_BYPASS_REVIEW_DISPOSITIONS=1 git commit ...
```

Skips the gate for one invocation. Logged loudly to stderr — no
silent skip path. Use with explicit conscious intent (e.g.,
the very first commit that introduces the file itself; recovery
from a malformed log; an emergency hotfix where review will catch
up after).

## Override file location

```bash
SICM_REVIEW_DECISIONS_FILE=/some/other/path.md tooling/scripts/check-review-decisions.sh
```

Useful for tests against synthetic inputs.

## What this does NOT do

- It does NOT verify that Claude actually ran a review. The file
  only knows about findings Claude logged. The discipline rule
  ("surface every finding") remains Claude's responsibility, with
  Ed's spot-checks as the audit.
- It does NOT verify that a disposition is reasonable. Ed's
  judgment on each fix/defer/reject is out of scope.
- It does NOT block commits that change non-reviewed code. Per the
  design discussion (2026-04-30), the gate fires every commit,
  full stop — "I'm just fixing a typo" is the slope toward old
  habits.

## Methodology

Per the global "principles transfer; processes do not" rule
(global CLAUDE.md), the discipline-via-file pattern is re-derived
from the spirit of iomoments / fireasmserver code-review hygiene,
not copied. The shared *tool* used here
(`~/tools/code-review/pre-commit-hook.sh`) IS reused per the
counter-example clause — it's a tool, not a process; the way SICM
composes it is local.
