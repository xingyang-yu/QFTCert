# Reproducibility and released artifacts

This note records what is released alongside the paper, and what integrity
checks were run before publication. It backs the artifact statement in
section 6 of the paper.

## Packaging

Artifacts are tracked in git rather than attached as a release tarball. The
paper cites in-repo paths (`runs/experiments/repair_d1/...`), so the data is
carved back in with targeted `.gitignore` negations while `runs/` stays
ignored otherwise. A fresh clone reproduces the paper with no extra download
step, and every hash is anchored in commit history instead of a mutable
release asset. The cost is small: 818 artifact files (528 depth-one, 290
depth-two), about 35 MB in the working tree, largest file under 1 MB.

### Included

- `runs/experiments/repair_d1/fixtures/`: the frozen benchmark manifest (159
  rows, SHA-256 pinned in `paper/execution_manifest.json`), 318 theory files,
  the generation config, and the attrition log.
- `runs/experiments/repair_d1/runs/conf_*`: all 57 confirmatory campaign
  directories (deepseek 18, qwen 18, minimax 21), including the `conf_*_e4_*`
  replay outputs and the `*_preclean` variants.
- `runs/experiments/repair_d1/confirmatory_analysis/`: both
  `confirmatory_analysis.json` reports, the preclean variant, and the six
  `e4_minimax_*` replay directories.
- `runs/experiments/repair_d1/quarantine_preclean_20260721/`: the full
  contamination-audit trail for the extension campaign (quarantined
  originals, removed rows, pass snapshots, `sha256_manifest.json`,
  `contaminated_ids.json`, `predicate.txt`).
- `runs/experiments/repair_d2/`: the exploratory depth-two fixtures and all
  ten run directories cited in appendix D.2, covering both data-producing
  campaigns (`d2_*`, `d2p2_*`) and the aborted attempt (`d2p_*`).

### Excluded

Exploratory pilot runs that predate the protocol freeze (`gemlite_*`, `glm*`,
`qwen*`, `scout_*`) and do not enter any analysis. Appendix D.2 discloses
them.

## Verification performed before release

All of the following were run in a fresh `git clone`, that is, against
exactly the file set a public cloner receives.

1. **Artifact integrity**, `scripts/verify_release_artifacts.py`: 104 checks,
   all passing. Covers `paper/execution_manifest.json` (config,
   fixture-manifest, and all seven prompt and schema hashes re-derived from
   the live code), benchmark arithmetic (159 rows, 14 certified positive
   controls, 145 runnable fixtures), campaign coverage (each of the 45 policy
   runs hits the 145 fixtures exactly once), the quarantine audit trail
   (original hashes, filtered states reconstructed from
   `contaminated_ids.json`, live-row provenance, final files clean under the
   frozen predicate), and the depth-two campaign counts cited in the
   appendix.
2. **Generated artifacts**, `scripts/paper_tables.py` rerun in the clone: all
   nine tables and the E4 forest figure regenerate byte-identical to the
   committed versions.
3. **Frozen analysis**, `scripts/run_gee.py`: both confirmatory GEE reports
   regenerate byte-identical to the committed JSON.
4. **Secret scan**: API-key patterns (Anthropic, OpenAI, OpenRouter, Groq,
   Gemini, GitHub tokens, JWTs, AWS keys, private-key headers) over the full
   clone and the entire git history. Zero real hits. The only match is the
   documentation placeholder at `docs/experiments.md:200`
   (`export OPENAI_API_KEY=sk-or-...`), which is literal and benign.
   Credential files are covered by `.gitignore` (`.env`, `*.env`) and appear
   nowhere in history.
5. **Freeze commits** referenced by `paper/execution_manifest.json`
   (`813fdb0` protocol freeze, `26c5241` tested harness) are ancestors of the
   published history.

## Re-running the checks

```bash
.venv/bin/python scripts/verify_release_artifacts.py
```

```bash
.venv/bin/python scripts/paper_tables.py && git diff --stat -- paper/tables paper/figures
```

```bash
.venv/bin/python scripts/run_gee.py
```

The full pipeline that produced the artifacts, from fixture generation to the
paper tables, is documented in appendix F of the paper.

## History

The repository is published with its full history, original hashes and dates,
without squashing. Two tags mark earlier curated subsets that predate the
open-source release: `public-demo-2026-05` and `public-curated-2026-05-23`.
