# DualityCert Paper and Preregistered Protocol

This directory contains the source and frozen protocol artifacts for
[*DualityCert: Verifier-Gated Language-Model Repair of Broken Duality Claims in
Quantum Field Theory*](https://arxiv.org/abs/2607.23614).

The paper reports a preregistered study on 145 broken but repairable
pure-quiver duality claims. The verifier, benchmark, all per-attempt records,
and scripts that regenerate the reported tables and figure are released in
the repository; see [`../REPRODUCIBILITY.md`](../REPRODUCIBILITY.md).

## Main Files

- `main.tex`: current paper source corresponding to the released study.
- `refs.bib`: bibliography.
- `analysis_protocol.md`: preregistered primary analysis protocol.
- `analysis_protocol_amendment1.md`: preregistered MiniMax-M2.5 extension.
- `execution_manifest.json`: frozen code, fixture, prompt, schema, and
  configuration hashes.
- `tables/`: generated tables used in the paper.
- `figures/`: generated E4 results figure.
- `xy-format.sty`, `xy-math.sty`, `xy-theorem.sty`: local style files.

Historical design material is retained for provenance. The released paper is
`main.tex`; older `QFTCert.tex` material should not be treated as the current
paper entry point.

## Build

```bash
latexmk -pdf main.tex
```

## Regenerate Results Artifacts

From the repository root:

```bash
.venv/bin/python scripts/verify_release_artifacts.py
.venv/bin/python scripts/paper_tables.py
.venv/bin/python scripts/run_gee.py
```

The release checker verifies benchmark arithmetic, campaign coverage, prompt
and schema hashes, and the contamination-audit trail before the generated
tables and frozen statistical reports are compared with committed artifacts.

## Status

The current public version is arXiv:2607.23614v2. The repository retains the
full artifact history and protocol freeze commits described in
[`../REPRODUCIBILITY.md`](../REPRODUCIBILITY.md).
