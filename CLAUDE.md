# sicm_modernized — project-local Claude instructions

Computational classical mechanics, general relativity, and quantum mechanics, organized around the action principle as the unifying object. Modernizes Sussman & Wisdom's SICM and FDG using Racket CS (Chez backend) on top, Python + JAX as test oracle and prototyping layer, and CUDA C for production GPU kernels.

## Start here
- `PROJECT_NOTES.md` — full design exploration from the 2026-04-25 kickoff conversation. The action-principle keystone (§10), the four-phase project arc (§11), and the language/architecture decisions live there. Read it before making any architectural recommendation.
- `DECISIONS.md` — immutable architectural decision log (D001+). Supersession-tracked per global convention; never edit prior entries.
- `~/.claude/projects/-home-ed-sicm-updated/memory/` — durable project memory. Pointers to PROJECT_NOTES.md and the action-principle keystone live here.

## Mode
**CD-first deliverable** per global `~/.claude/CLAUDE.md`. Full quality-gate machinery (lint + typecheck + test + branch coverage + ontology audit + review) is set up before functional code lands. The project has a publishable trajectory across four textbook-sized phases (classical → geometric machinery → GR → QM), each a usable artifact on its own.

This contrasts with silicritter's experimental mode: identical code-quality bar, but with full CD pipeline + Makefile + GitHub Actions + ontology DAG from day one.

## Methodology lineage
The discipline (ontology DAG, audit tool, two-tier gate split, Pydantic + YAML pattern, hooks layout) is **re-derived** from iomoments and fireasmserver, not copy-pasted and not forked from `python_agent`. Per the global "principles transfer; processes do not" rule. As the third independent re-derivation across the trio, the surviving abstractions become candidates for eventual extraction into a shared toolkit.

## Language stack
- **Racket CS** (Chez backend, default since ~2020) — symbolic top: Lagrangian construction, functional `D`, generic arithmetic, FDG manifold/form apparatus. The "executable mathematical notation" layer in the spirit of scmutils.
- **Typed Racket** — numerical mid-layer where Racket needs C-equivalent speed. TR auto-lowers to `unsafe-fl+` etc. when types are known. `racket/unsafe/ops` is the escape hatch of last resort.
- **Python 3.11+** — ontology infrastructure (Pydantic + YAML), test orchestration, JAX reference implementations.
- **JAX[cuda12]** — independent test oracle and rapid prototyping vehicle. Validates production CUDA C kernels via cross-implementation comparison ("isolate what you test"). Same role JAX plays in silicritter.
- **CUDA C** — production GPU kernels for the hot path (ensemble integration, Lyapunov spectra, path-integral Monte Carlo). Compiled with `nvcc`; lint via `clang-format` and (optionally) `clang-tidy` with CUDA support.

## JAX role
**Hybrid (option C)**: JAX is for prototyping and as an independent reference oracle. CUDA C is the production hot path, validated against the JAX reference. Two implementations of the same numerics, deliberately maintained for cross-checking. Decided 2026-04-25; see DECISIONS.md D003.

## GPU policy
**GPU runs locally only.** Never in CI. GitHub Pro does not include GPU runners (Linux 4-core GPU runner is $0.052/min, not justified for this project's test cadence). Tests that require GPU are tagged and gated at pre-push. CI runs on standard Linux runners and skips GPU-tagged tests. Decided 2026-04-25; see DECISIONS.md D004.

## Physics correctness — project-critical, not optional
Ed's undergraduate physics is rusty (showboated through it ~25+ years ago). The SICM books are peer-tested through 20+ years of MIT students; with Sussman & Wisdom's MIT 6.946 retiring after Fall 2024, this project carries the burden of physics correctness without active author engagement. Treat tutoring on physics as **load-bearing risk mitigation**, not a side detour. A physics-PhD reviewer is required in the loop before any phase ships publicly. See `~/.claude/projects/-home-ed-sicm-updated/memory/tutoring_required.md` for the full framing.

## Math correctness gates (SICM-specific)
Beyond standard linting and unit testing, the project requires verification cases for:
- Energy drift bounded over N orbits of known integrable systems
- Time-reversal symmetry: forward T steps + backward T steps must return to origin within ulp-bound
- Symplectic 2-form preservation (Jacobian determinant = 1 to numerical precision)
- Comparison against analytical solutions (harmonic oscillator, free particle, Kepler)
- JAX-reference comparison as cross-implementation oracle
- (When QM lands) Path-integral classical limit: stationary-phase recovery as `ℏ → 0`

## Code-review discipline

Code review (Gemini, clean-Claude subagent, or any independent review)
produces findings. **Triage decisions belong to Ed.** Claude's job is
to:

1. Surface every finding with a recommended disposition
   (fix / defer / reject) and a one-line rationale.
2. Stop and wait for Ed's explicit call on each finding.
3. Apply only the dispositions Ed has approved.

This applies to all severities, including LOW. "Premature
optimization," "matches existing pattern," and "doesn't matter at
our scale" are reasoning Claude can offer — never reasoning Claude
can use to skip surfacing the decision. Until the Day 2a.5
automation lands, this rule is enforced by Claude's own discipline
and Ed's review of triage tables.

Origin: established 2026-04-26 after Claude triaged seven Day 2a
findings unilaterally before Ed reviewed.

## License and posture
sicm_modernized is licensed **GNU AGPL-3.0-or-later**. Ed Hodapp is sole author and sole copyright holder. **No external contributions accepted** — preserves consolidated copyright ownership so Ed retains relicensing flexibility. Commercial users who cannot accept AGPL's §13 network-copyleft route to Ed for a commercial license / consulting engagement.

## Downstream directionality
Per global convention (~/PRODUCTS.md): code flows FROM BSD-licensed projects (e.g., ws_pi5) INTO proprietary sibling projects, but never the reverse. sicm_modernized is AGPL, not BSD; it cannot be pulled into proprietary sibling projects without violating the AGPL. It can serve as reference / teaching material for Ed's proprietary projects, but code does not flow from sicm_modernized into proprietary repos without Ed explicitly relicensing (which he can do unilaterally as sole copyright holder).
