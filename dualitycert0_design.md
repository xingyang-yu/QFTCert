# DualityCert-0: Machine-Checkable Consistency Certificates for 4d N=1 SQCD Dualities

**Draft v0.1.** DualityCert-0 is a deliberately small verifier/certificate prototype for Seiberg-duality-like claims in 4d \(\mathcal N=1\) SQCD. The system does **not** prove dualities. It takes a typed physics claim, generates a fixed set of consistency obligations, runs exact or semi-exact checkers, and emits a structured certificate describing what passed, what failed, and what remains unimplemented.

## 1. Project goal

The first milestone is a runnable Python package that can construct the standard electric/magnetic SQCD pair and produce a consistency certificate. The prototype should answer questions of the form:

> Given electric \(SU(N_c)\) SQCD with \(N_f\) flavors and proposed magnetic \(SU(N_f-N_c)\) dual with \(q,\tilde q,M\) and \(W=Mq\tilde q\), which machine-checkable consistency obligations are satisfied?

The intended output is not `true/false`, but a certificate with per-obligation status, formulas, normalization conventions, diagnostics, and repair hints.

## 2. Non-goals

DualityCert-0 will not:

- prove Seiberg duality as a theorem;
- formalize path integrals, RG flows, conformal dynamics, or full IR equivalence;
- parse arbitrary natural-language physics claims;
- support arbitrary gauge groups, matter content, generalized symmetries, defects, or line operators;
- compute exact superconformal indices beyond placeholders;
- become a benchmark of LLM physics problem-solving.

The first prototype is a verifier-rich environment, not a model-training project.

## 3. Why not “Lean for physics”?

A theorem prover asks for axioms, definitions, and proof terms. Theoretical physics often works differently: it constrains, matches, deforms, checks limits, and triangulates. DualityCert therefore treats a physical claim as a source of **obligations**, not as a proposition to be fully proven. Some obligations are exact and symbolic, for example gauge anomaly cancellation or superpotential charge invariance. Others are finite-order evidence or future checks, for example index matching or deformation consistency. The honest unit of output is therefore a **consistency certificate**, not a mathematical proof.

## 4. Core objects

The initial object model should be small and explicit.

- `Theory`: name, dimension, supersymmetry, gauge group, global symmetries, fields, superpotential terms, metadata.
- `GaugeGroup`: currently only `SU(n)`; stores rank/parameter, representation convention, and anomaly normalization.
- `GlobalSymmetry`: `SU(Nf)_L`, `SU(Nf)_R`, `U(1)_B`, `U(1)_R`.
- `Representation`: `fundamental`, `anti_fundamental`, `adjoint`, `singlet`; later extensible to products and Young-tableau labels.
- `Field`: chiral or vector multiplet; gauge representation; global representations; abelian charges; scalar/superfield R-charge.
- `SuperpotentialTerm`: ordered field monomial plus optional named contraction, for example `M q qtilde`.
- `DualityClaim`: electric theory, magnetic theory, operator map, parameter map, convention block.
- `Obligation`: generated check item with type, expected relation, checker name, dependencies, and severity.
- `Certificate`: JSON-serializable result containing obligations, statuses, formulas, evaluated values, warnings, failures, and repair hints.

## 5. First-version physics scope

Supported electric theory:

\[
SU(N_c)\quad \text{with}\quad Q:(\mathbf{N_c},\mathbf{N_f},1),\qquad
\tilde Q:(\overline{\mathbf{N_c}},1,\overline{\mathbf{N_f}}).
\]

Supported magnetic theory:

\[
SU(\tilde N_c),\qquad \tilde N_c=N_f-N_c,
\]

with dual quarks \(q,\tilde q\), meson \(M\), and

\[
W=Mq\tilde q.
\]

Default global symmetry:

\[
SU(N_f)_L\times SU(N_f)_R\times U(1)_B\times U(1)_R.
\]

Default charge convention:

