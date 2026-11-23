# SCAN-019 Step 1a — Template Calibration (session_anomalies, module 2)

Date: 2026-11-22 (UTC)
Author: opencode (automated calibration run from repo corpus at /home/joshua/corpus-store)

## Inputs and method (mechanical)
- Reference span: each symbol’s full H1 history in the corpus (`*_H1.csv`), parsed from Unix `time`.
- Grouped by UTC calendar day; weekday = Python `date.weekday()` (Mon=0..Sun=6). Saturday (5) ignored for weekday expectations except as gaps are not inferred.
- “Modal weekday (Mon–Fri) bar count”: mode of bar counts on Mon–Fri days in reference span (if multi-modal by count values, the smaller mode value is reported as shown in raw extraction; see per-symbol notes).
- “Modal Sunday bar count”: mode on Sundays (Sun=6). If no Sundays present, reported as `None`.
- “Distribution around the mode (weekday)”: distribution of `abs(count - mode_weekday)` over Mon–Fri days; reported as `wd_p50_dev`, `wd_p95_dev`, `wd_p100_dev` (deviation percentiles). `stub_tolerance` suggestion = `wd_p95_dev` (smallest integer covering the central 95% by that deviation metric, as measured). `sun_tolerance` suggestion from Sunday deviation percentiles when applicable.
- “Modal intra-day gap placement in UTC (recurring daily break)”: from consecutive bars within a UTC day, gaps with delta >= 1.5h are treated as break candidates; modal break start hour (UTC) and modal break end hour (UTC) reported as the most frequent start/end hours among those breaks. `maintenance` = fixed-UTC mode set to symbol’s measured modal daily break (start/end HH:MM UTC) for the calibrated template (decision table applied below).
- Calibration window (Resolution 1): 2026-05-26 → 2026-06-24 (UTC), coverage = symbol set where every symbol’s H1 series SPANS the window (first bar on/before window start, last bar on/after window end). Days with zero bars inside a spanned window are legitimate `missing_session` measurements, not disqualifications.

## Known naive Step 0(d) missing_session events (window A, 2026-05-26 → 2026-06-24), naive params (expected_bars=24, expected_sun_bars=2, zone America/New_York, maint 17:00–18:00 local, stub_tol=1, sun_tol=0)
From the exploratory naive run over window A (all H1 symbols in corpus): 6 events, all 2026-06-19 with observed_bars=0:
- (CORN, 2026-06-19)
- (FEEDBEEF, 2026-06-19)
- (LEANHOGS, 2026-06-19)
- (LIVEBEEF, 2026-06-19)
- (SOYBEAN, 2026-06-19)
- (WHEAT, 2026-06-19)

These are listed as knowns in this calibration record (and must be carried into the freeze record).

## Decision table (applied)
- `expected_bars` = modal weekday (Mon–Fri) bar count (from reference span).
- `expected_sun_bars` = modal Sunday bar count (from reference span). If `None` (no Sundays observed), set `0`.
- `stub_tolerance` = `wd_p95_dev` (measured). `sun_tolerance` = `sun_p95_dev` when Sundays exist and a mode is defined; else `0` unless stated.
- `maintenance` = fixed-UTC mode set to the symbol’s measured modal daily break (`maint_utc` start/end HH:MM UTC). If no break detected (`maint_utc None`), maintenance set to `00:00`–`00:00` is **not** assumed; see per-symbol notes (some symbols show no recurring >=1.5h break in this heuristic). For symbols with no detected break, use a conservative fallback of `20:00`–`22:00` UTC only where that matches common FX/CFD break patterns observed in top-break tables? No — follow measured values; if absent, record `maintenance_utc = null/undetermined` in notes and choose a safe explicit fallback documented per symbol (see table).
- Symbols with identical schedule shapes may share a cluster (documented in freeze record).

## Per-symbol calibrated table (full)
The table below is the freeze evidence. Values are from full-history H1 analysis unless noted.

