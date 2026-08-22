# Source Ledger

| ID | Source | Type | Date/version | Accessed | Relevance | Reliability notes |
| --- | --- | --- | --- | --- | --- | --- |
| S1 | `paper/analysis_protocol.md` | local frozen protocol | commit 813fdb0 | 2026-07-20 | Estimands, scope, arms, statistics | Canonical pre-data specification |
| S2 | `paper/execution_manifest.json` | local manifest | commit c155cff | 2026-07-20 | Prompt/config/fixture hashes and model routes | Canonical pre-data execution record |
| S3 | `paper/tables/primary.tex` and source analysis JSON | local generated result | commit 928d87e analysis | 2026-07-20 | Confirmatory endpoint values | Numbers checked against ignored local run artifact |
| S4 | `dualitycert/experiments/verifier.py` | local code | HEAD 495655e | 2026-07-20 | Gating status, feedback categories, strict verifier configuration | Implementation source of truth |
| S5 | `dualitycert/qft/checks.py` | local code | HEAD 495655e | 2026-07-20 | Obligation registry | Implementation source of truth |
| S6 | `dualitycert/experiments/repair.py` and `e4_replay.py` | local code | HEAD 495655e | 2026-07-20 | Repair policies and E4 replay semantics | Implementation source of truth |
| S7 | Seiberg, *Electric--magnetic duality in supersymmetric non-Abelian gauge theories*, hep-th/9411149 | primary paper | Nucl. Phys. B 435 (1995) | 2026-07-20 | Original 4d N=1 duality claim | INSPIRE key `Seiberg:1994pq`; published version and abstract checked |
| S8 | Intriligator and Seiberg, *Lectures on supersymmetric gauge theories and electric--magnetic duality*, hep-th/9509066 | review paper | 1996 | 2026-07-20 | Standard consistency checks and scope background | INSPIRE key `Intriligator:1995au`; use only for review-level background |
| S9 | Anselmi et al., *Nonperturbative formulas for central functions of supersymmetric gauge theories*, hep-th/9708042 | primary paper | Nucl. Phys. B 526 (1998) | 2026-07-20 | Central charges from R-symmetry anomalies | INSPIRE key `Anselmi:1997am`; abstract supports N=1 central-function formulas |
| S10 | Feng et al., *Toric duality as Seiberg duality and brane diamonds*, hep-th/0109063 | primary paper | JHEP 12 (2001) 035 | 2026-07-20 | Toric quiver duality background | INSPIRE key `Feng:2001bn`; abstract directly identifies toric and Seiberg duality in stated class |
| S11 | Yang et al., *LeanDojo: Theorem Proving with Retrieval-Augmented Language Models*, arXiv:2306.15626 | primary system paper | NeurIPS 2023 | 2026-07-20 | Programmatic interaction and feedback from Lean | Paper explicitly describes proof states, tactics, and Lean feedback |
| S12 | Hubert et al., *Olympiad-level formal mathematical reasoning with reinforcement learning* | primary paper | Nature 651 (2026) 607--613 | 2026-07-20 | AlphaProof as a formal-verifier learning environment | DOI and version-of-record metadata checked on Nature |
| S13 | Cobbe et al., *Training Verifiers to Solve Math Word Problems*, arXiv:2110.14168 | primary paper | 2021 | 2026-07-20 | Generate-and-rank verifier paradigm | Abstract supports verifier-based candidate selection on GSM8K only |
| S14 | Huang et al., *Large Language Models Cannot Self-Correct Reasoning Yet* | primary conference paper | ICLR 2024 | 2026-07-20 | Intrinsic versus externally grounded correction | Use narrow task-specific wording; reviewers challenged the title's breadth |
| S15 | Zhou et al., *Don't Trust: Verify---Grounding LLM Quantitative Reasoning with Autoformalization*, arXiv:2403.18120 | primary conference paper | ICLR 2024 | 2026-07-20 | Exact formal consistency checks for filtering LLM solutions | Autoformalization adds its own failure mode; not equivalent to typed native claims |
| S16 | Liang and Zeger, *Longitudinal data analysis using generalized linear models* | primary statistics paper | Biometrika 73 (1986) 13--22 | 2026-07-20 | GEE method citation | DOI 10.1093/biomet/73.1.13 verified |
| S17 | Holm, *A simple sequentially rejective multiple test procedure* | primary statistics paper | Scand. J. Stat. 6 (1979) 65--70 | 2026-07-20 | Multiplicity adjustment | Bibliographic record and DOI 10.2307/4615733 verified |
