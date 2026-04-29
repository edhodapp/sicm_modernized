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

from collections.abc import Iterator
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
    start: str,
    adj: dict[str, list[str]],
    color: dict[str, int],
) -> None:
    """Iterative DFS for prerequisite-cycle detection.

    Mutates `color` in place. Raises ValueError on the first
    back-edge into a gray (on-stack) node, naming the offender.
    Iterative rather than recursive so a long linear prerequisite
    chain doesn't hit Python's default recursion limit (~1000):
    pedagogical-unit chains beyond that depth are pathological but
    not crashes. Caller must ensure ``color[start] == _CYCLE_WHITE``
    before invoking; the per-start filter lives in
    ``Ontology._check_prerequisites_acyclic``.

    Stack frames are ``(node, iterator-over-children)`` so we can
    resume processing a node's remaining children after recursing
    into one of them. When a node's iterator exhausts, we paint it
    black and pop.
    """
    stack: list[tuple[str, Iterator[str]]] = [
        (start, iter(adj.get(start, []))),
    ]
    color[start] = _CYCLE_GRAY
    while stack:
        _cycle_dfs_step(stack, adj, color)


def _require_top_of_stack_gray(
    stack: list[tuple[str, Iterator[str]]],
    color: dict[str, int],
) -> None:
    """Contract guard for ``_cycle_dfs_step``.

    Top-of-stack node must already be painted ``_CYCLE_GRAY`` before
    a step runs. ``_cycle_dfs`` paints the seed; the push branch in
    the step paints each newly-stacked child. Pulled out as its own
    function so ``_cycle_dfs_step`` stays under the project
    complexity ceiling (max-complexity = 5). A real ``raise`` rather
    than ``assert`` so the guard survives ``python -O``.
    """
    node = stack[-1][0]
    if color.get(node) != _CYCLE_GRAY:
        raise RuntimeError(
            f"_cycle_dfs_step contract violated: top-of-stack node "
            f"{node!r} is not painted gray; caller must paint each "
            f"pushed node gray before invoking step",
        )


