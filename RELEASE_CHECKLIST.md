# Release checklist: public GitHub + arXiv v1

Gate for the section-6 artifact statement. Everything in "Done" is committed on
`phase2c-harness` and re-verifiable with the commands given; the "Your actions"
list is what remains before flipping the repository public. Target: complete
before arXiv v1 submission (2026-08-01).

## Done (verified, committed)

**Packaging decision: artifacts tracked in git, no release tarball.**
The paper cites in-repo paths (`runs/experiments/repair_d1/...`), so the data
is carved back into git with surgical `.gitignore` negations; `runs/` stays
ignored otherwise. A fresh clone reproduces the paper with no extra download
step, and the hashes are anchored in commit history rather than in a mutable
release asset. Cost is small: 528 files, ~31 MB working tree, ~3.6 MB packed,
largest file under 1 MB (GitHub's limit is 100 MB).

Included (commit `245b3ae`):

- `runs/experiments/repair_d1/fixtures/`: frozen benchmark manifest
  (159 rows, SHA-256 pinned in `paper/execution_manifest.json`), 318 theory
  files, generation config, attrition log.
- `runs/experiments/repair_d1/runs/conf_*`: all 57 confirmatory campaign
  dirs (deepseek 18, qwen 18, minimax 21), including the `conf_*_e4_*`
  replay outputs and the `*_preclean` variants.
- `runs/experiments/repair_d1/confirmatory_analysis/`: both
  `confirmatory_analysis.json` reports, the preclean variant, and the six
  `e4_minimax_*` replay dirs.
- `runs/experiments/repair_d1/quarantine_preclean_20260721/`: full MiniMax
  contamination-audit trail (quarantined originals, removed rows, pass
  snapshots, `sha256_manifest.json`, `contaminated_ids.json`,
  `predicate.txt`).

Excluded on purpose: exploratory pilot runs (`gemlite_*`, `glm*`, `qwen*`,
`scout_*`), depth-2 work under `runs/experiments/repair_d2/`, and macOS
`name 2.ext` duplicate files (note: `fixtures/attrition 2.jsonl` is a stale
pre-freeze copy that differs from the frozen `attrition.jsonl`; it stays
local-only and can be deleted).

**Verification already performed** (all in a fresh `git clone`, i.e. exactly
the file set a public cloner gets):

1. `scripts/verify_release_artifacts.py` (commit `3713eb4`): 99 checks, all
   passing. Covers `paper/execution_manifest.json` (config, fixture-manifest,
   and all 7 prompt/schema hashes re-derived from the live code), benchmark
   arithmetic (159 rows, 14 CERTIFIED positives, 145 runnable), campaign
   coverage (each of the 45 arm runs hits the 145 fixtures exactly once), and
   the quarantine audit trail (original hashes, filtered states reconstructed
   from `contaminated_ids.json`, live-row provenance, final files clean under
   the frozen predicate).
2. `scripts/paper_tables.py` rerun in the clone: all three tables and the E4
   forest figure regenerate byte-identical to the committed versions.
3. Secret scan: API-key patterns (Anthropic/OpenAI/OpenRouter/Groq/Gemini/
   GitHub tokens, JWTs) over the full clone and the entire git history. Zero
   real hits; the only match is the documentation placeholder
   `docs/experiments.md:200` (`export OPENAI_API_KEY=sk-or-...`), which is
   literal and benign.
4. `.env`: covered by `.gitignore` (`.env` and `*.env`) and never committed
   anywhere in history.
5. Freeze commits referenced by `paper/execution_manifest.json`
   (`813fdb0` protocol freeze, `26c5241` tested harness) are ancestors of
   this branch.

Re-run any time:

```bash
.venv/bin/python scripts/verify_release_artifacts.py
```

```bash
.venv/bin/python scripts/paper_tables.py && git diff --stat -- paper/tables paper/figures
```

## Your actions (in order, before the flip)

1. **Local working tree**: `paper/arch_loop.md` has uncommitted edits and
   there are untracked notes (`depth2_consistent_r_review.md`,
   `iso_guard_review.md`, `spp_depth2_review.md`, `paper/n1toolkit/`).
   Commit, relocate, or drop them; untracked files never publish, but the
   tagged release commit should be clean.
2. **LICENSE**: none in the repo yet. The 2026-07-14 pivot says MIT or
   Apache-2.0; pick one and commit it (Apache-2.0 adds an explicit patent
   grant, MIT is shorter). Also give `README.md` a quick pass for the public
   framing.
3. **Merge and push**: merge `phase2c-harness` into `main` (or decide the
   branch itself is the published head) and push. Publish with full history,
   no squashing: the dated commit history is the prior-invention evidence
   referenced in the FP carve-out.
4. **Optional belt-and-suspenders**: `brew install gitleaks && gitleaks git .`
   for an independent full-history secret scan.
5. **Tag**: `git tag arxiv-v1 <commit> && git push origin arxiv-v1`, then a
   GitHub Release pointing at it.
6. **Flip visibility** (you, not the agent):
   <https://github.com/xingyang-yu/QFTCert/settings> then "Danger Zone",
   "Change visibility". GitHub will warn that stars/watchers reset.
7. **Paper**: put the final repo URL + tag (or commit hash) into the
   section-6 artifact statement, rebuild, and submit arXiv v1.

## Post-flip sanity (5 minutes)

- Fresh clone from the public URL; run the two verification commands above.
- Check the GitHub file browser renders `runs/experiments/repair_d1/`
  (directory pages with many entries paginate; that is fine).
- Confirm the release tag resolves and the paper's cited paths exist at it.
