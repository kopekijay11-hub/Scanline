# Freeze record: session_anomalies 1.0.0 (SCAN-019 checkpoint release)

## Status
- **Module:** `session_anomalies`
- **param_version (frozen):** `1.0.0`
- **frozen_at:** `2026-11-23T02:04:11Z` (UTC) — actual freeze-record creation timestamp
- **Grading context:** Step 0 graded PASS by Jarvis (as recorded in SCAN-019 instructions). Step 1a graded PASS. This release supersedes ambiguous parts of the original order; everything else stands.

## What changed (SCAN-019)
- **Resolution 1 (coverage clause v1, recorded here):** A 30-day window qualifies for a symbol set if **every symbol’s H1 series SPANS the window**: first bar on or before the window start, last bar on or after the window end — so every interior weekday is observable. Days with zero bars inside a spanned window are legitimate `missing_session` measurements, **not** disqualifications (a coverage rule that censored them would censor the measurement).
- **Calibration window (Resolution 1):** `2026-05-26` → `2026-06-24` (UTC), comparability context as noted in SCAN-019.
- **Resolution 2 (Step 1a, template calibration, before freeze):** Full-history reference calibration performed (see “Template calibration (Step 1a)” below). The calibrated per-symbol table is the evidence of this freeze.

## What did not change
- Detector semantics in `scanline/sessions.py` (anomaly types, maintenance window handling, DST logic, duplicate rejection policy as implemented) remain unchanged by this freeze except the frozen config values recorded here.
- Clause v2 (module 1 rule) is **not** edited and remains module 1’s rule.

## Coverage clause v1 (module 2, session_anomalies) — binding for this freeze
- A 30-day window qualifies for a symbol set if every symbol’s H1 series **spans** the window: first bar on or before the window start, last bar on or after the window end.
- Days with zero bars inside a spanned window are legitimate `missing_session` measurements, **not** disqualifications.
- Calibration/confirmatory window for this checkpoint: **2026-05-26 → 2026-06-24** (UTC).

## Run order and pre-registration discipline
- **Window B (exploratory, read-only, no ledger outcome line):** `2026-08-08` → `2026-09-06` (UTC), measured at **2026-11-23T01:55:27Z** (scan `20261123T015527898710Z_3fe48e04287b2e7ac984f264bc50d88c`). Run used the calibration-identical pre-timestamp-fix config (placeholder `frozen_at 2026-11-22T00:00:00Z`, param sha256 `9ff2d7eadae814c3baf76a2923f7097f4e6f67cf621b17ad487e56be997ddfa9`); calibration values identical to freeze commit.
- **Ceilings fixed from window B before window A ran.** Window B output was not used to tune params; params were frozen from Step 1a full-history calibration.
- **Window A exploratory precheck:** `2026-05-26` → `2026-06-24` (UTC), measured at **2026-11-23T01:56:31Z** (scan `20261123T015631111462Z_b62598e6129c9cf7bf5dd3c5194d2021`), same calibration-identical pre-timestamp-fix config. Not a publication artifact.
- **Freeze commit config:** `config/scanner_params.session_anomalies-1.0.0.json` (`param_version 1.0.0`, `frozen_at 2026-11-23T02:04:11Z`, raw param sha256 `65e26e645c48c6f8a4f5f6b15be61bd2f8ca998d6ff5193f21fe3c94f7507b26`). Published window A scan is run through driver publication machinery from this freeze-commit state.

## Pre-registration baselines and ceilings (derived from window B only)
Symbol-days = 39 symbols × 30 days = **1170**. Window B observed counts (from frozen-config scan above):

