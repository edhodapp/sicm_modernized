"""Test-results DAG schema — sketch; producers and audit land later.

This module defines the data shape for a content-hashed, append-only
log of test outcomes that the audit gate will consult to answer:
*for each tested requirement, does a recent passing result exist
under every required environment, captured at-or-after all the
implementation files were last edited?*

The pattern is re-derived from iomoments per the global "principles
transfer; processes do not" rule. The mathematical core (record
what passed, when, and under which environment; gate on freshness
against code edits at pre-push time) transfers; iomoments' specific
producers (pytest plugin, vmtest matrix runner, AWS tracer, etc.),
its multi-environment matrix, and its make-target orchestration are
not lifted whole — sicm has its own runtime mix per D003 (Racket CS
+ Python/JAX + CUDA C, plus Lean per D005 once Phase-2 work begins).

**Architectural rule.** This module lives in `audit_ontology` and
imports from `sicm_ontology` (e.g., the `RefString` and `ShortName`
constrained-string types). The dependency direction is one-way:
the audit tool consumes ontology types; ontology code must NOT
import from `audit_ontology`. Cycles introduced later would
indicate a layering bug.

Today this module is types-only. No producer fires. No audit
consumes. The schema sits here so:
  - Pydantic-validated data shapes are pinned before any code
    starts producing records (so the first producer's output is
    immediately schema-valid).
  - The four failure modes (below) are documented as part of the
    schema, not lost in scattered audit-tool prose.
  - When the producer side lands (Phase 1, alongside the first
    tests of real project logic), it has a clean target.

The four audit failure modes the gate will eventually distinguish:

  STALE_RESULT
    A passing result exists for (verification_ref, environment),
    but its `captured_git_sha` is older than the last edit of at
    least one `implementation_refs` entry pointing at the same
    requirement. The test passed, but not against the current code.
    Fix: re-run the test under the current commit.

  RUNNER_FORGOT
    No result at all exists for (verification_ref, environment) at
    or after the last edit. The test exists, the environment is
    required, but nothing ran. Fix: invoke the producer (e.g.,
    `pytest`) before pushing.

  ENV_NEVER_EXERCISED
    A required environment for this verification_ref has never
    produced any result, in any commit. The producer for that
    environment may not exist yet. Fix: stand up the producer or
    drop the environment from the required-set with rationale.

  UNTRACKED_FILE
    An `implementation_refs` entry was edited recently but no
    `verification_refs` exercises it under any environment. The
    test discipline gap surfaces here. Fix: add the verification
    case (and the producer that runs it) before pushing.

Open design questions deferred to producer-implementation time:

  - The on-disk JSON format. iomoments uses a single 5+ MB blob;
    sicm may end up partitioning by environment or by phase, but
    that's a Phase-1 decision once real volume materializes.
  - Content-hash deduplication: should two byte-identical
    TestResult instances captured one second apart deduplicate? In
    iomoments yes, by content hash. Sicm leans the same direction
    pending a concrete reason to diverge.
  - The schema for richer measurements (units, kinds, string-
    valued metadata). The current `scalar_measurements` field
    holds simple `(name, float)` pairs only; a future `measurements`
    field name is reserved for the richer Measurement submodel.
  - The exact match rule for environment subsumption (e.g., a
    result captured on jax-cuda12 — does it satisfy a requirement
    asking for jax-cpu? Default answer: no, environments must
    match exactly; documented as policy when the audit lands).
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Literal

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
)

from sicm_ontology.types import RefString, ShortName

# --- Outcome and environment vocabularies --------------------------------

# pytest's outcome vocabulary plus 'error' (collection / setup
# failure distinct from a test that ran and asserted false). Future
# producers (Racket, Lean) will map their native outcomes onto this
# union; non-pytest mappings are documented at the producer site.
TestOutcome = Literal["pass", "fail", "xfail", "xpass", "skip", "error"]

# Engine: which test runner produced the result.
TestEngine = Literal["pytest", "racket", "lean", "cuda-c"]

# Hardware: gross-grain hardware class. The Environment field is
# `TestHardware | None`; None means "not relevant" (e.g., a pure-
# symbolic test where neither CPU vs GPU nor any accelerator
# distinction is meaningful).
TestHardware = Literal["cpu", "gpu"]

# Backend: which numerical / symbolic substrate ran the test. Same
# axis as `language_targets` on NumericalMethod nodes in the
# ontology, but extended with "lean" for proof-environment
# verification once Phase-2 work begins. Backend names are
# version-free (`jax-cuda` not `jax-cuda12`); the specific CUDA /
# JAX / mathlib version is recorded in `Environment.flags`
# (e.g., a flag like `cuda:12.4` or `mathlib:rev-abc123`).
TestBackend = Literal[
    "numpy",
    "jax-cpu",
    "jax-cuda",
    "racket",
    "cuda-c",
    "lean",
]

# Platform: gross-grain OS / runtime substrate. Linux only today;
# the literal is open-extended at need.
TestPlatform = Literal["linux"]


# --- Pydantic models -----------------------------------------------------


class Environment(BaseModel):
    """Pinned execution context for a TestResult.

    Two environments compare equal iff every field matches exactly
    (no structural-subtyping shortcuts). The audit's required-set
    for a given verification_ref names environments by equality;
    asking for jax-cpu does not accept a jax-cuda12 result.

    `flags` is a free-form labels tuple (e.g., "compiler:nvcc-12.4",
    "rng-seed-fixed", "perf-mode"). The validator sorts AND
    deduplicates on construction so two equivalent environments
    with the same flag set hash identically regardless of
    producer-side ordering or accidental duplication.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    engine: TestEngine
    hardware: TestHardware | None = None
    backend: TestBackend | None = None
    platform: TestPlatform = "linux"
    flags: tuple[str, ...] = Field(default_factory=tuple)

    @field_validator("flags")
    @classmethod
    def _sort_and_dedupe_flags(
        cls, value: tuple[str, ...],
    ) -> tuple[str, ...]:
        """Normalize: sort + dedupe so equality is set-semantics."""
        return tuple(sorted(set(value)))


