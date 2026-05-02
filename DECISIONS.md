# Architectural Decisions — sicm_modernized

This file is the project's **immutable** architectural decision log,
following the convention in `~/.claude/CLAUDE.md`:

- **Sequential numbering, never renumbered.** Entries appear in
  creation order: D001, D002, D003, ...
- **Entry content is immutable.** Once written, the decision text and
  rationale are never edited or deleted.
- **Supersession is bidirectional.** A new entry that replaces an
  earlier one opens with `**Supersedes:** D00N (deprecated YYYY-MM-DD
  HH:MM UTC). [reason]`. The superseded entry receives a single
  prepended annotation `**DEPRECATED YYYY-MM-DD HH:MM UTC —
  superseded by D00M.** [reason]` with the original body intact below.
- **Chained supersessions** annotate each link so a reader landing on
  any entry finds the successor or predecessor in one step.
- **Timestamps include UTC time** when same-day ordering matters.

Annotation of an old entry by a deprecation header is the **one
permitted addition**. It records a later event, not a revision; the
content-immutability rule holds.

Companion artifacts:
- `PROJECT_NOTES.md` — full design exploration from kickoff
- `CLAUDE.md` — project-local Claude instructions and policy summary
- `~/.claude/projects/-home-ed-sicm-updated/memory/` — durable project memory

---

## D001 — Project scope and working name (2026-04-25)

**Decision.** Initiate `sicm_modernized` as a multi-phase project to
modernize and extend the computational treatment of classical
mechanics established by Sussman & Wisdom in *Structure and
Interpretation of Classical Mechanics* (1st ed. 2001, 2nd ed. 2014)
and *Functional Differential Geometry* (with Farr, 2013).

**Working package name:** `sicm_modernized`. Used as the Python
package identifier, the working directory name (`/home/ed/
sicm_updated/`), and the COPYRIGHT line. The eventual artifact title
(book / publication name) is deferred — candidates include
*Structure and Interpretation of Action Principles*, *The Action
Principle: A Computational Approach*, and variants. Final title is
not load-bearing for project scaffolding and will be pinned in a
later D-N entry.

**Project arc** (each phase = textbook-sized deliverable):
1. Classical mechanics (SICM 1e + 2e scope) — re-derive in Racket CS
2. Geometric machinery (FDG scope) — manifolds, forms, connections
3. General relativity (geodesics in fixed backgrounds; *not*
   numerical relativity)
4. Quantum mechanics (Schrödinger + path integral + phase-space
   methods; *not* QFT)

**The architectural keystone.** The action `S = ∫L dt` is the same
object across all four phases. What changes phase-to-phase is what
you *do* with the action (stationarize, sum over paths, sum over
field configurations) — not what the action *is*. This unifies the
symbolic substrate, the numerical substrate, and the CUDA
orchestration pattern across the entire project arc.

Rationale and full design exploration: `PROJECT_NOTES.md`.

---

## D002 — CD-first deliverable mode; methodology re-derived from iomoments + fireasmserver (2026-04-25)

**Decision.** This project operates in **CD-first deliverable mode**
per the global `~/.claude/CLAUDE.md` distinction between deliverable
and experimental projects. Full quality-gate machinery (lint +
typecheck + test + branch coverage + ontology audit + review) is set
up before the first functional commit.

**Methodology lineage.** The discipline pattern (ontology DAG,
audit-ontology consistency tool, two-tier gate split, Pydantic + YAML
authoring surface, hooks layout, immutable DECISIONS.md) is
**re-derived** from iomoments and fireasmserver. It is *not*
copy-pasted from those projects, and it is *not* forked from
`python_agent` (the earlier shared substrate, which Ed has tabled
pending more real-world examples).

This is the third independent re-derivation of the SysE-discipline
pattern (after iomoments and fireasmserver). When the surviving
abstractions stabilize across the three, they become candidates for
extraction into a common toolkit. That extraction is **not yet
appropriate**; discovery is still in progress.

