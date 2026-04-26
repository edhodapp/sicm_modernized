"""sicm_modernized ontology — Pydantic schema, builder, persistence.

Re-derived 2026-04-25 from iomoments and fireasmserver patterns per
DECISIONS.md D002. Eight node types model the SICM domain:

- mathematical_object   — first-class objects in the formalism
- mathematical_relation — equations and transforms
- numerical_method      — finite-computation algorithms
- invariant             — conserved quantities / preserved structures
- code_module           — source files and their realizations
- pedagogical_unit      — chapter/section/exercise mappings
- verification_case     — tests checking correctness
- decision_ref          — back-pointers to DECISIONS.md entries

Edges live as named-string fields on the source node (no separate
edge collection); the Ontology validator cross-resolves at load time.
"""

from sicm_ontology.dag import (
    canonical_hash,
    load_ontology,
    save_ontology,
    verify_snapshot,
)
from sicm_ontology.models import (
    CodeModule,
    DecisionRef,
    Invariant,
    MathematicalObject,
    MathematicalRelation,
    NumericalMethod,
    Ontology,
    PedagogicalUnit,
    VerificationCase,
)

__all__ = [
    "CodeModule",
    "DecisionRef",
    "Invariant",
    "MathematicalObject",
    "MathematicalRelation",
    "NumericalMethod",
    "Ontology",
    "PedagogicalUnit",
    "VerificationCase",
    "canonical_hash",
    "load_ontology",
    "save_ontology",
    "verify_snapshot",
]