| field | gauge | \(SU(N_f)_L\) | \(SU(N_f)_R\) | \(U(1)_B\) | superfield \(R\) |
|---|---:|---:|---:|---:|---:|
| \(Q\) | \(\mathbf{N_c}\) | \(\mathbf{N_f}\) | 1 | \(+1\) | \(1-N_c/N_f\) |
| \(\tilde Q\) | \(\overline{\mathbf{N_c}}\) | 1 | \(\overline{\mathbf{N_f}}\) | \(-1\) | \(1-N_c/N_f\) |
| \(q\) | \(\mathbf{\tilde N_c}\) | \(\overline{\mathbf{N_f}}\) | 1 | \(N_c/\tilde N_c\) | \(N_c/N_f\) |
| \(\tilde q\) | \(\overline{\mathbf{\tilde N_c}}\) | 1 | \(\mathbf{N_f}\) | \(-N_c/\tilde N_c\) | \(N_c/N_f\) |
| \(M\) | 1 | \(\mathbf{N_f}\) | \(\overline{\mathbf{N_f}}\) | 0 | \(2\tilde N_c/N_f\) |

Implementation should initially run on integer \((N_c,N_f)\), with exact rational arithmetic. Symbolic formulas can be emitted as strings or SymPy expressions, but tests should include concrete values such as \((N_c,N_f)=(3,6),(4,7),(5,9)\). Edge cases \(N_c=2\), \(\tilde N_c=1,2\), \(N_f=N_c\), and \(N_f=N_c+1\) should be flagged with caveats or rejected in v0 unless explicitly tested.

## 6. Implemented checkers

The first checker set should be exact, small, and convention-aware.

1. **Gauge cubic anomaly cancellation**: verify local non-abelian gauge anomaly cancellation for electric and magnetic gauge groups. In SQCD this is vectorlike: fundamentals and anti-fundamentals cancel.
2. **Gauge-gauge-\(U(1)_R\) non-anomaly**: verify the chosen \(U(1)_R\) is non-anomalous with respect to the gauge group. Use fermion R-charge \(R_\psi=R_\Phi-1\) for chiral multiplets and gaugino R-charge \(1\).
3. **Superpotential global invariance**: verify \(W=Mq\tilde q\) is neutral under \(U(1)_B\), has valid flavor singlet contractions, and uses gauge singlet contractions.
4. **\(R(W)=2\)**: verify the superfield R-charges in each superpotential term sum to 2.
5. **’t Hooft anomaly matching**: compare electric and magnetic global anomalies computed from left-handed Weyl fermions. Minimal v0 list:
   - \(SU(N_f)_L^3\), \(SU(N_f)_R^3\);
   - \(SU(N_f)_L^2U(1)_B\), \(SU(N_f)_R^2U(1)_B\);
   - \(SU(N_f)_L^2U(1)_R\), \(SU(N_f)_R^2U(1)_R\);
   - \(U(1)_B^3\), \(U(1)_B\), \(U(1)_B^2U(1)_R\), \(U(1)_BU(1)_R^2\);
   - \(U(1)_R^3\), \(U(1)_R\)-gravity.
6. **Minimal operator-map consistency**: check quantum numbers of \(Q\tilde Q\leftrightarrow M\), and baryon charge matching \(Q^{N_c}\leftrightarrow q^{\tilde N_c}\). Full representation-level baryon matching can be marked `SUPPORTED` or `NOT_IMPLEMENTED`.
7. **Placeholders**: index matching, deformation checks, moduli-space checks, global-form/line-operator checks should emit `NOT_IMPLEMENTED`, not silently pass.

## 7. Certificate output format

The certificate is JSON-like and intentionally verbose:

```json
{
  "claim_id": "seiberg_sqcd_SU3_Nf6",
  "claim_type": "4d_N1_SQCD_Seiberg_duality",
  "parameters": {"Nc": 3, "Nf": 6, "Nctilde": 3},
  "top_level_status": "SUPPORTED",
  "conventions": {
    "fermions": "left-handed Weyl",
    "R_chiral_fermion": "R_superfield - 1",
    "SU_cubic_index": "A(fund)=+1, A(anti)=-1",
    "SU_quadratic_index": "T(fund)=1 by default; conventional T=1/2 available"
  },
  "obligations": [
    {
      "id": "gauge_anomaly_electric_SU_Nc_cubic",
      "status": "CERTIFIED",
      "formula": "Nf*A(fund)+Nf*A(anti)=0",
      "value": 0,
      "checker": "GaugeCubicAnomalyChecker"
    },
    {
      "id": "index_matching_full",
      "status": "NOT_IMPLEMENTED",
      "message": "Full superconformal index matching is outside DualityCert-0."
    }
  ],
  "failures": [],
  "warnings": ["This certificate is not a proof of IR equivalence."],
  "repair_hints": []
}
```

