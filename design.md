# QFTCert / DualityCert-0 Design

**Package:** `dualitycert`  **Project:** QFTCert  **Current system:** DualityCert-0

DualityCert-0 is a deliberately small verifier/certificate prototype for 4d
N=1 supersymmetric gauge theory duality claims. It is the first prototype
inside QFTCert, an auditable AI-assisted reasoning infrastructure project for
theoretical physics.

The system does not prove dualities. It takes a typed or machine-readable
physics claim, generates a fixed set of consistency obligations, runs
implemented exact checkers, and emits a structured certificate describing what
passed, what failed, and what remains unimplemented.

## Project Goal

The current milestone is a runnable Python package that can construct duality
claims for several duality profiles and answer:

> Given a proposed pair of dual theories with explicit field content,
> R-charges, superpotential, and symmetry assignments, which
> machine-checkable consistency obligations are satisfied?

Supported duality profiles today: `seiberg_sqcd` and `kutasov`.

The intended output is not a bare `true` or `false`, but a certificate with
per-obligation status, convention assumptions, diagnostic tables, warnings,
and explicit `NOT_IMPLEMENTED` entries.

The intended AI workflow is:

```text
LLM proposes claim -> QFTCert checks obligations -> certificate/critic report
-> repaired claim
```

The current repository implements this loop without requiring any paid model
API: QFTCert can generate critic reports and repair prompts from failed
certificates, and those prompts can be given to a human or any external LLM.

## Non-Goals

DualityCert-0 will not:

- prove Seiberg duality as a theorem;
- formalize path integrals, RG flows, conformal dynamics, or full IR
  equivalence;
- parse arbitrary natural-language physics claims;
- support arbitrary gauge groups, matter content, generalized symmetries,
  defects, or line operators;
- compute exact superconformal indices;
- train models or benchmark LLM physics reasoning.

The first prototype is a verifier-rich environment, not a model-training
project.

## Why Certificates, Not Proofs

A theorem prover asks for axioms, definitions, and proof terms. Theoretical
physics often works differently: it constrains, matches, deforms, checks
limits, and triangulates. QFTCert therefore treats a physical claim as a
source of obligations, not as a proposition that the prototype can fully
prove.

Some obligations are exact and symbolic, such as gauge anomaly cancellation
or superpotential charge invariance. Others are future checks, such as index
matching or deformation consistency. The honest unit of output is therefore a
consistency certificate, not a mathematical proof.

## Status Semantics

The status labels are deliberately conservative.

- `CERTIFIED`: all implemented exact obligations in the selected profile
  passed, and at least one nontrivial implemented obligation was checked.
- `FAILED`: at least one implemented obligation failed.
- `UNKNOWN`: the obligation has a scaffold/checker, but the claim did not
  encode enough data to run a substantive comparison.
- `NOT_APPLICABLE`: the obligation is outside the current claim profile or
  supported parameter regime.
- `NOT_IMPLEMENTED`: an obligation is known and recorded but has no checker.
- `SUPPORTED` and `PLAUSIBLE`: reserved for future partial-evidence or
  heuristic layers.
- `PROVED`: included only as a reserved enum value; this prototype should not
  use it for duality claims.

In this project, `CERTIFIED` is a legacy internal enum. Outward-facing output
uses safer labels:

- `PASSED_IMPLEMENTED_OBLIGATIONS`
- `FAILED_IMPLEMENTED_OBLIGATIONS`
- `PARTIAL_WITH_NOT_IMPLEMENTED_OBLIGATIONS`
- `NO_IMPLEMENTED_OBLIGATIONS`
- `OUT_OF_SCOPE`: the claim's theory kind is outside the current verifier scope;
  no physics obligations were run. This is NOT a physics failure.

These labels mean exactly what they say about implemented checks; none of them
means "the duality is proven."

## Core Objects

