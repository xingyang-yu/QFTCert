# Session handoff — Phase 2c/2d paper harness

This file lives **in the repo** (so it travels via iCloud / git even when the
Claude `~/.claude/.../memory/` notes do not). A fresh Claude Code session
should read this first, then `docs/experiments.md`. If the `.claude` project
memory IS present, prefer it (it may be newer); this file is the portable
fallback.

_Last updated: 2026-05-31 (end of Day 2)._

## Where things stand

Branch **`phase2c-harness`** (cut off `main` @ `69341ec`), **not pushed**
(embargo — see project confidentiality). Four commits:

1. `f9ac6d2` Phase 2c paper harness — `dualitycert/experiments/` package
   (config, manifest, verifier wrapper, perturbations, chains, generation,
   single-shot detection+diagnosis, repair loop, stats, CLI) + dry-run model
   client. MVP (`dualitycert/benchmark/`, `agent/detection.py`, fixtures) left
   untouched.
2. `66c7737` Hardening (Codex review): strict depth preflight → completeness
   check; diagnosis schema split (`failure_modes` primary / `suspected_cause`
   secondary, fixed-vocab macro-F1); `force_model_on_certified` do-no-harm
   challenge.
3. `27b36f8` Phase 2d depth-K Seiberg mutation **chain-runner**
   (`experiments/chains.py`): `apply_single_seiberg_mutation` (single step)
   + `generate_mutation_chain` (composes K steps; backtracking/repeated-state
   rejection; adjacent + seed-to-final verification; precise attrition
   reasons). `generated_depth` = chain length, NOT minimal distance.
4. `38824d9` Phase 2d-ext **endpoint-pool** pair sampling
   (`experiments/endpoint_pool.py`): build per-orbit endpoint pool, sample
   blind `(T_i, T_j)` pairs (not just `(T0, T_K)`), verifier-gate. `pair_origin`
   taxonomy + `pair_metadata` on manifest. Opt-in via
   `pair_generation_mode="endpoint_pool"` (default stays legacy).

Tests: **403 fast pass** (`pytest -m "not slow"`) + 1 slow real-depth-2 test.

WIP (this commit): `dualitycert/experiments/seed_catalog.py` — literature
seed encodings, **draft, NOT wired into `default_seed_specs`**.

## Day-2 work: expanding the seed set (9 paper-main seeds)

Motivation: only **2 independent physics families** today (dp0, F_0; dp0_N3 vs
dp0_N4 are NOT independent). Too few for a paper (memorization narrative;
GLMM random-effect power needs ≥~5–15 seed levels; physics coverage). Target
**~15–30** eventually; first batch **9**:

`dp0_C3_Z3, F0, dP_1, dP_2, SPP, C^3/(Z2×Z2), Y^{3,1}, Y^{3,2}, L^{a,b,c}`
(SPP replaced dP_3; C^3/(Z2×Z2) replaced the Z_6≅Z2×Z3 idea).

**Design rule (user):** every POSITIVE pair must have ≥1 NON-toric (mutated)
side; never compare two toric phases; so do NOT add F_0 phase I as a seed.

### Seed sources (transcribed; user confirmed dP_1/dP_2-I/C^3 superpotentials)

| seed | source | structure | W degree |
|---|---|---|---|
| dp0 (=C^3/Z_3) | in repo (`seeds.py`) | SU(N)^3, 9 fields | cubic |
| F_0 (cubic phase) | in repo (`seeds.py`) | 4 nodes, 12 fields | cubic |
| dP_1 | hep-th/0205144 eq (4.7), Fig 11; =Y^{2,1}=F_1 | 4 nodes, 10 fields | 2 cubic + 1 quartic |
| dP_2 Phase I | hep-th/0205144 W_I (sec 4.5) | 5 nodes, 13 fields | ≤ quartic (Phase II has a quintic → use I) |
| C^3/(Z2×Z2) | arXiv:0704.0262 eq (3.1)+Fig 1 | 4 nodes SU(N)^4, K4 12 bifund (non-chiral) | cubic (8 terms) |
| SPP | arXiv:1702.03958 eq **(2.3)** [not 3.2]+Fig 1 | 3 nodes, 7 fields, **adjoint X22** | 2 cubic + 2 quartic |
| dP_3 (DROPPED) | hep-th/0209228 | both phases high-degree (sextic/quintic) | replaced by SPP |
| Y^{3,1}, Y^{3,2} | hep-th/0411264 (Y^{p,q}=2p nodes) | 6 nodes | cubic+quartic — **user still locating exact data** |
| L^{a,b,c} | hep-th/0505211 | depends on a,b,c | cubic+quartic — **user still locating; needs (a,b,c)** |

