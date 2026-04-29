# sicm_modernized

Computational classical mechanics, general relativity, and quantum
mechanics, organized around the **action principle** as the
unifying object across all phases. A modernization of Gerald J.
Sussman and Jack Wisdom's *Structure and Interpretation of
Classical Mechanics* (MIT Press, 1st ed. 2001, 2nd ed. 2014) and
*Functional Differential Geometry* (with Will Farr, 2013), built
on Racket CS (Chez backend) for the symbolic substrate, Python +
JAX as test oracle and prototyping layer, and CUDA C for
production GPU kernels.

**Status:** Phase 0 — CD scaffolding. No functional code yet. The
project arc, design rationale, and architectural decisions are
documented; implementation begins after the gate machinery is in
place.

## Project arc

Each phase is a usable artifact on its own.

1. **Phase 1 — Classical mechanics.** Re-derive scmutils-style
   Lagrangian/Hamiltonian apparatus in Racket CS. Re-implement
   SICM 1e + 2e scope. Add GPU ensemble integration (10⁶
   trajectories in parallel for chaos exploration).
2. **Phase 2 — Geometric machinery.** *Functional Differential
   Geometry* scope: manifolds, charts, vector fields, forms,
   covariant derivatives.
3. **Phase 3 — General relativity.** Geodesics in fixed
   backgrounds (Schwarzschild, Kerr, FLRW). Real-time photon-
   trajectory visualization around black holes via GPU geodesic
   ensembles. *Numerical relativity (evolving the metric) is out
   of scope.*
4. **Phase 4 — Quantum mechanics.** Schrödinger picture, Feynman
   path integral, phase-space (Wigner) methods. The classical
   trajectory emerges visibly as the survivor of destructive
   interference among GPU-sampled paths. *Quantum field theory is
   out of scope.*

## Architecture

- **Racket CS** — symbolic top: Lagrangian construction, functional
  `D`, generic arithmetic, FDG apparatus.
- **Typed Racket** — numerical mid-layer; auto-lowers to
  `unsafe-fl+` when types prove out.
- **Python 3.11+** — ontology (Pydantic + YAML), tests,
  orchestration.
- **JAX[cuda12]** — independent test oracle and prototyping
  vehicle. Cross-validates production CUDA C kernels.
- **CUDA C** — production GPU kernels (ensemble integration,
  Lyapunov spectra, path-integral Monte Carlo).

GPU work runs **locally only**. CI uses standard Linux runners
and skips GPU-tagged tests (per `DECISIONS.md` D004).

## Ontology

The project tracks its formal-knowledge graph in a Pydantic-validated
ontology with YAML as the primary authoring surface. The DAG models
the SICM domain at design granularity: mathematical objects, the
relations between them, the numerical methods that realize them, the
invariants those methods must preserve, the code that implements
them, the chapters where they teach, the tests that verify them, and
the decisions that justify them.

### Eight node types

| Node type | What it is | Examples |
|---|---|---|
| `mathematical_object` | A first-class object in the formalism | action `S`, Lagrangian `L`, Hamiltonian `H`, manifold, vector field, k-form, metric, Riemann tensor, wavefunction |
| `mathematical_relation` | An equation or transform connecting math objects | Euler-Lagrange, Legendre transform, geodesic equation, Schrödinger equation |
| `numerical_method` | A finite-computation algorithm realizing a math object | leapfrog, Yoshida-4 symplectic, split-operator FFT, path-integral Monte Carlo |
| `invariant` | A conserved quantity or preserved structure | energy, symplectic 2-form, time-reversal symmetry, action variable |
| `code_module` | A source file in the project | a Racket file, a Typed Racket numerical module, a CUDA kernel, a JAX reference |
| `pedagogical_unit` | A chapter / section / exercise mapping | "SICM-1e Ch3.4", "FDG Ch5", "original: action-as-functional intro" |
| `verification_case` | A test that checks correctness | analytical-solution comparison, JAX-reference cross-check, invariant property test |
| `decision_ref` | Pointer to a `DECISIONS.md` entry | D001, D002, D003, D004 |

### Key edges

Edges live as named-string fields on the source node (no separate
edge collection). The `Ontology` validator cross-resolves all
references at load time and refuses unknowns.

- `code_module --realizes--> mathematical_object`
- `code_module --implements--> numerical_method`
- `numerical_method --realizes--> mathematical_object`
- `numerical_method --applies--> mathematical_relation`
- `numerical_method --preserves--> invariant`
- `mathematical_relation --derives_to--> mathematical_object | mathematical_relation`
- `pedagogical_unit --covers--> mathematical_object`
- `pedagogical_unit --prerequisites--> pedagogical_unit` (must form a DAG)
- `verification_case --asserts--> invariant`
- `verification_case --tests--> numerical_method | mathematical_object`
- any node `--decision_refs--> decision_ref`

### Status discipline

Every node carries `status ∈ {spec, tested, implemented, deviation, n_a}`:

- `spec` — written down; no `implementation_refs`, no `verification_refs`
- `tested` — `verification_refs` populated; `implementation_refs` may be empty
- `implemented` — both ref lists populated
- `deviation` — system does not satisfy this; **`rationale` field required** documenting why
- `n_a` — not applicable to current scope; **`rationale` field required** documenting why