def _cycle_dfs_step(
    stack: list[tuple[str, Iterator[str]]],
    adj: dict[str, list[str]],
    color: dict[str, int],
) -> None:
    """One iteration of the iterative DFS in ``_cycle_dfs``.

    Either advances into an unvisited child (push), retreats from a
    fully-explored node (pop + paint black), or raises on a back-
    edge into a gray ancestor. Pulled out so both sides stay under
    the project complexity ceiling (max-complexity = 5).
    """
    _require_top_of_stack_gray(stack, color)
    node, children = stack[-1]
    try:
        nxt = next(children)
    except StopIteration:
        color[node] = _CYCLE_BLACK
        stack.pop()
        return
    nxt_color = color.get(nxt, _CYCLE_WHITE)
    if nxt_color == _CYCLE_GRAY:
        raise ValueError(
            f"prerequisite cycle detected involving "
            f"pedagogical_unit {nxt!r}",
        )
    if nxt_color == _CYCLE_WHITE:
        color[nxt] = _CYCLE_GRAY
        stack.append((nxt, iter(adj.get(nxt, []))))

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

    `description` says what this node IS; `rationale` (optional in
    general, REQUIRED for status=deviation/n_a and archive=True) says
    WHY when the node either fails to satisfy a goal, doesn't apply,
    or has been moved to the historical branch. The split lets the
    audit tool surface deviations / n_a's / archived nodes with
    their justification attached, without polluting the description.

    `archive` is the opt-in flag for the historical DAG branch: a
    node moves to the historical branch when the decisions or
    structures it depended on were superseded. The active-branch
    invariant (Ontology._check_active_branch_clean) refuses to let a
    non-archived node carry decision_refs that point at deprecated
    DecisionRefs.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    name: SafeId
    description: Description
    rationale: Description | None = None
    status: Status = "spec"
    archive: bool = False
    decision_refs: tuple[DecisionId, ...] = Field(default_factory=tuple)
    implementation_refs: tuple[RefString, ...] = Field(default_factory=tuple)
    verification_refs: tuple[RefString, ...] = Field(default_factory=tuple)

    @model_validator(mode="after")
    def _check_status_refs(self) -> Self:
        """Status discipline check (mirrors iomoments D009 / our D002).

        Dispatches per-status to a small helper so the per-status
        rules read individually. deviation / n_a do not constrain
        ref-list contents, but DO require the `rationale` field to
        be populated so the audit tool can surface why.
        """
        handlers = {
            "spec": self._check_spec_refs,
            "tested": self._check_tested_refs,
            "implemented": self._check_implemented_refs,
            "deviation": self._check_rationale_required,
            "n_a": self._check_rationale_required,
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

    def _check_rationale_required(self) -> None:
        """Require rationale on deviation / n_a statuses.

        Both statuses describe a state the audit tool will surface
        for human review. Without a rationale, the surfaced item is
        useless ('node X deviates ... because ?'). The rationale
        field carries the answer to 'why' so the surface is
        actionable.
        """
        if not (self.rationale and self.rationale.strip()):
            raise ValueError(
                f"node {self.name!r} has status={self.status!r} but "
                f"no rationale; rationale is required for deviation "
                f"and n_a statuses to document why",
            )

    @model_validator(mode="after")
    def _check_archive_requires_rationale(self) -> Self:
        """Archived nodes must carry a rationale.

        Archive moves a node onto the historical DAG branch. The
        audit tool will surface archived nodes for human review (so a
        future reader can see why the node lives in history); without
        a rationale, the surface is useless.
        """
        if self.archive and not (self.rationale and self.rationale.strip()):
            raise ValueError(
                f"node {self.name!r} has archive=True but no rationale; "
                f"rationale is required for archived nodes to document "
                f"why the node was moved to the historical branch",
            )
        return self


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
    path-integral measure, etc.

    `appears_in` can target either objects or other relations
    (relations chain: E-L appears in the action, which appears in
    the path-integral measure). `derives_to` likewise.
    """

    latex_repr: ShortName | None = None
    kind: MathRelationKind
    phase: PhaseTag
    appears_in: tuple[SafeId, ...] = Field(default_factory=tuple)
    derives_to: tuple[SafeId, ...] = Field(default_factory=tuple)


class NumericalMethod(_OntologyNodeBase):
    """A finite-computation algorithm realizing one or more math objects:
    leapfrog, Yoshida-4 symplectic, split-operator FFT, Metropolis
    path-integral MC, etc.

    `realizes` targets the *object* the method makes computable
    (e.g., the Hamiltonian flow). `applies` targets the *relation*
    the method implements as its update rule (e.g., Hamilton's
    equations). The split mirrors `code_module.realizes` (objects)
    vs `code_module.implements` (methods): an object is the *what*,
    a relation/method is the *how*.
    """

    order_of_accuracy: ShortName | None = None  # e.g., "O(h^4)"
    cost: ShortName | None = None               # e.g., "O(N log N)"
    language_targets: tuple[LanguageTarget, ...] = Field(
        default_factory=tuple,
    )
    realizes: tuple[SafeId, ...] = Field(default_factory=tuple)
    applies: tuple[SafeId, ...] = Field(default_factory=tuple)
    preserves: tuple[SafeId, ...] = Field(default_factory=tuple)


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
    realizes: tuple[SafeId, ...] = Field(default_factory=tuple)
    implements: tuple[SafeId, ...] = Field(default_factory=tuple)


class PedagogicalUnit(_OntologyNodeBase):
    """A chapter / section / exercise mapping. Lets us derive 'which
    math objects appear in which chapter' coverage reports across the
    SICM 1e + 2e + FDG corpus and our own derivative units."""

    source: PedagogicalSource
    position: ShortName  # "ch3.4", "appendix-A", "lecture-19"
    title: ShortName
    covers: tuple[SafeId, ...] = Field(default_factory=tuple)
    prerequisites: tuple[SafeId, ...] = Field(default_factory=tuple)


class VerificationCase(_OntologyNodeBase):
    """A test that checks correctness: analytical-solution comparison,
    JAX-reference cross-check, invariant property test, etc.

    `tests` can target methods, objects, or relations (a test that
    'Legendre transform round-trips' targets a relation; a test that
    'leapfrog energy drift is bounded' targets a method).
    """

    kind: VerificationKind
    tier: VerificationTier
    test_path: RefString  # "tests/test_x.py::test_y"
    asserts: tuple[SafeId, ...] = Field(default_factory=tuple)
    tests: tuple[SafeId, ...] = Field(default_factory=tuple)


class DecisionRef(_OntologyNodeBase):
    """Back-pointer to a DECISIONS.md entry. The ontology can name
    decisions; the audit tool will verify the decision exists in the
    file and that the title here matches what's recorded.

    Supersession is recorded via `deprecated` + `superseded_by` (a
    biconditional pair: a DecisionRef is `deprecated=True` iff it
    carries a `superseded_by` pointer to its immediate successor).
    Per global CLAUDE.md, supersession chains annotate each link so
    a reader landing on any entry finds the next step in one hop;
    `superseded_by` thus points at the IMMEDIATE successor, which
    may itself be deprecated until the chain reaches the active
    terminus.

    For DecisionRef specifically, `archive` is also biconditional
    with `deprecated`: the only path to the historical branch for a
    decision is supersession, so the two flags must agree (other
    node kinds carry `archive` independently because they have no
    `deprecated` field). Archived deprecated DecisionRefs require a
    rationale (inherited from `_check_archive_requires_rationale`),
    typically explaining why the supersession was warranted.

    The inherited `decision_refs` field on a DecisionRef is not used
    for supersession (that lives on `superseded_by`) and is skipped
    by `_check_node_decision_refs` and `_check_active_branch_clean`.
    """

    decision_id: DecisionId
    title: ShortName  # denormalized for context
    deprecated: bool = False
    superseded_by: DecisionId | None = None

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

    @model_validator(mode="after")
    def _check_supersession_biconditional(self) -> Self:
        """`deprecated=True` iff `superseded_by` is populated.

        Either form alone leaves the supersession state ambiguous: a
        deprecated entry without a successor breaks the chain back to
        the active terminus; a `superseded_by` pointer without
        `deprecated=True` represents a successor relationship that
        the active-branch invariant cannot reason about.

        Self-supersession is checked first so that a malformed entry
        like `decision_id=D003, superseded_by=D003, deprecated=False`
        surfaces the structural defect (self-cycle) rather than the
        derivative biconditional mismatch (superseded_by-but-not-
        deprecated), saving the author a fix-rerun cycle.
        """
        if self.superseded_by == self.decision_id:
            raise ValueError(
                f"DecisionRef {self.decision_id!r} names itself as "
                f"its own successor (superseded_by="
                f"{self.superseded_by!r}); supersession chains must "
                f"terminate at a distinct active DecisionRef",
            )
        if self.deprecated and self.superseded_by is None:
            raise ValueError(
                f"DecisionRef {self.decision_id!r} has deprecated=True "
                f"but no superseded_by; a deprecated decision must "
                f"name its immediate successor",
            )
        if self.superseded_by is not None and not self.deprecated:
            raise ValueError(
                f"DecisionRef {self.decision_id!r} carries "
                f"superseded_by={self.superseded_by!r} but is not "
                f"marked deprecated; only deprecated decisions point "
                f"at successors",
            )
        return self

    @model_validator(mode="after")
    def _check_archive_iff_deprecated(self) -> Self:
        """For DecisionRef, `archive` and `deprecated` are biconditional.

        Supersession is the only path to the historical branch for a
        decision: a deprecated DecisionRef must be archived, and an
        archived DecisionRef must be deprecated. Other node kinds use
        `archive` independently (they carry no `deprecated` field),
        but DecisionRef has both flags and they must agree to keep
        the active-vs-historical partition unambiguous.
        """
        if self.deprecated and not self.archive:
            raise ValueError(
                f"DecisionRef {self.decision_id!r} is deprecated but "
                f"archive=False; deprecated decisions belong on the "
                f"historical branch (set archive=True and supply a "
                f"rationale)",
            )
        if self.archive and not self.deprecated:
            raise ValueError(
                f"DecisionRef {self.decision_id!r} has archive=True "
                f"but is not deprecated; the only path for a "
                f"DecisionRef onto the historical branch is "
                f"supersession (set deprecated=True and "
                f"superseded_by to the active successor)",
            )
        return self


# --- Outgoing-dependency edge map ---------------------------------------
#
# For the active-branch transitive-closure check: which fields on each
# node kind represent forward dependencies on other ontology nodes? A
# node X with edge to Y "depends on" Y in the sense that if Y's
# foundation (decision_refs) is deprecated, X transitively inherits
# the pin. DecisionRef is intentionally absent — its supersession
# lifecycle is tracked via `superseded_by`, not these edges. Math
# objects and invariants have no outgoing edges (they are foundations,
# not dependents).
_OUTGOING_EDGE_FIELDS: dict[type[_OntologyNodeBase], tuple[str, ...]] = {
    MathematicalRelation: ("appears_in", "derives_to"),
    NumericalMethod: ("realizes", "applies", "preserves"),
    CodeModule: ("realizes", "implements"),
    PedagogicalUnit: ("covers", "prerequisites"),
    VerificationCase: ("asserts", "tests"),
}


# --- The container --------------------------------------------------------


class Ontology(BaseModel):
    """The full SICM ontology — one snapshot of the project's
    formal-knowledge graph at a point in time.

    Cross-reference validation runs at construction time: every
    SafeId referenced in any node's edge fields must exist as a
    real node of the appropriate kind; every DecisionId referenced
    must appear in the decisions list.

    Validator declaration order is load-bearing. Pydantic v2 runs
    `mode="after"` validators in source order; later validators
    here assume earlier ones have already enforced their invariants.
    Specifically: `_check_active_branch_clean` depends on
    globally-unique node names (so `_index_non_decision_nodes`
    doesn't lose nodes to dict-key collision) and on resolved
    cross-references (so the dependency graph is well-formed).
    `_check_supersession_acyclic` depends on resolved supersession
    targets. Do not reorder without re-checking these dependencies.
    """

    # pylint: disable=too-many-instance-attributes
    # Nine fields = eight node-kind lists plus version/project metadata;
    # the count reflects the eight-type taxonomy, not tangled state.
    model_config = ConfigDict(extra="forbid", frozen=True)

    version: ShortName = "0.1.0"
    project: ShortName = "sicm_modernized"

    mathematical_objects: tuple[MathematicalObject, ...] = Field(
        default_factory=tuple,
    )
    mathematical_relations: tuple[MathematicalRelation, ...] = Field(
        default_factory=tuple,
    )
    numerical_methods: tuple[NumericalMethod, ...] = Field(
        default_factory=tuple,
    )
    invariants: tuple[Invariant, ...] = Field(default_factory=tuple)
    code_modules: tuple[CodeModule, ...] = Field(default_factory=tuple)
    pedagogical_units: tuple[PedagogicalUnit, ...] = Field(
        default_factory=tuple,
    )
    verification_cases: tuple[VerificationCase, ...] = Field(
        default_factory=tuple,
    )
    decisions: tuple[DecisionRef, ...] = Field(default_factory=tuple)

    # ---- helpers (private, used by validators) --------------------------

    @staticmethod
    def _resolve_refs(
        refs: tuple[str, ...],
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
    def _check_global_unique_names(self) -> Self:
        """Node names must be globally unique across all eight kinds.

        Per-kind uniqueness alone leaves cross-reference resolution
        ambiguous when an edge field unions multiple kinds (e.g.,
        VerificationCase.tests against numerical_methods or
        mathematical_objects; MathematicalRelation.derives_to
        against mathematical_objects or mathematical_relations).
        Reject the ambiguity at construction time. Catches both
        within-kind duplicates and cross-kind collisions in one pass.
        """
        name_to_locations: dict[str, list[str]] = {}
        for label, items in self._iter_node_kinds():
            for node in items:
                name_to_locations.setdefault(node.name, []).append(label)
        collisions = [
            (name, locations)
            for name, locations in name_to_locations.items()
            if len(locations) > 1
        ]
        if collisions:
            detail = "; ".join(
                f"{name!r} appears in {locations}"
                for name, locations in collisions
            )
            raise ValueError(
                f"name(s) not globally unique ({len(collisions)} "
                f"collision(s)): {detail}. Names must be unique "
                f"across all ontology kinds so cross-kind edges "
                f"resolve unambiguously.",
            )
        return self

    def _iter_node_kinds(
        self,
    ) -> list[tuple[str, tuple[_OntologyNodeBase, ...]]]:
        """Iterator over (label, tuple-of-nodes) for the eight kinds.

        Returns the underlying tuples directly (no defensive copy)
        since the tuples are themselves immutable.
        """
        return [
            ("mathematical_objects", self.mathematical_objects),
            ("mathematical_relations", self.mathematical_relations),
            ("numerical_methods", self.numerical_methods),
            ("invariants", self.invariants),
            ("code_modules", self.code_modules),
            ("pedagogical_units", self.pedagogical_units),
            ("verification_cases", self.verification_cases),
            ("decisions", self.decisions),
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
        obj_or_rel = math_obj_names | math_rel_names
        for r in self.mathematical_relations:
            self._resolve_refs(
                r.appears_in, obj_or_rel,
                f"{r.name}.appears_in", "math object/relation",
            )
            self._resolve_refs(
                r.derives_to, obj_or_rel,
                f"{r.name}.derives_to", "math object/relation",
            )

    def _check_method_refs(self) -> None:
        math_obj_names = {n.name for n in self.mathematical_objects}
        math_rel_names = {n.name for n in self.mathematical_relations}
        invariant_names = {n.name for n in self.invariants}
        for m in self.numerical_methods:
            self._resolve_refs(
                m.realizes, math_obj_names,
                f"{m.name}.realizes", "mathematical_object",
            )
            self._resolve_refs(
                m.applies, math_rel_names,
                f"{m.name}.applies", "mathematical_relation",
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
        math_rel_names = {n.name for n in self.mathematical_relations}
        method_names = {n.name for n in self.numerical_methods}
        invariant_names = {n.name for n in self.invariants}
        valid_targets = method_names | math_obj_names | math_rel_names
        for v in self.verification_cases:
            self._resolve_refs(
                v.asserts, invariant_names,
                f"{v.name}.asserts", "invariant",
            )
            self._resolve_refs(
                v.tests, valid_targets,
                f"{v.name}.tests", "method/object/relation",
            )

    def _check_decision_back_refs(self) -> None:
        decision_ids = {d.decision_id for d in self.decisions}
        for _, items in self._iter_node_kinds():
            for node in items:
                self._check_node_decision_refs(node, decision_ids)
        for d in self.decisions:
            self._check_supersession_target(d, decision_ids)

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

    @staticmethod
    def _check_supersession_target(
        d: DecisionRef,
        decision_ids: set[str],
    ) -> None:
        """`superseded_by`, when present, must name an existing DecisionRef."""
        if d.superseded_by is None:
            return
        if d.superseded_by not in decision_ids:
            raise ValueError(
                f"DecisionRef {d.decision_id!r}.superseded_by "
                f"references unknown decision "
                f"{d.superseded_by!r} (must be a DecisionRef in "
                f"the decisions list)",
            )

    @model_validator(mode="after")
    def _check_active_branch_clean(self) -> Self:
        """Active-DAG-branch invariant: non-archived nodes must not
        transitively depend on deprecated decisions.

        A node "depends on" a deprecated decision either DIRECTLY
        (via decision_refs) or TRANSITIVELY (any forward-reachable
        node along the dependency edges in `_OUTGOING_EDGE_FIELDS`
        has a direct decision_refs entry into a deprecated decision).
        Without the transitive case the active branch silently
        accumulates nodes whose ancestors are pinned to obsolete
        reasoning even though their own decision_refs are clean.

        Algorithm: build the reverse dependency graph from
        `name_to_node`, BFS from the directly-pinned set through
        reverse edges to collect every ancestor. The pinned set is
        the union; reject any non-archived member.

        DecisionRefs are excluded from `name_to_node` (their
        supersession lifecycle is on `superseded_by`, not these
        edges). Archived nodes are exempt from the rejection (they
        live on the historical branch by design).
        """
        deprecated_ids = {
            d.decision_id for d in self.decisions if d.deprecated
        }
        if not deprecated_ids:
            return self
        name_to_node = self._index_non_decision_nodes()
        pinned = self._transitive_pin_closure(
            name_to_node, deprecated_ids,
        )
        violations = sorted(
            name for name in pinned
            if not name_to_node[name].archive
        )
        if violations:
            raise ValueError(
                f"node(s) on the active branch (archive=False) but "
                f"transitively depending on a deprecated decision "
                f"({len(violations)} violation(s)): {violations}; "
                f"either set archive=True (with rationale) on each "
                f"or update the dependency chain to point at the "
                f"active successor",
            )
        return self

    def _index_non_decision_nodes(
        self,
    ) -> dict[str, _OntologyNodeBase]:
        """Map of node-name -> node for every non-DecisionRef node."""
        return {
            node.name: node
            for _, items in self._iter_node_kinds()
            for node in items
            if not isinstance(node, DecisionRef)
        }

    @staticmethod
    def _transitive_pin_closure(
        name_to_node: dict[str, _OntologyNodeBase],
        deprecated_ids: set[str],
    ) -> set[str]:
        """Names of every node that directly or transitively depends
        on a deprecated decision. Empty when no direct pin exists."""
        direct = Ontology._direct_pin_set(name_to_node, deprecated_ids)
        if not direct:
            return set()
        rev = Ontology._build_reverse_dependency_map(name_to_node)
        return Ontology._bfs_pin_ancestors(direct, rev)

    @staticmethod
    def _direct_pin_set(
        name_to_node: dict[str, _OntologyNodeBase],
        deprecated_ids: set[str],
    ) -> set[str]:
        """Nodes whose own decision_refs name a deprecated decision."""
        return {
            name for name, node in name_to_node.items()
            if any(d in deprecated_ids for d in node.decision_refs)
        }

    @staticmethod
    def _build_reverse_dependency_map(
        name_to_node: dict[str, _OntologyNodeBase],
    ) -> dict[str, set[str]]:
        """Reverse the forward-dependency edges: rev[Y] = {X | X -> Y}.

        Edges are read off `_OUTGOING_EDGE_FIELDS`. Targets not in
        `name_to_node` (e.g., DecisionRefs, dangling refs) are
        dropped — the cross-reference validators handle those.
        """
        rev: dict[str, set[str]] = {}
        for src_name, src_node in name_to_node.items():
            for dst_name in Ontology._outgoing_edges(src_node):
                if dst_name in name_to_node:
                    rev.setdefault(dst_name, set()).add(src_name)
        return rev

    @staticmethod
    def _outgoing_edges(node: _OntologyNodeBase) -> tuple[str, ...]:
        """Concatenated outgoing-edge target names for `node`."""
        edges: list[str] = []
        for field in _OUTGOING_EDGE_FIELDS.get(type(node), ()):
            edges.extend(getattr(node, field))
        return tuple(edges)

    @staticmethod
    def _bfs_pin_ancestors(
        seed: set[str],
        rev: dict[str, set[str]],
    ) -> set[str]:
        """Forward-closure of `seed` through reverse edges in `rev`."""
        pinned = set(seed)
        frontier = list(seed)
        while frontier:
            cur = frontier.pop()
            for predecessor in rev.get(cur, ()):
                if predecessor not in pinned:
                    pinned.add(predecessor)
                    frontier.append(predecessor)
        return pinned

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

    @model_validator(mode="after")
    def _check_supersession_acyclic(self) -> Self:
        """Supersession chains must terminate at an active DecisionRef.

        The supersession graph (edges d -> d.superseded_by) has
        out-degree ≤ 1 by construction, so it cannot form rho-shaped
        components — only pure cycles are possible. A linear walk
        from each chain head with a per-walk visited set suffices;
        the prerequisite-DFS machinery would be overkill here. The
        per-instance `_check_supersession_biconditional` already
        catches length-1 self-supersession; this validator catches
        lengths >= 2 (D003 -> D004 -> D003) once all decisions are
        assembled into the container.

        Unresolved `superseded_by` targets are tolerated here (the
        walk ends at the first ID not present in `next_of`), because
        `_check_supersession_target` raises on them separately and
        will fail the construction independently.
        """
        next_of: dict[str, str] = {
            d.decision_id: d.superseded_by
            for d in self.decisions
            if d.superseded_by is not None
        }
        for start in next_of:
            self._walk_supersession_chain(start, next_of)
        return self

    @staticmethod
    def _walk_supersession_chain(
        start: str,
        next_of: dict[str, str],
    ) -> None:
        """Follow superseded_by from `start` until terminus or cycle.

        Raises ValueError naming the cycle membership on revisit;
        returns cleanly when the chain reaches a non-deprecated
        DecisionRef (no entry in `next_of`).
        """
        seen: set[str] = set()
        cur: str | None = start
        while cur is not None:
            if cur in seen:
                raise ValueError(
                    f"supersession cycle detected involving "
                    f"DecisionRef {cur!r}; chains must terminate at "
                    f"a non-deprecated active DecisionRef",
                )
            seen.add(cur)
            cur = next_of.get(cur)