`seed_catalog.py` currently encodes `c3_z2z2_electric` + `dp1_electric`
(0-indexed `X{i}{j}[k]` convention; R via placeholder → `repair_r_charges`
→ rational feasible R). Both build fine as valid theories.

## ⚠️ CRITICAL FINDING (drives the next decision)

**The MVP single-node mutation engine correctly produces Seiberg duals ONLY
for dp0 and F_0.** For C^3/(Z2×Z2) and dP_1, a single mutation **FAILS
't Hooft anomaly matching** (failed obligations: *global anomaly matching*,
*central charge matching*, *bounded chiral-ring*) → the output is NOT a valid
dual. Confirmed via the identical code path (dp0/F0 CERTIFY; new seeds FAIL).

Root cause: `integrate_linear_fields` only does **LINEAR** F-term reduction.
More-connected quivers (C^3/Z2×Z2 is complete-K4; dP_1 has a quartic) produce
**quadratic** post-mutation mass terms that need **general (nonlinear)
reduction**; the MVP leaves spurious un-integrated fields (C^3/Z2×Z2's T1 had
21 fields vs a clean dual's ~12) → anomaly mismatch. NOTE: C^3/Z2×Z2 uses the
natural R=2/3 and still fails ⇒ this is an **engine** problem, not a
rational-R problem. ⇒ **With the current engine, the new seeds CANNOT generate
certified positives** (only depth-0 endpoints for cross-orbit negatives).

## The fix = the precise duality superpotential rule (DWZ QP mutation)

- Premutation μ̃_k (= our `mutate_bare`): reverse incident arrows
  `a:i→k ↦ a*:k→i`, `b:k→j ↦ b*:j→k`; add meson `M_{ab}:i→j` per `i→k→j`
  path; `W̃ = [W with each through-k composite ba → M_{ab}] + Σ M_{ab} a* b*`.
- **Reduction (the missing step):** split off 2-cycle/mass terms and integrate
  them out via F-terms — generally a **nonlinear / path-polynomial**
  substitution that raises W degree; iterate until no 2-cycles. In our
  "field=arrow, W=monomial-in-labels" JSON this means substituting an arrow by
  a **formal sum of paths** (path-algebra substitution).
- Refs: **Derksen–Weyman–Zelevinsky, arXiv:0704.0649 §5** (rigorous,
  algorithmic, terminates); physics: Berenstein–Douglas hep-th/0207027,
  Herzog hep-th/0405118.

## OPEN DECISION (make this first next session)

- **(A)** implement general DWZ reduction in the engine → new seeds become
  positive sources. Well-defined, sizeable. The "real" path.
- **(B)** use new seeds as negative-only diversity (depth-0 cross-orbit);
  positives stay dp0/F_0.
- **(C)** cheaply probe for other engine-friendly positive seeds (low
  connectivity → linear mass after mutation, like dp0/F_0; e.g. conifold/KW?
  other C^3/Z_k?).
- (D) encode known dual PAIRs directly — excluded by the no-toric-vs-toric rule.

I recommended (C) cheap probe + (B) meanwhile; (A) is the long-term fix.
Pending: Y^{3,1}/Y^{3,2}/L^{a,b,c} exact encodings from the user.

## New-device setup checklist

1. Let iCloud **fully** sync before opening; watch for `xxx 2.py` conflict
   copies; don't operate on `.git` mid-sync.
2. **Rebuild the venv** (not portable across machines):
   `python -m venv .venv && pip install -e ".[test,llm]"` (+ `pip install pypdf`
   only if re-reading arXiv PDFs).
3. `pytest -m "not slow"` should show ~403 passing.
4. Read this file + `docs/experiments.md`; then settle the A/B/C decision.
