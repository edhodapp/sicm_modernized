# Requirements — sicm_modernized

This file is the project's **immutable** requirements log. Each
requirement is a verifiable assertion derived from one or more
architectural decisions in `DECISIONS.md`.

## Format and conventions

**Phrasing.** Requirements use the RFC 2119 / RFC 8174 keyword
convention: `SHALL`, `SHOULD`, `MAY`, with `MUST` reserved for
external (e.g., legal / safety) constraints not yet present in this
project. Sentences follow the INCOSE pattern (subject + auxiliary +
verifiable predicate). Empirically vague language (e.g., "fast,"
"simple") is not permitted in normative text; if a requirement
needs a numerical bound, the bound is named explicitly.

**Identifiers.** Each requirement carries a stable ID of the form
`<CATEGORY>-NNN` (e.g., `PHYS-001`). Numbering is sequential within
a category and never renumbered. Gaps in the numeric sequence are
permitted (see "first-pass landing" below). Category prefixes in
use:

- `PHYS-` — physics correctness (analytical, numerical, symbolic)
- `INFRA-` — project infrastructure (build, test, gates, CI)

New categories are introduced explicitly (e.g., a future `GR-` or
`QM-` prefix as those phases land).

**Per-requirement fields.**

- One-line title following the ID and a colon.
- Body: the verifiable assertion, RFC 2119-keyworded.
- **Derived from:** comma-separated list of `D-NNN` decision IDs.
  At least one entry required; multi-decision derivations are
  expected for cross-cutting requirements. A requirement may also
  cite project-level normative documents (e.g., project
  `CLAUDE.md` sections) when the originating decision delegates
  to them; such citations are explicit and ride alongside the
  D-NNN list.
- **Implementation refs:** zero or more `path:symbol` entries
  pointing at code that realizes the requirement. The single-colon
  separator is the code-symbol convention (file path, then symbol
  name). Empty until implementation lands.
- **Verification refs:** zero or more `path::test_function` entries
  pointing at executable tests that exercise the requirement.
  The double-colon separator is pytest's standard test-address
  syntax; the asymmetry against `implementation_refs` is
  deliberate. Empty until tests land.
- **Proof refs:** zero or more Lean theorem names (per
  `DECISIONS.md` D005) discharging the requirement formally. Empty
  until Phase-2 work lands; the per-entry namespacing convention
  (bare name vs. fully-qualified path vs. tuple) is deferred to a
  later D-N.
- **Status:** one of `spec`, `tested`, `implemented`, `deviation`,
  `n_a`. Same enum as ontology nodes carry. Discipline:
  - `spec` — written down; both ref lists empty
  - `tested` — verification refs populated; impl refs may be
    populated or empty
  - `implemented` — both ref lists populated
  - `deviation` — system does not satisfy the requirement;
    a `Rationale:` field is then required documenting why
  - `n_a` — not applicable to current scope; `Rationale:` required
  - **No legal status exists for "implementation refs populated,
    verification refs empty."** That state corresponds to code
    landing without tests, which the project's TDD discipline
    (global `CLAUDE.md` "Repro before fix") explicitly forbids.
    The audit tool will surface any REQ in that shape as a
    discipline violation, not as a valid intermediate.

**Immutability and supersession.** Once recorded here, requirement
text is never edited or deleted. A requirement that becomes wrong
or obsolete is superseded by a later entry (with a higher ID
within the same category) and the old entry receives a single
prepended annotation: `**SUPERSEDED YYYY-MM-DD UTC by REQ-NNN.**
[reason]`, with the original body intact below. Mirrors the
`DECISIONS.md` convention.

**First-pass landing.** Three requirements are recorded below as
illustrations of the format derived from `D001`, `D003`, `D004`.
The full requirements set for Phase 1 (and beyond) lands
incrementally. New entries are appended in creation order; the
gap between sequence numbers (e.g., `PHYS-001` then later
`PHYS-007`) does not imply six unwritten requirements — it
implies six requirements written in some other category whose
numbers come out of the global creation sequence.

---

## PHYS-001 — Bounded shadow-Hamiltonian energy error for symplectic integrators on integrable reference systems

