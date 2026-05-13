# Critic Report

QFTCert should return `FAILED_IMPLEMENTED_OBLIGATIONS` because the magnetic
superpotential term references M, but M is absent from the magnetic field list.
The report should make this a missing-field/superpotential-consistency failure,
not a proof-level statement.

Regenerate:

```bash
python3 -m dualitycert.cli check ai_runs/002_missing_meson/model_output_claim.json --json
```
