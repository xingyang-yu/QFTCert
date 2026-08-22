# Research Report

## Bottom Line

The literature supports a narrow analogy: formal mathematics demonstrates that
machine-checkable environments can ground agent search, and prior work shows that
verifier-guided selection can improve particular reasoning benchmarks. It does not
support calling DualityCert a proof assistant or claiming that verifier feedback is
universally beneficial. The physics literature supports the obligation families as
standard necessary consistency conditions, while the local code and frozen protocol
remain the sole evidence for what DualityCert implements and how the repair policies
perform.

## Findings

1. Use LeanDojo and AlphaProof to motivate exact environment feedback, with an explicit
   sentence that DualityCert emits no proof terms and proves no duality.
2. Use Cobbe et al. and Zhou et al. for verifier-filtered candidate search; distinguish
   learned ranking and autoformalization from DualityCert's deterministic typed checker.
3. Use Huang et al. only for a narrow statement about intrinsic self-correction on the
   tasks studied; its broad title drew scope objections.
4. Cite Seiberg, the Intriligator--Seiberg review, Anselmi et al., and Feng et al. for
   physics background. Attribute the concrete bounded checker solely to this artifact.

## Evidence

See `source_ledger.md` and `claim_ledger.md`.

## Conflicts And Caveats

- Proof-assistant success does not establish that a domain-specific consistency checker
  yields the same learning dynamics.
- A learned verifier score, a formal proof check, and a deterministic symbolic
  consistency certificate are different interventions.
- The strongest paper claims therefore come from the local randomized model calls on
  the fixed benchmark, not from analogy to prior systems.

## Claim Audit

Claims C1--C9 survived the scope/refutation pass with the limitations recorded in the
claim ledger. No source supports a population-level model typology or proof-of-duality
language.

## Sources

See `source_ledger.md`; canonical BibLaTeX entries are stored in `paper/refs.bib`.