For a symplectic integrator applied to an integrable
time-independent Hamiltonian system on a fixed reference problem,
the integrator SHALL exhibit no secular growth in energy error
over exponentially long integration windows. Specifically, by
backward error analysis: the integrator SHALL be characterized by
a shadow Hamiltonian H̃ = H + O(h^p), where p is the integrator's
documented order of accuracy and h is the step size, such that

  |H(q(t), p(t)) − H(q(0), p(0))| ≤ C(h, system)

for all t ∈ [0, T], where C(h, system) scales as O(h^p) and is
independent of T over T ≤ exp(c/h) for some integrator-and-
system-dependent c > 0. The energy error oscillates around the
shadow-Hamiltonian offset rather than drifting monotonically; the
bound C is on the oscillation amplitude.

**Out of scope of this requirement** (covered by separate REQs to
land later):
- Non-symplectic integrators applied to conservative systems
  (different bound; secular growth permitted).
- Symplectic integrators applied to non-integrable systems
  (KAM-theoretic / chaotic regime; bound holds in measure but
  not pointwise).
- Dissipative-flow integrators (energy is not conserved by the
  underlying flow; requirement does not apply).

**Derived from:** D001 (project scope: SICM 1e/2e classical
mechanics is Phase 1 — establishes that energy-conservation work
falls inside the project's scope). The specific normative claim
here is sourced from the project `CLAUDE.md` "Math correctness
gates" section, which lists "Energy drift bounded over N orbits
of known integrable systems" as a Phase-1 gate. A future D-N may
lift that gates list into the immutable decision log; until then
this requirement cites the `CLAUDE.md` section directly.

**Implementation refs:** (none yet — Phase 1)
**Verification refs:** (none yet — Phase 1)
**Proof refs:** (none yet — Phase 2 candidate via backward error
analysis once mathlib's symplectic-geometry coverage matures)
**Status:** spec

---

## INFRA-001 — Hybrid JAX-and-CUDA-C cross-validation

For every numerical method the project ships as a CUDA C kernel,
a JAX reference implementation of the same numerics SHALL also
exist, and at least one verification case SHALL exercise both
implementations on identical inputs and assert agreement to
within a per-method tolerance. The tolerance for each method
SHALL be specified in that method's own REQ entry, and SHALL be
expressed as a concrete bound (e.g., a multiple of working-
precision machine epsilon, or a fraction of the integrator's
empirically measured one-step truncation error on the test
case). Tolerance values stated only as "tighter than the
integrator's intrinsic error budget" or other unverifiable
language are not permitted.

**Derived from:** D003 (language stack: hybrid JAX-as-oracle +
CUDA-C-as-production posture).

**Implementation refs:** (none yet — first JAX/CUDA-C pair lands
in Phase 1)
**Verification refs:** (none yet)
**Proof refs:** (none expected — this is an operational
requirement on cross-validation discipline, not a mathematical
theorem)
**Status:** spec

---

## INFRA-002 — GPU tests gated to local pre-push only

Tests that require a CUDA-capable GPU SHALL carry the
`@pytest.mark.gpu` pytest marker. The CI configuration SHALL
invoke pytest with `-m "not gpu"` to skip those tests. The
pre-push gate SHALL invoke pytest without that filter on Ed's
local machine.

**Threat model.** The project is currently single-developer;
pre-push gate compliance is honor-system. Bypass mechanisms
(e.g., `git push --no-verify`, manual gate-script exclusion,
running `git push` from an environment where the hook has not
been installed) are out of scope of this requirement. The
re-evaluation triggers in D004 list the conditions under which
this trust posture is revisited.

**Derived from:** D004 (GPU testing policy: local-only, never in
CI; rationale: GitHub Pro free quota does not include GPU
runners; pre-push catches GPU bugs before they leave the
workstation).

**Implementation refs:**
- `pyproject.toml:[tool.pytest.ini_options]` (markers list
  declares `gpu`)

**Verification refs:** (none yet — first GPU-tagged test lands in
Phase 1; the pre-push hook that enforces "no filter on local
runs" lands alongside)
**Proof refs:** (none — operational, not theorematic)
**Status:** spec