| anomaly_type | B count | B rate / 100 symbol-days | derivation (×/÷2 band, B>0) | ceiling (operative test) |
|---|---:|---:|---|---:|
| `intra_session_gap` | 255 | 21.794871794871796 | band [21.794871794871796/2, 21.794871794871796×2] = [10.897435897435898, 43.58974358974359] | 43.58974358974359 / 100 symbol-days (510.0 events / 1170) |
| `missing_session` | 1 | 0.08547008547008547 | band [0.08547008547008547/2, 0.08547008547008547×2] = [0.042735042735042736, 0.17094017094017094] | **0.17094017094017094 / 100 symbol-days (2.0 events / 1170)** — ceiling is the operative test |
| `stub_session` | 0 | 0.0 | B==0: ×/÷2 band undefined; ceiling fixed at 0.0 by the B-derived zero baseline | **0.0 / 100 symbol-days (0 events / 1170)** — ceiling is the operative test |
| `sunday_anomaly` | 28 | 2.3931623931623935 | band [2.3931623931623935/2, 2.3931623931623935×2] = [1.1965811965811968, 4.786324786324787] | 4.786324786324787 / 100 symbol-days (56.0 events / 1170) |

Notes:
- Rates are `count / 1170 * 100`. The ×/÷2 band is applied where B>0; `stub_session` has B==0 so its ceiling is the B-derived zero baseline (operative test).
- For `missing_session` and `stub_session`, the **ceiling** is the operative pre-registration test named by SCAN-019; counts/rates above ceiling are a breach.
- The six window-A `missing_session` events are the **Juneteenth set**: `2026-06-19`, US agricultural/livestock symbols (`CORN`, `FEEDBEEF`, `LEANHOGS`, `LIVEBEEF`, `SOYBEAN`, `WHEAT`), observed_bars=0. This is the documented no-holiday-calendar trap (legitimate CME holiday closure reads as `missing_session`); it is named here, not hidden.

## Window A observed (calibrated config, same frozen config)
Symbol-days = 1170. Observed: `intra_session_gap` 288 (24.615384615384617/100), `missing_session` 6 (0.5128205128205128/100), `stub_session` 4 (0.3418803418803419/100), `sunday_anomaly` 28 (2.3931623931623935/100).

| anomaly_type | A count | A rate / 100 sd | ceiling / 100 sd | verdict vs ceiling |
|---|---:|---:|---:|---|
| `intra_session_gap` | 288 | 24.615384615384617 | 43.58974358974359 | inside band/ceiling |
| `missing_session` | 6 | 0.5128205128205128 | 0.17094017094017094 | **breach (ceiling operative)**; Juneteenth set named |
| `stub_session` | 4 | 0.3418803418803419 | 0.0 | **breach (ceiling operative)** |
| `sunday_anomaly` | 28 | 2.3931623931623935 | 4.786324786324787 | inside band/ceiling |

## Template calibration (Step 1a), full-history reference
Reference span: each symbol’s full H1 history in the corpus (`/home/joshua/corpus-store/*_H1.csv`).  
Method (mechanical summary):
- Group bars by UTC calendar day; Mon–Fri counted as weekdays, Sun as Sunday, Sat ignored.
- `expected_bars` = modal weekday (Mon–Fri) bar count over the reference span.
- `expected_sun_bars` = modal Sunday bar count over the reference span (if none observed, `0`).
- `stub_tolerance` = `wd_p95_dev` (95th percentile of `|observed_weekday_count - mode_weekday|` over Mon–Fri days, by the calibration script’s index rule). `sun_tolerance` = `sun_p95_dev` when Sundays exist; else `0`.
- Maintenance = symbol’s measured modal daily break from consecutive bars: gaps >= 1.5h define break candidates; modal break start/end hour (UTC) taken as most frequent start/end hours among those breaks. Recorded as `maint_utc (start–end)`. If no break detected, a documented fallback is stated per symbol.
- Symbols with identical schedule shapes may share a cluster (noted by inspection; table is source of truth per symbol).

