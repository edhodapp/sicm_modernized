# SICM, Modernized: Design Exploration

A design conversation between Ed Hodapp and Claude (Opus 4.7) on
2026-04-25, at project kickoff.

This document captures the full exploration: from the initial idea
through the Feynman/least-action keystone realization that reorganizes
the project's architecture. It is the kickoff record, not a decisions
log. Decisions, when made, will go into a separate `DECISIONS.md`
following the standard ADR-style convention.

---

## 0. Premise

Update *Structure and Interpretation of Classical Mechanics*
(Sussman & Wisdom) using **Racket** (specifically Racket CS, the
Chez-backed default since ~2020) and **CUDA**.

Working directory: `/home/ed/sicm_updated/` (greenfield).

Ed's relevant context:
- 1st edition of SICM on the bookshelf.
- Undergraduate physics taken but rusty — "I aced it, but as a
  consequence I don't remember much." Tutoring is part of the
  collaboration, not a side detour.
- High-ideation, multi-project pattern; this thread is exploratory.

---

## 1. Initial framing

The natural shape is a **two-layer stack**:
- **Top:** Racket on top, inheriting scmutils's functional-
  differentiation + generic-arithmetic abstractions (the *whole point*
  of SICM as a computational notation).
- **Bottom:** CUDA underneath, for the embarrassingly parallel
  numerics — trajectory ensembles, Poincaré sections, Lyapunov
  spectra, phase-space Monte Carlo.

The interesting "update" angle is **not** replacing the symbolic core;
it is making chaos exploration *interactive* by pushing 10⁶ initial
conditions through a symplectic integrator in real time.

**Tradeoff to flag at the outset:** Sam Ritchie's `sicmutils`
(Clojure/JVM, now part of the Mentat Collective) is the
actively-maintained scmutils descendant and has a substantial user
base. Choosing Racket means re-deriving that work, with the payoff
being Racket's language-oriented-programming machinery (contracts,
`#lang`s, Typed Racket) which arguably fits Sussman's "executable
mathematical notation" thesis better than the JVM does.

---

## 2. CUDA-wins inventory for SICM's problem set

Mapping SICM's computational workloads to where GPU acceleration
genuinely pays off vs. where it is a poor fit.

### 2.1 Strong wins — embarrassingly parallel, SIMT-friendly

1. **Trajectory ensembles — the headline win.** Integrate N initial
   conditions through the same Hamiltonian flow in lockstep. Each
   thread = one IC. Same RHS, divergent state. The canonical
   warp-friendly workload.
   - *SICM use:* Ch. 3 (Hamiltonian mechanics) chaos exploration —
     driven pendulum, double pendulum, restricted 3-body. Texts show
     1–10 trajectories; GPU shows 10⁶ at 60 Hz.
   - *Pedagogical payoff:* "sensitive dependence on initial
     conditions" stops being a phrase and becomes a *visible*
     phenomenon as a Gaussian blob of ICs shears and folds in real
     time.

2. **Poincaré section construction.** Integrate ensemble until each
   trajectory crosses the section plane *k* times, log the crossings.
   Per-thread event detection, no inter-thread communication.
   - *SICM use:* Ch. 3.6, Hénon-Heiles, standard map. Currently a
     slow batch job; becomes interactive.

3. **Lyapunov spectrum.** Per-IC: integrate state + variational
   equation (or N tangent vectors with periodic Gram-Schmidt). Each
   IC independent — one block per IC, threads handle the
   tangent-vector reorthogonalization.
   - *SICM use:* quantifying chaos in Ch. 3. Computing a Lyapunov
     *map* over a 2D parameter slice (1024×1024 = 10⁶ points) is a
     natural extension the book gestures at but does not pursue
     because it was infeasible.

4. **Surface-of-section / basin-of-attraction maps.** Color a 2D
   grid of ICs by long-term behavior (which attractor, escape time,
   winding number). One thread per pixel. Trivially parallel,
   visually striking.

5. **Monte Carlo phase-space sampling.** Microcanonical-ensemble
   averages, Liouville-measure integration over energy shells.
   cuRAND + per-thread sample + reduction.

6. **Action-angle coordinate computation by FFT.** For integrable /
   near-integrable systems: integrate, FFT the trajectory, extract
   frequencies. cuFFT is mature.

### 2.2 Moderate wins — parallelism exists, care needed

7. **Symplectic integrator inner loops on a single trajectory.** For
   high-dimensional systems (N-body, field theories discretized to
   lattices), the *force evaluation* parallelizes over particles /
   sites even within one trajectory. Less relevant for SICM's
   pedagogical low-D systems; very relevant if the update extends
   into many-body chaos.

8. **Variational integrator assembly.** Discrete Lagrangian on a
   spacetime mesh — local stencils, GPU-friendly, but SICM treats
   this lightly.

9. **Sensitivity analysis / parameter sweeps.** Same problem as
   ensembles but parameterized over coupling constants instead of
   ICs. Same SIMT pattern.

### 2.3 Poor fits — do NOT push to GPU

