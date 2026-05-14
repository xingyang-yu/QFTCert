# AI-Assisted Critic / Repair Examples

These are small synthetic audit examples, not raw chat logs. Each folder shows:

```text
LLM proposes a claim
-> QFTCert checks implemented obligations
-> critic report identifies failures and NOT_IMPLEMENTED obligations
-> repaired claim is recorded
```

Regenerate a JSON certificate for any `model_output_claim.json` with:

```bash
python3 -m dualitycert.cli check ai_runs/<case>/model_output_claim.json --json
```

Generate a model-free repair prompt with:

```bash
python3 -m dualitycert.cli repair-prompt ai_runs/<case>/model_output_claim.json
```

The certificate is an implemented-check report under stated assumptions. It is
not a proof of duality.
