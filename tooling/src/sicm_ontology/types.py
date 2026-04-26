"""Shared scalar / literal types for the sicm_modernized ontology.

Re-derived 2026-04-25 from iomoments and fireasmserver patterns per
DECISIONS.md D002. SafeId / Description / Status mirror those projects
so a future cross-project audit unification stays viable; SICM-specific
literals (PhaseTag, MathRelationKind, PedagogicalSource, etc.) diverge
as needed for the project's mathematical-pedagogical domain.
"""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import StringConstraints

# --- Constrained string types --------------------------------------------

# First char must be alnum or underscore: prevents IDs like "-rf" from
# being mistaken for CLI flags when passed through shell tooling.
# Matches iomoments / fireasmserver pattern.
SafeId = Annotated[
    str,
    StringConstraints(
        pattern=r"^[a-zA-Z0-9_][a-zA-Z0-9_-]*$",
        max_length=100,
    ),
]

ShortName = Annotated[str, StringConstraints(max_length=200)]

Description = Annotated[str, StringConstraints(max_length=4000)]

# path:symbol or path:test_function form; validated lightly here, the
# audit tool resolves them against the working tree.
RefString = Annotated[str, StringConstraints(max_length=400)]

# Decision IDs follow the D### convention from DECISIONS.md.
DecisionId = Annotated[
    str,
    StringConstraints(pattern=r"^D\d{3,}$"),
]

# --- Status discipline ---------------------------------------------------

# Position of an ontology node in its lifecycle. Mirrors iomoments
# RequirementStatus so cross-project audit tooling can unify them.
#
#   spec         - written down but no impl, no test yet.
#   tested       - test exists and passes; impl may be partial.
#   implemented  - impl + test; (where applicable) measured value
#                  meets the stated criterion.
#   deviation    - the system does NOT satisfy this; rationale belongs
#                  in description; audit flags for human review.
#   n_a          - not applicable to current scope; retained for
#                  traceability against the originating decision.
Status = Literal[
    "spec",
    "tested",
    "implemented",
    "deviation",
    "n_a",
]

# --- Phase tag for math objects, relations, invariants -------------------

# Which phase of the project arc (PROJECT_NOTES.md §11) does this
# entity belong to. Lets the audit gate scope: a math object tagged
# "qm" is not expected to have implementation_refs while we're in
# Phase 1 (classical mechanics).
PhaseTag = Literal["classical", "geometric", "gr", "qm"]

# --- Mathematical-relation kinds -----------------------------------------

MathRelationKind = Literal[
    "variational",    # δS=0 → equations of motion
    "transform",      # Legendre, Fourier, gauge change, etc.
    "definition",     # H := pq̇ − L, etc.
    "equation",       # the equation of motion itself
    "approximation",  # stationary-phase, ℏ→0 limit, etc.
]

# --- Numerical-method targets --------------------------------------------

# Which language/runtime does this numerical_method target? A method
# may target multiple under the hybrid posture per D003 (e.g., the
# same leapfrog has a Typed Racket reference, a JAX reference, and a
# CUDA C production kernel).
LanguageTarget = Literal[
    "typed-racket",
    "racket",       # untyped Racket, for prototype/reference
    "cuda-c",
    "python-jax",
]

# --- Invariant bound type ------------------------------------------------

# How tightly is the invariant preserved by the numerical realization?
#
#   exact          - conserved to numerical precision (symplectic 2-form
#                    in symplectic integrators).
#   bounded_drift  - drifts within a known bound over T (energy in
#                    leapfrog; the "modified Hamiltonian" is exact).
#   stochastic     - conserved in expectation (path-integral observables).
InvariantBound = Literal["exact", "bounded_drift", "stochastic"]

# --- Code-module language ------------------------------------------------

CodeLanguage = Literal[
    "racket",
    "typed-racket",
    "cuda-c",
    "python",
    "python-jax",
    "shell",
    "make",
    "yaml",
]

# --- Pedagogical-unit source ---------------------------------------------

# Which upstream textbook (or "original": this project's own derivation)
# does this chapter/section/exercise come from?
PedagogicalSource = Literal[
    "sicm-1e",   # SICM 1st edition (2001)
    "sicm-2e",   # SICM 2nd edition (2014)
    "fdg",       # Functional Differential Geometry (2013)
    "feynman",   # Feynman Lectures or Quantum Mechanics & Path Integrals
    "original",  # this project's own derivation, no upstream source
]

# --- Verification-case kinds and tiers -----------------------------------

VerificationKind = Literal[
    "analytical",            # closed-form vs numerical
    "cross_implementation",  # JAX-reference vs CUDA-C production
    "property",              # invariant property over generated inputs
    "integration",           # end-to-end
    "regression",            # against a recorded baseline
]

VerificationTier = Literal["unit", "integration", "system"]
