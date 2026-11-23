# Freeze record: session_anomalies 1.1.0 (SCAN-022)
## Status
- **Module:** `session_anomalies`
- **param_version:** `1.1.0`
- **frozen_at:** `2026-11-23T08:07:02Z`
- **Scope:** Step 3 freeze released per SCAN-022 checkpoint response; confirmatory scan/publication in Step 4 after freeze commit.
## What changed (1.0.0 -> 1.1.0)
- **Calendar attribution tightened (Step 1 gate PASS):** `scanline/calendar_attribution.py` restricts attribution to `missing_session` and `stub_session` clusters only; `intra_session_gap`/`sunday_anomaly` never attributed. `CAL_ATTR_VERSION=scan022-calendar-v1`. Calendar v2 `config/calendars/session_anomalies.calendar.v2.json` (sha256 `d958a74296302612066a160d259de26bb6b8cbb29138594aad10c542eaffcea4`) used; v1 untouched.
- **Fit era rule (Amendment 1):** per-symbol template fit span is the 365 calendar days immediately before confirmatory window start (2024-09-02..2025-09-01, strictly before 2025-09-02). Provenance recorded per symbol in frozen params and this record.
- **Confirmatory window (Amendment 2):** 2025-09-02 -> 2026-01-19 (140 days inclusive), E_A=4620 symbol-days, n=33. Earliest start among qualifying span-eligible unburned windows of length>=140; burned A/B and overlaps excluded. Thanksgiving/Christmas inside window accepted by design (cluster-count verdicts; calendar annotates live).
- **Maintenance:** corrected fixed-UTC maintenance from SCAN-021 derivations (a). Cohort with 21:00Z hole encoded 20:00-22:00Z; symbols with no systematic hole encoded 00:00-00:01Z fixed UTC (harmless no-op window; start!=end required by validator). 1.0.0 America/New_York maintenance replaced.
- **Universe:** 33-symbol confirmatory set (mechanical rule: spans window and >=60 weekdays H1 history strictly before window start). Excluded 6 by rule: FEEDBEEF,HEATOIL,LEANHOGS,LIVEBEEF,LSGOIL,US2000. Params file retains full 39-symbol cluster table for detector compatibility; confirmatory pre-reg/scan uses the 33-symbol set.
## Step 1 gate evidence
- SCAN-021 fixture rerun (same rules/dates/universe/control): rule_occurrence_dates=214, clusters_on_scanned_dates=92, matches_on_scanned_dates=20, TP=14 FP=0 FN=0, precision=1.0, recall=1.0. Juneteenth 2026 missing_session and stub_session 2026-06-19 attributed. Control days 72, control false attributions 0. Report: `reports/scan022/SCAN-022-calendar-fixtures-v2.md`.
## Step 2 confirmatory selection
- Window: 2025-09-02 -> 2026-01-19 (140 days). Qualifying count 127 (length>=140). Selection: earliest start. E_A=4620.
- Included 33: AUDCAD, AUDUSD, CADCHF, CADJPY, CADNOK, CADSEK, COPPER, CORN, EURCAD, EURUSD, GASOLINE, GBPCAD, GBPUSD, GER40, GOLD, JPN225, NDAQ100, NZDCAD, NZDUSD, PALLADIUM, PLATINUM, SILVER, SOYBEAN, SPX500, UK100, UKOIL, US30, USDCAD, USDCHF, USDJPY, USNATGAS, USOIL, WHEAT
- Excluded 6: FEEDBEEF(weekdays_before=0<60), HEATOIL(1<60), LEANHOGS(0<60), LIVEBEEF(0<60), LSGOIL(1<60), US2000(26<60).
## Pre-registration (cluster-based, SCAN-020/021)
- Baselines from window A published clusters (driver-semantics): gap k_B=18, missing k_B=1, stub k_B=2, sunday k_B=4; E_B=1170. Alpha=0.0125. Rho floors per 100 symbol-days: gap 0.5, missing 0.1, stub 0.1, sunday 0.2. Ceilings computed by `scanline.prereg.cluster_ceiling(k_B, r=max(k_B/E_B,rho_floor/100), alpha)` at E_A=4620.
| anomaly_type | k_B | E_B | E_A | alpha | rho_floor/100sd | r=E_A/E_B | p | C | breach condition |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| intra_session_gap | 18 | 1170 | 4620 | 0.0125 | 0.5 | 3.94871795 | 0.79792746 | 124 | k_A>124 and rate_A>0.00500 |
| missing_session | 1 | 1170 | 4620 | 0.0125 | 0.1 | 3.94871795 | 0.79792746 | 27 | k_A>27 and rate_A>0.00100 |
| stub_session | 2 | 1170 | 4620 | 0.0125 | 0.1 | 3.94871795 | 0.79792746 | 35 | k_A>35 and rate_A>0.00100 |
| sunday_anomaly | 4 | 1170 | 4620 | 0.0125 | 0.2 | 3.94871795 | 0.79792746 | 48 | k_A>48 and rate_A>0.00200 |

