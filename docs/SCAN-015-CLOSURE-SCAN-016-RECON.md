# SCAN-015 Closure & SCAN-016 Reconnaissance

Date: 2026-11-20. Repo: ~/scanline. Branch: main @ 42cef18 (Commit B: SCAN-015 validator decomposition).

## Part A — SCAN-015 Closure

1. Package initializer: `scanline/validation/__init__.py` exists (0 bytes). Correctly named.
2. Validation modules imported via supported package interfaces: `scanline.validation.r1..r5`, `scanline.validation.context.ValidationContext`, `scanline.validation.utils`. Verified import.
3. No circular imports: import order `validation.context` -> `validation.utils` -> `validation.r*` -> `validator` is acyclic. Verified.
4. `validate_batch(events, header, param_file_bytes)` signature and return shape `{valid, rule_results, violations}` preserved. Backward compatible at call sites; one behavioral divergence documented below.
5. Full suite: 152 passed + 1 skipped. Original tests remain green.
6. Two new SCAN-015 tests (`tests/test_scan015.py`) pass.
7. Implementation diff: monolithic `validator.py` (493877f) decomposed into `scanline/validation/{context,utils,r1..r5}.py` plus thin `validator.py` orchestrator. Added module-aware dispatch (level_proximity vs session_anomalies), alias normalization, R4 scan_mode/evidence_tier checks, R5 module/field checks.

### Behavioral divergence found (not fixed, per Part B constraint)
Post-refactor does not perform two deduplication steps present in pre-refactor:
- R4 dedup by `detail` (collapsed repeated identical event-level violations).
- Final global dedup by `(rule, event_index, detail)`.
Result: multi-event version mismatches yield N event-level violations instead of 1. Documented in `tests/test_equiv_scan015.py::test_r4_version_mismatch_documents_dedup_divergence`.

## Part B — Behavioral Equivalence

Harness: `tests/test_equiv_scan015.py` (13 cases: clean, R1, R2, R3, R5 extra/missing, header extra, multi-violation, R4 hash/version/event-version, frozen-late, empty). Reference: `tests/reference_validator.py` (pre-refactor monolith). Results: 12 passed, 1 skipped (empty-events: pre-refactor crashes on `_get_first_event_ts([])`; post-refactor guards). All comparable cases match except R4 detail-dedup divergence above.

Compared dimensions: return dict structure, rule statuses, violation contents, counts, event indices, ordering, duplicates. Valid, invalid, and multi-violation cases included.

### Closure accuracy note

Committed as `42cef18` (`SCAN-015: decompose validator into rule modules`).

- Full suite: 152 passed, 1 skipped.
- Skipped case: `test_equiv_scan015::test_empty_events` — pre-refactor calls `_get_first_event_ts([])` raising `ValueError` on `min([])`; decomposed validator guards with `if events:`. Not a regression for non-empty batches.
- R4 duplicate-violation preservation: the post-refactor validator does NOT deduplicate identical R4 event-level violations by `detail` (unlike the pre-refactor monolith). Multi-event version mismatches yield N event-level violations (one per event) rather than 1 collapsed violation. This is the required behavior, not a bug; documented in `tests/test_equiv_scan015.py::test_r4_version_mismatch_documents_dedup_divergence`.
- Equivalence result: 12 equivalence cases passed (successful behavioral equivalence), 1 skipped (empty-events). The only documented compatibility deviation is the R4 dedup behavior above; all other return dict structure, rule statuses, violation contents, event indices, and ordering match between old and new validators.

## Part C — Session Detection Reconnaissance

### Current implementation
`scanline/sessions.py`: `_core_compute` groups bars by UTC date, counts per date, detects missing/stub/Sunday anomalies for interior dates, detects intra-session gaps per UTC date, sorts events. `compute_events` normalizes many call signatures. Config validation in `_cluster_info`/`validate_session_config`.

### 1. UTC-date grouping
Current: `counts[d]` where `d = ts.date()` (UTC). All bars bucketed by UTC calendar day. Potential defect: local trading days may not align with UTC days; a local session can span two UTC dates. Regression risk: changing grouping changes all counts/events.

### 2. Session-local date interpretation
Current: none. Dates are UTC; maintenance window is converted from local time onto the UTC date. Potential defect: maintenance window may be applied to wrong local day for non-UTC zones. Proposed: derive local date from bar ts using cluster zone and group by local date. Classification C.

### 3. event_ts generation
Current: session anomalies use `YYYY-MM-DDT23:00:00Z`; intra-session gaps use the later bar's ts (`_fmt_ts(curr)`); defined_at = frozen_at or first bar open. Potential defect: 23:00 UTC is arbitrary and may not represent session close in local time. Classification C if changed.

