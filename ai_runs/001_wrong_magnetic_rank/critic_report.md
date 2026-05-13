# Critic Report

QFTCert should return `FAILED_IMPLEMENTED_OBLIGATIONS` for this claim. The
implemented local gauge anomaly checks can still pass, but global 't Hooft
anomaly matching fails because the proposed magnetic rank is 3 rather than
Nf - Nc = 2.

Regenerate:

```bash
python3 -m dualitycert.cli check ai_runs/001_wrong_magnetic_rank/model_output_claim.json --json
```
