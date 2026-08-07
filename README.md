# QFTCert: Auditable Verifiers for Theoretical Physics

QFTCert is a research program for turning native consistency checks in quantum
field theory and string theory into auditable tools for humans and AI agents.
Rather than asking a language model to judge another model in free-form text,
QFTCert turns a typed physics claim into explicit obligations, runs the exact
checkers that are available, and returns a structured certificate recording
what passed, what failed, and what could not be checked.

**DualityCert** is the first released QFTCert system. It combines:

- a symbolic verifier for 4d N=1 duality claims;
- machine-readable consistency certificates and deterministic critic output;
- a verifier-gated language-model repair environment;
- a reproducible benchmark and experiment harness for comparing how agents
  use the same certificate.

The accompanying paper is
[*DualityCert: Verifier-Gated Language-Model Repair of Broken Duality Claims in
Quantum Field Theory*](https://arxiv.org/abs/2607.23614). The verifier,
benchmark, preregistered protocol, per-attempt records, analysis, and artifacts
behind every reported number are released in this repository. See
[REPRODUCIBILITY.md](REPRODUCIBILITY.md).

## What Has Been Demonstrated

The paper evaluates verifier-guided repair on 145 deliberately broken but
repairable quiver-duality claims, generated from six toric quiver families and
four perturbation classes. The confirmatory study was preregistered before the
first confirmatory model call.

Key findings:

- verifier-gated retry improves final repair success over one attempt by
  **+8.3 percentage points on DeepSeek-Chat** and **+7.1 points on Qwen-Plus**;
- under the same budget of eleven attempts, the ordering of a stop-first
  feedback portfolio and independent verifier-filtered resampling reverses
  across models (**-10.3 points on DeepSeek-Chat, +14.7 on Qwen-Plus**);
- interpretable obligation-level feedback helps Qwen-Plus in this experiment,
  while the same effect is not detected on DeepSeek-Chat;
- a separately preregistered MiniMax-M2.5 extension again finds an iteration
  gain and favors independent verifier-filtered resampling.

The result is not that one repair policy is universally best. It is that the
same inexpensive symbolic certificate can support different model-specific
search and feedback policies. Every winning policy in the study uses the same
verifier.

## Project Map

| Layer | Role | Where to look |
| --- | --- | --- |
| QFTCert | Umbrella program for machine-checkable consistency substrates in theoretical physics | This repository and the roadmap in [design.md](design.md) |
| DualityCert verifier | Typed claims, obligation registry, exact checkers, certificates, critic output | [`dualitycert/qft/`](dualitycert/qft/) and [`dualitycert/core/`](dualitycert/core/) |
| Agent and experiment layer | Single-shot evaluation, repair loops, feedback projections, policy comparison, run manifests | [`dualitycert/agent/`](dualitycert/agent/) and [`dualitycert/experiments/`](dualitycert/experiments/) |
| Released benchmark | Frozen fixtures, confirmatory runs, quarantine audit trail, and per-attempt records | [`runs/experiments/`](runs/experiments/) |
| Paper and protocol | Preregistered endpoints, amendments, tables, figures, and source | [`paper/`](paper/) |

## Verification Surfaces Available Today

### Pure-quiver profile used in the paper

The paper's repair environment represents ordered pairs of 4d N=1 quiver
gauge theories and evaluates a fixed obligation registry. The implemented
profile includes:

- gauge anomaly and gauge-global mixed-anomaly cancellation;
- global 't Hooft anomaly matching;
- superpotential gauge invariance and R-charge consistency;
- central-charge matching from the encoded R-symmetry;
- a bounded, R-graded classical chiral-ring consistency check.

Certificates also record profile-gated, unknown, and unimplemented
obligations instead of silently treating them as passed. Interaction-time and
final checks can use different strictness, so an agent cannot receive the
answer to the exact held-out check it must ultimately pass.

The released benchmark contains 145 runnable broken claims from six seed
families (`dP_0`, `dP_1`, `dP_2`, `F_0`, SPP, and
`C^3/(Z_2 x Z_2)`) across 14 family/rank/node cells. Perturbations delete a
superpotential term, flip a coefficient sign, alter an R-charge, or change a
gauge-node rank.

### Flavored single-gauge profiles

The general certificate CLI also supports two explicit builder profiles:

- `seiberg_sqcd`;
- `kutasov` (Kutasov-Schwimmer duality with an adjoint and meson tower).

These profiles include exact rational checks for gauge and mixed anomalies,
superpotential consistency, global anomalies, encoded central charges,
supported operator maps, unitarity bounds, and selected SQCD deformation-flow
arithmetic. See [design.md](design.md) for the precise scope and conventions.

## What a Certificate Means

A certificate is an auditable report of checks that actually ran under stated
assumptions and conventions. It is not a proof of a duality, IR equivalence,
RG-flow statement, or path-integral identity.

Outward-facing statuses avoid proof-like language:

- `PASSED_IMPLEMENTED_OBLIGATIONS`
- `FAILED_IMPLEMENTED_OBLIGATIONS`
- `PARTIAL_WITH_NOT_IMPLEMENTED_OBLIGATIONS`
- `NO_IMPLEMENTED_OBLIGATIONS`
- `OUT_OF_SCOPE`

Individual obligations may also be `UNKNOWN`, `NOT_APPLICABLE`, or
`NOT_IMPLEMENTED`. A passed certificate means that no implemented in-scope
obligation failed; it does not mean that every physical consistency condition
has been checked.

## Quickstart

```bash
python3 -m pip install -e .
python3 -m pytest
python3 -m dualitycert.examples.seiberg_sqcd
```

Check a machine-readable claim:

```bash
dualitycert check claims/sqcd_Nc3_Nf5.json
dualitycert check claims/wrong_magnetic_rank.json --json
```

Generate a model-free critic report or repair prompt from a failed
certificate:

```bash
dualitycert critique claims/wrong_magnetic_rank.json
dualitycert repair-prompt claims/missing_meson.json
```

The core agent interface is:

```text
typed claim
-> obligation registry
-> exact implemented checkers
-> structured certificate
-> policy-controlled feedback
-> repaired or rejected claim
-> final judge at least as strict as the interaction-time verifier
```

The experiment CLI additionally exposes fixture generation, manifest
verification, single-shot evaluation, repair-loop policies, and the E4 policy
replay used in the paper:

```bash
dualitycert --help
dualitycert run-repair-loop --help
dualitycert score-e4 --help
```

## Reproducing the Released Study

A fresh clone contains the frozen fixtures and confirmatory artifacts; no
separate dataset download is required. The release checker verifies manifest
hashes, benchmark arithmetic, campaign coverage, prompt and schema hashes,
and the contamination-audit trail:

```bash
.venv/bin/python scripts/verify_release_artifacts.py
.venv/bin/python scripts/paper_tables.py
.venv/bin/python scripts/run_gee.py
```

The generated paper tables, figure, and frozen statistical reports are checked
against the committed artifacts. See [REPRODUCIBILITY.md](REPRODUCIBILITY.md)
for the full inventory and exact guarantees.

## Current Boundaries

- QFTCert checks necessary consistency obligations; it does not prove a
  duality or derive full IR dynamics.
- The natural-language-to-typed-claim step is not a general QFT parser.
- The bounded chiral-ring check is a controlled classical proxy, not full
  quantum chiral-ring or moduli-space equivalence.
- Central charges are only physical when the encoded R-symmetry is the correct
  superconformal one; support for a-maximization and accidental symmetries is
  limited and profile-dependent.
- General index matching, arbitrary Lie groups and tensor products, global
  forms, line operators, defects, and higher-form symmetries are not covered
  uniformly.
- A repair strategy that works well for one model should not be assumed to be
  optimal for another; the paper demonstrates this non-universality directly.

## Program Direction

QFTCert is designed so that new physics areas can supply their own typed claim
schema, obligation registry, exact or bounded checkers, certificate fields,
and final-judge policy. Natural extensions include richer quiver and operator
checks, protected quantities, amplitudes and bootstrap constraints, string
compactification consistency conditions, and adapters to AI-physicist agents.

The aim is not to replace physical judgment with a binary oracle. It is to
make the mechanically checkable part of that judgment explicit, reusable, and
auditable enough to guide and evaluate AI-assisted research.

## License

Apache License 2.0; see [LICENSE](LICENSE) and [NOTICE](NOTICE). The NeurIPS
LaTeX style file under `paper/` is distributed under its own terms.