### Known naive Step 0(d) missing_session events (window A, naive params) — carried forward
Naive detector run (expected_bars=24, expected_sun_bars=2, zone America/New_York, maint 17:00–18:00 local, stub_tol=1, sun_tol=0) produced **6** `missing_session` events, all **2026-06-19** (observed_bars=0):
- (CORN, 2026-06-19)
- (FEEDBEEF, 2026-06-19)
- (LEANHOGS, 2026-06-19)
- (LIVEBEEF, 2026-06-19)
- (SOYBEAN, 2026-06-19)
- (WHEAT, 2026-06-19)

These are the same Juneteenth set observed under calibrated config in window A; the no-holiday-calendar trap is explicit.

### Calibrated per-symbol table (evidence)
Source: `reports/scan019/SCAN-019-step1a-calibration.md` (generated 2026-11-22). The table below is the authoritative summary for this freeze.

| Symbol | Ref first..last | expected_bars (mode Mon–Fri) | stub_tolerance (wd_p95_dev) | expected_sun_bars (mode Sun) | sun_tolerance (sun_p95_dev) | maintenance_utc (modal break) | Notes |
|---|---|---:|---:|---:|---:|---|---|
| AUDCAD | 1993-04-26..2026-11-21 | 24 | 23 | 3 | 2 | 04:00–06:00 | Wide historic spread; mode-based template. |
| AUDUSD | 2006-01-01..2026-11-21 | 24 | 4 | 3 | 0 | 00:00–02:00 |  |
| CADCHF | 2006-01-01..2026-11-21 | 24 | 5 | 3 | 1 | 12:00–14:00 |  |
| CADJPY | 2007-02-12..2026-11-21 | 24 | 4 | 3 | 0 | 12:00–14:00 |  |
| CADNOK | 2023-02-27..2026-11-21 | 24 | 3 | 3 | 1 | 04:00–06:00 |  |
| CADSEK | 2023-02-27..2026-11-21 | 24 | 3 | 3 | 1 | 04:00–06:00 |  |
| COPPER | 2021-08-03..2026-11-21 | 1 | 22 | 1 | 1 | 20:00–22:00 | Full-history mode shows 1; interpret carefully against recent regimes. |
| CORN | 2021-06-22..2026-11-21 | 1 | 18 | 1 | 0 | 03:00–05:00 | Juneteenth set member (2026-06-19). |
| EURCAD | 2006-01-01..2026-11-21 | 24 | 5 | 3 | 1 | 12:00–14:00 |  |
| EURUSD | 2006-01-01..2026-11-21 | 24 | 4 | 3 | 0 | 00:00–14:00 | Measured break heuristic modal start/end 00:00–14:00. |
| FEEDBEEF | 2025-09-02..2026-11-21 | 6 | 0 | 0 | 0 | 20:00–22:00 (fallback) | No Sundays observed; no >=1.5h break detected — fallback documented. Juneteenth set member. |
| GASOLINE | 2021-08-16..2026-11-21 | 1 | 22 | 1 | 1 | 20:00–22:00 |  |
| GBPCAD | 2007-08-21..2026-11-21 | 24 | 4 | 3 | 1 | 12:00–14:00 |  |
| GBPUSD | 2006-01-01..2026-11-21 | 24 | 4 | 3 | 1 | 00:00–14:00 |  |
| GER40 | 2021-06-07..2026-11-21 | 1 | 22 | 1 | 0 | 20:00–22:00 |  |
| GOLD | 2021-06-20..2026-11-21 | 1 | 22 | 1 | 1 | 20:00–22:00 | Full-history mode_wd=1 per calibration summary; recent regimes differ, template follows full-history rule. |
| HEATOIL | 2025-08-31..2026-11-21 | 23 | 2 | 2 | 1 | 20:00–22:00 |  |
| JPN225 | 2021-06-21..2026-11-21 | 1 | 22 | 1 | 0 | 20:00–22:00 |  |
| LEANHOGS | 2025-09-02..2026-11-21 | 6 | 0 | 0 | 0 | 20:00–22:00 (fallback) | No Sundays; no break detected — fallback documented. Juneteenth set member. |
| LIVEBEEF | 2025-09-02..2026-11-21 | 6 | 0 | 0 | 0 | 20:00–22:00 (fallback) | No Sundays; no break detected — fallback documented. Juneteenth set member. |
| LSGOIL | 2025-08-31..2026-11-21 | 21 | 2 | 2 | 0 | 14:00–18:00 |  |
| NDAQ100 | 2021-06-21..2026-11-21 | 1 | 22 | 1 | 1 | 20:00–22:00 |  |
| NZDCAD | 2018-01-01..2026-11-21 | 24 | 21 | 3 | 0 | 04:00–06:00 |  |
| NZDUSD | 2022-10-20..2026-11-21 | 24 | 23 | 3 | 0 | 04:00–06:00 |  |
| PALLADIUM | 2021-06-20..2026-11-21 | 1 | 22 | 1 | 1 | 20:00–22:00 |  |
| PLATINUM | 2021-06-20..2026-11-21 | 1 | 22 | 1 | 1 | 20:00–22:00 |  |
| SILVER | 2021-06-20..2026-11-21 | 1 | 22 | 1 | 1 | 20:00–22:00 |  |
| SOYBEAN | 2021-06-23..2026-11-21 | 1 | 18 | 1 | 0 | 12:00–18:00 | Juneteenth set member (2026-06-19). |
| SPX500 | 2021-06-21..2026-11-21 | 1 | 22 | 1 | 1 | 20:00–22:00 |  |
| UK100 | 2021-05-16..2026-11-21 | 1 | 22 | 1 | 0 | 20:00–22:00 |  |
| UKOIL | 2021-06-27..2026-11-21 | 1 | 21 | 1 | 0 | 15:00–18:00 |  |
| US2000 | 2025-07-28..2026-11-21 | 23 | 4 | 2 | 0 | 20:00–22:00 |  |
| US30 | 2021-06-21..2026-11-21 | 1 | 22 | 1 | 1 | 20:00–22:00 |  |
| USDCAD | 2006-01-01..2026-11-21 | 24 | 4 | 3 | 1 | 20:00–22:00 |  |
| USDCHF | 2006-01-01..2026-11-21 | 24 | 4 | 3 | 1 | 00:00–18:00 |  |
| USDJPY | 2006-01-01..2026-11-21 | 24 | 23 | 3 | 0 | 00:00–02:00 |  |
| USNATGAS | 2021-06-20..2026-11-21 | 1 | 22 | 1 | 1 | 20:00–22:00 |  |
| USOIL | 2021-06-20..2026-11-21 | 1 | 22 | 1 | 1 | 20:00–22:00 |  |
| WHEAT | 2021-06-21..2026-11-21 | 1 | 18 | 1 | 0 | 12:00–18:00 | Juneteenth set member (2026-06-19). |

## Open traps (carried into this record)
- **No holiday calendar:** legitimate closures will read as `missing_session` (accepted for 1.0.0, named limitation). The Juneteenth set is the concrete instance in window A.
- **Half-days may read as `stub_session`** within tolerance design.
- **Templates are UTC-calendar-day based.**
None block 1.0.0; all stated here so readers do not mistake events for pure market signal.

## References
- `reports/scan019/SCAN-019-step1a-calibration.md`
- `config/scanner_params.session_anomalies-1.0.0.json` (param_sha256 `65e26e645c48c6f8a4f5f6b15be61bd2f8ca998d6ff5193f21fe3c94f7507b26`, frozen_at `2026-11-23T02:04:11Z`)
- `scanline/sessions.py`, `scanline/config_load.py`, `scanline/config_registry.py`
- Prior freezes: `docs/freezes/level_proximity-2.0.0.md`, `docs/freezes/level_proximity-2.1.0.md`
