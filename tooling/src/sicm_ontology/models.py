"""Pydantic models for the sicm_modernized ontology DAG.

Re-derived 2026-04-25 from iomoments and fireasmserver patterns per
DECISIONS.md D002. The eight-type taxonomy is project-specific to the
SICM domain (mathematical objects, relations, numerical methods,
invariants, code modules, pedagogical units, verification cases, and
decision back-pointers).

Edges between nodes are represented inline as named-string reference
fields on the source node (matching iomoments' pattern). The
Ontology-level validator cross-resolves all references at construction
time and refuses unknowns.

Status discipline (mirroring iomoments D009 / our D002):
  spec         - both ref lists empty
  tested       - verification_refs non-empty
  implemented  - both ref lists non-empty
  deviation    - rationale in description
  n_a          - retained for traceability against the originating decision
"""

from __future__ import annotations

from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from sicm_ontology.types import (
    CodeLanguage,
    DecisionId,
    Description,
    InvariantBound,
    LanguageTarget,
    MathRelationKind,
    PedagogicalSource,
    PhaseTag,
    RefString,
    SafeId,
    ShortName,
    Status,
    VerificationKind,
    VerificationTier,
)

# DFS coloring for the prerequisites-acyclic check.
_CYCLE_WHITE = 0  # unvisited
_CYCLE_GRAY = 1   # on the current DFS stack
_CYCLE_BLACK = 2  # fully explored


def _cycle_dfs(
    node: str,
    adj: dict[str, list[str]],
    color: dict[str, int],
) -> None:
    """Recursive DFS for prerequisite-cycle detection.

    Mutates `color` in place. Raises ValueError on the first
    back-edge into a gray (on-stack) node, naming the offender.
    Pulled out of the validator method so each side stays under
    the project complexity ceiling (max-complexity = 5).
    """
    color[node] = _CYCLE_GRAY
    for nxt in adj.get(node, []):
        nxt_color = color.get(nxt, _CYCLE_WHITE)
        if nxt_color == _CYCLE_GRAY:
            raise ValueError(
                f"prerequisite cycle detected involving "
                f"pedagogical_unit {nxt!r}",
            )
        if nxt_color == _CYCLE_WHITE:
            _cycle_dfs(nxt, adj, color)
    color[node] = _CYCLE_BLACK

# Strictness for every node and the container. extra=forbid catches
# typos in the YAML at validation time; frozen=True locks instances
# after construction so canonical_hash stays trustworthy across
# downstream passes. Inlined per-class rather than via a shared
# module-level ConfigDict because pylint mis-classifies the latter
# as a class definition.


