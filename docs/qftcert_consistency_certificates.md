# QFTCert: Consistency Certificates for AI-Assisted Quantum Field Theory Reasoning

## 1. Motivation

AI-assisted theoretical physics reasoning needs more than fluent answers. A
model can propose plausible-looking QFT claims that fail basic consistency
conditions. QFTCert explores a verifier/oracle/critic layer: typed claims are
converted into explicit obligations, checked where possible, and returned as
auditable certificates.

The certificate is not a proof. It is a record of implemented checks under
explicit assumptions and conventions.

## 2. Why SQCD / Seiberg Duality First

4d N=1 SQCD-like Seiberg duality is a controlled first target: the standard
claim is familiar, the expected consistency checks are well understood, and
failure cases are easy to construct without pretending to solve general QFT.

The point is not to rediscover the standard magnetic theory. The point is to
build a minimal environment where explicit electric and proposed magnetic
claims can be checked, criticized, and repaired.

Current duality profiles: `seiberg_sqcd` and `kutasov` (Kutasov-Schwimmer:
SU(Nc) + adjoint X + Nf flavors, W = Tr(X^{k+1})).

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

**All claims:**

- theory kind classification (pure_quiver / flavored_single_gauge /
  flavored_quiver); flavored_quiver → OUT_OF_SCOPE, no physics checks run.

**flavored_single_gauge claims (SQCD and Kutasov):**

- SU(N) gauge cubic anomaly cancellation (K-agnostic, loops over gauge nodes);
- SU(gauge)^2 U(1) mixed gauge-global anomaly cancellation;
- superpotential gauge invariance and R-charge = 2;
- global 't Hooft anomaly table matching;
- Tr R, Tr R^3, a, c from encoded R-symmetry;
- operator-map U(1)_B and U(1)_R charge matching;
- R >= 2/3 for encoded gauge-invariant chiral operators.

**seiberg_sqcd only:**

- SU(Nf)_L, SU(Nf)_R flavor-label matching for operators;
- SQCD magnetic F-term consequence constraining q qtilde;
- one-flavor mass-deformation and mesonic flat-direction rank-flow arithmetic.

**kutasov only:**

- Kutasov meson tower completeness (M0..M_{k-1} present in magnetic theory).

**Metadata scaffolds** (return `UNKNOWN` when data absent): chiral rings,
moduli spaces, conformal manifolds, generalized symmetries, protected quantities.

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
-> QFTCert generates a deterministic repair prompt
-> agent or human repairs the claim
-> repaired claim is checked again
```

This gives downstream AI systems a more auditable way to interact with QFT
claims than free-form text alone.

The current implementation does not require a model API. The repair prompt can
be generated locally and then handed to a human, a chatbox, or a future
automated agent.

## 7. Limitations

The prototype does not prove dualities or IR equivalence.

**Theory kind scope**: only `flavored_single_gauge` (K=1 with SU(Nf) flavor)
claims are checked. `flavored_quiver` (K>1 with flavor) → OUT_OF_SCOPE.
`pure_quiver` has data model support but no implemented physics checks yet.

**Data model vs. verifier gap**: `Theory.gauge_nodes` supports K >= 1 nodes,
and anomaly/superpotential checkers are K-agnostic. But no obligation yet
verifies K>1 duality physics — the multi-node data model is a scaffold
for Phase 2, not a claim of current capability.

Not yet implemented: general tensor-product decomposition, index matching,
full deformation checks, global forms, line operators, accidental symmetries,
full a-maximization, full chiral-ring equivalence, general QFT schema.

## 8. Roadmap

**Phase 2a**: pure_quiver chiral ring check (closed-walk enumeration +
F-term Koszul step 1). Enables verifying toric duality for quiver theories.

**Phase 2b**: dP_0 (C^3/Z_3 orbifold) builder + fixture + tests. First
concrete pure_quiver duality check.

**Other**: structured failure schema for certificates; experiment harness
with reproducible seed/temperature/token logging.