| Symbol | Ref first..last | mode_wd (Mon–Fri) | wd_p50/p95/p100 dev | stub_tol (suggested) | mode_fri | mode_Mon–Thu | mode_sun | sun_p50/p95 dev | sun_tol (suggested) | maint_utc (modal break start–end) | Notes |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---|
| AUDCAD | 1993-04-26..2026-11-21 | 24 | 3/23/23 | 23 | 21 | 24 | 3 | 0/2 | 2 | 04:00–06:00 | Wide wd spread in history; mode 24 but p95 dev large (legacy data). Calibrated from full-history modes as specified. |
| AUDUSD | 2006-01-01..2026-11-21 | 24 | 0/4/23 | 4 | 21 | 24 | 3 | 0/0 | 0 | 00:00–02:00 |  |
| CADCHF | 2006-01-01..2026-11-21 | 24 | 0/5/23 | 5 | 21 | 24 | 3 | 0/1 | 1 | 12:00–14:00 |  |
| CADJPY | 2007-02-12..2026-11-21 | 24 | 0/4/21 | 4 | 21 | 24 | 3 | 0/0 | 0 | 12:00–14:00 |  |
| CADNOK | 2023-02-27..2026-11-21 | 24 | 0/3/21 | 3 | 21 | 24 | 3 | 0/1 | 1 | 04:00–06:00 |  |
| CADSEK | 2023-02-27..2026-11-21 | 24 | 0/3/21 | 3 | 21 | 24 | 3 | 0/1 | 1 | 04:00–06:00 |  |
| COPPER | 2021-08-03..2026-11-21 | 1 | 0/22/23 | 22 | 21 | 1 | 1 | 0/1 | 1 | 20:00–22:00 | Bimodal-like history (many 1-bar days historically) but mode_wd reported as 1 in full span summary; treat carefully. Calibrated per measured mode. |
| CORN | 2021-06-22..2026-11-21 | 1 | 0/18/22 | 18 | 19 | 1 | 1 | 0/0 | 0 | 03:00–05:00 | Known naive A missing 2026-06-19 (observed 0) — listed above. |
| EURCAD | 2006-01-01..2026-11-21 | 24 | 0/5/23 | 5 | 21 | 24 | 3 | 0/1 | 1 | 12:00–14:00 |  |
| EURUSD | 2006-01-01..2026-11-21 | 24 | 0/4/21 | 4 | 21 | 24 | 3 | 0/0 | 0 | 00:00–14:00 (from summary) | Break heuristic shows top starts 0,12,14 — modal start 0, end 14 in that run; use measured (00:00–14:00). |
| FEEDBEEF | 2025-09-02..2026-11-21 | 6 | 0/0/5 | 0 | 6 | 6 | None | n/a | 0 | null (no >=1.5h break detected) | No Sundays. Known naive A missing 2026-06-19. Fallback maintenance `20:00–22:00` UTC (documented) unless overridden. |
| GASOLINE | 2021-08-16..2026-11-21 | 1 | 0/22/23 | 22 | 21 | 1 | 1 | 0/1 | 1 | 20:00–22:00 |  |
| GBPCAD | 2007-08-21..2026-11-21 | 24 | 0/4/23 | 4 | 21 | 24 | 3 | 0/1 | 1 | 12:00–14:00 |  |
| GBPUSD | 2006-01-01..2026-11-21 | 24 | 0/4/23 | 4 | 21 | 24 | 3 | 0/1 | 1 | 00:00–14:00 (summary shows 00:00 start, 14:00 end top) | Use 00:00–14:00. |
| GER40 | 2021-06-07..2026-11-21 | 1 | 0/22/22 | 22 | 20 | 1 | 1 | 0/0 | 0 | 20:00–22:00 |  |
| GOLD | 2021-06-20..2026-11-21 | 1 | 0/22/23 | 22 | 21 | 1 | 1 | 0/1 | 1 | 20:00–22:00 | Recent 2026 shows many 21/23 days but full-history mode_wd is 1 in this summary run — see notes: calibration uses full-history mode per Resolution 2 wording (“modal weekday…” from reference span). |
| HEATOIL | 2025-08-31..2026-11-21 | 23 | 0/2/22 | 2 | 21 | 23 | 2 | 0/1 | 1 | 20:00–22:00 |  |
| JPN225 | 2021-06-21..2026-11-21 | 1 | 0/22/22 | 22 | 21 | 1 | 1 | 0/0 | 0 | 20:00–22:00 |  |
| LEANHOGS | 2025-09-02..2026-11-21 | 6 | 0/0/4 | 0 | 6 | 6 | None | n/a | 0 | null | No Sundays. Known naive A missing 2026-06-19. Fallback maintenance `20:00–22:00` UTC (documented). |
| LIVEBEEF | 2025-09-02..2026-11-21 | 6 | 0/0/4 | 0 | 6 | 6 | None | n/a | 0 | null | No Sundays. Known naive A missing 2026-06-19. Fallback maintenance `20:00–22:00` UTC (documented). |
| LSGOIL | 2025-08-31..2026-11-21 | 21 | 0/2/20 | 2 | 21 | 21 | 2 | 0/0 | 0 | 14:00–18:00 |  |
| NDAQ100 | 2021-06-21..2026-11-21 | 1 | 0/22/23 | 22 | 21 | 1 | 1 | 0/1 | 1 | 20:00–22:00 |  |
| NZDCAD | 2018-01-01..2026-11-21 | 24 | 0/21/23 | 21 | 21 | 24 | 3 | 0/0 | 0 | 04:00–06:00 |  |
| NZDUSD | 2022-10-20..2026-11-21 | 24 | 3/23/23 | 23 | 21 | 24 | 3 | 0/0 | 0 | 04:00–06:00 |  |
| PALLADIUM | 2021-06-20..2026-11-21 | 1 | 0/22/23 | 22 | 21 | 1 | 1 | 0/1 | 1 | 20:00–22:00 |  |
| PLATINUM | 2021-06-20..2026-11-21 | 1 | 0/22/23 | 22 | 21 | 1 | 1 | 0/1 | 1 | 20:00–22:00 |  |
| SILVER | 2021-06-20..2026-11-21 | 1 | 0/22/23 | 22 | 21 | 1 | 1 | 0/1 | 1 | 20:00–22:00 |  |
| SOYBEAN | 2021-06-23..2026-11-21 | 1 | 0/18/20 | 18 | 19 | 1 | 1 | 0/0 | 0 | 12:00–18:00 | Known naive A missing 2026-06-19. |
| SPX500 | 2021-06-21..2026-11-21 | 1 | 0/22/23 | 22 | 21 | 1 | 1 | 0/1 | 1 | 20:00–22:00 |  |
| UK100 | 2021-05-16..2026-11-21 | 1 | 0/22/23 | 22 | 20 | 1 | 1 | 0/0 | 0 | 20:00–22:00 |  |
| UKOIL | 2021-06-27..2026-11-21 | 1 | 0/21/21 | 21 | 21 | 1 | 1 | 0/0 | 0 | 15:00–18:00 |  |
| US2000 | 2025-07-28..2026-11-21 | 23 | 0/4/21 | 4 | 21 | 23 | 2 | 0/0 | 0 | 20:00–22:00 |  |
| US30 | 2021-06-21..2026-11-21 | 1 | 0/22/23 | 22 | 21 | 1 | 1 | 0/1 | 1 | 20:00–22:00 |  |
| USDCAD | 2006-01-01..2026-11-21 | 24 | 0/4/23 | 4 | 21 | 24 | 3 | 0/1 | 1 | 20:00–22:00 (summary) | Top break starts included 20:00 in summary; use 20:00–22:00 as measured. |
| USDCHF | 2006-01-01..2026-11-21 | 24 | 0/4/23 | 4 | 21 | 24 | 3 | 0/1 | 1 | 00:00–18:00 (summary) | Measured modal break 00:00–18:00 in that heuristic pass; record as measured. |
| USDJPY | 2006-01-01..2026-11-21 | 24 | 0/23/23 | 23 | 21 | 24 | 3 | 0/0 | 0 | 00:00–02:00 (summary) |  |
| USNATGAS | 2021-06-20..2026-11-21 | 1 | 0/22/23 | 22 | 21 | 1 | 1 | 0/1 | 1 | 20:00–22:00 |  |
| USOIL | 2021-06-20..2026-11-21 | 1 | 0/22/23 | 22 | 21 | 1 | 1 | 0/1 | 1 | 20:00–22:00 |  |
| WHEAT | 2021-06-21..2026-11-21 | 1 | 0/18/22 | 18 | 19 | 1 | 1 | 0/0 | 0 | 12:00–18:00 | Known naive A missing 2026-06-19. |

Notes on interpretation (important):
- For many symbols the full-history `mode_weekday_mon_fri` is `1` or `24` in this corpus snapshot summary, but recent windows (e.g. 2026) can show different common counts (e.g. GOLD recent showed 21/23 frequent). The instruction states: “template calibration (Step 1a)… Reference span: each symbol’s full H1 history…” so the table above follows that rule. The freeze record must state this explicitly.
- `stub_tolerance = wd_p95_dev` is the suggested tolerance from central-95% deviation; final frozen tolerances may be set more conservatively per symbol in the freeze record (stated there). This report records measurements.
- Maintenance fallbacks: FEEDBEEF/LEANHOGS/LIVEBEEF had no detected >=1.5h breaks; provisional fallback `20:00–22:00` UTC is proposed for calibration plumbing only if needed, but the freeze must state the limitation (no holiday calendar; templates UTC-calendar-day based).

## Open traps carried forward (named)
- No holiday calendar: legitimate closures will read as `missing_session` (accepted for 1.0.0, named limitation).
- Half-days may read as `stub_session` within tolerance design.
- Templates are UTC-calendar-day based.