class _OntologyNodeBase(BaseModel):
    """Common shape for every ontology node.

    Subclasses add kind-specific fields. The base does not perform
    cross-reference resolution directly; the Ontology container
    performs that after all nodes are loaded so that forward
    references (A points to B defined later) resolve correctly.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    name: SafeId
    description: Description
    status: Status = "spec"
    decision_refs: list[DecisionId] = Field(default_factory=list)
    implementation_refs: list[RefString] = Field(default_factory=list)
    verification_refs: list[RefString] = Field(default_factory=list)

    @model_validator(mode="after")
    def _check_status_refs(self) -> Self:
        """Status discipline check (mirrors iomoments D009 / our D002).

        Dispatches per-status to a small helper so the per-status
        rules read individually. deviation / n_a have no ref-list
        constraint; rationale belongs in `description` and the audit
        tool will surface them for human review.
        """
        handlers = {
            "spec": self._check_spec_refs,
            "tested": self._check_tested_refs,
            "implemented": self._check_implemented_refs,
        }
        handler = handlers.get(self.status)
        if handler is not None:
            handler()
        return self

    def _check_spec_refs(self) -> None:
        if self.implementation_refs or self.verification_refs:
            raise ValueError(
                f"node {self.name!r} has status=spec but carries "
                f"implementation/verification refs; either remove "
                f"the refs or advance status",
            )

    def _check_tested_refs(self) -> None:
        if not self.verification_refs:
            raise ValueError(
                f"node {self.name!r} has status=tested but no "
                f"verification_refs",
            )

    def _check_implemented_refs(self) -> None:
        if not self.implementation_refs:
            raise ValueError(
                f"node {self.name!r} has status=implemented but no "
                f"implementation_refs",
            )
        if not self.verification_refs:
            raise ValueError(
                f"node {self.name!r} has status=implemented but no "
                f"verification_refs",
            )


# --- Eight node kinds -----------------------------------------------------


class MathematicalObject(_OntologyNodeBase):
    """A first-class object in the formalism: action S, Lagrangian L,
    Hamiltonian H, manifold, vector field, k-form, metric, Riemann
    tensor, wavefunction, propagator, etc."""

    latex_repr: ShortName | None = None
    domain: ShortName | None = None  # e.g., "cotangent_bundle"
    phase: PhaseTag


class MathematicalRelation(_OntologyNodeBase):
    """An equation or transform connecting math objects: Euler-Lagrange,
    Legendre transform, geodesic equation, Schrödinger equation,
    path-integral measure, etc."""

    latex_repr: ShortName | None = None
    kind: MathRelationKind
    phase: PhaseTag
    appears_in: list[SafeId] = Field(default_factory=list)
    derives_to: list[SafeId] = Field(default_factory=list)


class NumericalMethod(_OntologyNodeBase):
    """A finite-computation algorithm realizing one or more math objects:
    leapfrog, Yoshida-4 symplectic, split-operator FFT, Metropolis
    path-integral MC, etc."""

    order_of_accuracy: ShortName | None = None  # e.g., "O(h^4)"
    cost: ShortName | None = None               # e.g., "O(N log N)"
    language_targets: list[LanguageTarget] = Field(default_factory=list)
    realizes: list[SafeId] = Field(default_factory=list)
    preserves: list[SafeId] = Field(default_factory=list)


class Invariant(_OntologyNodeBase):
    """A conserved quantity or preserved structure: energy, symplectic
    2-form, time-reversal symmetry, action variable, etc."""

    bound_type: InvariantBound
    noether_origin: ShortName | None = None
    phase: PhaseTag


class CodeModule(_OntologyNodeBase):
    """A source file in the project. Cross-references the math objects
    and numerical methods it realizes."""

    path: RefString
    language: CodeLanguage
    realizes: list[SafeId] = Field(default_factory=list)
    implements: list[SafeId] = Field(default_factory=list)


class PedagogicalUnit(_OntologyNodeBase):
    """A chapter / section / exercise mapping. Lets us derive 'which
    math objects appear in which chapter' coverage reports across the
    SICM 1e + 2e + FDG corpus and our own derivative units."""

    source: PedagogicalSource
    position: ShortName  # "ch3.4", "appendix-A", "lecture-19"
    title: ShortName
    covers: list[SafeId] = Field(default_factory=list)
    prerequisites: list[SafeId] = Field(default_factory=list)


class VerificationCase(_OntologyNodeBase):
    """A test that checks correctness: analytical-solution comparison,
    JAX-reference cross-check, invariant property test, etc."""

    kind: VerificationKind
    tier: VerificationTier
    test_path: RefString  # "tests/test_x.py::test_y"
    asserts: list[SafeId] = Field(default_factory=list)
    tests: list[SafeId] = Field(default_factory=list)


class DecisionRef(_OntologyNodeBase):
    """Back-pointer to a DECISIONS.md entry. The ontology can name
    decisions; the audit tool will verify the decision exists in the
    file and that the title here matches what's recorded."""

    decision_id: DecisionId
    title: ShortName  # denormalized for context

    @model_validator(mode="after")
    def _check_name_matches_decision_id(self) -> Self:
        """For DecisionRef nodes, name must equal decision_id.

        Keeps the unique-name discipline from _OntologyNodeBase aligned
        with the DECISIONS.md ID space; cross-kind name collision
        between (e.g.) a DecisionRef "D003" and a math object "D003"
        is checked at the Ontology level, not here.
        """
        if self.name != self.decision_id:
            raise ValueError(
                f"DecisionRef name {self.name!r} must equal "
                f"decision_id {self.decision_id!r}",
            )
        return self


# --- The container --------------------------------------------------------


