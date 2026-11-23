# SCAN-022 Preregistration (session_anomalies 1.1.0)

## Scope
- Confirmatory window A (SCAN-022): 2025-09-02 -> 2026-01-19 (140 days, inclusive), E_A=4620 symbol-days, n=33.
- Baseline window B provenance: window A published clusters from SCAN-019 (driver-semantics), E_B=1170; k_B: gap=18, missing=1, stub=2, sunday=4.
- Alpha=0.0125. Rho floors per 100 symbol-days: gap=0.5, missing=0.1, stub=0.1, sunday=0.2.
- Ceiling rule: `scanline.prereg.ceiling_breach(k_B, k_A, E_B, E_A, alpha, rho_floor=rho/100)` / `cluster_ceiling(k_B, E_A/E_B, alpha)`; breach iff `k_A > C` and (if rho_floor) `k_A/E_A > rho_floor`.

| anomaly_type | k_B | E_B | E_A | alpha | rho_floor/100sd | r=E_A/E_B | p | C | breach condition |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| intra_session_gap | 18 | 1170 | 4620 | 0.0125 | 0.5 | 3.9487179487 | 0.7979274611 | 124 | k_A>124 and rate_A>0.00500 |
| missing_session | 1 | 1170 | 4620 | 0.0125 | 0.1 | 3.9487179487 | 0.7979274611 | 27 | k_A>27 and rate_A>0.00100 |
| stub_session | 2 | 1170 | 4620 | 0.0125 | 0.1 | 3.9487179487 | 0.7979274611 | 35 | k_A>35 and rate_A>0.00100 |
| sunday_anomaly | 4 | 1170 | 4620 | 0.0125 | 0.2 | 3.9487179487 | 0.7979274611 | 48 | k_A>48 and rate_A>0.00200 |