class TestResult(BaseModel):
    """One observed outcome of one verification_ref under one Environment.

    `verification_ref` follows REQUIREMENTS.md's `path::test_function`
    convention for pytest tests; for non-pytest engines (Racket,
    Lean, raw CUDA C) the producer documents its mapping at the
    producer site. `captured_git_sha` is the hex SHA of HEAD at
    result-capture time; the regex accepts 40 chars (SHA-1, Git's
    historical default) or 64 chars (SHA-256, supported since
    Git 2.29 and the project's eventual target), case-insensitive.
    `captured_at` is a timezone-aware datetime; the validator pins
    UTC. `scalar_measurements` is free-form `(name, float)` pairs
    (perf numbers, error magnitudes, etc.); a future `measurements`
    field name is reserved for a richer Measurement submodel
    covering units, kinds, and string-valued metadata.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    verification_ref: RefString
    environment: Environment
    outcome: TestOutcome
    captured_git_sha: str = Field(
        pattern=r"^([0-9a-fA-F]{40}|[0-9a-fA-F]{64})$",
    )
    captured_at: AwareDatetime
    scalar_measurements: tuple[tuple[str, float], ...] = Field(
        default_factory=tuple,
    )

    @field_validator("captured_at")
    @classmethod
    def _check_utc(cls, value: datetime) -> datetime:
        """Pin captured_at to UTC; offset must be exactly zero."""
        if value.utcoffset() != timedelta(0):
            raise ValueError(
                "captured_at must be UTC (offset 0); got "
                f"{value.utcoffset()!r}",
            )
        return value


class TestResultsSnapshot(BaseModel):
    """A frozen append-only collection of TestResult records.

    `content_hash` and `parent_id` are reserved fields for the
    cross-snapshot DAG structure (content-hashed dedup + parent
    pointer for the iomoments-style append-only log). Their
    population rules and on-disk persistence (JSON file plus
    sidecar) are deferred to the producer-implementation pass;
    pinning the field names now keeps that pass from forcing a
    breaking schema rename.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    version: ShortName = "0.1.0"
    project: ShortName = "sicm_modernized"
    results: tuple[TestResult, ...] = Field(default_factory=tuple)
    content_hash: str | None = None
    parent_id: str | None = None
