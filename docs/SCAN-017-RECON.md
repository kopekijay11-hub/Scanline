# SCAN-017 — Session Boundary & Count Semantics (Reconnaissance)

Status: RECONNAISSANCE ONLY. No source, tests, config, or fixtures modified. Awaiting approval.

## 1. Current architecture and date/count flow

Pipeline (`scanline/sessions.py`):

1. `compute_events(*args, **kwargs)` -> `_normalize_args` resolves `(symbol, bars, params)` from many call shapes (list of bars, symbol+bars, bars+params, dict mapping symbol->bars, list of (symbol,bars)).
2. `_core_compute(bars, params)`:
   - If `params` is dict, `validate_session_config(params)`.
   - Empty `bars` -> `[]`.
   - Sort bars by `open_ts`.
   - Derive `symbol` and `timeframe` from first bar (`timeframe` defaults to `"H1"`; `symbol` may be `None`).
   - `_cluster_info(params, symbol)` resolves cluster config (expected bars, Sunday expected, zone, maintenance window, tolerances) with aliases and defaults.
   - `defined_at = frozen_at if present else first bar open_ts` (formatted); `param_version` from params.
   - `_group_bars_by_utc_date`: bucket bars by UTC calendar date (`ts.date()`); returns `counts`, `by_date_bars`, `first_date`, `last_date`.
   - `_session_level_anomalies(first_date, last_date, counts, ...)`: interior dates only (`first_date < cur < last_date`).
   - `_intra_session_gap_events(by_date_bars, ...)`: consecutive bars within the same UTC date.
   - Sort events by `(event_ts, anomaly_type, session_date)`.

Session-level anomaly rules:
- Saturday (`weekday == 5`): skipped.
- Sunday (`weekday == 6`): `sunday_anomaly` if `abs(observed - expected_sun) > sun_tol`.
- Mon-Fri (`weekday <= 4`):
  - `missing_session` if `observed == 0 and expected_weekday > 0`.
  - `stub_session` if `0 < observed < expected_weekday - stub_tol`.

Intra-session gap rule:
- Consecutive bars on same UTC date; gap `> INTERVAL_H1 (1h) + GAP_TOLERANCE (1min)`.
- Allowed if any maintenance window (with 30-min tolerance / overlap heuristic) covers it.

Event fields are fixed by `scanline/schema.py::SESSION_EVENT_FIELDS`; anomaly types: `missing_session`, `stub_session`, `intra_session_gap`, `sunday_anomaly`.

## 2. Findings A-F

### A. Date boundaries

- First/last dates are the UTC calendar dates of the earliest and latest bars after sorting by `open_ts` (`_group_bars_by_utc_date`).
- Boundary dates are excluded from session-level anomaly detection: `_session_level_anomalies` starts at `first_date + 1 day` and stops at `last_date` (exclusive). First and last dates are never evaluated for missing/stub/Sunday anomalies, even if their observed count is low.
- With 1 date: no interior dates -> no session-level anomalies (intra-session gaps still evaluated for that date).
- With 2 dates: no interior dates -> no session-level anomalies.
- Missing dates at boundaries cannot be detected: the data range is defined by observed bars, so there is no notion of an expected first/last day outside the observed span; boundary days themselves are excluded by construction.
- Boundary exclusion is inherited behavior (docstring "unchanged semantics"), not explicitly documented as a contract clause in code; SCAN-015/016 recon notes treat it as by-design.

### B. Missing dates

- Missing weekdays identified only for interior UTC dates, Mon-Fri (`weekday <= 4`), where `observed == 0` and `expected_weekday > 0`.
- Weekends: Saturday skipped entirely; Sunday handled by separate Sunday rule. No Saturday expected-count configuration exists.
- Holidays are not special-cased: a weekday holiday with 0 bars fires `missing_session` if `expected_weekday > 0`.
- A date with zero bars (`observed == 0`) is distinguishable from an incomplete session: zero bars -> `missing_session`; partial count -> `stub_session` (if below tolerance) or no event (if within tolerance). Over-count (more than expected) never fires for weekdays.

### C. Expected vs observed counts

- `expected_bars` (weekday) applied to every Mon-Fri interior date; `expected_sun_bars` applied to every Sunday interior date.
- `stub_tolerance` affects only the weekday stub branch: `stub_session` fires when `0 < observed < expected_weekday - stub_tol`. Thus:
  - `observed == expected_weekday`: no anomaly.
  - `observed == expected_weekday - stub_tol`: no anomaly (accepted, within tolerance).
  - `observed == expected_weekday - stub_tol - 1`: `stub_session`.
  - `observed == 0`: `missing_session` (if `expected_weekday > 0`), not stub.