10. **Symbolic differentiation (`D`) and simplification.** The whole
    `scmutils` symbolic core — tree-walking, pattern matching, term
    rewriting — is branch-heavy, pointer-chasing, irregular. Belongs
    on the CPU in Racket. Trying to GPU-ify this is a classic
    training-data trap (sounds parallel; isn't).

11. **Generic arithmetic dispatch.** Runtime type dispatch over the
    tower (number → function → structure → matrix → differential).
    CPU work.

12. **Single short trajectory, low dimension.** A 4D double-pendulum
    integrated for 1000 steps is faster on the CPU than the
    kernel-launch + memcpy round-trip. GPU only wins when N (ensemble
    size) × T (trajectory length) is large.

13. **Adaptive step-size with per-trajectory step decisions.** Warps
    diverge when one IC needs a small step and its neighbors don't.
    Mitigations exist (per-warp clustering, fixed-step + Richardson)
    but it is a real hazard. Use fixed-step symplectic methods where
    possible — which is what SICM teaches anyway, so the alignment
    is fortunate.

### 2.4 The architectural implication

The two-layer split is not arbitrary — it falls out of where the
parallelism actually lives:

```
Symbolic Lagrangian → D → Hamiltonian → JIT-compiled vector field RHS
    ↓
GPU kernel does the ensemble work
    ↓
Results flow back for plotting/analysis
```

The handoff is at the *numerical RHS*, which is exactly the boundary
scmutils already establishes (the symbolic system produces a callable
numeric procedure).

So the update is not "rewrite SICM in CUDA" — it is "preserve the
symbolic top, replace the lonely-CPU-trajectory bottom with a GPU
ensemble engine, and let the pedagogy expand into the regimes the
original book could not visit because the hardware was not there."

---

## 3. State of Racket / Scheme scmutils ports

### 3.1 Racket-specific landscape

- **`bennn/mechanics`** — the canonical Racket port. Started by Ben
  Greenman (Northeastern, the typed-Racket / contract-research
  group). 96 commits, 12 open issues, 37 stars, **no releases**,
  README says "UNDER CONSTRUCTION." Stalled. Exists as a starting
  point, not a foundation to build on without significant
  excavation.

- **Racket-users thread (July 2018)** led by Alex Gian, with input
  from Jens Axel Søgaard (`racket-cas`), Ben Greenman, Philip
  McGrath, and Matthias Felleisen. Got to "coming on well, almost
  working" — then went quiet. The valuable artifact is the
  **technical postmortem**:
  - *Blocker that mattered:* circular module dependencies between
    `generic.rkt`, `ghelper.rkt`, `types.rkt`. The scmutils
    generic-arithmetic system has bidirectional registration (types
    know about operators, operators know about types). MIT Scheme's
    loose load semantics absorb this; Racket's strict module system
    does not.
  - *Suggested fix:* Racket's unit system, or explicit setter-based
    lazy registration.
  - *Planned layering* (worth inheriting): structured objects →
    generic operators + literals → simplifier → calculus / autodiff →
    mechanics.

- **`soegaard/racket-cas`** — not a SICM port; a general Racket CAS
  by Jens Axel Søgaard. Has symbolic simplification, Taylor series,
  limits. Provides primitives but does not have scmutils's *defining*
  abstractions (functional `D`, up/down tuples, generic arithmetic
  over functions, Lagrangian/Hamiltonian apparatus). Useful as a
  pattern reference, not a substrate.

### 3.2 Non-Racket Scheme ports — for comparison

- **`alexgian/guile-scmutils`** — Guile port based on Daniel Gildea's
  earlier work. Closer to the original than any Racket effort.
  Documented gotcha: Guile lacks MIT Scheme's *apply hooks*, so
  some glue is needed for book examples. Useful as a translation
  reference *because* it documents the MIT-Scheme-isms that don't
  translate cleanly.

- **`fedeinthemix/chez-scmutils`** — Chez Scheme port. Less prominent
  than the Guile port. Chez has a strong numerics story; ecosystem
  is smaller than Racket's.

- **`sicmutils/sicmutils` (Clojure)** — Sam Ritchie + Colin Smith.
  **The actively-maintained port that filled the vacuum.** This is
  the bar. Clojure choice is pragmatic: persistent data structures,
  JVM ecosystem, ClojureScript for browser visualization, and
  Clojure's loose macro / multimethod system handles the
  generic-arithmetic registration problem more naturally than
  Racket's strict modules do. Mentat Collective ecosystem
  (`emmy-viewers`, etc.) builds on it.

### 3.3 Honest read

- No actively-maintained Racket scmutils port exists.
- Two serious attempts (`bennn/mechanics`, Gian's 2018 effort) both
  stalled, each leaving useful artifacts but neither a working
  foundation.
- The Clojure port consolidated the community in the gap.
- The recurring stall point is structural: scmutils's
  generic-arithmetic registration cycle fights Racket's strict
  module system. Anyone restarting must commit up front to a
  resolution strategy (units, explicit two-phase init, or rethink
  the dispatch architecture using Racket's `#lang` machinery).

### 3.4 Three viable paths

1. **Use `sicmutils` (Clojure) and add a CUDA layer via JNI.** Lowest
   risk, highest ecosystem, but you have bought into Clojure / JVM
   and the tradeoff against Racket's notation-as-language thesis.
2. **Salvage `bennn/mechanics`, finish it, build CUDA on top.**
   Medium risk. You inherit unfinished work and 12 open issues you
   did not write.
3. **Greenfield Racket port, commit to a chosen module-dependency
   strategy from day one.** Highest risk, but the *only* path that
   gets the full payoff of Racket-as-host (typed boundaries, `#lang
   sicm`, contracts, language-oriented mechanics). The 2018 thread
   is a free design review of what fails — re-derive, do not
   copy-paste, but absorb the lessons.

---

## 4. Racket-on-Chez (Racket CS) clarification

### 4.1 The transition

Racket switched its default runtime to Chez Scheme in 2020 (Racket
7.7 / 8.0 era). The variant is "Racket CS" — Racket's surface
language and module system, but compiled and executed atop a Chez
backend rather than the legacy C-based runtime ("Racket BC"). As of
current Racket releases, **Racket CS is the default and Racket BC is
deprecated**. Matthew Flatt drove this — Chez gives Racket better
numerics, better GC, and a more solid foundation than the homegrown
C runtime ever had.

The switch is essentially invisible at the source-program level —
`#lang racket` code runs unchanged — but it changes the strategic
picture for this project.

### 4.2 Consequences for the SICM port question

- **The "Chez vs Racket" choice partially collapses.** When you run
  Racket today, you are already running on Chez.
- `fedeinthemix/chez-scmutils` is no longer a *separate ecosystem*
  from Racket — it runs on the same VM Racket targets. In principle
  you could call into it from Racket via FFI or by embedding it as
  a Chez sub-language, though there is friction (Chez's library
  system vs Racket's module system, R6RS vs `#lang`).
- **The numerics-performance argument that historically favored Chez
  over Racket is gone.** Racket CS gets Chez's numeric tower, fast
  unsafe ops, and codegen quality. So "use Chez for the heavy
  lifting" does not buy you anything Racket CS does not already
  have.
- **The module-cycle problem from the 2018 thread is unchanged.**
  That was a Racket *language-level* issue (strict module system,
  phased initialization), not a runtime issue. The architectural
  blocker that stalled `bennn/mechanics` is still there.
- **One concrete new option opens up:** *port directly to `#lang
  racket` on Racket CS, and where you genuinely need raw Chez
  performance (e.g., the symplectic integrator's RHS before it goes
  to GPU), drop into `racket/unsafe/ops` or use Racket's FFI to a
  hand-written Chez or C kernel.* You get Racket's
  notation/language-oriented machinery on top, Chez's numerics
  underneath, and CUDA at the bottom. Three layers, one runtime for
  the top two.

### 4.3 Revised path picture

The three paths from §3.4 mostly hold, with sharpened framing:

1. Clojure `sicmutils` + CUDA via JNI — same as before.
2. Salvage `bennn/mechanics` on Racket CS — same code, runs faster
   than when written. Does not fix the architectural debt.
3. **Greenfield Racket CS port** — now the most honest framing of
   this option is *"Racket-on-Chez port,"* and it dominates a
   hypothetical "pure Chez port" because you get Chez's numerics
   *plus* Racket's module / macro / contract / `#lang` machinery.
   There is no longer a tradeoff between "modern Racket tooling"
   and "Chez's runtime quality" — you get both.

The Clojure-vs-Racket-CS question is now mostly about
**macro/dispatch semantics and ecosystem**, not performance:
- *Clojure advantage:* multimethods + protocols + the JVM ecosystem
  (visualization, ML libs) handle the generic-arithmetic dispatch
  loosely and naturally.
- *Racket-CS advantage:* `#lang` lets you build SICM-as-a-language
  in a way Clojure structurally cannot, plus typed/untyped contract
  boundaries.

The real choice is on language-design grounds, not runtime grounds.

---

## 5. Consequences of `racket/unsafe/ops`

### 5.1 What it is

`racket/unsafe/ops` exposes unchecked variants of arithmetic and
data-structure primitives — `unsafe-fl+`, `unsafe-fl*`,
`unsafe-flvector-ref`, `unsafe-fx+`, `unsafe-vector-ref`,
`unsafe-struct-ref`, etc. They strip three things the safe versions
do:

1. **Type dispatch.** Safe `+` handles fixnum, flonum, rational,
   complex, bignum. `unsafe-fl+` assumes both args are flonums and
   goes straight to a `double` add.
2. **Bounds checks.** `unsafe-vector-ref` skips the index-in-range
   check.
3. **Overflow checks.** `unsafe-fx+` does not promote to bignum on
   overflow — it wraps or corrupts.

The name is honest. Pass a non-flonum to `unsafe-fl+` and you do not
get a contract violation. You get memory corruption, a segfault, or
— worst case — a plausible-looking wrong answer.

### 5.2 The honest tradeoff

You buy **C-equivalent inner-loop speed**. You pay with **type
discipline that the language no longer enforces**. The compiler
trusts you; if you are wrong, the failure mode is nasal-demons, not
an exception.

Fine for hot kernels under tight discipline. NOT fine sprinkled
through a 10k-line library.

### 5.3 Racket CS narrows the gap

On the old Racket BC runtime, `unsafe-fl+` versus `+` for float work
was often **5–10× faster** on tight loops. On Racket CS (Chez
backend), Chez's compiler unboxes flonums aggressively when it can
prove the types. The safe-vs-unsafe ratio is now closer to **1.5–3×**
for typical numeric loops — sometimes flat.

You reach for `unsafe-ops` only when profiling says you have to, not
reflexively. For most code Chez's safe path is competitive.

### 5.4 Typed Racket is usually the right answer

The clean modern pattern: **don't write `unsafe-ops` directly —
write Typed Racket.** When TR can prove operand types are `Float`,
it lowers to `unsafe-fl+` automatically. You get the speed without
giving up the type guarantee:

```racket
#lang typed/racket
(: rhs (-> Float Float (Values Float Float)))
(define (rhs q p) (values p (- (sin q))))
```

TR emits unsafe ops under the hood. If you violate the contract,
you get a *type error at compile time*, not a segfault at runtime.
Strictly better than hand-rolled `unsafe-ops` for any code that
lives more than a week.

You drop to literal `racket/unsafe/ops` only when:
- TR cannot prove what you know to be true (inference limits)
- You are working with raw memory views (e.g., a `cpointer` to
  GPU-mapped host memory)
- You need ops Typed Racket does not surface

### 5.5 The boundary-crossing cost — the real architectural concern

When typed code calls untyped code or vice versa, Racket inserts
**contract checks at the boundary** to enforce TR's invariants
against untyped callers. Expensive per call (microseconds), and
invisible until you profile.

The rule: **the typed/untyped boundary must be crossed at
analysis-construction time, not at integrator-tick time.**

- WRONG: symbolic top calls typed RHS once per timestep — boundary
  cost dominates, you have lost everything `unsafe-ops` won.
- RIGHT: symbolic top *compiles* a typed RHS module once, that
  module integrates 10⁵ steps internally, returns a trajectory.
  Boundary crossed twice per analysis.

This is the SICM-specific architectural pressure. Each Lagrangian →
Hamiltonian → vector-field-RHS pipeline must end in a *frozen,
typed, performant function* that the integrator can call without
re-crossing the boundary on every tick.

### 5.6 CUDA changes the calculation again

Once the inner-loop float work moves to GPU, `unsafe-ops` for *that*
work drops to near-zero importance — the kernel runs in CUDA C, not
Racket. What `unsafe-ops` (or really, Typed Racket) is for, on the
CPU side, is:

- The **CPU reference integrator** — needed for verification,
  ground-truth comparison, and low-N debugging where kernel-launch
  overhead dominates.
- **Per-launch orchestration:** assembling input buffers,
  post-processing output, adaptive-step decisions not pushed to GPU.
- **Reductions and aggregations** over GPU output (e.g., computing
  Lyapunov exponents from logged tangent-vector norms) when the
  reduction is too small for GPU but still in a tight loop on CPU.

CPU-side hot path is *narrower* than in a pure-CPU port. Most
CPU-side numeric code becomes "shape data, hand to GPU, receive
results, summarize." Typed Racket pressure stays real but localized.

### 5.7 The discipline cost

The maintenance hazard with `unsafe-ops` is not writing them — it
is the next person changing them.

A code change that subtly violates the implicit type contract
produces *no error*. Tests pass. CI is green. Wrong answers may
even look plausible — slightly off energy conservation looks like
ordinary integrator drift. You discover the bug six months later
when a paper reviewer notices.

**Mitigations, in order of effectiveness:**

1. Don't write raw `unsafe-ops`. Use Typed Racket.
2. Confine the unsafe region to one small module. A 50-line file is
   reviewable; a 5000-line file with `(require racket/unsafe/ops)`
   at the top is a liability surface.
3. Property-test the unsafe path against a safe reference path.
   Same RHS, integrate a known orbit, check positions and conserved
   quantities match to ulp-level over short trajectories. Match
   observable behavior, not just compile-time types.
4. Energy-drift / symplectic-invariant monitoring as a runtime
   canary. For a Hamiltonian system, energy should drift in a
   bounded way under symplectic integration. A sudden non-physical
   jump is a flag.

### 5.8 Numerics-correctness gotchas specific to chaos work

- `unsafe-fl+` does not trap NaN or inf. If a trajectory enters a
  singular region (3-body close approach, pendulum at the
  separatrix) and produces a NaN, it propagates silently. Per-
  trajectory NaN guards at the analysis level.
- Denormals will quietly tank performance on some hardware. For
  ensemble work, one trajectory hitting denormals can drag the
  whole warp / CPU loop down. Standard mitigation: flush-to-zero
  mode, or pre-bound state magnitudes.
- `unsafe-flvector-ref` with an out-of-bounds index reads adjacent
  memory. In a long ensemble run sized by user input, this turns
  "I changed the integrator" into "the program now silently
  corrupts other trajectories' state." Bounds checks at *outer*
  loop entry, unsafe access in the *inner* loop.

### 5.9 Recommended layering

```
┌─────────────────────────────────────────────────────────┐
│  #lang racket   — symbolic Lagrangian / D / simplify    │  untyped, generic, slow OK
│           ↓ (compiles to)                               │
│  #lang typed/racket   — RHS kernels, integrator         │  TR → auto unsafe-fl
│           ↓ (FFI)                                       │
│  CUDA C kernels   — ensemble integration, Lyapunov      │  GPU does real work
│           ↑ (results)                                   │
│  #lang typed/racket   — reduction, analysis             │
│           ↑                                             │
│  #lang racket   — plotting, REPL, notation              │
└─────────────────────────────────────────────────────────┘
```

Two boundaries (symbolic→typed, typed→CUDA), each crossed once per
analysis. Inside each layer, no further boundary cost.
`racket/unsafe/ops` is reserved as an escape hatch for the few
places Typed Racket cannot infer what you know — used with the same
discipline as inline assembly. **Last tool reached for, not first.**

The thing to internalize: on Racket CS the question is not "safe vs
unsafe," it is **"can the compiler see the types?"** Typed Racket is
the mechanism for making the answer yes.

---

## 6. Has this been done?

### 6.1 Honest answer

**Not as a unified project.** Components exist scattered across
other ecosystems.

### 6.2 The pieces, individually

- **Racket + CUDA bindings.** DeepRacket (Charles Earl, Automattic,
  RacketCon 2017) — Typed Racket + Math + FFI wrapper for CUDA aimed
  at deep-learning workloads. Single-purpose, no signs of active
  maintenance. Beyond that, no general-purpose Racket CUDA bindings
  as a published package. Racket's FFI is mature enough that binding
  to CUDA's C runtime API is straightforward, but **nobody has
  published the substrate for you**. You write that layer.

- **scmutils-style symbolic Lagrangian/Hamiltonian apparatus.** Done
  well in Clojure (`sicmutils`, actively maintained). Done partially
  in Racket (`bennn/mechanics`, stalled). Not done in Racket and
  combined with anything GPU-related.

- **GPU symplectic integration as a research artifact.** Extensive
  astrophysics literature, all in CUDA C/C++:
  - **QYMSYM** (Moore & Quillen 2011, *New Astronomy*) — hybrid 2nd-
    order symplectic, switches to Hermite for close encounters.
  - **FROST** (Rantala et al. 2021, *MNRAS*) — hierarchical 4th-
    order forward symplectic, momentum-conserving, large dynamical
    range.
  - **NbodySimGPU** — Rein-style operator splitting on GPU.
  - **Charged particles around Kerr black holes** (Wu, Wang et al.
    2021, *EPJ C*) — explicit symplectic methods for studying chaos
    in non-integrable Hamiltonian systems on GPU.

  These are research codes for specific astrophysical problems —
  N-body, accretion, relativistic chaos. None has a high-level
  symbolic frontend, none was built for pedagogy. You inherit
  *kernel-design knowledge* from this literature, not the codebase.

- **GPU ensemble ODE integration with high-level frontend.** This is
  `DiffEqGPU.jl` in Julia's SciML ecosystem — closest existing
  analogue to the bottom-and-middle layers of what we are
  describing.

### 6.3 The Julia / SciML question — take this seriously

The honest competitive picture: **Julia + ModelingToolkit.jl +
DiffEqGPU.jl is doing approximately the bottom 80% of what was
sketched, well, today, with a large active community.**

- `ModelingToolkit.jl` — Julia symbolic Lagrangian/Hamiltonian
  capabilities (CAS-level), JIT-compiles symbolic systems to fast
  numeric RHS functions.
- `DiffEqGPU.jl` — runs ensembles of those compiled RHS functions
  across GPU initial conditions / parameter sweeps. Exactly the
  "10⁶ trajectories in parallel" workload from §2.1.
- The composition is clean — symbolic top, GPU bottom, JIT-compiled
  RHS as the handoff. Same architecture as the Racket version.

**What Julia does NOT have, and what justifies the Racket project:**

1. **SICM as a pedagogical lineage.** Julia/SciML is research-
   tooling-first. ModelingToolkit's symbolic apparatus is general
   CAS, not the specific scmutils orientation: functional `D`
   operating on procedures, up/down tuples for Einstein-notation
   extension, the *Functional Differential Geometry* manifold/form
   apparatus, the deliberate equational-reasoning discipline of the
   Sussman-Wisdom books. The whole point of scmutils is that a
   Lagrangian *literally is a function*, written using the same
   notation a student reads in the book. Julia does not preserve
   that.
2. **Language-oriented programming for the textbook.** Racket's
   `#lang` machinery lets you build `#lang sicm` where the surface
   syntax matches the textbook. Julia's macro system can do a lot,
   but it cannot replace the host language's parser the way Racket
   can. The textbook-as-executable-environment thesis is
   structurally a Racket fit, not a Julia fit.
3. **Contracts at the typed/untyped boundary.** Racket's contract
   system offers a principled story for what happens when symbolic
   (untyped, generic) code meets numeric (typed, fast) code. Not
   just performance — correctness. Julia's type system is more
   uniform but does not have an equivalent boundary discipline.

### 6.4 The strategic question

If the project's goal is *general-purpose GPU classical-mechanics
tooling*, you would be reinventing what Julia already does well.

If the project's goal is *pedagogical: a successor to the SICM books
that updates them for a generation of students who have a GPU on
their laptop*, this is uncontested ground worth taking. Only a Lisp
with a hookable reader and module language can be the substrate.
Julia structurally cannot. Clojure structurally cannot.

This question — pedagogy vs research tooling — determines almost
every architectural decision downstream. **Default: pedagogical
instrument.**

---

## 7. SICM 3rd edition — what we can find

### 7.1 No active 3rd edition

I see no public indication that a 3rd edition is in active
preparation. The 2nd edition (2014) appears to be canonical.

### 7.2 The big news

**MIT 6.946 (Classical Mechanics: A Computational Approach) — the
course Sussman & Wisdom built SICM around — is being taught for the
LAST TIME in Fall 2024.** Announced directly on the course page
(`groups.csail.mit.edu/mac/users/gjs/6946/`). After Fall 2024 the
course retires.

The course was the organism that fed the books — student exercises,
errata, new chapters in the 2nd edition, the FDG companion. With the
course winding down, the natural feedback loop that would produce a
3rd edition is closing.

Both authors are at the natural end of long academic careers —
Sussman is 78, Wisdom is in his early 70s. Sussman is still active
(Taylor L. Booth Education Award 2023, FSF board, occasional
RacketCon talks) but the course retirement reads as deliberate
scaling back, not as runway for a new edition.

### 7.3 What is alive

- **2nd edition (2014)** + **Functional Differential Geometry
  (2013)** — canonical body of work. MIT Press editions are stable.
- **scmutils itself** — still maintained at MIT; differential-
  geometry capability automatically included in the latest version.
  Not abandoned, but not evolving aggressively.
- **`sicmutils` (Clojure)** — effectively the active development
  front for the *ideas* in scmutils. New mathematical capabilities
  (better simplification, autodiff enhancements, ClojureScript
  visualization) appear there, not in MIT scmutils.
- **The Mentat Collective ecosystem** around `sicmutils`
  (`emmy-viewers`, Nextjournal notebooks) — closest thing to a
  living "SICM development frontier" today.

### 7.4 Strategic implications

The pedagogical-vacuum framing from §6.4 just got sharper.

**Opportunity:**
- An updated SICM treatment that adds modern infrastructure (GPU
  ensembles, interactive visualization, language-as-notation via
  `#lang sicm`) sits in genuinely uncontested space — original
  authors will not do it, Clojure community is not focused on
  textbook-shaped artifacts, Julia/SciML is research-tooling-first.
- "Update SICM for the GPU era" is a project an aging author body
  would *welcome* if done with care and respect for the original.
  Worth eventually reaching out to Sussman and Wisdom — they are
  approachable; multiple people have corresponded with them about
  scmutils derivatives.

**Risk:**
- Without the original authors' active engagement, you carry the
  burden of physics correctness alone, on a body of work that has
  been peer-tested through 20+ years of MIT students. **This is
  where Ed's "physics is weak" note matters: tutoring is not just
  personal-growth — it is *necessary risk mitigation* for the
  project. A SICM successor that gets the physics wrong is worse
  than no SICM successor at all.** Need a physics-PhD reviewer in
  the loop before anything ships, not just clean code review.
- A 3rd edition could materialize unexpectedly. Sussman has
  surprised people before. If it does, align with it, do not
  compete; build the project to be flexible enough to do that.

### 7.5 Concrete suggestion

Add the 2nd edition + *Functional Differential Geometry* to the
bookshelf alongside the 1st ed. The 1st ed. is the most readable
for re-entry — that's where tutoring starts. But the project needs
to track the 2nd ed. and FDG as canonical scope, since those
represent what Sussman & Wisdom themselves consider the mature
treatment. Used copies of both are inexpensive on AbeBooks.

---

## 8. Extending to gravity (general relativity)

The cleaner of the two physics extensions, and partially
already-trodden by Sussman & Wisdom themselves.

**Functional Differential Geometry** (2013) was written specifically
because GR is the domain where SICM-style functional notation pays
off most. Tensors, manifolds, connections, and curvature get
notationally horrible in traditional index notation; FDG's machinery
(vector fields as derivations, forms as multilinear functions on
tuples of vector fields, Christoffel computation as honest function
composition) is genuinely cleaner. The book's last chapter computes
Schwarzschild and FLRW geodesics.

### 8.1 What this looks like

- **Symbolic top:** Inherit FDG's apparatus directly. Manifolds,
  charts, vector fields, forms, Lie derivatives, covariant
  derivatives, Riemann tensor — all already exist in scmutils-and-
  descendants. Re-derive in Racket CS.
- **Numerical mid:** Geodesic equations as Hamilton's equations on
  the cotangent bundle of spacetime. Same RHS pattern as classical
  mechanics — `dq/dλ = ∂H/∂p`, `dp/dλ = −∂H/∂q` — just with
  `H = (1/2) g^{μν}(q) p_μ p_ν` instead of kinetic + potential. The
  integrator does not change.
- **CUDA bottom:** Ensemble geodesic integration is the same SIMT
  pattern as classical ensembles. Each thread = one initial
  4-position + 4-momentum, integrate the Hamiltonian flow on the
  metric. **Pedagogical payoff:** *seeing* photon trajectories
  around a black hole, light bending around a galaxy cluster, frame-
  dragging in Kerr — visually, in real time, with 10⁶ rays.
- **Live prior art:** Wu/Wang 2021 (charged particles around Kerr,
  EPJ C) is exactly this workload. Black-hole shadow visualizations
  (the "Gargantua" look from *Interstellar*) are GPU geodesic
  ensembles. Technically well-trodden — what is missing is
  **pedagogical scaffolding from manifolds up**, which is the SICM
  differentiator.

### 8.2 Complications worth naming

1. **Field theory is a different beast.** Geodesics in a *fixed*
   background spacetime are a Hamiltonian-flow problem, fits
   cleanly. *Solving Einstein's field equations* — metric as
   dynamical variable evolving under coupled PDEs — is numerical
   relativity, an entire research field with its own gauge-condition
   machinery (BSSN, generalized harmonic). Don't try. Stop at
   "geodesics in fixed backgrounds" and that is already 90% of the
   pedagogical payoff.
2. **Symbolic Christoffel/Riemann computation explodes.** For a
   generic metric, the symbolic Riemann tensor has ~20 independent
   components, each a horrible mess. scmutils handles this; so will
   Racket. But the simplifier becomes load-bearing in a way it is
   not for classical mechanics.
3. **Choice of signature, choice of conventions.** GR has three live
   sign-convention variants (MTW, Weinberg, Landau-Lifshitz). FDG
   picks one. Pick the same one and document it as a *project
   axiom*; once chosen everything downstream depends on it.

**Difficulty: moderate.** Roughly 1.5× the work of classical
mechanics. Substrate is the same; math is cleaner conceptually but
uglier symbolically.

---

## 9. Extending to quantum mechanics

Where the SICM thesis has to *bend*, because QM does not fit
Hamiltonian flow on phase space the way classical mechanics does.
There are several legitimate computational formulations of QM, and
which one you pick determines the entire architecture.

### 9.1 The four computational formulations

1. **Schrödinger picture / wavefunctions.** State is `ψ(x, t)`,
   evolution is `iℏ ∂ψ/∂t = Ĥψ`. Computationally: discretize space
   on a grid, evolve a complex array under a (sparse, banded)
   Hamiltonian operator. **GPU-friendly:** yes, exactly what cuFFT
   and CUDA tensor cores are good at. **SICM-flavor:** medium fit.
   Symbolic top becomes "manipulate operators on Hilbert space"
   rather than "manipulate functions on phase space" — different
   abstraction layer.
2. **Heisenberg picture / operator algebra.** State is fixed,
   operators evolve. Symbolic-friendly: operator-algebra
   manipulation is *exactly* what scmutils-style symbolic
   infrastructure was built for. **GPU fit:** less natural, except
   for matrix-mechanics with finite-dimensional Hilbert spaces
   (qubits, spin systems).
3. **Path integrals / Feynman.** State is a sum-over-histories.
   Computationally: Monte Carlo over discretized paths. **GPU fit:**
   *spectacular*. Each thread = one path, importance-sample the
   action, accumulate. **This is where SICM's Lagrangian apparatus
   carries forward** — the action `S = ∫L dt` from classical
   mechanics *is* the thing being summed over. Real continuity.
4. **Geometric / phase-space QM (Wigner, Husimi, Moyal).** Quasi-
   probability distributions on classical phase space, evolved
   under deformation-quantized Hamiltonian flow. **SICM-flavor:**
   the *strongest* fit — phase-space methods preserve the geometric
   apparatus from classical mechanics; the Wigner function lives on
   the same `(q, p)` manifold the classical trajectories did.
   **GPU fit:** good (grid-based, FFT-friendly).

### 9.2 Recommended pedagogical sequence

Schrödinger first (it is what undergrad QM showed, even if Ed does
not remember it), then path integral (inherits SICM's action
principle directly, MC workload is gorgeous on GPU), then phase-
space methods as the bridge that retroactively unifies QM with the
classical mechanics built first. Heisenberg-picture operator
algebra appears as a tool throughout, not as the primary
formulation.

### 9.3 Complications worth naming

1. **Hilbert space is infinite-dimensional.** Every QM computation
   is a discretization choice (finite basis, finite grid, finite
   path-time-step). Each choice has its own convergence properties
   and its own pedagogical pitfalls. Classical mechanics had finite-
   dimensional phase space; QM does not. This changes the
   typed/untyped boundary story — *type* of the state is now
   parameterized by discretization.
2. **Complex arithmetic everywhere.** Doable on GPU (CUDA has good
   complex support, cuFFT mature), but it changes inner-loop
   primitives. Typed Racket needs `Float-Complex` or a custom
   complex-flonum representation; Racket's built-in complex numbers
   are boxed and slow.
3. **Measurement and decoherence.** SICM never has to talk about
   measurement. QM does. The "measurement problem" is a
   philosophical and notational mess that an SICM successor has to
   take a position on (Copenhagen? many-worlds? consistent
   histories? decoherence-only?). The clean computational answer is
   "we evolve unitary dynamics; measurement is a separate
   observable-extraction step that we make explicit." Defensible
   and matches how working physicists actually compute.
4. **Quantum field theory is out of scope.** Same logic as
   numerical relativity — QFT is its own world (perturbative
   diagrams, lattice gauge theory). Stop at non-relativistic QM +
   maybe relativistic single-particle (Dirac equation) and that is
   already a major contribution.

**Difficulty: substantial.** 2-3× the classical-mechanics work,
with real architectural pressure. CUDA payoff is large (path
integrals, real-time wavefunction evolution in 2D/3D potentials,
large-basis matrix mechanics). Pedagogical payoff is enormous —
**interactive QM visualization is something existing textbooks
structurally cannot offer.**

---

## 10. The Feynman keystone: action as the unifying principle

This section reorganizes the project around the single observation
Ed surfaced about Feynman.

### 10.1 What Feynman actually did

The famous chapter is **Volume II, Chapter 19: "The Principle of
Least Action."** Feynman recounts his high-school physics teacher
Bader pulling him aside privately because Feynman was bored in
class. Feynman says explicitly that this conversation "set me
afire." He found least action more beautiful than anything else in
physics.

In the *Lectures*, Feynman does something almost no introductory
text does: **he derives Newton's laws *from* least action**, not
the other way around. The mechanical Lagrangian `L = T − V` is
presented not as an algebraic convenience but as the object whose
stationarity *defines* what classical motion is.

This is also the chapter where he introduces — almost casually, in
a freshman lecture — the *path integral* idea that became his
Nobel work. He says (paraphrasing): *"the classical path is the
one for which the action is stationary, but in quantum mechanics
the particle 'tries every path' and the amplitudes interfere; the
classical limit emerges because non-stationary paths cancel."* In
a freshman physics course. In 1963.

He returns to this throughout the *Lectures* and makes it the
foundation of his QM approach in **Volume III** and his book
*Quantum Mechanics and Path Integrals* (with Hibbs, 1965). The
action `S = ∫L dt` is the *single throughline* connecting his
treatment of classical mechanics, optics (Fermat's principle),
electromagnetism (the action for fields), GR (the Einstein-Hilbert
action `S = ∫R √(−g) d⁴x`), and QM (the path integral
`⟨f|i⟩ = ∫𝒟[path] exp(iS/ℏ)`).

### 10.2 Why this is structurally important for the project

Architectural keystone — lets all four phases share one symbolic
substrate, one numerical substrate, one pedagogical narrative.

| Phase | What it computes | Center |
|---|---|---|
| Classical mechanics | Stationary paths of `S = ∫L(q, q̇, t) dt` | Lagrangian `L` |
| GR / geodesics | Stationary paths of `S = ∫√(g_μν dx^μ dx^ν)` | Metric `g`, action `S` |
| Path-integral QM | Sum over *all* paths weighted by `exp(iS/ℏ)` | Same `S` |
| Field theory (visible, OOS) | Stationary or summed-over field configurations of `S = ∫ℒ d⁴x` | Lagrangian density `ℒ` |

**The action is the same object in every phase.** What changes is
what you do with it: stationarize (classical, GR), sum over (QM),
or sum over field configurations (QFT). The mathematical apparatus
does not fork — only the operator that turns the action into a
prediction does.

```
Symbolic top:  Lagrangian L (or action S) as a function   ←  same in every phase
                              │
            ┌─────────────────┼──────────────────┬──────────────────┐
            ▼                 ▼                  ▼                  ▼
    Euler-Lagrange     Hamilton's eqns    Path integral       Field equations
    (classical, GR)    (any flow)         (QM, QFT)            (NR, etc.)
            │                 │                  │
            ▼                 ▼                  ▼
    Symplectic         Phase-space        Monte Carlo
    integrator         ensemble           over paths
    on CUDA            on CUDA            on CUDA
```

The symbolic top is *literally the same scmutils-flavored apparatus*
across all four phases. CUDA workloads differ (deterministic ODE
ensembles vs. stochastic path-integral Monte Carlo) but sit in the
same orchestration pattern: compile-RHS-once, ensemble-over-initial-
conditions-or-paths, reduce-results. Even the GPU code shares
structure: per-thread, advance state under a force/action
computation, accumulate observable.

### 10.3 The pedagogical arc this unlocks

A thread Feynman himself laid down but no textbook has fully
followed through computationally:

- **Lecture 1:** Define the action `S = ∫L dt`. Show that requiring
  `δS = 0` yields Newton's laws. (SICM Chapter 1; Feynman's Vol II
  Ch 19.)
- **Lecture N:** "What if we don't insist `δS = 0` — what if every
  path contributes? What's the natural way to weight them?" Path
  integral falls out. The classical limit (`ℏ → 0`) is recovered as
  stationary-phase approximation: only paths near the classical
  (stationary-action) one survive the interference. **The student
  sees, with their own eyes on a GPU, the classical trajectory
  emerge as the survivor of destructive interference among 10⁶
  Monte Carlo paths.** No textbook can do this. Feynman *described*
  it; we can show it.
- **Lecture M:** "What if the Lagrangian is `L = (1/2) g_μν ẋ^μ
  ẋ^ν`?" Geodesics. GR appears as another instance of the same
  machinery. Light bending around a black hole is the same
  `δS = 0` we did on day one, with a different `L`.
- **Lecture K:** "What if we replace the variable `q(t)` with a
  field `φ(x, t)` and integrate over spacetime?" QFT in outline.
  The action principle is the *only* organizing principle that
  makes this transition feel inevitable instead of imposed.

This is the textbook Feynman would have written if he had had a
GPU. And — relevant to Ed's "weak physics" caveat — it is also the
cleanest way to re-learn modern physics from where Ed is now. The
action principle is the single concept where, if you understand it
well, the rest of physics opens up; if you don't, every subfield
feels disconnected.

### 10.4 What this changes about the project plan

1. **The action `S` should be a first-class object in the symbolic
   system, not just the Lagrangian `L`.** scmutils has both, but
   tends to emphasize `L` because Euler-Lagrange operates on `L`
   directly. For a project that wants the path-integral extension
   to feel natural, `S` (as a *functional* on paths, not just an
   integrand on `L`) deserves first-class representation. Small
   architectural decision now; large dividends later.
2. **Don't defer the path-integral Monte Carlo kernel to "Phase
   4."** Build a *toy* path-integral demo as part of Phase 1 — even
   just for the harmonic oscillator, even just on CPU. Forces the
   action-as-functional design to be load-bearing from day one,
   not retrofitted later when QM arrives. Cost: a week's work.
   Benefit: architecture stays coherent.
3. **The pedagogy should follow Feynman's lead, not SICM's.** SICM
   is *strict* about Lagrangian → Hamiltonian → canonical
   transformations. Feynman is *narrative* — action first, then
   "what does requiring stationarity give us," then "what does *not*
   requiring stationarity give us." For a textbook-shaped artifact
   aimed at modern students, Feynman's narrative is friendlier and
   connects directly to what students will care about (GR, QM)
   without sacrificing rigor. SICM's machinery is the substrate;
   Feynman's narrative is the throughline.
4. **The project has a working title now.** Candidates:
   - *Structure and Interpretation of Action Principles*
   - *The Action Principle: A Computational Approach*
   - *SICM, modernized: from Lagrangians to Path Integrals, on the
     GPU*
   - The action principle is the through-line of *both* SICM and
     Feynman, and of this project too.

### 10.5 The organizing test

When implementation decisions come up later, the test will be:
**does this preserve the action as a first-class, manipulable,
optimizable, sample-able object across all four phases?** If yes,
on track. If no, drift.

---

## 11. Project arc

```
Phase 1: Classical mechanics (SICM 1e/2e scope)        — re-derive in Racket CS
Phase 2: Geometric machinery (FDG scope)               — manifolds, forms, connections
Phase 3: General relativity (geodesics in fixed bgs)   — Schwarzschild, Kerr, FLRW
Phase 4: QM (Schrödinger + path integral + phase-space)— the textbook nobody has written
```

Each phase a usable artifact on its own. Each roughly the size of
one textbook. **Phase 1 alone is a publishable contribution.**
Phases 1+2+3 = the spiritual successor to FDG. Phase 4 = uncontested
ground, harder than the others combined, where the project becomes
genuinely novel rather than a modernization.

**Crucially: the GPU architecture from Phase 1 carries forward
unchanged into all four phases.** Ensemble integration on GPU works
for: classical trajectories, geodesics, Schrödinger evolution
(different kernel — split-operator FFT — but same orchestration
pattern), path-integral MC. So the Phase 1 substrate amortizes
across the whole arc.

The tutoring side scales naturally. Classical mechanics is where
physics intuition rebuilds. GR is where most of what undergrad GR
class did not cover (or what Ed has forgotten) gets filled in. QM
is where Ed re-tutors alongside building. **The project itself
becomes the curriculum, which is the *original SICM thesis* applied
to Ed's relearning.**

---

## 12. Open decisions & next moves

Decisions still genuinely open (none have been made yet):

1. **Pedagogy vs. research-tool orientation.** Default: pedagogical
   instrument. Confirm.
2. **Path: Clojure `sicmutils`+JNI vs. salvage `bennn/mechanics`
   vs. greenfield Racket CS.** Default leans toward greenfield
   Racket CS for the `#lang sicm` payoff. Confirm.
3. **Module-cycle resolution strategy** (if greenfield Racket).
   Options: Racket unit system; explicit two-phase init via setter
   procedures; rethink dispatch using `#lang` machinery. Pick one
   up front to avoid the 2018-thread stall mode.
4. **Sign / metric / connection convention** (when Phase 3 begins).
   Default: track FDG.
5. **Project title.**
6. **Reach out to Sussman & Wisdom?** When and how. Courtesy
   heads-up vs. collaboration invitation are different things.

Next moves not yet chosen between:
- Continue (c): GPU symplectic-integration prior art in more depth
  (now needed for both classical and GR-geodesic workloads).
- Lay out tutoring arc through SICM 1st ed.
- Begin physical-bookshelf updates (acquire SICM 2e + FDG used).

---

## 13. Sources

- [Functional Differential Geometry (MIT Press, 2013)](https://mitpress.mit.edu/9780262019347/functional-differential-geometry/)
- [Functional Differential Geometry preprint (Sussman, Wisdom 2005)](https://web.mit.edu/wisdom/www/AIM-2005-003.pdf)
- [MIT 6.946 course page (Sussman & Wisdom)](https://groups.csail.mit.edu/mac/users/gjs/6946/) — Fall 2024 = last offering
- [bennn/mechanics — Racket port of scmutils, stalled](https://github.com/bennn/mechanics)
- [Racket-users thread on porting scmutils (Alex Gian, July 2018)](https://groups.google.com/g/racket-users/c/pyIm_uahy3k)
- [alexgian/guile-scmutils](https://github.com/alexgian/guile-scmutils)
- [fedeinthemix/chez-scmutils](https://github.com/fedeinthemix/chez-scmutils)
- [sicmutils/sicmutils (Clojure)](https://github.com/sicmutils/sicmutils)
- [soegaard/racket-cas](https://github.com/soegaard/racket-cas)
- [Tipoca/scmutils (mirror of MIT scmutils)](https://github.com/Tipoca/scmutils)
- [DeepRacket talk slides (Charles Earl, RacketCon 2017)](https://con.racket-lang.org/2017/earl.pdf)
- [Racket FFI tutorial (Northeastern PRL)](https://prl.khoury.northeastern.edu/blog/2016/06/27/tutorial-using-racket-s-ffi/)
- [DiffEqGPU.jl (SciML)](https://github.com/SciML/DiffEqGPU.jl)
- [QYMSYM: GPU-accelerated hybrid symplectic integrator (Moore & Quillen 2011)](https://ascl.net/1210.028)
- [FROST: hierarchical 4th-order forward symplectic on CUDA (arXiv 2011.14984)](https://arxiv.org/abs/2011.14984)
- [Explicit symplectic integrator for charged particles in Kerr field (Wu et al. 2021, EPJ C)](https://link.springer.com/article/10.1140/epjc/s10052-021-09579-7)
- [Gerald Jay Sussman — Wikipedia](https://en.wikipedia.org/wiki/Gerald_Jay_Sussman)
- Feynman, Leighton, Sands, *The Feynman Lectures on Physics*, Vol. II Ch. 19 ("The Principle of Least Action"), 1963.
- Feynman & Hibbs, *Quantum Mechanics and Path Integrals*, 1965.
