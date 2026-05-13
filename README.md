# QFTCert

QFTCert is an auditable AI-assisted reasoning infrastructure project for
theoretical physics. The first prototype, `dualitycert`, turns typed or
machine-readable 4d N=1 SQCD-like duality claims into consistency obligations,
runs implemented exact checkers, and emits structured certificates that can be
used by humans or AI agents as a verifier/oracle/critic layer.

QFTCert does not prove QFT statements and does not prove Seiberg duality. It
checks implemented consistency obligations under stated assumptions and
conventions.

## DualityCert-0 Scope

The current target is SQCD-like Seiberg-duality-style claims:

- electric SU(Nc) SQCD with Nf flavors Q and Qtilde;
- proposed magnetic SU(Nf - Nc) or user-specified SU(rank) theory;
- magnetic fields q, qtilde, and optionally meson M;
- global symmetries SU(Nf)_L, SU(Nf)_R, U(1)_B, and U(1)_R;
- magnetic superpotential terms such as W = M q qtilde.

Currently implemented checks:

- electric and magnetic SU(N) gauge anomaly cancellation;
- superpotential invariance under supported symmetries;
- superpotential R-charge equal to 2;
- global 't Hooft anomaly table matching.
- minimal operator-map matching for U(1)_B and U(1)_R charges.

Known obligations recorded as `NOT_IMPLEMENTED`:

- non-Abelian operator-map flavor representation matching;
- index matching;
- deformation checks.

## What a Certificate Means

A certificate is an auditable report of the checks that actually ran. It
records assumptions, conventions, obligations, per-obligation messages,
warnings, failures, and placeholders for checks that are not implemented.

Outward-facing statuses avoid proof-like language:

- `PASSED_IMPLEMENTED_OBLIGATIONS`
- `FAILED_IMPLEMENTED_OBLIGATIONS`
- `PARTIAL_WITH_NOT_IMPLEMENTED_OBLIGATIONS`
- `NO_IMPLEMENTED_OBLIGATIONS`

The legacy internal enum still includes `CERTIFIED`, but user-facing output
should be read as "implemented checks passed", not as a proof.

## What a Certificate Does Not Mean

A certificate does not prove a duality, IR equivalence, RG-flow statement, or
path-integral identity. It also does not check unimplemented obligations
silently. Missing operator-map, index, or deformation checks remain explicit
`NOT_IMPLEMENTED` entries.

## Quickstart

```bash
python3 -m pip install -e .
python3 -m pytest
python3 -m dualitycert.examples.seiberg_sqcd
```

## Check a Machine-Readable Claim

Correct SQCD-style claim:

```bash
python3 -m dualitycert.cli check claims/sqcd_Nc3_Nf5.json
python3 -m dualitycert.cli check claims/sqcd_Nc3_Nf5.json --json
```

Intentionally wrong magnetic rank:

```bash
python3 -m dualitycert.cli check claims/wrong_magnetic_rank.json --json
```

The CLI exits nonzero for program errors, not merely because a physics claim
fails implemented consistency checks.

## Example Workflow for AI-Assisted QFT Reasoning

```text
LLM proposes a QFT claim
-> QFTCert loads the typed/machine-readable claim
-> QFTCert generates obligations
-> implemented checkers run
-> certificate and critic report identify failures and NOT_IMPLEMENTED checks
-> the claim is repaired or rejected under the stated conventions
```

This is the intended role: an auditable verifier/oracle/critic layer for
AI-generated QFT claims.

## Current Limitations

- JSON claim input is SQCD-builder-level, not a universal QFT schema.
- Only Abelian U(1)_B and U(1)_R operator-map checks are implemented.
- Non-Abelian operator-map representation matching is not implemented.
- Index matching, deformation checks, moduli-space checks, global forms, and
  line operators are not implemented.
- The superpotential invariant checker is intentionally SQCD-like and narrow.
- Baryon-number normalization is explicit; a global rescaling is not by itself
  treated as a physical failure.

See [design.md](design.md) for conventions, implementation details, and
roadmap.