- The comparison is one-sided for weekdays (only under-count detected) and absolute for Sundays (`abs(observed - expected_sun) > sun_tol`). Weekday over-count is never flagged.
- If `expected_weekday == 0`, weekday detection is effectively disabled (no missing, no stub; condition `observed < 0 - stub_tol` cannot hold for non-negative observed).
- Observed counts include duplicate bars (no deduplication), so duplicates can inflate counts and suppress anomalies.

### D. Sunday behavior

- `expected_sun_bars` optional, default `0`; `sun_tolerance` optional, default `0`.
- `sunday_anomaly` fires when `abs(observed - expected_sun) > sun_tol` (both under- and over-count).
- With `expected_sun_bars == 0` and `sun_tol == 0`: any Sunday with observed bars > 0 fires; a Sunday with 0 bars does not.
- With `expected_sun_bars == 0` and `sun_tol > 0`: up to `sun_tol` Sunday bars are accepted (no anomaly).
- Sunday rules are independent of weekday stub rules: separate config fields and separate branch; no stub concept for Sunday.
- Saturday is never evaluated under either rule.

### E. Duplicate handling

- No deduplication anywhere: bars are sorted by `open_ts`; duplicate timestamps remain separate entries.
- Identical duplicate bars increment `counts` and `by_date_bars`, so observed counts are inflated; this can suppress `missing_session`/`stub_session`/`sunday_anomaly` or, for Sunday, suppress/trigger depending on expected.
- Duplicate timestamps with differing OHLCV values are counted separately; they do not create intra-session gaps between each other (gap 0).
- Duplicates are not rejected, surfaced, or collapsed; they silently affect counts and gap detection.
- Whether deduplication belongs in this module or upstream is an open contract question.

### F. Input and configuration interactions

- Empty input -> `[]`.
- Single-symbol list with mixed symbols: `symbol` and `timeframe` taken from the first bar; all bars are attributed to that symbol/timeframe. Mixed-symbol lists are not split (dict input is required for per-symbol handling).
- Dict input (`symbol -> bars`) runs `_core_compute` per symbol and aggregates events.
- Missing config fields receive defaults: `expected_sun_bars=0`, `zone="UTC"`, maintenance `17:00`-`18:00`, `stub_tolerance=1`, `sun_tolerance=0`.
- Invalid config values are rejected before detection: `validate_session_config` / `_cluster_info` raise `ValueError` for unknown fields, missing `expected_bars`, bad types, bad HH:MM, invalid zone, identical maintenance start/end, conflicting aliases. `_core_compute` calls validation when params is a dict.
- `defined_at` falls back to first bar's `open_ts` (formatted UTC) when `frozen_at` is absent.
- `param_version` propagated from params (may be `None`).

## 3. Existing test coverage and gaps

Existing (`tests/test_sessions.py`, 23 tests):
- `TestAnomalies`: missing/stub/sunday combined; Sunday stub counts (2/3/0); outside-bounds (2 dates); intra-session gap; DST summer/winter no false gap.
- `TestScan016A`: strict `_parse_hhmm`; `GAP_TOLERANCE` constant; valid parse.
- `TestScan016B`: Honolulu defect (false gap), UTC maintenance window, Tokyo, NY winter, local-date-differs, cross-midnight, UTC boundary tolerance allowed/not, DST spring/autumn, real gap, fixed UTC, existing DST.

Coverage gaps (missing tests):
- Boundary exclusion: first/last date with low count does not fire; no dedicated assertion.
- One-date and two-date inputs (session anomalies absent) only indirectly.
- Stub tolerance boundary `observed == expected - stub_tol` (accepted) not explicitly asserted.
- `observed == expected - stub_tol - 1` (stub) only via general cases.
- `expected_bars == 0` weekday behavior.
- Saturday behavior (skipped) not tested.
- Holiday weekday behavior not tested.
- Sunday: `expected_sun_bars == 0` with observed > 0; `sun_tol > 0`; over-count; zero observed with nonzero expected.
- Duplicate bars (identical and differing OHLCV) not tested.
- Mixed-symbol list mis-attribution not tested.
- Empty input not tested in `test_sessions.py` (covered indirectly).
- Config defaults and invalid values beyond `_parse_hhmm` not tested.
- Intra-session gap `gap_hours` floor and cross-date gaps not tested.
- `defined_at`/`param_version` propagation not tested.

## 4. Concrete examples for suspected defects

