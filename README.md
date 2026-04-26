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
