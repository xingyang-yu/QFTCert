# QFTCert: Consistency Certificates for AI-Assisted Quantum Field Theory Reasoning

## 1. Motivation

AI-assisted theoretical physics reasoning needs more than fluent answers. A
model can propose plausible-looking QFT claims that fail basic consistency
conditions. QFTCert explores a verifier/oracle/critic layer: typed claims are
converted into explicit obligations, checked where possible, and returned as
auditable certificates.

The certificate is not a proof. It is a record of implemented checks under
explicit assumptions and conventions.

## 2. Why SQCD / Seiberg Duality

4d N=1 SQCD-like Seiberg duality is a controlled first target: the standard
claim is familiar, the expected consistency checks are well understood, and
failure cases are easy to construct without pretending to solve general QFT.

The point is not to rediscover the standard magnetic theory. The point is to
build a minimal environment where explicit electric and proposed magnetic
claims can be checked, criticized, and repaired.

## 3. Typed Claims, Obligations, Certificates

The current prototype takes a small SQCD-level JSON claim and builds a
`DualityClaim`. It then generates obligations such as gauge anomaly
cancellation, superpotential consistency, and global anomaly matching.

The certificate records:

- what ran;
- what passed;
- what failed;
- what remains `NOT_IMPLEMENTED`;
- the assumptions and conventions used.

## 4. Implemented Checks

DualityCert-0 currently implements:

- SU(N) gauge cubic anomaly cancellation;
- superpotential gauge/flavor/U(1) invariance for SQCD-like terms;
- superpotential R-charge equal to 2;
- global 't Hooft anomaly table matching for supported symmetries.
- minimal operator-map U(1)_B and U(1)_R charge matching.

## 5. Failure Cases

The repository includes intentionally broken JSON claims:

- wrong magnetic rank;
- missing meson;
- wrong meson R-charge;
- inconsistent magnetic U(1)_B charge in the superpotential.

These examples are meant to show a critic loop, not physical no-go theorems.

## 6. AI Critic / Repair Loop

The intended workflow is:

```text
LLM proposes claim
-> QFTCert checks implemented obligations
-> certificate highlights failures and unimplemented checks
-> agent or human repairs the claim
-> repaired claim is checked again
```

This gives downstream AI systems a more auditable way to interact with QFT
claims than free-form text alone.

## 7. Limitations

The prototype does not prove dualities or IR equivalence. It does not yet
implement non-Abelian operator-map representation matching, index matching,
deformation checks, global forms, line operators, accidental symmetries, or a
general QFT schema.

## 8. Roadmap

Near-term next steps:

- extend operator-map checks beyond Abelian charges;
- JSON certificate regeneration in `ai_runs/`;
- richer repair hints from failed obligations;
- edge-case warnings for low-rank special cases;
- broader but still explicit claim schemas.