1. Mixed-symbol mis-attribution: input `[GOLD bar, SILVER bar, GOLD bar]` with both clusters configured attributes all bars to GOLD (first bar's symbol); SILVER's bars count toward GOLD's session. Expected (if corrected): split by symbol or reject.
2. Duplicate inflation: two identical bars on a day with expected 3, tol 1 makes observed 2 (accepted) instead of 1 (stub). Duplicates can mask stub sessions.
3. Boundary invisibility: a series spanning Mon Jan 5 (1 bar) .. Wed Jan 7 (3 bars) emits no stub/missing for Jan 5 despite low count; a genuinely broken first session is invisible.
4. Holiday false positive: a market holiday on a weekday interior date with 0 bars fires `missing_session` if `expected_bars > 0`.
5. Sunday over-count: Sunday with expected 2 and observed 5 fires `sunday_anomaly`; weekday with expected 3 and observed 5 fires nothing (asymmetric).
6. `expected_bars == 0` disables weekday detection entirely; a weekday with 0 bars and expected 0 yields no event.
7. Over-count on weekday never flagged (only under-count via stub/missing).
8. Duplicate differing OHLCV at same timestamp counted twice but no gap event between them.

## 5. Classification of every finding

A. Existing intended behavior; preserve it:
- A1 UTC-date grouping of bars.
- A2 Boundary exclusion (first/last dates not evaluated).
- A3 Saturday skipped; Sunday separate rule.
- A4 Missing vs stub distinction and zero-bar handling.
- A5 Stub tolerance one-sided under-count for weekdays.
- A6 Sunday absolute tolerance with `abs(observed - expected) > tol`.
- A7 Empty input -> `[]`.
- A8 Config validation raising on invalid values.
- A9 Event sorting and fixed event schema.

B. Potential defect correctable without documented contract change:
- B1 Mixed-symbol list mis-attribution (SCAN-016 B1).
- B2 Duplicate bars inflating counts / masking anomalies (SCAN-016 B3) — dedup of identical anomaly records.
- B3 Stub tolerance boundary off-by-one: `observed == expected - stub_tol` currently accepted; whether inclusive boundary is intended needs clarification (SCAN-016 B5).
- B4 `_parse_hhmm` strictness already fixed (SCAN-016 A4/B2) — verify no residual callers.

C. Intentional behavior change requiring explicit approval:
- C1 Include boundary dates in anomaly detection.
- C2 Group by session-local date instead of UTC date.
- C3 Change `event_ts` from 23:00 UTC to local session close.
- C4 Saturday anomaly detection / Saturday expected config.
- C5 Holiday handling (exclude holidays or special-case).
- C6 Weekday over-count detection.
- C7 Change Sunday default `expected_sun_bars` from 0.
- C8 Cross-date / cross-midnight intra-session gap detection.
- C9 Deduplication of input bars (vs. anomaly records) — contract decision.

D. Insufficient evidence; requires product/domain decision:
- D1 Whether holidays should fire `missing_session`.
- D2 Whether `expected_bars == 0` should disable detection or mean "no session expected".
- D3 Whether boundary exclusion should remain (data-window edges vs. trading calendar).
- D4 Whether duplicate input bars should be rejected upstream vs. deduped here.
- D5 Whether Sunday tolerance should be one-sided (under-count only) like weekdays.

## 6. Proposed implementation sequence

1. Recon approval + contract clarification for C/D items (boundaries, holidays, local-date grouping, dedup scope).
2. Add missing tests for tolerance boundaries, Sunday matrix, duplicates, mixed symbols, empty input, config defaults (test-only; no source change).
3. Fix B-class defects in isolated commits: mixed-symbol handling, duplicate anomaly-record dedup, stub boundary clarification.
4. Only after approval implement C-class changes one at a time with golden fixtures and DST coverage.
5. Re-run full suite and equivalence harness after each step.

## 7. Risks and dependencies

- Changing UTC-date grouping (C2) alters all counts/events and golden outputs; high regression risk.
- Boundary inclusion (C1) increases event counts for real scans; affects scan ledgers.
- Dedup scope ambiguity (input bars vs. anomaly records) could change event counts.
- Maintenance window date basis (SCAN-016B) interacts with any local-date grouping change.
- Config alias complexity increases risk of conflicting values; validation already guards.
- Test suite currently green (23 session tests); any behavior change requires golden updates.

## 8. Files likely to change in future implementation

- `scanline/sessions.py` (grouping, anomaly loops, gap detection, dedup, arg normalization).
- `tests/test_sessions.py` (new cases; golden expectations).
- `tests/test_scan014.py` (if schema/config changes).
- `scanline/schema.py` (only if new anomaly types or fields).
- `scanline/scan.py` (if per-symbol splitting moves here).
- `docs/SCAN-016*-PROPOSAL.md` (contract updates).
- Config fixtures under `config/` (if defaults change).

## Summary

Session anomaly detection is UTC-date based, interior-dates only, with weekday stub (one-sided, tolerance-exclusive upper boundary), Sunday absolute tolerance, Saturday skip, and no deduplication. Mixed-symbol lists are mis-attributed; duplicates inflate counts; boundaries and holidays have non-obvious (inherited) behavior. Most B-class items are correctable; C/D items require explicit approval or product decisions. No files modified.
PY
echo written