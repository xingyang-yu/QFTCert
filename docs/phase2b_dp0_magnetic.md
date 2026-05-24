# Phase 2b dP_0 Magnetic Spec

**Status:** spec for Phase 2b-α (magnetic-side construction and standalone
validation). Phase 2b-β (the actual electric ↔ magnetic duality claim)
builds on this.

**Purpose:** lock down the physics of the magnetic dual of the dP_0
toric phase under single-node Seiberg duality, before writing any
code. The verifier will black-box check both anomaly cancellation and
chiral-ring consistency on this magnetic side; if the spec is wrong,
the verifier will (correctly) reject and we will not be able to tell
the verifier from the physics. Writing the derivation here first lets
us debug physics and code independently.

---

## 1. Electric theory (recap from Phase 2a+)

dP_0 = world-volume theory of D3-branes at the tip of the C³/ℤ_3
orbifold. Three SU(N) gauge nodes in a cyclic triangle A → B → C → A
(with A = 0, B = 1, C = 2 in the builder's 0-indexed nodes). Nine
bifundamentals organized as three copies on each directed edge:

| Field        | Direction | R-charge | Multiplicity |
|--------------|-----------|----------|--------------|
| X_AB[a]      | A → B     | 2/3      | 3 (a=0,1,2)  |
| X_BC[b]      | B → C     | 2/3      | 3            |
| X_CA[c]      | C → A     | 2/3      | 3            |

Superpotential: W_el = ε_{abc} X_AB[a] X_BC[b] X_CA[c], with
R(W_el) = 2 and the diagonal SU(3) flavor symmetry (rotating the
3 copies on each edge in tandem) preserved.

Concretely we will work at N = 3, so all gauge groups are SU(3) on the
electric side. SU(3) ABJ cubic and SU(3)² × U(1)_R mixed anomalies
both vanish at R = 2/3 (Phase 2a+ regression gate).

## 2. Seiberg duality at node A

At node A we have:
- 3 chiral antifundamentals X_AB[a] (Q̃-type at A)
- 3 chiral fundamentals X_CA[c] (Q-type at A)

Each pair (X_AB[a], X_CA[c]) is one chiral field with one extra
spectator index in SU(N) at the neighbor node. The effective flavor
count at A is therefore N_f = 3·N (three copies times N color
indices from the neighbor). With N_c = N and N_f = 3N, the magnetic
gauge rank is N_m = N_f − N_c = 2N.

**Convention (locked):** Seiberg duality at node A *reverses* the
arrows incident to A. Arrows not touching A are unchanged. A
gauge-invariance + anomaly-cancellation check (Section 4 below) pins
this convention; the alternative "arrows unchanged" convention would
not balance the SU(N)² × U(1)_R anomalies on nodes B and C with the
field content listed below.

## 3. Magnetic field content (effective)

After integrating out the antisymmetric component of the mesons
together with the field X_BC (see Section 5 for the mass-deformation
argument), the magnetic theory has:

| Field         | Direction | R-charge | Multiplicity | Physical role                |
|---------------|-----------|----------|--------------|------------------------------|
| q̃[a]         | A → C     | 1/3      | 3            | reversed X_CA, magnetic antiquark at A |
| q[c]          | B → A     | 1/3      | 3            | reversed X_AB, magnetic quark at A     |
| M^{(a,c)}     | C → B     | 4/3      | 6            | symmetric Sym²(3) of mesons survived   |

Gauge: SU(2N) × SU(N) × SU(N) at nodes A, B, C. At N = 3 this is
SU(6) × SU(3) × SU(3).

Twelve bifundamental fields total, in edge multiplicities (3, 3, 6).
This is the working field content for the Phase 2b public demo.

### 3.1 Symmetric-pair indexing for the 6 mesons

The 6 surviving mesons M^{(a,c)} are indexed by unordered pairs (a, c)
with a ≤ c. We use lexicographic order on those pairs:

| k | (a, c) |
|---|--------|
| 0 | (0, 0) |
| 1 | (0, 1) |
| 2 | (0, 2) |
| 3 | (1, 1) |
| 4 | (1, 2) |
| 5 | (2, 2) |

In code, `build_pure_quiver` auto-generates field names from edges;
the 6 mesons on edge C → B (= 2 → 1) get machine labels `X21[0..5]`,
which we read against the table above. The q̃ fields get labels
`X02[0..2]` (edge 0 → 2) and the q fields get `X10[0..2]` (edge 1 → 0).

## 4. Anomaly cancellation (verified by hand)

Each gauge node must have vanishing SU(N_node)³ cubic anomaly and
vanishing SU(N_node)² × U(1)_R mixed anomaly. With T(fund) = T(antifund)
= 1/2, T(adj) = N, gauginos contributing T(adj) = N on the mixed
anomaly (their fermion R-charge is +1):

### 4.1 Cubic SU(N_node)³ anomaly

Each chiral field in fund contributes +1 (in fund-equivalent units),
antifund contributes −1, times its multiplicity times its spectator
dimension at the neighbor node.

- **Node A = SU(2N):**
  - q̃ (3 copies, antifund A, spectator dim N at C): contributes
    3 · N · (−1) = −3N.
  - q (3 copies, fund A, spectator dim N at B): contributes
    3 · N · (+1) = +3N.
  - Total: 0. ✓

- **Node B = SU(N):**
  - q (3 copies, antifund B, spectator dim 2N at A): −3 · 2N = −6N.
  - M (6 copies, fund B, spectator dim N at C): +6 · N = +6N.
  - Total: 0. ✓

- **Node C = SU(N):**
  - q̃ (3 copies, fund C, spectator dim 2N at A): +3 · 2N = +6N.
  - M (6 copies, antifund C, spectator dim N at B): −6 · N = −6N.
  - Total: 0. ✓

### 4.2 Mixed SU(N_node)² × U(1)_R anomaly

Formula at gauge node: Σ_chirals T(rep) · (R_boson − 1) · dim(spectator)
+ T(adj) · 1 (gaugino) = 0.

- **Node A = SU(2N):**
  - q̃ (3 copies, R = 1/3, antifund A, spectator N at C):
    3 · (1/2) · (1/3 − 1) · N = −N.
  - q (3 copies, R = 1/3, fund A, spectator N at B):
    3 · (1/2) · (1/3 − 1) · N = −N.
  - Gauginos: T(adj of SU(2N)) = 2N.
  - Total: −N − N + 2N = 0. ✓

- **Node B = SU(N):**
  - q (3 copies, R = 1/3, antifund B, spectator 2N at A):
    3 · (1/2) · (1/3 − 1) · 2N = −2N.
  - M (6 copies, R = 4/3, fund B, spectator N at C):
    6 · (1/2) · (4/3 − 1) · N = N.
  - Gauginos: T(adj of SU(N)) = N.
  - Total: −2N + N + N = 0. ✓

- **Node C = SU(N):** (mirror of node B)
  - q̃ (3 copies, R = 1/3, fund C, spectator 2N at A): −2N.
  - M (6 copies, R = 4/3, antifund C, spectator N at B): +N.
  - Gauginos: +N.
  - Total: 0. ✓

All gauge anomalies cancel — this passes regardless of N.

## 5. Where the magnetic superpotential comes from

The pre-integration magnetic superpotential is the standard Seiberg
recipe plus the mass term inherited from the electric W_el via meson
substitution:

  W_mag^{pre} = y M[a, c] q̃[a] q[c]  +  ε_{abc} M[a, c] X_BC[b]

with y a Yukawa coefficient (we set y = 1 by field normalization),
M[a, c] the full 9-component (a, c) ∈ {0,1,2}² meson field on edge
C → B, and X_BC[b] still present.

The mass term sets the F-equation ∂_{X_BC[b]} W = ε_{abc} M[a, c] = 0,
i.e. the antisymmetric component of M in (a, c) vanishes in the chiral
ring. Simultaneously ∂_{M_{antisym}} W = (antisym part of q̃ q) +
X_BC = 0 (schematically), which pairs three antisymmetric M's with
three X_BC's into massive multiplets that we integrate out at low
energy.

After integration:

  W_mag^{eff} = M^{(a,c)} q̃[a] q[c]  (sum over a, c ∈ {0,1,2}²)

restricted to the symmetric (a, c) sector. Expanding (a, c) into the
6 symmetric pairs gives 9 monomial terms:

- 3 diagonal: M^{(a,a)} q̃[a] q[a] for a = 0, 1, 2.
- 3 off-diagonal pairs × 2 monomials each: M^{(a,c)} (q̃[a] q[c] +
  q̃[c] q[a]) for (a, c) ∈ {(0,1), (0,2), (1,2)}.

Each term has R = R(M) + R(q̃) + R(q) = 4/3 + 1/3 + 1/3 = 2 ✓.

## 6. The 9 W_eff monomials (machine labels)

The closed-walk requirement of `validate_w_terms` constrains the
factor order: each monomial's arrow sequence must compose into a
closed walk. With q on edge B → A (= 1 → 0), q̃ on edge A → C (= 0 → 2),
and M on edge C → B (= 2 → 1), the only composable order is
(q, q̃, M) (or any cyclic rotation thereof). We use (q, q̃, M):

| # | (a, c) | Factors (machine labels)              | Coefficient |
|---|--------|---------------------------------------|-------------|
| 1 | (0, 0) | (X10[0], X02[0], X21[0])              | +1          |
| 2 | (1, 1) | (X10[1], X02[1], X21[3])              | +1          |
| 3 | (2, 2) | (X10[2], X02[2], X21[5])              | +1          |
| 4 | (0, 1) | (X10[1], X02[0], X21[1])              | +1          |
| 5 | (0, 1)*| (X10[0], X02[1], X21[1])              | +1          |
| 6 | (0, 2) | (X10[2], X02[0], X21[2])              | +1          |
| 7 | (0, 2)*| (X10[0], X02[2], X21[2])              | +1          |
| 8 | (1, 2) | (X10[2], X02[1], X21[4])              | +1          |
| 9 | (1, 2)*| (X10[1], X02[2], X21[4])              | +1          |

The (a, c)* rows are the second monomial of the off-diagonal coupling
M^{(a,c)} (q̃[a] q[c] + q̃[c] q[a]).

## 7. What the verifier should report (Phase 2b-α)

Self-equivalence on the magnetic theory alone, default cutoff L = 6:
- All 4 upstream anomaly obligations CERTIFIED (verified Section 4).
- bounded_chiral_ring_consistency CERTIFIED at L = 6, r_graded = True.
- Two tested blocks: length 3, R = 2 has dim 10; length 6, R = 4
  has dim 28. Same numbers as electric — but with a structurally
  different quiver.

Note: lengths 4, 5, 7, 8 emit no blocks because magnetic arrows still
realize a 3-cycle (q̃ then M then q goes A → C → B → A), so closed
walks exist only at multiples of 3 — exactly as on the electric side.

## 8. Performance note (forward-looking to Phase 2b-β)

Wall-clock for the magnetic-side `evaluate_claim` at L = 6 is roughly
140 s (vs ~4 s for the electric side at L = 6). The cost is dominated
by Fraction-rank computation in `build_relation_matrix` on the larger
basis at length 6 (more arrows, more contexts, larger matrices). This
is within research-prototype tolerance but informs Phase 2b-β: tests
that compare electric ↔ magnetic at L = 6 will be on the order of
2-3 minutes per run.

## 9. Out of scope for this spec

- The Seiberg dual on a *different* node of dP_0 (B or C): trivially
  related by the cyclic symmetry of dP_0 and not separately tested.
- Two-node or three-node sequential Seiberg-duality chains.
- a-maximization or central charge matching: handled by existing
  Phase 1 obligations through evaluate_claim; not a Phase 2b focus.
- Non-toric topology / branes-at-singularities derivation: the
  field-content and R-charges above are stated as the verifier's
  input. Their physical justification is in standard references
  (Feng–Hanany–He, Berenstein, Klemm–Mayr–Vafa).