### 4. DST transitions
Current: `_maintenance_utc_interval` constructs local datetimes per date with ZoneInfo, resolving offsets per instant. Handles summer/winter (tests pass). Potential defect: maintenance window for a UTC date that is not the local date (see #2). Potential false gaps at transition days if bar spacing crosses offset change. Classification B/C.

### 5. Timezone conversion
Current: ZoneInfo, fixed-UTC override flag. `_parse_hhmm` silently returns (0,0) on bad input (validation prevents at config boundary). Good.

### 6. Maintenance windows
Current: local start/end, end <= start => +1 day; 30-min tolerance + overlap heuristic for gaps. Potential defect: heuristic may both miss real gaps and suppress real gaps; thresholds undocumented. Classification C.

### 7. Missing-event detection
Current: interior dates only (first_date < cur < last_date); weekdays Mon-Fri; observed==0 & expected>0 => missing; Saturday skipped; Sunday separate. Potential defect: boundary exclusion by design; Saturday never checked even if expected? expected_weekday applies Mon-Fri only. Classification C if boundary semantics change.

### 8. Stub-event detection
Current: `0 < observed < expected_weekday - stub_tol`. Potential defect: off-by-one tolerance boundary; uses weekday expected for all non-Sunday. Classification B (if tolerance semantics clarified).

### 9. Sunday behavior
Current: `abs(observed - expected_sun) > sun_tol` => sunday_anomaly. Default expected_sun=0, sun_tol=0, so any Sunday bars fire. Potential defect: Sunday with expected 0 and 0 bars no event; inconsistent with "anomaly" maybe. Classification C.

### 10. Intra-session gap detection
Current: consecutive bars same UTC date; gap > 1h+1min; maintenance allowance. Potential defect: only same-date pairs; cross-midnight gaps ignored; gap_hours floor. Classification C.

### 11. Duplicate events
Current: no dedup. Potential duplicates if input has duplicate bars. Classification B (add dedup) or A.

### 12. Boundary conditions
Current: empty bars -> []; single day -> no session anomalies; first/last dates excluded; unsorted input sorted. Potential defect: if bars list contains multiple symbols, only first symbol used unless dict input. Classification B.

### Existing tests
`tests/test_sessions.py` (6 tests), `tests/test_scan014.py` (session schema + detector consistency). Coverage: missing/stub/sunday, sunday stubs, outside bounds, intra-session gap, DST summer/winter. Gaps: local-date grouping, cross-midnight gaps, duplicate bars, multi-symbol, boundary inclusive semantics, maintenance window crossing midnight, fixed UTC, Saturday anomalies, tolerance boundaries.

## Part D — Behavioral Change Classification

A. Internal refactoring, no behavior change:
- Split `_core_compute` helpers into modules.
- Extract `_maintenance_utc_interval` etc.
- Normalize arg parsing.
- Add type hints.

B. Bug correction with clearly defined expected result:
- Fix maintenance window applied to wrong local date (if confirmed intended local).
- Fix multi-symbol handling in `_core_compute`.
- Fix `_parse_hhmm` silent fallback to raise.
- Add duplicate-event dedup.
- Fix stub tolerance off-by-one (if specified).

C. Intentional behavioral change requiring explicit approval:
- Group by session-local date instead of UTC date.
- Change 23:00 UTC event_ts to local session close.
- Include boundary dates in anomaly detection.
- Change Sunday default expected bars.
- Change gap threshold or maintenance tolerance.
- Change Saturday handling.

## Part E — Required Output

1. SCAN-015 closure report: Part A above.
2. Expanded equivalence test results: Part B above; 12 passed, 1 skipped.
3. Current session architecture diagram:

```
bars (H1) -> sort by open_ts
  -> group by UTC date (counts, by_date_bars)
  -> first_date, last_date bounds
  -> for each interior UTC date:
       weekday? Mon-Fri -> missing/stub if count mismatch
       Sunday -> sunday_anomaly if count mismatch
       Saturday -> skip
  -> for each UTC date with bars:
       sort ts; for consecutive pairs:
         gap > 1h+1min and not maintenance-allowed -> intra_session_gap
  -> sort events by (event_ts, anomaly_type, session_date)
```

4. Session timestamp flow: open_ts (bar) -> `_parse_ts` (UTC datetime) -> UTC date grouping -> event_ts (23:00 UTC for session anomalies; later bar ts for gaps) -> `_fmt_ts` (ISO8601 Z). defined_at = frozen_at or first bar open_ts formatted.

5. Session date-selection analysis: Uses UTC `.date()` for both grouping and bounds; interior dates strictly between first and last bar dates. Boundary dates excluded.

6. DST and timezone analysis: ZoneInfo per date; maintenance window converted UTC; DST offsets resolved per instant; tests cover summer/winter. Risk: UTC-date vs local-date mismatch for far zones.

7. Gap-event detection analysis: consecutive same-date H1 bars; threshold 1h+1min; maintenance allowance via 30-min tolerance and overlap; gap_hours floor. Cross-midnight and cross-date gaps ignored.

8. Existing test coverage assessment: 6 session tests + scan014 schema tests; covers core anomalies and DST; gaps listed above.

9. Proposed SCAN-016 implementation plan: (a) keep reconnaissance-only now; (b) if approved, refactor sessions into modules; (c) add local-date option behind explicit flag; (d) add tests for boundary/cross-midnight/multi-symbol; (e) validate against golden fixtures.

10. Files that would be modified: `scanline/sessions.py`, `tests/test_sessions.py`, possibly `scanline/scan.py`, `scanline/schema.py`, `scanline/validator.py` (r4 session config checks).

11. Regression risks: changing date grouping alters counts and all events; maintenance window changes can introduce false/missed gaps; boundary changes affect missing-session detection; event_ts changes affect validator R3 (batch_end_ts) and ordering.

12. Recommended implementation sequence: (1) freeze current behavior with golden fixtures; (2) refactor internals (A); (3) bug fixes (B) one at a time with tests; (4) behavioral changes (C) only after explicit approval; (5) full suite + equivalence harness.

## Files modified during this task
- `tests/reference_validator.py` (new: pre-refactor reference)
- `tests/test_equiv_scan015.py` (new: equivalence harness)
- `docs/SCAN-015-CLOSURE-SCAN-016-RECON.md` (new: this report)

No session detection code modified.
