# QFTCert: Consistency Certificates for AI-Assisted Theoretical Physics

## 1. Motivation

AI-assisted theoretical physics needs more than fluent answers or a second
model saying that an answer looks correct. QFTCert explores a verifier,
oracle, and critic layer in which typed physics claims are converted into
explicit obligations, checked where possible, and returned as auditable
certificates.

A certificate is not a proof. It records the implemented checks that ran,
their assumptions and conventions, and the obligations that remain unknown,
out of scope, or unimplemented.

## 2. From a Small Prototype to a Research Environment

QFTCert began with SQCD-like Seiberg duality because the claims are familiar,
the expected consistency checks are well understood, and meaningful failure
cases can be constructed without pretending to solve general QFT. The current
repository now contains two complementary surfaces:

- flavored single-gauge certificate profiles for Seiberg SQCD and
  Kutasov-Schwimmer duality;
- the pure-quiver DualityCert verifier and verifier-gated repair environment
  used in the paper
  [*DualityCert: Verifier-Gated Language-Model Repair of Broken Duality Claims
  in Quantum Field Theory*](https://arxiv.org/abs/2607.23614).

The paper surface evaluates ordered pairs of 4d N=1 quiver gauge theories. It
was used to construct a preregistered benchmark of 145 broken but repairable
claims from six toric quiver families and to compare how several language
models exploit the same exact certificate.

## 3. Typed Claims, Obligations, and Certificates

The common abstraction is:

```text
typed claim
-> applicable obligation registry
-> exact or explicitly bounded checkers
-> structured certificate
-> policy-controlled critic feedback
-> human or agent repair
-> final verification
```

The certificate records:

- what ran and under which profile;
- what passed or failed;
- detailed observed and expected quantities where available;
- what remained `UNKNOWN`, `NOT_APPLICABLE`, or `NOT_IMPLEMENTED`;
- assumptions, conventions, warnings, and limitations.

This structure separates three questions that free-form model criticism often
blurs: whether the claim was represented faithfully, whether a particular
necessary condition was checked, and what the result of that check was.

## 4. Implemented Verification Surfaces

### Pure-quiver paper profile

The released paper profile checks:

- electric and magnetic gauge anomaly cancellation;
- gauge-global mixed-anomaly cancellation;
- global 't Hooft anomaly matching;
- superpotential gauge invariance and R-charge consistency;
- central-charge matching from the encoded R-symmetry;
- a bounded, R-graded classical chiral-ring consistency proxy.

The full committed registry contains 23 obligations. On a committed positive
fixture, 11 run and pass; the remaining obligations stay visible with
conservative statuses. The final judge can be stricter than the
interaction-time verifier, preventing the agent from simply being shown the
exact held-out numerical check that decides acceptance.

### Flavored single-gauge profiles

The `seiberg_sqcd` and `kutasov` builders support exact rational checks for:

- SU(N) gauge and SU(gauge)^2 U(1) mixed anomalies;
- superpotential gauge invariance and R-charge two;
- global anomaly tables and encoded central charges;
- supported Abelian and non-Abelian operator-map data;
- unitarity bounds for encoded chiral operators;
- selected SQCD F-term and deformation-flow consequences;
- Kutasov meson-tower completeness.

Metadata scaffolds preserve requested but unavailable checks for chiral rings,
moduli spaces, conformal manifolds, generalized symmetries, and protected
quantities instead of silently dropping them.

## 5. Verifier-Gated Repair and Evaluation

The repository includes a model-independent certificate and critic layer plus
an experiment harness for:

- deterministic fixture generation and manifest hashing;
- single-shot detection and diagnosis;
- generic retry, named-obligation feedback, masked-feedback controls, and
  independent verifier-filtered resampling;
- bounded multi-round repair;
- final judging at least as strict as the interaction-time verifier;
- token, cost, invalid-output, and per-attempt logging;
- frozen statistical analysis and artifact regeneration.

The released study finds a stable gain from verifier-gated iteration, but not
a universal best policy for exploiting the verifier. Feedback and search
policies therefore need to be calibrated to the agent while the exact
certificate can remain fixed.

## 6. Boundaries

QFTCert checks necessary conditions under encoded assumptions. It does not
prove a duality, derive a path integral, or establish full IR equivalence.

Important current boundaries include:

- no universal natural-language QFT parser;
- no full quantum chiral-ring or moduli-space equivalence;
- limited and profile-dependent a-maximization and accidental-symmetry
  handling;
- no uniform support for arbitrary Lie algebras and tensor products, index
  matching, global forms, defects, line operators, or higher-form symmetries;
- `flavored_quiver` claims remain outside the supported verifier scope.

The paper's results are claims about the named models, policies, benchmark,
and verifier profile. They do not establish that one feedback strategy is
best for all language models or all physics domains.

## 7. Program Direction

QFTCert is intended to grow through domain-specific verifier plugins that
share certificate semantics and agent interfaces. Near-term research includes
broader duality obligations, more general quiver reduction and operator
machinery, protected-quantity hooks, typed-claim compilers, and adapters to
AI-physicist systems.

The long-term aim is a collection of machine-checkable substrates for areas of
formal QFT and string theory: not replacements for physical judgment, but
auditable components that make AI-assisted reasoning easier to test, repair,
and trust.
