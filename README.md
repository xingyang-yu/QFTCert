# QFTCert

QFTCert is an auditable AI-assisted reasoning infrastructure project for
theoretical physics. The first prototype, `dualitycert`, turns typed or
machine-readable 4d N=1 SQCD-like duality claims into consistency obligations,
runs implemented exact checkers, and emits structured certificates that can be
used by humans or AI agents as a verifier/oracle/critic layer.

QFTCert does not prove QFT statements and does not prove Seiberg duality. It
checks implemented consistency obligations under stated assumptions and
conventions.

> This repository is a public-facing subset of QFTCert demonstrating the
> architecture and core verifier loop. Additional in-development capabilities
> are kept private and shown on request.

## DualityCert-0 Scope

The current target is SQCD-like Seiberg-duality-style claims:

- electric SU(Nc) SQCD with Nf flavors Q and Qtilde;
- proposed magnetic SU(Nf - Nc) or user-specified SU(rank) theory;
- magnetic fields q, qtilde, and optionally meson M;
- global symmetries SU(Nf)_L, SU(Nf)_R, U(1)_B, and U(1)_R;
- magnetic superpotential terms such as W = M q qtilde.

Currently implemented checks:

- electric and magnetic SU(N) gauge anomaly cancellation;
- electric and magnetic SU(gauge)^2 U(1) mixed gauge-global anomaly cancellation;
- superpotential invariance under supported symmetries;
- superpotential R-charge equal to 2;
- represented continuous global symmetry factor matching;
- global 't Hooft anomaly table matching;
- Tr R, Tr R^3, a, and c comparison from the encoded R-symmetry;
- minimal operator-map matching for U(1)_B and U(1)_R charges;
- standard SQCD operator-map matching for SU(Nf)_L and SU(Nf)_R flavor labels;
- SQCD magnetic F-term consequence that constrains q qtilde in the chiral ring;
- R >= 2/3 checks for encoded/default SQCD gauge-invariant chiral operators;
- SQCD one-flavor mass-deformation rank-flow arithmetic.
- SQCD mesonic flat-direction rank-flow arithmetic.

Metadata-level scaffold checks return `UNKNOWN` when the required data is not
encoded, instead of failing the claim:

- general chiral ring / F-term relation metadata;
- moduli-space branch metadata;
- conformal-manifold metadata;
- generalized-symmetry / defect metadata;
- protected quantity hooks for indices, partition functions, and Hilbert series.

Known obligations recorded as `NOT_IMPLEMENTED`:

- index matching;
- deformation checks.

## Pure-Quiver and dP_0 Capabilities

Beyond strict SQCD scope, the current build implements:

- **Pure-quiver bounded chiral-ring consistency** (`pure_quiver` claims): a
  cyclic-derivative F-term quotient check on bounded paths of length up to a
  user-specified depth `L`. The output is a *bounded chiral-ring verdict*, not
  a full chiral-ring equivalence. See
  [docs/phase2a_pure_quiver_chiral_ring.md](docs/phase2a_pure_quiver_chiral_ring.md).
- **dP_0 paired Seiberg-dual consistency**: a paired check of the toric
  `SU(N)^3` electric phase against its non-toric
  `SU(2N) x SU(N) x SU(N)` single-node Seiberg dual with 12 bifundamentals.
  Covers anomaly matching, R-charge constraints, superpotential structure,
  and bounded chiral-ring verdicts on both sides. See
  [docs/phase2b_dp0_magnetic.md](docs/phase2b_dp0_magnetic.md).
- **Adversarial catch/miss characterization** on `dP_0`: a documented map of
  which adversarial perturbations the verifier currently catches versus
  misses. See
  [docs/phase2b_adversarial_catch_miss.md](docs/phase2b_adversarial_catch_miss.md).

## What a Certificate Means

A certificate is an auditable report of the checks that actually ran. It
records assumptions, conventions, obligations, per-obligation messages,
warnings, failures, and placeholders for checks that are not implemented.

Outward-facing statuses avoid proof-like language:

- `PASSED_IMPLEMENTED_OBLIGATIONS`
- `FAILED_IMPLEMENTED_OBLIGATIONS`
- `PARTIAL_WITH_NOT_IMPLEMENTED_OBLIGATIONS`
- `NO_IMPLEMENTED_OBLIGATIONS`

Per-obligation statuses may also include `UNKNOWN` for missing optional
metadata and `NOT_APPLICABLE` for checks outside the current physics profile.

The legacy internal enum still includes `CERTIFIED`, but user-facing output
should be read as "implemented checks passed", not as a proof.

## What a Certificate Does Not Mean

A certificate does not prove a duality, IR equivalence, RG-flow statement, or
path-integral identity. It also does not check unimplemented obligations
silently. Missing index, general deformation, or more general operator-map
checks remain explicit `NOT_IMPLEMENTED` entries.

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

## Generate Critic Reports and Repair Prompts

QFTCert can turn a failed certificate into a short critic report or a repair
prompt for a human or LLM, without calling any model API:

```bash
python3 -m dualitycert.cli critique claims/wrong_magnetic_rank.json
python3 -m dualitycert.cli repair-prompt claims/missing_meson.json
```

Both commands support `--out path/to/file.md`. This is the current
verifier-in-the-loop interface:

```text
claim.json -> certificate -> critic report / repair prompt -> repaired claim
```

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
- Operator-map checks cover Abelian charges and standard SQCD non-Abelian
  flavor labels; general tensor-product decomposition is not implemented.
- General index matching, full deformation checks, full chiral-ring
  equivalence, full moduli-space equivalence, global forms, line operators,
  and higher-form anomalies are not implemented. The only implemented
  chiral-ring consequence is the SQCD magnetic q qtilde F-term constraint.
- a and c are computed from the encoded R-symmetry; full a-maximization and
  accidental-symmetry handling are not implemented.
- The superpotential invariant checker is intentionally SQCD-like and narrow.
- Baryon-number normalization is explicit; a global rescaling is not by itself
  treated as a physical failure.

A detailed design document covering conventions, implementation, and roadmap
is available on request.