- `GaugeGroup`: currently SU(N). Each node has a label (e.g. `"SU(3)"`).
- `GlobalSymmetry`: currently SU(N), U(1), and U(1)_R labels.
- `Representation`: `fundamental`, `antifundamental`, `adjoint`, `singlet`.
- `Field`: chiral multiplet data. `gauge_reps: Mapping[str, Representation]`
  maps gauge node labels to representations (empty = singlet under all nodes).
  Also carries `global_reps`, `u1_charges`, `r_charge`, `multiplicity`.
- `SuperpotentialTerm`: a field monomial such as `M q qtilde`.
- `Theory`: `gauge_nodes: tuple[GaugeGroup, ...]` (K >= 1), fields, global
  symmetries, superpotential terms. K=1 is the SQCD/Kutasov special case.
- `SymmetryMap`: a label map from electric global symmetries to magnetic.
- `DualityClaim`: electric theory, magnetic theory, symmetry map, operator
  map, and `metadata` dict (contains `duality_profile`, `theory_kind`,
  `parameters`, etc.).
- `Obligation`: generated consistency task with an optional checker.
- `Certificate`: structured result containing `duality_profile`, `theory_kind`,
  passed/failed/unimplemented/unknown/not-applicable obligations, warnings,
  assumptions, limitations, and detailed tables.

## Theory Kind Classification

Before running physics obligations, the verifier classifies each claim into
one of three mutually exclusive **theory kinds**:

- **`pure_quiver`**: K >= 1 gauge nodes, no non-Abelian flavor fundamentals
  in global_reps (D-brane probe theories, toric duality targets).
- **`flavored_single_gauge`**: K = 1, has SU(Nf) flavor fundamentals
  (Seiberg SQCD, Kutasov-Schwimmer).
- **`flavored_quiver`**: K > 1 with non-Abelian flavor — currently
  **OUT_OF_SCOPE**. No physics checks run; the certificate records
  `outward_status = OUT_OF_SCOPE`.

Classification is inferred from field content. An explicit
`metadata["theory_kind"]` entry overrides the inference; a mismatch is
flagged as FAILED by the `theory_kind_classification` check.

Currently implemented duality profiles, by kind:
- `flavored_single_gauge`: `seiberg_sqcd`, `kutasov`
- `pure_quiver`: none yet (Phase 2 target: toric dP_0)

## Supported Duality Profiles

### seiberg_sqcd

Electric: SU(Nc) with Q, Qtilde in Nf flavors, W_el = 0.  
Magnetic: SU(Nf-Nc) with q, qtilde, singlet M, W_mag = M q qtilde.  
Global symmetry: SU(Nf)_L × SU(Nf)_R × U(1)_B × U(1)_R.

Exact rational arithmetic; requires Nf > Nc and magnetic rank >= 2.

### kutasov

Electric: SU(Nc) with Q, Qtilde in Nf flavors + adjoint X, W_el = Tr(X^{k+1}).  
Magnetic: SU(kNf-Nc) with q, qtilde + adjoint Y + meson tower M_j (j=0..k-1),
W_mag = Tr(Y^{k+1}) + Σ_j M_j q Y^{k-1-j} qtilde.  
R-charge: R(X) = R(Y) = 2/(k+1), R_el = 1 - 2Nc/(Nf(k+1)).

k=1 reduces to Seiberg duality with one adjoint; k >= 2 adds a meson tower.

## Representation Conventions

For SU(N), dimensions are normalized as:

- dim(fundamental) = dim(antifundamental) = N
- dim(adjoint) = N^2 - 1
- dim(singlet) = 1

For SU(N)^3 anomalies:

- A(fundamental) = +1
- A(antifundamental) = -1
- A(adjoint) = 0
- A(singlet) = 0

For SU(N)^2 U(1) anomalies:

- T(fundamental) = T(antifundamental) = 1/2
- T(adjoint) = N
- T(singlet) = 0

These normalizations are conventional and internally consistent. Other
literature may choose different overall factors, so certificates explicitly
record the normalization assumptions.

## Fermion and R-Charge Conventions

Anomaly matching is computed using left-handed Weyl fermions. For a chiral
multiplet with superfield R-charge `R`, the fermion has R-charge `R - 1`.
Non-R U(1) charges are taken to be the same for the scalar and fermion.