Per global "principles transfer; processes do not": tooling is
re-implemented for this project's specific mix of languages
(Racket CS + Python + JAX + CUDA C), not lifted whole.

**What's adopted in spirit:**
- `tooling/` directory layout with `src/` + `hooks/`
- Pydantic models in `tooling/src/sicm_ontology/` matching the
  iomoments/fireasm `models.py / build.py / dag.py / types.py /
  __init__.py` shape
- `audit_ontology` package with `audit.py / resolver.py /
  consistency.py / parser.py / formatter.py / cli.py / __main__.py`
  matching the fireasm shape
- YAML as primary authoring surface for the ontology; JSON as
  content-hash-gated build snapshot
- `tooling/hooks/install.sh` symlinking pre-commit and pre-push
- Pre-commit fast gates (Python lints + clang-format on staged C/.cu)
- Pre-push full gates (everything pre-commit + ontology audit +
  Racket lint + JAX reference tests)
- CI mirrors pre-push minus local-only Gemini review
- Shared review toolchain at `~/tools/code-review/` (not duplicated)
- AGPL + COPYRIGHT split (LICENSE verbatim AGPLv3, COPYRIGHT
  carrying the four-section project notice)

**What's not adopted:** eBPF tooling, BTF verification, vmtest
matrix, four-engine C lint stack (gcc + clang + clang-tidy +
cppcheck + scan-build), QEMU harness, multi-arch boot matrix.
Domain-irrelevant.

---

## D003 — Language stack: Racket CS + Python + JAX + CUDA C (2026-04-25)

**Decision.** The implementation languages and their roles are:

- **Racket CS** (Chez Scheme backend, the default since
  Racket 7.7 / ~2020) — symbolic top: Lagrangian construction,
  functional `D` operator, generic arithmetic, the FDG manifold and
  differential-form apparatus. Plays the role scmutils plays in
  Sussman & Wisdom's MIT codebase.

- **Typed Racket** — numerical mid-layer where Racket needs
  C-equivalent inner-loop speed. Typed Racket auto-lowers `Float`
  arithmetic to `unsafe-fl+` etc. when types are proven, giving
  speed without surrendering type discipline. Direct use of
  `racket/unsafe/ops` is the escape hatch of last resort, not the
  default.

- **Python 3.11+** — ontology infrastructure (Pydantic + YAML),
  test orchestration (pytest + branch coverage), and JAX reference
  implementation host. Same Python tooling stack as iomoments and
  silicritter (flake8, pylint, mypy --strict, pytest, pytest-cov).

- **JAX[cuda12]** — independent test oracle and rapid prototyping
  vehicle. JAX implementations of integrators, Hamiltonian flows,
  and ensemble kernels exist in parallel with the production
  Racket→CUDA-C path. Cross-implementation comparison catches bugs
  that would silently agree across a single implementation. The
  "isolate what you test" principle from global CLAUDE.md.

- **CUDA C** — production GPU kernels for the hot path: ensemble
  integration of trajectories, Lyapunov spectrum computation,
  path-integral Monte Carlo, surface-of-section maps. Compiled with
  `nvcc`; format-checked with `clang-format`; optionally
  static-analyzed with `clang-tidy` (CUDA support); runtime-checked
  with NVIDIA's `compute-sanitizer` during development.

**The hybrid JAX+CUDA-C posture (option C).** JAX serves as
prototyping vehicle and reference oracle; CUDA C carries the
production load; both implementations coexist permanently, with
cross-validation as a first-class verification case. The cost
(maintaining two GPU implementations of the same numerics) is
justified by:
1. Independent oracle for production correctness (different language,
   different compiler, different runtime)
2. Faster iteration during numerical-algorithm exploration in JAX
3. JAX's autodiff / vmap / pmap / jit machinery available for
   exploratory work without committing to the production code path
4. Defense against silent kernel-compiler bugs that a single-
   implementation project cannot detect

