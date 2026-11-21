# SCAN-017 Contract Decisions

Status: ANALYSIS AND DOCUMENTATION ONLY. No source, tests, config, fixtures, or detection behavior changed. Awaiting approval.

## 1. Corrected finding classifications

### A. Confirmed implementation defects
- Mixed-symbol list input in `_core_compute`: `symbol` and `timeframe` are taken from the first bar, so later bars with a different symbol or timeframe are mis-attributed. This is a real implementation defect in input handling, even though normal callers do not exercise it.

### B. Existing behavior to preserve (until an explicit contract change)
- Duplicate input bars are counted exactly as supplied; observed counts include duplicates.
- Stub tolerance uses `0 < observed < expected_bars - stub_tolerance` (weekday).
- First and last observed UTC dates are excluded from session-level anomaly detection.
- Saturday is skipped; Sunday uses a separate rule.
- Weekday detection is one-sided (under-count only); weekday over-counts do not fire.
- `expected_bars == 0` disables weekday missing/stub detection.
- Sunday uses absolute tolerance: `abs(observed - expected_sun_bars) > sun_tolerance`.
- Holidays are treated as ordinary weekdays.
- Event sorting and fixed session event schema.

### C. Product/domain decisions
- Whether duplicate bars should be rejected, deduplicated, or preserved.
- Whether holidays should fire missing-session anomalies.
- Whether first/last boundary dates should be included.
- Whether Saturday should gain anomaly detection.
- Whether weekday detection should also flag over-counts.
- Whether Sunday tolerance should be one-sided instead of absolute.
- Whether `expected_bars == 0` means "no session expected" or "disabled".

### D. Unresolved questions
- Whether mixed timeframes should be rejected or split (H1-only contract vs. per-bar timeframe).
- Whether mixed-symbol lists should be rejected or split internally.
- Exact duplicate identity (which fields define equality).
- Whether boundary exclusion is an intentional contract or inherited data-window behavior.
- Whether stub tolerance boundary should be inclusive.

## 2. Mixed-symbol and mixed-timeframe handling

### Call sites
- `scanline/scan.py`: for module `session_anomalies`, calls `compute_session_events(em_bars, params)` once per `(symbol, timeframe)` from `em_bars = extracted[(symbol, tf)]`. Bars are extracted per symbol/timeframe and tagged with `symbol` if missing. Inputs are therefore homogeneous by construction.
- Tests (`tests/test_sessions.py`, `tests/test_scan014.py`): pass single-symbol, single-timeframe bar lists.
- Direct/ad-hoc callers may pass mixed lists or dict input.

### Argument forms actually used
- `compute_events(bars, params)` with a homogeneous bar list.
- `compute_events(symbol, bars, params)` / `compute_events(bars, params)` variants via `_normalize_args`.
- Dict input `symbol -> bars` for multi-symbol aggregation.
- List of `(symbol, bars)` tuples.

### Mixed-symbol lists
- Possible only through direct/ad-hoc calls, not through `scan.py`.
- Dict-based input is the intended multi-symbol interface.
- Rejecting mixed-symbol lists would preserve all valid existing callers, because `scan.py` and tests never pass mixed symbols in one list.
- Recommendation: reject mixed-symbol lists with `ValueError`, rather than silently attributing all bars to the first symbol. Splitting would hide data-quality problems and complicate symbol attribution.

### Mixed-timeframe lists
- Possible through direct/ad-hoc calls; `scan.py` does not mix timeframes in one call.
- Session detection is documented as H1-only.
- Recommendation: reject mixed timeframes with `ValueError`. If a future multi-timeframe session mode is desired, that is a separate contract change requiring approval.

### Classification
- Mixed-symbol mis-attribution: A (confirmed defect).
- Mixed-timeframe handling: D (unresolved, but recommendation is rejection).

## 3. Duplicate input bars

### Current behavior
- Bars are sorted by `open_ts`; duplicates remain.
- `_group_bars_by_utc_date` increments counts for every bar, including duplicates.
- `_intra_session_gap_events` uses the per-date timestamp list, including duplicate timestamps.
- No duplicate detection, rejection, or deduplication exists.

### Duplicate kinds
1. Identical duplicate bars: same symbol, timeframe, open_ts, and OHLCV values.
2. Same timestamp, different OHLCV values.
3. Duplicate bars across different symbols (only relevant in dict or mixed input; not in normal single-symbol calls).

### Effects
- Inflates `observed_bars`, which can suppress `missing_session`, `stub_session`, or `sunday_anomaly`.
- Can make an under-counted session appear within tolerance.
- Duplicate identical timestamps do not create intra-session gaps (gap 0).
- Differing OHLCV at the same timestamp is counted twice but produces no gap event between those two bars.