Vector multiplet gauginos are included in pure U(1)_R and
gravitational-U(1)_R global anomalies. Their R-charge is +1, with
multiplicity equal to the dimension of the gauge adjoint. Gauge fields are
not included in non-R flavor anomalies.

## SQCD Charge Conventions

The bundled SQCD builder uses baryon number normalized so that an electric
baryon made from Nc quarks has charge +1:

- B(Q) = +1 / Nc
- B(Qtilde) = -1 / Nc
- B(q) = +1 / (Nf - Nc)
- B(qtilde) = -1 / (Nf - Nc)
- B(M) = 0

R-charge assignments for the default SQCD example are:

- R(Q) = R(Qtilde) = 1 - Nc / Nf
- R(q) = R(qtilde) = Nc / Nf
- R(M) = 2(1 - Nc / Nf)

The magnetic superpotential W = M q qtilde then has R-charge 2.

Some physics references instead normalize B(Q) = 1 and
B(q) = Nc / (Nf - Nc). That convention is equivalent up to an overall
baryon-number rescaling, but this prototype currently uses the normalized
baryon convention above.

## Implemented Obligations

All claims (any theory kind):

- **theory kind classification**: classifies the claim and confirms verifier
  scope; flags `OUT_OF_SCOPE` for `flavored_quiver`.

`flavored_single_gauge` claims (both profiles):

- electric / magnetic gauge anomaly cancellation (K-agnostic, loops over nodes);
- electric / magnetic SU(gauge)^2 U(1) mixed gauge-global anomaly cancellation;
- electric / magnetic superpotential consistency (gauge invariance + R-charge 2);
- global symmetry factor matching;
- global 't Hooft anomaly matching;
- Tr R, Tr R^3, a, c matching from encoded R-symmetry;
- operator-map Abelian charge matching (U(1)_B, U(1)_R);
- R >= 2/3 for encoded gauge-invariant chiral operators.

`seiberg_sqcd` only:

- SQCD operator-map non-Abelian flavor-label matching;
- SQCD magnetic F-term meson-lifting consequence;
- SQCD one-flavor mass-deformation rank-flow arithmetic;
- SQCD mesonic flat-direction rank-flow arithmetic.

`kutasov` only:

- Kutasov meson tower completeness (checks M0..M_{k-1} are all present).

Metadata-level scaffolds (return `UNKNOWN` when data is absent):

- chiral ring / F-term relation metadata;
- moduli-space branch metadata;
- conformal-manifold metadata;
- generalized-symmetry / defect metadata;
- protected-quantity hooks (index, partition function, Hilbert series).

Known but unimplemented obligations (recorded as `NOT_IMPLEMENTED`):

- index matching;
- deformation checks.

## Superpotential Checks

Superpotential terms are checked for:

- gauge singlet structure, using representation tensor products needed for
  SQCD-like monomials;
- nonabelian global singlet structure, using the same limited tensor-product
  logic;
- U(1) neutrality for all non-R U(1) charges;
- total superfield R-charge equal to 2.

The tensor-product checker is intentionally narrow. It recognizes singlets
and basic fundamental-antifundamental pairings needed for SQCD-like cubic
terms. It is not a general invariant-theory engine.

## F-Term / Chiral-Ring Consequence Check

QFTCert extracts simple monomial F-term relations from the encoded
superpotential. For the SQCD magnetic theory it checks the consequence

```text
dW/dM contains q qtilde.
```

This is not implemented as a literal "required superpotential string" check.
It checks the physical consequence that the magnetic composite q qtilde is
constrained rather than becoming an extra independent mesonic chiral-ring
generator in the supported SQCD profile.

The same F-term data is used by deformation checks. One-flavor mass
deformation requires dW/dM to contain q qtilde, so a linear m M term can
produce q qtilde + m = 0 and trigger the expected magnetic Higgsing.
Mesonic flat-direction checks require the encoded F-terms to contain the
mass couplings dW/dq ~ M qtilde and dW/dqtilde ~ M q.

This is still far from full chiral-ring equivalence: QFTCert does not compute
Groebner bases, quantum constraints, nilpotent relations, or moduli-space
isomorphisms.