**Bridge mechanism (deferred).** The exact handoff format between
Racket symbolic top, Python/JAX, and CUDA C is **not pinned in this
decision.** It will be specified in a later D-N once enough code
exists to know what the handoff actually needs to carry. Initial
working assumption: JSON or s-expression problem specs emitted by
Racket, consumed by both JAX and the CUDA C harness.

---

## D004 — GPU testing policy: local-only, never in CI (2026-04-25)

**Decision.** Tests that require a GPU run **locally only**, gated
at pre-push. CI (GitHub Actions) runs on standard GitHub-hosted
Linux runners and **skips GPU-tagged tests**.

**Rationale.**
- GitHub Pro does not include GPU runners in its free monthly
  minutes. GitHub's Linux 4-core GPU larger runner costs $0.052
  per minute (verified 2026-04-25 against
  docs.github.com/billing/reference/actions-runner-pricing).
- The project's test cadence (per-commit and per-push) would burn
  GPU-runner budget at a rate not justified by the catch-rate
  improvement over CPU-only CI.
- The pre-push gate already exercises the GPU path on Ed's local
  machine, where development happens. Bugs in GPU code are caught
  before they leave the workstation.
- The CPU-only path in CI still exercises: all linting, all
  Python unit tests not tagged GPU, all Racket tests, the full
  ontology audit, and any analytical-solution comparison tests
  that don't depend on GPU.

**Tagging convention (provisional).** GPU-requiring tests carry the
pytest mark `@pytest.mark.gpu`. CI invokes pytest with `-m "not
gpu"` to skip them. Pre-push runs the full suite without filtering.

**Re-evaluation triggers.**
- If GitHub adds GPU runners to the Pro free quota, revisit.
- If self-hosting a GPU runner becomes operationally cheap, revisit.
- If a class of bugs starts escaping to publicly-visible artifacts
  because pre-push is skipped on a tired evening, tighten enforcement
  (e.g., require GPU-test-passed-on-this-commit metadata at push).

---

## D005 — Lean as Phase-2+ formal-verification track (2026-05-01)

**Decision.** Adopt **Lean 4 + mathlib4** as the formal-verification
track for `sicm_modernized`. A new committed file `REQUIREMENTS.md`
(landed separately) carries formal requirements derived from the
DECISIONS log; each requirement may be discharged by any combination
of three verification kinds:

- `verification_refs` — executable tests (empirical, sampled inputs)
- `proof_refs` — Lean theorem names (formal, all inputs satisfying
  hypotheses)
- `implementation_refs` — code locations realizing the requirement

`proof_refs` is the new ref-kind introduced by this decision. Its
audit-gate semantics: each name must resolve to a `theorem` /
`lemma` / `def` in the project's Lean code, and the file must
compile under the pinned Lean+mathlib toolchain.

**Rationale.**

The project's academic posture — action-principle keystone, the
MIT 6.946 lineage we believe was last offered in Fall 2024 (cf.
project memory `mit_course_retirement.md`; not independently
re-verified against an authoritative MIT source as of this entry),
FDG/GR/QM phase arc — makes formal verification a natural and
load-bearing differentiator, not a luxury.
A textbook that ships with mechanically-verified theorems alongside
empirical tests carries a stronger claim than one that ships with
either alone. Concretely:

- Tests bound `|H_numerical - H_analytical|` over 1000 sampled
  initial conditions. A Lean theorem can establish the *bound itself*
  over all initial conditions in some characterized set.
- "δS = 0 implies the Euler-Lagrange equations" is a textbook
  derivation today. As a Lean theorem under mathlib's differential-
  geometric machinery, it becomes a mechanically-checked artifact
  the project ships.
- Symplectic-integrator backward error analysis (perturbed
  Hamiltonian H̃ = H + O(h^p), exact preservation of H̃, bounded
  drift in H over exponentially long times) is exactly the kind of
  numerical-analysis claim that empirical sampling cannot establish.
  Whether a clean Lean discharge is *achievable* at mathlib's current
  state is a separate question from whether the goal is right.

