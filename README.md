# QFTCert

Ongoing project on a new scientific reasoning environment.

`dualitycert` is the first prototype package inside QFTCert: a small,
physics-native consistency-certificate system for theoretical physics
reasoning. It currently targets 4d N=1 SQCD-like Seiberg duality claims.

QFTCert is not a theorem prover, and it does not prove physical dualities.
When the prototype reports `CERTIFIED`, it means only that the implemented
exact consistency checks passed under the stated assumptions and conventions.

## Prototype Scope

DualityCert-0 supports SQCD-like examples with:

- electric SU(Nc) SQCD with Nf flavors Q and Qtilde;
- magnetic SU(Nf - Nc) theory with q, qtilde, meson M;
- global symmetries SU(Nf)_L, SU(Nf)_R, U(1)_B, and U(1)_R;
- magnetic superpotential W = M q qtilde.

Implemented checks:

- electric and magnetic gauge anomaly cancellation;
- superpotential invariance under supported symmetries;
- superpotential R-charge equal to 2;
- global 't Hooft anomaly table matching.

Known but not implemented yet:

- operator map consistency;
- index matching;
- deformation checks.

## Install

```bash
python3 -m pip install -e .
```

## Run Tests

```bash
python3 -m pytest
```

## Run Example

```bash
python3 -m dualitycert.examples.seiberg_sqcd
```

The example builds the Nc=3, Nf=5 SQCD-like claim, runs the generated
obligations, and prints a readable certificate with assumptions, limitations,
warnings, and `NOT_IMPLEMENTED` obligations.

## Design Notes

See [design.md](design.md) for the project goal, physics conventions, anomaly
normalizations, certificate semantics, limitations, and roadmap.
