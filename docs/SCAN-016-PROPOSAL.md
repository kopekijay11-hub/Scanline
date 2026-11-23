# SCAN-016 Implementation Proposal (Reconnaissance Only)

Status: PROPOSAL — no code, config, fixtures, or tests modified. Awaiting approval.

## 1. Review Inputs
- `docs/SCAN-015-CLOSURE-SCAN-016-RECON.md`
- `tests/test_equiv_scan015.py` (13 cases; 12 passed, 1 skipped)
- Full suite result: 94 passed, 1 skipped
- Skipped test reason: `test_empty_events` — pre-refactor `validate_batch` calls `_get_first_event_ts(events)` unconditionally inside the frozen_at branch and raises `ValueError` on `min([])`; post-refactor guards with `if events:`. Not a behavioral regression for non-empty batches.

## 2. Scope
Session detection pipeline in `scanline/sessions.py` only. No validator behavior changes in this proposal beyond consuming session config (already present). No SCAN-016 code implementation yet.

## 3. Classification

### A. Internal refactors (no intended behavior change)
A1. Split `sessions.py` into focused modules (`session_config.py`, `session_compute.py`, `session maintenance.py`) mirroring SCAN-015.
A2. Extract `_core_compute` helpers (`_group_by_date`, `_detect_session_anomalies`, `_detect_gaps`) with identical logic.
A3. Normalize `_normalize_args` into explicit typed entry points (`compute_events(bars, params)`, `compute_events_by_symbol(mapping, params)`).
A4. Replace `_parse_hhmm` silent `(0,0)` fallback with explicit validation at config boundary (config already validates; helper becomes strict).
A5. Add type hints and docstrings to internal helpers.

### B. Defects correctable while preserving documented contract
B1. Multi-symbol input in `_core_compute`: currently uses `bars_sorted[0]` symbol/timeframe for all bars; if a mixed list is passed, wrong symbol/timeframe. Fix: require per-bar symbol or reject mixed input; dict path already handles per symbol.
B2. `_parse_hhmm` returning `(0,0)` on bad input masks config errors if validation is bypassed. Make it raise `ValueError`.
B3. Duplicate bars/events: no dedup; duplicate input bars can create duplicate gap events. Add deterministic dedup of identical `(rule-ish) anomaly` records.
B4. Cross-midnight maintenance window for fixed-UTC and far timezones: `_maintenance_utc_interval` uses the UTC date as the local date base; for zones where the local calendar date differs from the UTC date, the window lands on the wrong day. Correct by deriving the local date from the bar timestamps / cluster zone.
B5. Stub tolerance boundary: condition `0 < observed < expected_weekday - stub_tol` excludes `observed == expected - stub_tol`. Clarify and align with documented tolerance (inclusive upper bound likely intended).
B6. Intra-session gap threshold uses `INTERVAL_H1 + 1 minute` hardcoded; should reference a configurable tolerance or named constant.

### C. Intentional behavior changes requiring explicit approval
C1. Group by session-local date instead of UTC date.
C2. Change session anomaly `event_ts` from 23:00 UTC to local session close.
C3. Include first/last (boundary) dates in anomaly detection.
C4. Change Sunday default `expected_sun_bars` from 0 to a configured value.
C5. Allow Saturday anomaly detection.
C6. Change gap detection to include cross-midnight/cross-date consecutive bars.
C7. Change maintenance window overlap heuristic thresholds.

## 4. Detailed change specifications

### B1 — Multi-symbol handling
- Current: `_core_compute` derives `symbol`/`timeframe` from first bar; mixed-symbol lists mis-attributed.
- Proposed: if bars contain differing symbols, split internally by symbol (as dict path) or raise `ValueError`.
- Why: prevent silent mis-attribution.
- Affected: `_core_compute`, `compute_events`.
- Regression tests: mixed-symbol list raises or splits; per-symbol outputs match dict path.
- Event outputs: none for existing single-symbol inputs.