Top-level status rule for v0: if any exact implemented obligation fails, the claim is `FAILED`; if all implemented exact obligations pass but major future obligations remain unimplemented, the top-level status is `SUPPORTED`; if the selected obligation profile contains only implemented exact checks and all pass, it may be `CERTIFIED`. `PROVED` is reserved and should not be used in v0.

## 8. Example: standard Seiberg SQCD

Input builder:

```python
claim = build_seiberg_sqcd_claim(Nc=3, Nf=6)
certificate = certify(claim, profile="dualitycert0")
```

Expected behavior:

- gauge cubic anomalies pass on both sides;
- mixed gauge-gauge-\(U(1)_R\) anomalies vanish;
- \(W=Mq\tilde q\) is neutral under baryon number and flavor symmetries;
- \(R(M)+R(q)+R(\tilde q)=2\);
- implemented ’t Hooft anomalies match;
- index/deformation/line-operator obligations are emitted as `NOT_IMPLEMENTED`.

## 9. Failure examples

The test suite should include intentionally broken claims:

- wrong magnetic baryon charge, for example \(B(q)=1\), causing \(SU(N_f)_L^2U(1)_B\) anomaly mismatch and baryon-map failure;
- wrong meson R-charge, causing \(R(W)\ne 2\);
- missing meson \(M\), causing superpotential and meson-map obligations to fail;
- omitted superpotential, causing an explicit `FAILED` or high-severity warning because the magnetic theory no longer encodes the standard claim;
- edge-case input \(N_f\le N_c+1\), causing domain warnings or rejection in v0.

## 10. First-week implementation plan

Day 1: create repo skeleton, `pyproject.toml`, `README.md`, `design.md`, status enum, certificate dataclasses.

Day 2: implement `SUGroup`, `U1Symmetry`, representation labels, multiplicity handling, and convention object.

Day 3: implement `Theory`, `Field`, `SuperpotentialTerm`, and a `build_seiberg_sqcd_claim(Nc,Nf)` example.

Day 4: implement gauge cubic anomaly and gauge-gauge-\(U(1)_R\) checkers with rational arithmetic and tests.

Day 5: implement superpotential invariance, \(R(W)=2\), and the core ’t Hooft anomaly table.

Day 6: implement minimal operator-map checker, failure examples, pytest suite, and JSON certificate export.

Day 7: write README narrative, run examples, freeze v0 scope, and prepare a short “system card” explaining what the certificate does and does not claim.

## 11. Risks and convention caveats

- **Anomaly normalization**: the package must store the chosen normalization in every certificate. Recommended implementation default: \(A(\mathbf f)=+1\), \(A(\bar{\mathbf f})=-1\), \(T(\mathbf f)=1\), with optional conversion to \(T(\mathbf f)=1/2\).
- **Scalar vs fermion R-charge**: superpotential checks use superfield/scalar R-charges; anomaly checks use Weyl fermion charges \(R_\psi=R_\Phi-1\). This should be impossible to confuse in the object model.
- **Special groups**: \(SU(2)\) has pseudoreal fundamentals and possible global-symmetry enhancement; v0 should warn or restrict rather than silently applying generic \(SU(N\ge3)\) logic.
- **Global forms and quotients**: the actual global symmetry may involve discrete quotients. v0 uses Lie-algebra-level continuous symmetries only.
- **IR subtleties**: accidental symmetries, free fields, conformal-window distinctions, s-confining limits, and quantum-deformed moduli spaces are not modeled in v0.
- **Certificate language**: passing all v0 checks means “no implemented consistency obstruction was found,” not “the duality is proven.”