### Policy comparison
1. Reject duplicates: strongest data-quality guarantee; requires a defined duplicate identity and may break callers with legitimately repeated bars. Recommended only if the input contract states bars are unique by `(symbol, timeframe, open_ts)`.
2. Deduplicate before counting: changes observed counts and event output; requires a defined duplicate identity and raises questions about which OHLCV to retain when values differ.
3. Preserve current behavior: no behavior change; duplicates remain an upstream data-quality concern.

### Duplicate identity
- A duplicate should be defined as same `(symbol, timeframe, open_ts)` at minimum.
- For identical duplicate bars, all fields including OHLCV match.
- For same timestamp with differing OHLCV, the bars are not identical duplicates; policy must specify whether timestamp uniqueness is required.

### Policy decision

**Policy B — reject duplicate keys at the input boundary (implemented in SCAN-017F).** Repeated `(symbol, timeframe, open_ts)` keys are rejected by `scanline/validation/duplicate.py::validate_unique_bar_keys`, including identical and conflicting OHLCV records. No silent deduplication. Cross-symbol (Class C) and cross-timeframe (Class D) timestamp matches are accepted.

Enforcement: `scanline/sessions.py::_core_compute` (before session counting/sorting) and `scanline/levels.py::compute_events` (before sorting/state processing), both calling the shared helper. `run_scan` is covered through these detectors; `scanline/scan.py` is not modified.

Error contract: `DuplicateBarKeyError(ValueError)` naming the canonical key (symbol, timeframe, UTC `open_ts` ISO + epoch seconds) and both occurrence input indices, plus `source` where available. No OHLCV values in error messages. Missing bar metadata or an unparseable `open_ts` raises a distinct plain `ValueError`.

## 4. Count semantics

### Weekday expected counts
- Applies to Mon-Fri interior dates only.
- `expected_bars` is required and must be a non-negative integer.
- Observed count is the number of input bars whose UTC date equals that date.

### Stub tolerance boundary
- Current condition: `0 < observed < expected_bars - stub_tolerance`.
- `observed == expected_bars`: no anomaly.
- `observed == expected_bars - stub_tolerance`: no anomaly (accepted).
- `observed == expected_bars - stub_tolerance - 1`: `stub_session`.
- `observed == 0`: `missing_session` if `expected_bars > 0`, otherwise no anomaly.
- `observed > expected_bars`: no anomaly (weekday over-count is not detected).

Example with `expected_bars = 3`, `stub_tolerance = 1`:
- observed 0 -> missing_session.
- observed 1 -> stub_session.
- observed 2 -> no anomaly.
- observed 3 -> no anomaly.
- observed 5 -> no anomaly.

### Zero-bar sessions
- Weekday interior date with 0 bars and `expected_bars > 0` -> `missing_session`.
- Weekday interior date with 0 bars and `expected_bars == 0` -> no anomaly.
- Sunday interior date with 0 bars and `expected_sun_bars > 0` -> `sunday_anomaly` if `expected_sun_bars > sun_tolerance`.
- Sunday interior date with 0 bars and `expected_sun_bars == 0` -> no anomaly.

### Sunday expected counts
- `expected_sun_bars` optional, default 0, non-negative integer.
- Anomaly condition: `abs(observed - expected_sun_bars) > sun_tolerance`.
- Applies to Sunday interior dates only.

Example with `expected_sun_bars = 2`, `sun_tolerance = 0`:
- observed 0 -> sunday_anomaly.
- observed 1 -> sunday_anomaly.
- observed 2 -> no anomaly.
- observed 3 -> sunday_anomaly.

Example with `expected_sun_bars = 2`, `sun_tolerance = 1`:
- observed 0 -> sunday_anomaly.
- observed 1 -> no anomaly.
- observed 2 -> no anomaly.
- observed 3 -> no anomaly.
- observed 4 -> sunday_anomaly.

### Sunday tolerance
- Absolute and symmetric.
- Unlike weekday stub tolerance, Sunday flags both under-counts and over-counts.

### Weekday over-counts
- Current behavior: no anomaly for `observed > expected_bars`.
- This is an intentional asymmetry in the current detector (it targets missing/stub sessions, not excess bars).

### `expected_bars == 0`
- Disables weekday missing and stub detection entirely.
- A weekday with 0 bars and expected 0 produces no event.
- A weekday with bars and expected 0 produces no event.
- This can be interpreted as "no session expected" or as "disabled"; the contract is not explicit.

## 5. Calendar semantics

### First/last date exclusion
- `first_date` and `last_date` are the UTC calendar dates of the earliest and latest bars.
- `_session_level_anomalies` evaluates only dates strictly between them.
- Reason: the input series boundaries are defined by available data; the first and last dates are treated as partial/edge sessions and are not evaluated for missing/stub/Sunday anomalies.
- This is inherited behavior from the detector's data-window model, documented as "unchanged semantics" but not explicitly stated as a contract clause.
- Whether this is intentional or merely inherited is unresolved (D3). Preserve current behavior until decided.