## Template sanity comparison (vs ACTUAL 1.0.0 frozen params)
Comparison is against `config/scanner_params.session_anomalies-1.0.0.json` (frozen 1.0.0). Sanity flag means |delta expected_bars| > fitted stub_tolerance under Amendment 1; flagged deltas explained with 365-day fit-era evidence.

| Symbol | 1.0.0 exp | 1.0.0 stub_tol | 1.1.0 exp | 1.1.0 stub_tol | delta exp | flag | explanation |
|---|---:|---:|---:|---:|---:|---|---|
| AUDCAD | 24 | 23 | 24 | 3 | +0 | OK | unchanged |
| AUDUSD | 24 | 4 | 24 | 3 | +0 | OK | unchanged |
| CADCHF | 24 | 5 | 24 | 3 | +0 | OK | unchanged |
| CADJPY | 24 | 4 | 24 | 3 | +0 | OK | unchanged |
| CADNOK | 24 | 3 | 24 | 3 | +0 | OK | unchanged |
| CADSEK | 24 | 3 | 24 | 3 | +0 | OK | unchanged |
| COPPER | 1 | 22 | 23 | 2 | +22 | FLAG | Era-dominated 1.0.0 (full-history mode 1). 365d fit 2024-09-02..2025-09-01 wd_n=257 top_counts=[[23, 193], [21, 58], [2, 2], [14, 1], [17, 1]] |
| CORN | 1 | 18 | 19 | 1 | +18 | FLAG | Era-dominated 1.0.0 (full-history mode 1). 365d fit 2024-09-02..2025-09-01 wd_n=247 top_counts=[[19, 213], [18, 28], [6, 2], [17, 2], [5, 1]] |
| EURCAD | 24 | 5 | 24 | 3 | +0 | OK | unchanged |
| EURUSD | 24 | 4 | 24 | 3 | +0 | OK | unchanged |
| FEEDBEEF | 6 | 0 | 6 | 0 | +0 | OK | unchanged |
| GASOLINE | 1 | 22 | 23 | 2 | +22 | FLAG | Era-dominated 1.0.0 (full-history mode 1). 365d fit 2024-09-02..2025-09-01 wd_n=257 top_counts=[[23, 193], [21, 58], [2, 2], [14, 1], [17, 1]] |
| GBPCAD | 24 | 4 | 24 | 3 | +0 | OK | unchanged |
| GBPUSD | 24 | 4 | 24 | 3 | +0 | OK | unchanged |
| GER40 | 1 | 22 | 23 | 3 | +22 | FLAG | Era-dominated 1.0.0 (full-history mode 1). 365d fit 2024-09-02..2025-09-01 wd_n=252 top_counts=[[23, 186], [20, 52], [21, 7], [22, 4], [1, 2]] |
| GOLD | 1 | 22 | 23 | 2 | +22 | FLAG | Era-dominated 1.0.0 (full-history mode 1). 365d fit 2024-09-02..2025-09-01 wd_n=257 top_counts=[[23, 193], [21, 58], [2, 2], [14, 1], [17, 1]] |
| HEATOIL | 23 | 2 | 23 | 2 | +0 | OK | unchanged |
| JPN225 | 1 | 22 | 23 | 4 | +22 | FLAG | Era-dominated 1.0.0 (full-history mode 1). 365d fit 2024-09-02..2025-09-01 wd_n=257 top_counts=[[23, 191], [21, 51], [19, 7], [2, 2], [18, 2]] |
| LEANHOGS | 6 | 0 | 6 | 0 | +0 | OK | unchanged |
| LIVEBEEF | 6 | 0 | 6 | 0 | +0 | OK | unchanged |
| LSGOIL | 21 | 2 | 21 | 2 | +0 | OK | unchanged |
| NDAQ100 | 1 | 22 | 23 | 4 | +22 | FLAG | Era-dominated 1.0.0 (full-history mode 1). 365d fit 2024-09-02..2025-09-01 wd_n=257 top_counts=[[23, 191], [21, 51], [19, 7], [2, 2], [18, 2]] |
| NZDCAD | 24 | 21 | 24 | 3 | +0 | OK | unchanged |
| NZDUSD | 24 | 23 | 24 | 3 | +0 | OK | unchanged |
| PALLADIUM | 1 | 22 | 23 | 2 | +22 | FLAG | Era-dominated 1.0.0 (full-history mode 1). 365d fit 2024-09-02..2025-09-01 wd_n=257 top_counts=[[23, 193], [21, 58], [2, 2], [14, 1], [17, 1]] |
| PLATINUM | 1 | 22 | 23 | 2 | +22 | FLAG | Era-dominated 1.0.0 (full-history mode 1). 365d fit 2024-09-02..2025-09-01 wd_n=257 top_counts=[[23, 193], [21, 58], [2, 2], [14, 1], [17, 1]] |
| SILVER | 1 | 22 | 23 | 2 | +22 | FLAG | Era-dominated 1.0.0 (full-history mode 1). 365d fit 2024-09-02..2025-09-01 wd_n=257 top_counts=[[23, 193], [21, 58], [2, 2], [14, 1], [17, 1]] |
| SOYBEAN | 1 | 18 | 19 | 0 | +18 | FLAG | Era-dominated 1.0.0 (full-history mode 1). 365d fit 2024-09-02..2025-09-01 wd_n=247 top_counts=[[19, 241], [6, 2], [18, 2], [5, 1], [10, 1]] |
| SPX500 | 1 | 22 | 23 | 4 | +22 | FLAG | Era-dominated 1.0.0 (full-history mode 1). 365d fit 2024-09-02..2025-09-01 wd_n=257 top_counts=[[23, 191], [21, 51], [19, 7], [2, 2], [18, 2]] |
| UK100 | 1 | 22 | 23 | 3 | +22 | FLAG | Era-dominated 1.0.0 (full-history mode 1). 365d fit 2024-09-02..2025-09-01 wd_n=250 top_counts=[[23, 188], [20, 51], [21, 4], [22, 4], [12, 2]] |
| UKOIL | 1 | 21 | 22 | 1 | +21 | FLAG | Era-dominated 1.0.0 (full-history mode 1). 365d fit 2024-09-02..2025-09-01 wd_n=255 top_counts=[[22, 195], [21, 50], [18, 7], [19, 2], [13, 1]] |
| US2000 | 23 | 4 | 23 | 4 | +0 | OK | unchanged |
| US30 | 1 | 22 | 23 | 4 | +22 | FLAG | Era-dominated 1.0.0 (full-history mode 1). 365d fit 2024-09-02..2025-09-01 wd_n=257 top_counts=[[23, 191], [21, 51], [19, 7], [2, 2], [18, 2]] |
| USDCAD | 24 | 4 | 24 | 3 | +0 | OK | unchanged |
| USDCHF | 24 | 4 | 24 | 3 | +0 | OK | unchanged |
| USDJPY | 24 | 23 | 24 | 3 | +0 | OK | unchanged |
| USNATGAS | 1 | 22 | 23 | 2 | +22 | FLAG | Era-dominated 1.0.0 (full-history mode 1). 365d fit 2024-09-02..2025-09-01 wd_n=257 top_counts=[[23, 193], [21, 58], [2, 2], [14, 1], [17, 1]] |
| USOIL | 1 | 22 | 23 | 2 | +22 | FLAG | Era-dominated 1.0.0 (full-history mode 1). 365d fit 2024-09-02..2025-09-01 wd_n=257 top_counts=[[23, 193], [21, 58], [2, 2], [14, 1], [17, 1]] |
| WHEAT | 1 | 18 | 19 | 0 | +18 | FLAG | Era-dominated 1.0.0 (full-history mode 1). 365d fit 2024-09-02..2025-09-01 wd_n=247 top_counts=[[19, 240], [18, 3], [6, 2], [5, 1], [10, 1]] |

## Limitations / traps
- No holiday calendar in detector; calendar v2 provides additive attribution for missing/stub only (never suppresses/alters events).
- Thanksgiving/Christmas inside confirmatory window by design; verdicts on cluster counts; calendar annotations expected.
- 1.1.0 maintenance for no-hole symbols encoded as 00:00-00:01Z fixed UTC no-op (validator requires start!=end).
- Params file contains 39 symbols; confirmatory pre-reg/scan universe is 33-symbol mechanical set.
