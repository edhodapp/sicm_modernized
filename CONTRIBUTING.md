# Contributing to sicm_modernized

## No external contributions accepted

`sicm_modernized` is a single-author project. Pull requests,
patches, and similar upstream submissions are **not accepted** at
this time. The rationale (consolidated copyright ownership for
future licensing flexibility, including dual-licensing for
commercial clients) is recorded in [`COPYRIGHT`](COPYRIGHT).

If your intended use of `sicm_modernized` is compatible with the
AGPL, the [`LICENSE`](LICENSE) already grants you everything you
need. Deployments that cannot accept AGPL §13's network-copyleft
obligations should contact Ed Hodapp <ed@hodapp.com> to discuss a
commercial license or consulting engagement.

---

## Maintainer notes

The remainder of this document is for the project maintainer.
External readers can stop here.

### Local environment bypasses

These environment variables exist for local-only, maintainer-side
development. They must not appear in CI scripts, shared automation,
or committed configuration.

- `AUDIT_ONTOLOGY_ALLOW_STUB=1` — by default the `audit-ontology`
  console script exits non-zero while the package is still in
  stub form (no real audit logic); this variable inverts that for
  local smoke checks against the Pydantic schema. Wiring the
  script into a pre-push gate waits until the real implementation
  lands.

### Pointers

Project-local engineering discipline (review pipeline, disposition
log, immutability rules for `DECISIONS.md` / `REQUIREMENTS.md`) is
recorded in [`CLAUDE.md`](CLAUDE.md) and the project memory
directory referenced therein.
