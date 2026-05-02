"""Audit tool for the SICM ontology — scaffold; full impl in Phase 1+.

This package will eventually:

- Cross-check ontology references against the working tree:
  every ``implementation_refs`` resolves to a real file/symbol;
  every ``verification_refs`` names a test that exists; every
  ``proof_refs`` (per DECISIONS.md D005) names a Lean theorem
  that compiles.
- Discharge consistency rules that Pydantic-time validation
  cannot reach (semantic ref resolution, ontology-vs-DECISIONS
  ID consistency, ontology-vs-REQUIREMENTS coverage).
- Run the test-results DAG freshness gate at pre-push (sketched
  per the iomoments pattern; schema lands separately as part of
  the engine-head bolt-tightening pass).

Today this package is a stub. Its presence makes
``pyproject.toml``'s coverage-source reference resolvable (no more
"Module audit_ontology was never imported" warning), gives the
``audit-ontology`` console script a real entry point, and gives the
audit work a real home when Phase 1 begins.

See:
- ``DECISIONS.md`` D002 — methodology lineage (re-derived from
  iomoments + fireasmserver, not lifted whole)
- ``DECISIONS.md`` D005 — Lean as Phase-2+ formal-verification
  track; introduces ``proof_refs`` as a third ref-kind alongside
  implementation/verification refs
"""
