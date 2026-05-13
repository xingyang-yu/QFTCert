# Critic Report

QFTCert should return `FAILED_IMPLEMENTED_OBLIGATIONS`. The meson R-charge
override makes the magnetic superpotential fail the implemented R(W)=2 check
and changes global anomalies involving U(1)_R.

Regenerate:

```bash
python3 -m dualitycert.cli check ai_runs/003_wrong_R_charge/model_output_claim.json --json
```