class Ontology(BaseModel):
    """The full SICM ontology — one snapshot of the project's
    formal-knowledge graph at a point in time.

    Cross-reference validation runs at construction time: every
    SafeId referenced in any node's edge fields must exist as a
    real node of the appropriate kind; every DecisionId referenced
    must appear in the decisions list.
    """

    # pylint: disable=too-many-instance-attributes
    # Nine fields = eight node-kind lists plus version/project metadata;
    # the count reflects the eight-type taxonomy, not tangled state.
    model_config = ConfigDict(extra="forbid", frozen=True)

    version: ShortName = "0.1.0"
    project: ShortName = "sicm_modernized"

    mathematical_objects: list[MathematicalObject] = Field(
        default_factory=list,
    )
    mathematical_relations: list[MathematicalRelation] = Field(
        default_factory=list,
    )
    numerical_methods: list[NumericalMethod] = Field(default_factory=list)
    invariants: list[Invariant] = Field(default_factory=list)
    code_modules: list[CodeModule] = Field(default_factory=list)
    pedagogical_units: list[PedagogicalUnit] = Field(default_factory=list)
    verification_cases: list[VerificationCase] = Field(default_factory=list)
    decisions: list[DecisionRef] = Field(default_factory=list)

    # ---- helpers (private, used by validators) --------------------------

    @staticmethod
    def _resolve_refs(
        refs: list[str],
        valid_targets: set[str],
        context: str,
        target_label: str,
    ) -> None:
        """Raise if any string in `refs` isn't in `valid_targets`."""
        for ref in refs:
            if ref not in valid_targets:
                raise ValueError(
                    f"{context} references unknown {target_label} "
                    f"{ref!r}",
                )

    # ---- validators ------------------------------------------------------

    @model_validator(mode="after")
    def _check_unique_names(self) -> Self:
        """Node names must be unique within their kind."""
        for label, items in self._iter_node_kinds():
            seen: set[str] = set()
            for n in items:
                if n.name in seen:
                    raise ValueError(
                        f"duplicate name {n.name!r} in {label}",
                    )
                seen.add(n.name)
        return self

    def _iter_node_kinds(self) -> list[tuple[str, list[_OntologyNodeBase]]]:
        """Iterator over (label, list-of-nodes) for the eight kinds."""
        return [
            ("mathematical_objects",
             list(self.mathematical_objects)),
            ("mathematical_relations",
             list(self.mathematical_relations)),
            ("numerical_methods",
             list(self.numerical_methods)),
            ("invariants",
             list(self.invariants)),
            ("code_modules",
             list(self.code_modules)),
            ("pedagogical_units",
             list(self.pedagogical_units)),
            ("verification_cases",
             list(self.verification_cases)),
            ("decisions",
             list(self.decisions)),
        ]

    @model_validator(mode="after")
    def _check_cross_references(self) -> Self:
        """Dispatch all cross-reference checks to per-kind helpers."""
        self._check_relation_refs()
        self._check_method_refs()
        self._check_code_refs()
        self._check_pedagogical_refs()
        self._check_verification_refs()
        self._check_decision_back_refs()
        return self

    def _check_relation_refs(self) -> None:
        math_obj_names = {n.name for n in self.mathematical_objects}
        math_rel_names = {n.name for n in self.mathematical_relations}
        for r in self.mathematical_relations:
            self._resolve_refs(
                r.appears_in, math_obj_names,
                f"{r.name}.appears_in", "mathematical_object",
            )
            self._resolve_refs(
                r.derives_to, math_obj_names | math_rel_names,
                f"{r.name}.derives_to", "math object/relation",
            )

    def _check_method_refs(self) -> None:
        math_obj_names = {n.name for n in self.mathematical_objects}
        invariant_names = {n.name for n in self.invariants}
        for m in self.numerical_methods:
            self._resolve_refs(
                m.realizes, math_obj_names,
                f"{m.name}.realizes", "mathematical_object",
            )
            self._resolve_refs(
                m.preserves, invariant_names,
                f"{m.name}.preserves", "invariant",
            )

    def _check_code_refs(self) -> None:
        math_obj_names = {n.name for n in self.mathematical_objects}
        method_names = {n.name for n in self.numerical_methods}
        for c in self.code_modules:
            self._resolve_refs(
                c.realizes, math_obj_names,
                f"{c.name}.realizes", "mathematical_object",
            )
            self._resolve_refs(
                c.implements, method_names,
                f"{c.name}.implements", "numerical_method",
            )

    def _check_pedagogical_refs(self) -> None:
        math_obj_names = {n.name for n in self.mathematical_objects}
        ped_names = {n.name for n in self.pedagogical_units}
        for p in self.pedagogical_units:
            self._resolve_refs(
                p.covers, math_obj_names,
                f"{p.name}.covers", "mathematical_object",
            )
            self._resolve_refs(
                p.prerequisites, ped_names,
                f"{p.name}.prerequisites", "pedagogical_unit",
            )

    def _check_verification_refs(self) -> None:
        math_obj_names = {n.name for n in self.mathematical_objects}
        method_names = {n.name for n in self.numerical_methods}
        invariant_names = {n.name for n in self.invariants}
        for v in self.verification_cases:
            self._resolve_refs(
                v.asserts, invariant_names,
                f"{v.name}.asserts", "invariant",
            )
            self._resolve_refs(
                v.tests, method_names | math_obj_names,
                f"{v.name}.tests", "numerical_method/mathematical_object",
            )

    def _check_decision_back_refs(self) -> None:
        decision_ids = {d.decision_id for d in self.decisions}
        for _, items in self._iter_node_kinds():
            for node in items:
                self._check_node_decision_refs(node, decision_ids)

    @staticmethod
    def _check_node_decision_refs(
        node: _OntologyNodeBase,
        decision_ids: set[str],
    ) -> None:
        """Per-node back-ref check; DecisionRef itself doesn't back-ref."""
        if isinstance(node, DecisionRef):
            return
        for d in node.decision_refs:
            if d not in decision_ids:
                raise ValueError(
                    f"{node.name}.decision_refs references unknown "
                    f"decision {d!r} (must be a DecisionRef in the "
                    f"decisions list)",
                )

    @model_validator(mode="after")
    def _check_prerequisites_acyclic(self) -> Self:
        """Pedagogical-unit prerequisites must form a DAG (no cycles)."""
        adj: dict[str, list[str]] = {
            p.name: list(p.prerequisites)
            for p in self.pedagogical_units
        }
        color: dict[str, int] = dict.fromkeys(adj, _CYCLE_WHITE)
        for n_name in adj:
            if color[n_name] == _CYCLE_WHITE:
                _cycle_dfs(n_name, adj, color)
        return self
