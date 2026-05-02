"""CLI entry point for ``audit-ontology`` — scaffold; full impl in Phase 1+.

Registered as a console script in ``pyproject.toml``::

    [project.scripts]
    audit-ontology = "audit_ontology.cli:main"

Today this is a fail-loud stub. When implemented (Day 3+ / Phase 1),
``main`` will orchestrate:

- load Ontology snapshot from ``tooling/sicm-ontology.json``
- resolve every implementation/verification/proof ref against the
  working tree (path + symbol; proof refs against the Lean project
  per DECISIONS.md D005)
- run the consistency module's status-vs-refs rules
- run the freshness module's test-results-DAG check (schema sketched
  separately per the engine-head bolt-tightening pass)
- emit a structured report; exit nonzero on any unresolved or stale
  finding.

Exit-code discipline of the stub: ``main`` exits **non-zero** with
a clear stderr message rather than silently returning 0. This
prevents the well-known footgun where a future pre-push wiring
that calls ``audit-ontology`` and trusts ``0 → audit passed``
gets a silent green from the stub. To opt into "stub-OK" behavior
(e.g., a smoke check that the entry point is invokable), set
``AUDIT_ONTOLOGY_ALLOW_STUB=1`` in the environment for that
single invocation.
"""

from __future__ import annotations

import os
import sys


def main() -> int:
    """Stub entry point. Fails loudly unless explicitly bypassed.

    See module docstring for the eventual orchestration scope and
    the bypass mechanism.
    """
    print(
        "audit-ontology: scaffold; full implementation in Phase 1+.",
        file=sys.stderr,
    )
    print(
        "See DECISIONS.md D005 for the verification-track scope; "
        "package docstring for the audit work plan.",
        file=sys.stderr,
    )
    if os.environ.get("AUDIT_ONTOLOGY_ALLOW_STUB") == "1":
        print(
            "audit-ontology: AUDIT_ONTOLOGY_ALLOW_STUB=1 honored; "
            "exiting 0 without auditing anything.",
            file=sys.stderr,
        )
        return 0
    print(
        "audit-ontology: refusing to silently pass while "
        "unimplemented. Set AUDIT_ONTOLOGY_ALLOW_STUB=1 only for "
        "smoke-checks; do NOT wire this into a pre-push gate "
        "until the real implementation lands.",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