## Global Anomaly Table

The implemented table includes:

- SU(F)^3 for every nonabelian global SU(F);
- SU(F)^2 U(1) for every global SU(F) and every U(1), including U(1)_R;
- U(1)^3 and mixed U(1)^2 U(1) anomalies for all U(1) labels;
- gravitational-U(1) anomalies.

Only global symmetries are compared. Gauge symmetries are used to count
fermion multiplicities and gaugino contributions.

## Mixed Gauge-Global Anomalies

For every represented U(1) global symmetry, QFTCert checks
SU(gauge)^2 U(1) anomaly cancellation on each side of the proposed duality.
For U(1)_R this includes the adjoint gaugino contribution with R=1. This
validates that the encoded U(1) is a nonanomalous symmetry of the dynamical
gauge theory under the stated conventions.

## Encoded R-Symmetry Observables

Given an encoded U(1)_R, QFTCert computes:

```text
Tr R, Tr R^3,
a = 3/32 (3 Tr R^3 - Tr R),
c = 1/32 (9 Tr R^3 - 5 Tr R).
```

These are compared between the electric and magnetic descriptions. This is a
validation of the encoded R-symmetry data, not full a-maximization. The
prototype does not yet detect accidental symmetries or automatically repair
decoupled free fields.

For encoded gauge-invariant chiral operators, and for the default SQCD meson
and baryon maps, QFTCert also checks the SCFT unitarity-bound condition
R >= 2/3 and reports Delta = 3R/2 under the chiral-primary assumption.

## Deformation-Flow Check

The implemented deformation checks are deliberately narrow. For SQCD-like
claims, QFTCert verifies one-flavor mass-deformation rank arithmetic,

```text
SU(Nc), Nf -> SU(Nc), Nf-1
SU(Nf-Nc) -> SU(Nf-Nc-1) = SU((Nf-1)-Nc).
```

If the resulting magnetic rank is below the current SU(N>=2) implementation,
the checker records a warning while still checking the rank arithmetic. This
does not implement general Higgsing, confinement, or integrating-out logic.

QFTCert also checks mesonic flat-direction rank arithmetic. For a branch with
B=Btilde=0 and rank(M)=k, it records the expected schematic flow

```text
electric:  SU(Nc), Nf -> SU(Nc-k), Nf-k
magnetic:  SU(Nf-Nc), Nf -> SU(Nf-Nc), Nf-k
```

and verifies that the magnetic rank equals `(Nf-k)-(Nc-k)=Nf-Nc`. This is a
rank and field-content check, not a proof of moduli-space equivalence.

## Operator-Map Flavor Labels

The standard SQCD operator maps are checked for both Abelian charges and
supported non-Abelian flavor labels:

```text
Q Qtilde       <-> M
Q^Nc           <-> q^(Nf-Nc)
Qtilde^Nc      <-> qtilde^(Nf-Nc)
```

For baryons, the checker uses the SU(Nf) epsilon-tensor equivalence
`Lambda^k F ~= Lambda^(N-k) anti-F`. It does not perform general
Young-tableau tensor decomposition or multiplicity counting.

## Machine-Readable Claims

The machine-readable input format is JSON. A minimal claim contains:

- `name`;
- `duality_profile`: `"seiberg_sqcd"` or `"kutasov"`;
- `parameters.Nc`, `parameters.Nf` (and `parameters.k` for Kutasov);
- optional `magnetic.rank`;
- optional `magnetic.include_meson`;
- optional R-charge or U(1)_B overrides for failure examples;
- optional `superpotential.terms` (seiberg_sqcd only).

The loader dispatches on `duality_profile` to the appropriate builder. The
`theory_kind` is inferred from field content at claim-load time; it can also
be stated explicitly in the JSON `metadata` object.

**Schema note**: the field was renamed from `claim_type` to `duality_profile`
in Phase 1.6. Historical traces in `traces/` may still use the old name.

## Certificate Output

The certificate records human-readable text and JSON-serializable structured
output:

- `claim_name`, `claim_id` (slug);
- `outward_status` (one of the five OUTWARD_* strings including OUT_OF_SCOPE);
- `internal_status` (legacy internal enum);
- `duality_profile` and `theory_kind`;
- `parameters`;
- passed / failed / not-implemented / unknown / not-applicable obligations;
- `warnings`, `assumptions`, `conventions`, `limitations`;
- `detailed_tables` from individual checkers.

For `OUT_OF_SCOPE` claims, the certificate explicitly states that no physics
checks ran and this is not a physics failure.

Readable text output emphasizes that the certificate is not a proof. JSON
output is intended for downstream AI tools, critic reports, and repair loops.

## Critic and Repair Prompt Output

For failed claims, QFTCert can generate:

- a critic report summarizing failed implemented obligations, repair hints,
  passed checks, and `NOT_IMPLEMENTED` obligations;
- a repair prompt that asks a human or LLM to make minimal JSON edits while
  preserving stated conventions.

The repair prompt generator is deliberately deterministic and model-free. It
is the bridge to an AlphaProof-like loop without committing the project to any
particular commercial or open-source language model.

## Failure Examples Covered by Tests

The test suite includes intentionally broken claims:

- wrong magnetic gauge group, causing global anomaly matching to fail;
- wrong meson R-charge, causing the superpotential R-charge check to fail;
- missing meson, causing a clear failed superpotential obligation;
- vector-like SQCD electric matter, verifying local gauge anomaly
  cancellation.
- JSON certificate stability for downstream AI tools;
- claim-file loading for a correct and a broken SQCD-like claim;
- CLI JSON mode for a correct and a broken claim.
- minimal operator-map U(1)_B and U(1)_R matching.

## Limitations

**Verifier scope**: Only `flavored_single_gauge` (K=1 with SU(Nf) flavor)
claims can be physically checked. `flavored_quiver` (K>1 with flavor) returns
OUT_OF_SCOPE. `pure_quiver` (no flavor) has data model support but no
implemented physics checks yet (Phase 2 target).

**Data model vs. verifier capability gap**: `Theory.gauge_nodes` supports
K >= 1 nodes and `Field.gauge_reps` supports per-node representations. The
anomaly/superpotential checkers loop over all nodes and are K-agnostic. But
no obligation verifies non-Abelian flavor matching, chiral ring equivalence,
or operator matching for K > 1 theories.

**Other limitations**:

- no theorem proving or dynamical proof of duality;
- no full Hilbert-series, index, or deformation-flow engine;
- no general Lie algebra package;
- no automatic discovery of operator maps;
- no general non-Abelian tensor-product decomposition;
- no full accidental-symmetry detection, decoupled-field repair, or
  a-maximization;
- SU(2), Nf = Nc + 1, and low-rank boundary cases may have special physics
  (s-confinement, enhanced symmetries) not explicitly modeled;
- profiles `seiberg_sqcd` and `kutasov` are hand-coded builders, not generic
  solvers.

Failures are failures of modeled consistency obligations under stated
conventions, not physical no-go theorems.

## Roadmap

**Phase 2a (next)**: pure_quiver chiral ring check.

- closed-walk enumeration of gauge-invariant single-trace operators up to
  a given R-charge cutoff;
- F-term Koszul step 1: subtract image of ∂W/∂Φ from the free algebra;
- check that the operator count and dimension matches between dual phases.

**Phase 2b**: dP_0 (C^3/Z_3 orbifold) builder + fixture + tests.

- 3-node cyclic SU(N)^3 quiver with 9 bifundamentals X_{ij};
- W = ε_{abc} X_{12}^a X_{23}^b X_{31}^c;
- verify toric Phase I ↔ Phase II duality via the pure_quiver chiral ring check.

**Other near-term**:

- structured failure schema for certificates (principle / observed /
  expected / affected_objects / severity) for better downstream agent use;
- OUT_OF_SCOPE section in `render_text()` (done in Phase 1.6);
- improve edge-case diagnostics for SU(2), Nf = Nc + 1, low magnetic rank;
- experiment harness: seed/temperature/cost/token logging, run manifest.