### B2 — Strict `_parse_hhmm`
- Current: returns `(0,0)` on non-str/non-numeric.
- Proposed: raise `ValueError`.
- Why: fail fast; config validation already rejects bad input.
- Affected: `_parse_hhmm`, `_maintenance_utc_interval`, `_cluster_info`.
- Regression tests: invalid HH:MM raises.
- Event outputs: none.

### B3 — Duplicate dedup
- Current: no dedup.
- Proposed: dedup identical events by `(symbol,timeframe,anomaly_type,session_date,event_ts)`.
- Why: idempotent output on duplicate input bars.
- Affected: `_core_compute` final sort.
- Regression tests: duplicate bar input yields one event.
- Event outputs: could reduce counts if duplicate inputs existed (none in current scans).

### B4 — Maintenance window local date basis
- Current: uses UTC date for local window construction.
- Proposed: derive local date from bar timestamps using cluster zone.
- Why: correct maintenance window for far zones.
- Affected: `_maintenance_utc_interval`, `_core_compute`.
- Regression tests: far-zone (e.g., Asia/Tokyo) maintenance window tests.
- Event outputs: may change for non-UTC zones; UTC-zone outputs unchanged.

### B5 — Stub tolerance boundary
- Current: `observed < expected - stub_tol`.
- Proposed: `observed <= expected - stub_tol` (inclusive) if documented tolerance means "within tol".
- Why: align tolerance semantics.
- Affected: `_core_compute` stub branch.
- Regression tests: observed == expected - tol case.
- Event outputs: may add stub events at boundary.

### B6 — Named gap tolerance constant
- Current: `INTERVAL_H1 + timedelta(minutes=1)`.
- Proposed: `GAP_TOLERANCE = timedelta(minutes=1)` constant, documented.
- Why: clarity.
- Affected: `_core_compute`.
- Regression tests: existing DST tests unchanged.
- Event outputs: none.

### C1 — Local-date grouping (requires approval)
- Current: UTC `.date()`.
- Proposed: group by local date per cluster zone.
- Why: align session days with trading days.
- Affected: `_core_compute` counts/by_date_bars/bounds.
- Regression tests: new golden fixtures for local-date grouping.
- Event outputs: changes for all non-UTC zones.

### C2 — event_ts local close (requires approval)
- Current: 23:00 UTC.
- Proposed: local end-of-day converted to UTC.
- Why: meaningful session timestamp.
- Affected: event construction.
- Event outputs: changes event_ts for all events.

### C3 — Boundary inclusion (requires approval)
- Current: interior dates only.
- Proposed: include first/last dates.
- Why: detect anomalies at edges.
- Event outputs: adds edge anomalies.

### C4 — Sunday default (requires approval)
- Current: 0.
- Proposed: configurable, default maybe 2? (needs spec).
- Event outputs: changes.

### C5 — Saturday detection (requires approval)
- Current: skipped.
- Proposed: apply weekday expected to Saturday or new expected_sat_bars.
- Event outputs: changes.

### C6 — Cross-date gaps (requires approval)
- Current: same-date only.
- Proposed: consecutive bars across dates.
- Event outputs: changes.

### C7 — Maintenance heuristic thresholds (requires approval)
- Current: 30-min tolerances.
- Proposed: configurable or documented thresholds.
- Event outputs: changes.

## 5. Dependencies
- A1-A5 first (no behavior change), enabling B/C work.
- B4 depends on A (zone handling).
- B5/B6 independent.
- C1 depends on B4.
- C2 depends on C1.
- C3/C5/C6 independent but affect fixtures.
- B3 independent.

## 6. Safe implementation order
1. Add golden-fixture capture of current outputs (before changes).
2. A: internal refactor, full suite must remain 94 passed + 1 skipped.
3. B: defect fixes one at a time, each with new regression tests.
4. C: only after explicit approval; each as separate commit with fixture updates.
5. Re-run full suite + equivalence harness after each step.

## 7. Approval gate
No implementation until approval. Approve subset of B/C items explicitly.