Every node carries an optional `rationale` field. It is *required*
when status is `deviation` or `n_a` (so the audit tool can surface
the deviation with its justification attached); it is optional and
useful for any other status to document a non-obvious choice.

### Active vs historical DAG branch

Every node also carries `archive: bool = False`. Setting `archive=True`
moves the node onto the historical branch and **requires a `rationale`**
explaining why. The active branch is the project's working set; the
historical branch retains traceability to superseded structures and
decisions without polluting the active formal-knowledge graph.

`DecisionRef` nodes have two extra fields tracking supersession:

- `deprecated: bool = False` — this decision has been superseded.
- `superseded_by: DecisionId | None = None` — names the *immediate*
  successor (per global CLAUDE.md, supersession chains link one step
  at a time so any link reaches its neighbor in one hop).

`deprecated` and `superseded_by` are biconditional: a DecisionRef
is `deprecated=True` iff it carries a `superseded_by` pointer.

For `DecisionRef` specifically, `archive` and `deprecated` are also
biconditional: supersession is the only path onto the historical
branch for a decision. Other node kinds use `archive` independently
because they have no `deprecated` field.

The active-branch invariant enforced at construction time:

> A non-archived node may not depend on a deprecated decision —
> directly or transitively. Either set `archive=True` (with
> rationale) or update the dependency chain to point at the active
> successor.

A node *directly* depends on a decision when its own `decision_refs`
names that decision. A node *transitively* depends when any node it
points at along its forward-dependency edges is itself directly or
transitively pinned. Forward-dependency edges (per
`_OUTGOING_EDGE_FIELDS` in `models.py`):

| node kind | dependency fields |
|---|---|
| `MathematicalRelation` | `appears_in`, `derives_to` |
| `NumericalMethod` | `realizes`, `applies`, `preserves` |
| `CodeModule` | `realizes`, `implements` |
| `PedagogicalUnit` | `covers`, `prerequisites` |
| `VerificationCase` | `asserts`, `tests` |

`MathematicalObject` and `Invariant` are foundations (no outgoing
dependency edges); `DecisionRef` is exempt entirely (its supersession
lifecycle lives on `superseded_by`, not these edges). The transitive
closure is computed at construction time via reverse-edge BFS over
the directly-pinned seed set; any non-archived member of the closure
is rejected.

The discipline is enforced at Pydantic-validation time. The
`audit-ontology` tool (Day 3) additionally resolves
`implementation_refs` and `verification_refs` against the working
tree and refuses dangling references.

### Files

- [`tooling/sicm-ontology.yaml`](tooling/sicm-ontology.yaml) — primary
  authoring surface (human-edited)
- `tooling/sicm-ontology.json` — built snapshot (`build-sicm-ontology`)
- `tooling/sicm-ontology.json.sha256` — content-hash sidecar
- [`tooling/src/sicm_ontology/`](tooling/src/sicm_ontology/) — Pydantic
  models, builder, persistence (`models.py`, `build.py`, `dag.py`,
  `types.py`, `__init__.py`)

### Methodology lineage

The ontology pattern (Pydantic + YAML + content-hash snapshot, eight
domain-specific node kinds, status discipline, named-string edges,
cross-reference resolution at load time) is **re-derived** from
iomoments and fireasmserver per `DECISIONS.md` D002. Per the global
"principles transfer; processes do not" rule, the *abstractions* are
inherited; the SICM-specific node taxonomy and edge types are
project-local. SICM is the third independent re-derivation across the
trio; surviving abstractions become candidates for an eventual common
toolkit.

## Quality gates

The project operates in CD-first deliverable mode (`DECISIONS.md`
D002). Gate machinery is being staged in:

- Pre-commit (fast): Python lints (flake8 + pylint + mypy
  --strict) on staged `*.py`, clang-format check on staged `*.cu`,
  Racket format check on staged `*.rkt`. Plus advisory Gemini
  review.
- Pre-push (full): everything pre-commit, plus pytest with branch
  coverage, Racket test suite, JAX reference tests (GPU), CUDA
  kernel tests (GPU), ontology audit.
- CI: mirrors pre-push minus GPU-tagged tests and minus the
  local-only Gemini step.

The `Makefile` and `tooling/hooks/` are not yet in place; they
land in the next scaffolding pass.

## Project documentation

- [`PROJECT_NOTES.md`](PROJECT_NOTES.md) — full design exploration
  from the 2026-04-25 kickoff conversation. Read this before
  proposing any architectural change.
- [`DECISIONS.md`](DECISIONS.md) — immutable architectural
  decision log.
- [`CLAUDE.md`](CLAUDE.md) — project-local Claude Code
  instructions.

## License

AGPL-3.0-or-later. Ed Hodapp is sole author and sole copyright
holder. **No external contributions accepted** at this time;
consolidated copyright preserves future relicensing flexibility.
Commercial deployments that cannot accept AGPL's §13 network-
copyleft route to Ed for a commercial license / consulting
engagement.

See [`LICENSE`](LICENSE) for the full AGPL text and
[`COPYRIGHT`](COPYRIGHT) for the project notice and lineage
acknowledgment.

## Lineage

This project independently re-derives the computational-physics
treatment established by Sussman, Wisdom, and Farr in SICM and
FDG. No endorsement by those authors or by MIT is implied. The
intellectual debt is acknowledged with the deepest respect.
