# QFTCert

Ongoing project on a new scientific reasoning environment.

`dualitycert` is the first prototype package inside QFTCert: a physics-native
verifier layer for theoretical physics reasoning. It decomposes SQCD-like
Seiberg duality claims into machine-checkable consistency obligations and
returns structured certificates.

It is not a theorem prover, and it does not prove physical dualities.
`CERTIFIED` means only that the implemented exact consistency checks passed
under the stated assumptions and conventions.

## Prototype scope

DualityCert-0 supports 4d N=1 SQCD-like examples with:

- electric SU(Nc) SQCD with Nf flavors Q and Qtilde;
- magnetic SU(Nf - Nc) theory with q, qtilde, meson M;
- global symmetries SU(Nf)_L, SU(Nf)_R, U(1)_B, and U(1)_R;
- magnetic superpotential W = M q qtilde.

Implemented checks:

- electric and magnetic gauge anomaly cancellation;
- superpotential invariance under supported symmetries;
- superpotential R-charge equal to 2;
- global 't Hooft anomaly table matching.

Recorded but not implemented yet:

- operator map consistency;
- index matching;
- deformation checks.

## Install

```bash
python3 -m pip install -e .
```

## Run tests

```bash
python3 -m pytest
```

## Run the SQCD example

```bash
python3 -m dualitycert.examples.seiberg_sqcd
```

The example builds the Nc=3, Nf=5 SQCD-like claim, runs the generated
obligations, and prints a readable certificate with assumptions, limitations,
warnings, and NOT_IMPLEMENTED obligations.

## Conventions

See [design.md](design.md) for anomaly normalizations and limitations. In
brief, anomalies are computed from left-handed Weyl fermions, chiral multiplet
fermions use R-charge `R_superfield - 1`, and gauginos contribute to pure
U(1)_R and gravitational-U(1)_R anomalies.