### Holidays
- No holiday calendar exists in the implementation.
- A weekday holiday with 0 bars fires `missing_session` if `expected_bars > 0`.
- Whether holidays should be represented as expected zero-bar days or excluded from detection is a product/domain decision (C/D1).

### Saturday
- Saturday is skipped in `_session_level_anomalies`.
- There is no Saturday expected-count configuration.
- Saturday is assumed to be a non-trading day.
- Whether Saturday should remain excluded or gain anomaly detection is a product/domain decision (C/C4).

### Sunday absolute tolerance
- Sunday uses `abs(observed - expected_sun_bars) > sun_tolerance`.
- This is broader than weekday stub tolerance and is intentional in the current implementation.
- Whether Sunday should be one-sided (under-count only) like weekdays is unresolved (D5).

## 6. Test strategy

### A. Characterization tests (document existing behavior)
- Boundary exclusion: first/last dates with low counts do not fire.
- One-date and two-date inputs produce no session-level anomalies.
- Stub boundary: `observed == expected - stub_tolerance` does not fire.
- `expected_bars == 0` disables weekday detection.
- Weekday over-count does not fire.
- Sunday absolute tolerance matrix.
- Duplicate bars inflate counts.
- Mixed-symbol mis-attribution (current behavior) before any fix.
- Empty input returns `[]`.

### B. Contract tests (already-approved behavior)
- Missing weekday detection.
- Stub session detection.
- Sunday anomaly detection.
- Intra-session gap detection and maintenance allowance.
- DST summer/winter no false gap.
- Config validation errors.
- Fixed UTC maintenance windows.
- Empty input.

### C. Proposed behavior tests (require approval)
- Rejecting mixed-symbol or mixed-timeframe input.
- Rejecting or deduplicating duplicate bars.
- Including boundary dates.
- Saturday anomaly detection.
- Holiday handling.
- Weekday over-count detection.
- One-sided Sunday tolerance.
- Inclusive stub tolerance boundary.
- Local-date grouping instead of UTC-date grouping.

### Test caution
- Do not convert questionable current behavior into permanent contract tests merely because it exists. Characterization tests should be clearly labeled as documenting current behavior, not as approved contract.

## 7. Deliverable summary

### Current behavior
- UTC-date grouping; interior dates only; Saturday skipped; Sunday separate.
- Weekday: missing at 0 bars (if expected > 0), stub below `expected - stub_tolerance`.
- Sunday: absolute tolerance around `expected_sun_bars`.
- No duplicate handling; duplicates are rejected at the input boundary under Policy B (SCAN-017F; see `scanline/validation/duplicate.py`). Mixed-symbol and mixed-timeframe lists are rejected (SCAN-017).
- Empty input returns `[]`; config defaults and validation as documented.

### Unresolved decisions
- Duplicate policy.
- Holiday representation.
- Boundary inclusion.
- Saturday handling.
- Weekday over-count detection.
- Sunday tolerance direction.
- `expected_bars == 0` semantics.
- Stub tolerance inclusivity.
- Mixed input rejection vs. splitting.

### Recommended policy
- Reject mixed-symbol and mixed-timeframe lists; use dict input for multi-symbol.
- Preserve duplicate handling as-is until a uniqueness contract is approved; prefer rejection over silent deduplication if approved.
- Preserve boundary exclusion, Saturday skip, weekday one-sided detection, and absolute Sunday tolerance until explicitly changed.
- Treat `expected_bars == 0` as "no session expected" only after contract clarification.
- Clarify stub tolerance inclusivity in the contract before changing the operator.

### Compatibility risks
- Rejecting mixed input changes error behavior for direct/ad-hoc callers only; `scan.py` and tests remain valid.
- Duplicate policy changes would alter observed counts and event output.
- Boundary or Saturday changes would increase event counts in real scans.
- Local-date grouping would change all non-UTC outputs.

### Required tests
- Characterization tests for all current behaviors listed above.
- Contract tests for approved behavior.
- Proposed behavior tests only after approval.

### Recommended implementation sequence
1. Approve or reject each unresolved decision.
2. Add characterization tests for current behavior.
3. Fix confirmed defect: mixed-symbol/mixed-timeframe rejection.
4. Only then consider duplicate policy, boundary, holiday, Saturday, over-count, and tolerance changes as separate approved work items.

### Exact files likely to change
- `scanline/sessions.py` (`_core_compute`, `_group_bars_by_utc_date`, `_session_level_anomalies`, `_normalize_args`, validation).
- `tests/test_sessions.py` and `tests/test_scan014.py`.
- `docs/SCAN-016-PROPOSAL.md` and `docs/SCAN-016B-PROPOSAL.md` if contract clauses are amended.
- `scanline/schema.py` only if new anomaly types or fields are approved.
- `scanline/scan.py` only if input contract or per-symbol handling changes.
PY
echo written