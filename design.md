# dualitycert design notes

`dualitycert` is a consistency-certification prototype for theoretical
physics reasoning. It is not a theorem prover, and it does not prove
physical dualities. A certificate reports that the implemented exact checks
passed under explicitly stated assumptions and conventions.

The first target, DualityCert-0, supports SQCD-like 4d N=1 Seiberg duality
claims:

- electric theory: SU(Nc) SQCD with Nf flavors Q and Qtilde;
- magnetic theory: SU(Nf - Nc) SQCD-like theory with q, qtilde, meson M;
- global symmetry labels: SU(Nf)_L, SU(Nf)_R, U(1)_B, U(1)_R;
- superpotential on the magnetic side: W = M q qtilde.

## Status semantics

The status labels are deliberately conservative.

- `CERTIFIED`: all implemented obligations passed, and at least one
  nontrivial implemented obligation was checked.
- `FAILED`: at least one implemented obligation failed.
- `NOT_IMPLEMENTED`: an obligation is known and recorded but has no checker.
- `SUPPORTED` and `PLAUSIBLE`: reserved for future heuristic or partial
  evidence layers.
- `PROVED`: included only as a reserved enum value; this prototype should not
  use it for duality claims.

In this project, `CERTIFIED` always means "the implemented checks passed",
not "the duality is proven."

## Representation conventions

This prototype currently supports SU(N) gauge and flavor groups, U(1), and
U(1)_R labels. The supported representation names are:

- `fundamental`
- `antifundamental`
- `adjoint`
- `singlet`

For SU(N), dimensions are normalized as usual:

- dim(fundamental) = dim(antifundamental) = N
- dim(adjoint) = N^2 - 1
- dim(singlet) = 1

For SU(N) cubic anomalies, the convention is:

- A(fundamental) = +1
- A(antifundamental) = -1
- A(adjoint) = 0
- A(singlet) = 0

For SU(N)^2 U(1) anomalies, the Dynkin index convention is:

- T(fundamental) = T(antifundamental) = 1/2
- T(adjoint) = N
- T(singlet) = 0

These normalizations are conventional and internally consistent, but other
physics literature may choose different overall factors. The certificate
prints the convention assumptions so comparisons are interpretable.

## Chiral multiplet and fermion conventions

Anomaly matching is computed using left-handed Weyl fermions. For a chiral
multiplet with scalar/superfield R-charge `R`, its fermion has R-charge
`R - 1`. Non-R U(1) charges are taken to be the same for the scalar and the
fermion.

Vector multiplet gauginos are included in pure U(1)_R and gravitational-U(1)_R
global anomalies. Their R-charge is +1 and their multiplicity is the dimension
of the gauge adjoint. Gauge fields are not included in non-R flavor anomalies.

## SQCD charge conventions

The bundled SQCD builder uses baryon number normalized so that an electric
baryon made from Nc quarks has charge +1:

- B(Q) = +1 / Nc
- B(Qtilde) = -1 / Nc
- B(q) = +1 / (Nf - Nc)
- B(qtilde) = -1 / (Nf - Nc)
- B(M) = 0

R-charge assignments for the conformal-window-like SQCD example are:

- R(Q) = R(Qtilde) = 1 - Nc / Nf
- R(q) = R(qtilde) = Nc / Nf
- R(M) = 2(1 - Nc / Nf)

The magnetic superpotential W = M q qtilde then has R-charge 2.

## Superpotential checks

Superpotential terms are checked for:

- gauge singlet structure, using representation tensor products needed for
  SQCD-like monomials;
- nonabelian global singlet structure, using the same limited tensor-product
  logic;
- U(1) neutrality for all non-R U(1) charges;
- total R-charge equal to 2.

The tensor-product checker is intentionally narrow. It recognizes pairings
such as fundamental x antifundamental -> singlet, antifundamental x
fundamental -> singlet, singlets, and SQCD-like cubic contractions. It is not
a general invariant-theory engine.

## Implemented obligations

The first prototype generates and evaluates these obligations:

- electric gauge anomaly cancellation;
- magnetic gauge anomaly cancellation;
- electric superpotential consistency;
- magnetic superpotential consistency;
- global 't Hooft anomaly matching.

The certificate also records these known but unimplemented obligations:

- operator map consistency;
- index matching;
- deformation checks.

## Global anomaly table

The implemented table includes:

- SU(F)^3 for every nonabelian global SU(F);
- SU(F)^2 U(1) for every global SU(F) and every U(1), including U(1)_R;
- U(1)^3 and mixed U(1)^2 U(1) anomalies for all U(1) labels;
- gravitational-U(1) anomalies.

Only global symmetries are compared; gauge symmetries are used only to count
fermion multiplicities and gaugino contributions.

## Limitations

The first prototype is intentionally modest:

- no theorem proving;
- no path-integral or dynamical proof of duality;
- no Hilbert-series, index, or deformation checks yet;
- no general Lie algebra package;
- no automatic discovery of operator maps;
- no automatic validation that a claimed global symmetry is truly nonanomalous
  beyond the implemented checks;
- no support for accidental symmetries, decoupled fields, a-maximization, or
  unitarity-bound diagnostics;
- no support for general superpotential invariant construction.

Failures should be read as failures of the modeled consistency obligations
under these conventions, not as physical no-go theorems.