**Methodology lineage.** The traceability chain
`DECISIONS.md → REQUIREMENTS.md → {tests, proofs, code}` is
re-derived from fireasmserver's requirements-from-decisions pattern,
extended with the `proof_refs` dimension specific to this project's
academic scope. Per global "principles transfer; processes do not":
the chain abstraction transfers; the specific REQ category prefixes,
audit-tool wiring, and Lean+mathlib toolchain integration are
project-local.

**Scope of this decision.**

In scope:
- Adoption of Lean 4 + mathlib4 as the formal-verification toolchain.
- Reservation of a `proofs/` directory at repo root for Lean code.
- Reservation of the `proof_refs: tuple[str, ...]` field on REQ
  entries (and, optionally, ontology nodes) for theorem-name
  back-pointers.
- Phase-1 use limited to **theorem statements without proofs**
  (`sorry`-bodied stubs). The forcing function of writing the
  precise statement against mathlib's types is itself valuable
  even before the proof discharges.
- Phase-2 (geometric machinery) onward: proofs discharged for
  theorems that benefit, prioritizing those where mathlib's
  differential-geometry coverage already supports the lemmas.

Not in scope (deferred to later D-N entries):
- The exact mathlib version pin and update cadence.
- The CI strategy for Lean compilation (it can be slow; cache
  strategy + when to recompile from clean is its own design).
- The ordering of which theorems get proven first.
- The shape of Lean-Racket bridge code (if any). Bridging is
  orthogonal to verification — Lean proves properties, Racket
  computes; the proofs constrain what the computations are
  allowed to deviate from, but the proofs themselves don't run
  numerically.
- The exact spelling of `proof_refs` entries — bare theorem name
  vs. fully-qualified path (`Sicm.Mechanics.Lagrangian.foo`) vs.
  `(module, name)` tuple. The `tuple[str, ...]` shape is
  reserved here for the field, but the per-entry namespacing
  convention is left to a later D-N once enough Lean code exists
  to know what disambiguation actually needs to carry. Bare names
  collide across modules; that's known and will be addressed
  before any cross-module references land.

**Honest cost ledger.**

- A new toolchain (`lake` build system, `lean-toolchain` pin,
  mathlib4 dependency) sits alongside Python/Racket/CUDA-C.
- mathlib4 compiles slowly (gigabytes of `.olean` cache); a clean
  CI rebuild is minutes-long even on warm caches.
- Mathlib coverage is uneven for physics-specific structures.
  Differential forms / exterior derivative and Riemannian metrics
  have nontrivial coverage. Symplectic geometry as a developed
  theory (Darboux, moment maps, symplectic reduction) is
  thin-to-absent at the time of this entry; specific
  symplectic-integrator lemmas, path-integral measure theory, and
  any QFT path-integral construction are absent. Phase-2 work
  will need to contribute auxiliary lemmas; this is expected, not
  a blocker.
- The maintainer's formal-math skill axis is a documented constraint
  (project memory `tutoring_required.md`); Lean proof work will lean
  heavily on AI assistance. This is real but tractable; the alternative
  (no formal verification) leaves the academic claim weaker.

**Re-evaluation triggers.**
- If Lean+mathlib compilation costs become a CI bottleneck not
  cleanly mitigated by caching, revisit.
- If the proof-discharge skill burden outpaces what Ed + AI can
  sustainably carry, scope down to theorem-statement-only work
  permanently and seek community contributions for proof bodies.
- If a sibling project adopts Lean for a similar reason, revisit
  whether a shared toolchain extraction is appropriate (per
  `python_agent`-style abstraction discovery).
- If mathlib's physics coverage matures to the point where symplectic
  integrator backward-error analysis becomes routine, accelerate
  Phase-2 proof targets.

**Companion artifacts (landing alongside this decision).**
- `tooling/src/audit_ontology/` package stub — gives the eventual
  audit work a real home and resolves the `pyproject.toml` coverage
  source reference that was previously unbacked.
- The `proof_refs` field on REQ entries lands when REQUIREMENTS.md
  itself lands (separate first-torque pass per the engine-head
  bolt-tightening discipline).
