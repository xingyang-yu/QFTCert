# QFTCert / DualityCert-0 Design

DualityCert-0 is a deliberately small verifier/certificate prototype for
SQCD-like Seiberg-duality-style claims in 4d N=1 supersymmetric gauge theory.
It is the first prototype inside QFTCert, an auditable AI-assisted reasoning
infrastructure project for theoretical physics.

The system does not prove dualities. It takes a typed or machine-readable
physics claim, generates a fixed set of consistency obligations, runs
implemented exact checkers, and emits a structured certificate describing what
passed, what failed, and what remains unimplemented.

## Project Goal

The first milestone is a runnable Python package that can construct the
standard electric/magnetic SQCD pair and answer:

> Given electric SU(Nc) SQCD with Nf flavors and a proposed magnetic
> SU(Nf - Nc) dual with q, qtilde, M, and W = M q qtilde, which
> machine-checkable consistency obligations are satisfied?

The intended output is not a bare `true` or `false`, but a certificate with
per-obligation status, convention assumptions, diagnostic tables, warnings,
and explicit `NOT_IMPLEMENTED` entries.

The intended AI workflow is:

```text
LLM proposes claim -> QFTCert checks obligations -> certificate/critic report
-> repaired claim
```

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

These labels mean exactly what they say about implemented checks; none of them
means "the duality is proven."

## Core Objects

The initial object model is small and explicit.

- `GaugeGroup`: currently SU(N).
- `GlobalSymmetry`: currently SU(N), U(1), and U(1)_R labels.
- `Representation`: `fundamental`, `antifundamental`, `adjoint`, `singlet`.
- `Field`: chiral or vector multiplet data, including gauge representation,
  global representations, U(1) charges, R-charge, and multiplicity.
- `SuperpotentialTerm`: a field monomial such as `M q qtilde`.
- `Theory`: a gauge group, fields, global symmetries, and superpotential
  terms.
- `SymmetryMap`: a label map from electric global symmetries to magnetic
  global symmetries.
- `DualityClaim`: electric theory, magnetic theory, symmetry map, and an
  operator-map placeholder.
- `Obligation`: generated consistency task with an optional checker.
- `Certificate`: structured result containing passed, failed, and
  unimplemented obligations, warnings, assumptions, limitations, and detailed
  tables.

## First-Version Physics Scope

Supported electric theory:

```text
SU(Nc) with Q and Qtilde, Nf flavors.
```

Supported magnetic theory:

```text
SU(Nf - Nc) with q, qtilde, meson M, and W = M q qtilde.
```

Default global symmetry:

```text
SU(Nf)_L x SU(Nf)_R x U(1)_B x U(1)_R
```

The current builder supports integer `Nc`, `Nf` with exact rational
arithmetic. It requires `Nf > Nc` and a supported magnetic gauge rank of at
least 2.

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

The first prototype generates and evaluates:

- electric gauge anomaly cancellation;
- magnetic gauge anomaly cancellation;
- electric superpotential consistency;
- magnetic superpotential consistency;
- global 't Hooft anomaly matching.

It also records these known but unimplemented obligations:

- operator map consistency;
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

## Global Anomaly Table

The implemented table includes:

- SU(F)^3 for every nonabelian global SU(F);
- SU(F)^2 U(1) for every global SU(F) and every U(1), including U(1)_R;
- U(1)^3 and mixed U(1)^2 U(1) anomalies for all U(1) labels;
- gravitational-U(1) anomalies.

Only global symmetries are compared. Gauge symmetries are used to count
fermion multiplicities and gaugino contributions.

## Machine-Readable Claims

The first machine-readable input format is JSON, not YAML, to avoid dependency
churn. It is intentionally SQCD-builder-level rather than a universal QFT
schema. A minimal claim contains:

- `name`;
- `claim_type: seiberg_sqcd`;
- `parameters.Nc`;
- `parameters.Nf`;
- optional `magnetic.rank`;
- optional `magnetic.include_meson`;
- optional R-charge or U(1)_B overrides for failure examples;
- optional `superpotential.terms`.

The loader adapts this input to the existing SQCD builder and check pipeline.

## Certificate Output

The current certificate records human-readable text and JSON-serializable
structured output:

- `claim_name`;
- outward-facing top-level status;
- legacy internal enum status;
- claim type and parameters when available;
- passed obligations;
- failed obligations;
- not-implemented obligations;
- warnings;
- assumptions;
- conventions;
- limitations;
- detailed tables from checkers.

Readable text output emphasizes that the certificate is not a proof. JSON
output is intended for downstream AI tools, critic reports, and repair loops.

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

## Limitations

The first prototype is intentionally modest:

- no theorem proving;
- no path-integral or dynamical proof of duality;
- no Hilbert-series, index, or deformation checks yet;
- no general Lie algebra package;
- no automatic discovery of operator maps;
- no implemented operator-map quantum-number checker yet;
- no automatic validation that a claimed global symmetry is truly
  nonanomalous beyond the implemented checks;
- no support for accidental symmetries, decoupled fields, a-maximization, or
  unitarity-bound diagnostics;
- no support for general superpotential invariant construction;
- no treatment of global forms, discrete quotients, defects, or line
  operators.

Failures should be read as failures of the modeled consistency obligations
under these conventions, not as physical no-go theorems.

## Roadmap

Natural next steps:

- add a minimal operator-map checker for Q Qtilde <-> M quantum numbers;
- add baryon operator charge checks in the current baryon normalization;
- add a gauge-gauge-U(1)_R non-anomaly checker as its own obligation;
- add richer critic/repair reports derived from JSON certificates;
- improve edge-case diagnostics for SU(2), Nf = Nc + 1, and low magnetic
  rank;
- add richer repair hints for common failed SQCD-like claims.
