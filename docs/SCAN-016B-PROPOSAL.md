# SCAN-016B — Maintenance-Window Date Correctness (Proposal)

Status: PROPOSAL — reconnaissance only. No code, config, fixtures, or tests modified. Awaiting approval.

## 1. Current implementation and timestamp flow

### 1.1 Pipeline

`compute_events` -> `_core_compute`:

1. Sort bars by `open_ts`.
2. `_group_bars_by_utc_date`: bucket bars by UTC calendar date `ts.date()` (UTC). Returns `counts`, `by_date_bars`, `first_date`, `last_date`.
3. `_session_level_anomalies`: interior UTC dates only (first < cur < last); missing/stub/Sunday detection.
4. `_intra_session_gap_events`: for each UTC date `d` with bars, sort timestamps; for each consecutive pair, if gap > `INTERVAL_H1 + GAP_TOLERANCE`, check maintenance allowance; emit `intra_session_gap` if not allowed.
5. Sort events by `(event_ts, anomaly_type, session_date)`.

### 1.2 Maintenance-window construction

`_maintenance_utc_interval(info, date)` (`date` is a UTC date):

- Fixed-UTC mode (`_fixed_utc` True): builds `datetime(date.year, date.month, date.day, sh, sm, tzinfo=UTC)` for start/end using UTC date; if `end <= start`, `end += 1 day`. Correct by definition (window is in UTC).
- Local mode: builds `datetime(date.year, date.month, date.day, sh, sm, tzinfo=zone)` and same for end, using the **UTC date as the local calendar date**; if `local_end <= local_start`, `local_end += 1 day`; converts both to UTC via `.astimezone(timezone.utc)`.

Zone offset is resolved per-instant by `ZoneInfo` when constructing the aware datetimes.

### 1.3 Gap allowance logic

For a gap `(prev, curr)` on UTC date `d`:

- `maint_start, maint_end = _maintenance_utc_interval(info, d)` (single window).
- Allowed if `prev >= maint_start - 30min` and `curr <= maint_end + 30min`.
- Else allowed if overlap `[max(prev, maint_start), min(curr, maint_end)]` is positive and >= 30 minutes.

### 1.4 Defect

In local mode the calendar date used is the UTC date `d`, not the local date of the bars. For zones where the UTC calendar date and local calendar date differ, the window is constructed on the wrong day. Concrete: `Pacific/Honolulu` (UTC-10) with `date=2026-01-15` yields `2026-01-16 03:00-04:00 UTC`, one day late; a gap at `2026-01-15 03:00-04:30 UTC` (local Jan 14 17:00-18:30, squarely across the intended maintenance) is reported as a gap. Reproduced (see section 3).

## 2. Confirmed defect

Yes. The local-mode branch assumes `date` (UTC) is the local calendar date. This holds only when the UTC date and local date coincide for the maintenance instant. For sufficiently negative offsets (and certain maintenance times / cross-midnight windows) the window lands on an adjacent UTC day and never overlaps the bars on `d`, defeating gap suppression (false gaps) or, conversely, suppressing real gaps if an adjacent-day window happens to overlap.

## 3. Reproducible example

Input (current behavior):

- zone `Pacific/Honolulu`, maintenance `17:00-18:00` local.
- bars: `2026-01-15T03:00:00Z`, `2026-01-15T04:30:00Z`, `2026-01-16T00:00:00Z`.

Current `_maintenance_utc_interval` for `2026-01-15` returns `2026-01-16 03:00-04:00 UTC`. The 90-minute gap at `03:00->04:30` (local Jan 14 17:00->18:30, crossing the intended maintenance Jan 15 03:00-04:00 UTC) is **not** suppressed -> emits `intra_session_gap` (gap_hours=1).

Intended: maintenance Jan 15 03:00-04:00 UTC overlaps the gap by 60 minutes -> gap should be allowed -> no event.

Verified via script (no repo changes): current emits one gap; expected after correction zero gaps.

## 4. Timezone and DST analysis

Zone behavior of `_maintenance_utc_interval` for `date = D` (UTC), maintenance `17:00-18:00`:

| Zone | Offset (approx) | Current window for UTC date D | Correct window for UTC date D | Status |
|---|---|---|---|---|
| UTC | +0 | D 17:00-18:00 | D 17:00-18:00 | OK |
| Europe/London (winter) | +0 | D 17:00-18:00 | D 17:00-18:00 | OK |
| Europe/London (BST) | +1 | D 16:00-17:00 | D 16:00-17:00 | OK |
| America/New_York (EST) | -5 | D 22:00-23:00 | D 22:00-23:00 | OK |
| America/New_York (EDT) | -4 | D 21:00-22:00 | D 21:00-22:00 | OK |
| Asia/Tokyo | +9 | D 08:00-09:00 | D 08:00-09:00 | OK |
| Pacific/Auckland (NZST) | +12 | D 05:00-06:00 | D 05:00-06:00 | OK |
| Pacific/Auckland (NZDT) | +13 | D 04:00-05:00 | D 04:00-05:00 | OK |
| Pacific/Honolulu | -10 | D+1 03:00-04:00 (wrong day) | D 03:00-04:00 | **FAILS** |
| Alaska (AKST, -9/-10) | -9/-10 | may land D+1 | D 02:00/03:00-... | **FAILS** for far-west |

Failure occurs when the offset is negative enough that `17:00 local` on UTC date `D` falls on UTC date `D+1` (i.e., `17:00 - offset >= 24h`). Equivalent: offset <= -7 hours for a 17:00 window. Generalizes: failure when the maintenance time-of-day minus the offset crosses midnight.

DST transitions (America/New_York 2026):
- Spring forward (Mar 8): 17:00 local resolves to EDT (-4) -> D 21:00 UTC. `ZoneInfo` resolves per instant; no change needed.
- Fall back (Nov 1): 17:00 local resolves to EST (-5) -> D 22:00 UTC. `ZoneInfo` resolves per instant.
- Ambiguous (autumn overlap) and nonexistent (spring gap) local times at the maintenance instant: current code constructs `datetime(..., tzinfo=zone)` with default `fold=0`, which for a nonexistent time does not raise but yields the pre-transition offset. This is existing behavior; the correction should preserve `fold=0` and not introduce new exceptions. Cross-midnight windows (`start > end`) are already handled by `end += 1 day` in local time before conversion, so a 22:00-02:00 window correctly spans local midnight; combined with the date fix, both adjacent local dates' windows may need consideration.

Local date vs UTC date: a single UTC date `D` spans up to two (sometimes three at boundaries) local dates. Bars grouped by UTC date can have local dates `D-1`, `D`, or `D+1`. Therefore the maintenance window that actually intersects the bars on `D` may be the window on local date `D-1` (far-west) or `D` (typical). Both the current and preceding local dates must be considered; for safety also `D+1` to cover cross-midnight windows whose start is on `D` but extend into `D+1` UTC.

## 5. Proposed minimal correction

Do not implement now. Proposed change (smallest safe):

1. Change `_maintenance_utc_interval(info, date)` to consider multiple candidate local dates instead of assuming `date` is local:
   - Fixed-UTC mode: unchanged (window is defined in UTC; `date` is correct).
   - Local mode: candidate local dates are `{date - 1 day, date, date + 1 day}` expressed in the cluster zone. For each, build the local window (existing `end <= start => +1 day` cross-midnight handling) and convert to UTC. Keep a candidate only if its raw UTC interval intersects `[date 00:00 UTC, (date+1) 00:00 UTC)`.

   Candidate selection safety (tolerance interaction): the existing gap allowance applies a 30-minute tolerance (`maint_start - 30min`, `maint_end + 30min`) and a 30-minute overlap heuristic. A window that does not intersect the UTC day `[D, D+1)` cannot satisfy either heuristic for a gap on `D`, because every gap on `D` is longer than `INTERVAL_H1 + GAP_TOLERANCE` (61 min) and lies within `[D 00:00, D 24:00)`: the tolerance can extend an affectable window into `D` by at most 30 minutes, which is less than the 61-minute minimum gap, so any window that could affect a `D` gap must already have its raw UTC span intersect `D`. Therefore filtering candidates by raw UTC-day intersection cannot discard a window that could legitimately affect the gap-allowance calculation. The 30-minute tolerance and overlap heuristic themselves are not changed.

   Equivalently, derive the candidate local dates from the UTC day boundaries converted to the zone: `date 00:00 UTC -> zone` gives the local date at the start of the UTC day (often `D-1` for negative offsets); `date+1 00:00 UTC -> zone` gives the local date at the end. The `{D-1, D, D+1}` set is the smallest set that can contain a local date whose window (at most +1 day cross-midnight) intersects `D`. Return the list of qualifying `(start, end)` windows.

2. Update `_intra_session_gap_events` to fetch the candidate windows for date `d` and test gap allowance against **any** of them (OR of the existing two heuristics, per window). This keeps the 30-minute tolerance and overlap heuristic unchanged.

3. Signature: either keep `_maintenance_utc_interval` returning a single window by selecting the candidate whose start falls within the UTC day (simpler, but misses windows starting the previous UTC day yet extending into `D`), or change to return a list. The list form is more correct for cross-midnight windows and is recommended. No external callers depend on the return shape (only internal use; tests do not call it directly).

4. Derivation basis: the UTC date `d` of the bar group determines the candidate set; the local date is derived by converting UTC day boundaries (equivalently, the bars' timestamps) to the zone, rather than assuming `d` is local. This is the "appropriate local timestamp" — the bars' `open_ts` / the UTC day they belong to.

5. UTC behavior: for `zone == "UTC"` and fixed-UTC mode, candidate set collapses to `{D}`; windows identical to current. Existing DST tests (America/New_York summer/winter) keep passing because the qualifying window for those dates is the same as today.

6. Ambiguous/nonexistent local times: preserve `fold=0` (current) for maintenance datetimes; no new exceptions. The proposed New York spring (2026-03-08) and autumn (2026-11-01) tests verify seasonal offset handling (EDT vs EST) only; on those dates the maintenance time 17:00 is not an ambiguous or nonexistent local time, so they do not exercise DST-transition resolution. No new DST resolution rules are introduced; `fold=0` behavior is retained.

## 6. Regression-test plan (proposed, not implemented)

All scenarios use `params(...)` helper style from `tests/test_sessions.py` with GOLD cluster, expected=3, sun=2, stub_tol=1, sun_tol=0, bars as needed.

1. UTC maintenance window (ordinary): zone `UTC`, maintenance `17:00-18:00`, bars `2026-01-15T16:30Z`, `2026-01-15T18:30Z`, `2026-01-16T00:00Z`. Gap 16:30->18:30 overlaps 17:00-18:00 by 30 min -> allowed -> no gap. Why: UTC zone, date unchanged.

2. Positive UTC offset (Asia/Tokyo): zone `Asia/Tokyo`, maintenance `17:00-18:00`, bars `2026-01-15T08:00Z`, `2026-01-15T09:30Z`, `2026-01-16T00:00Z`. Maintenance UTC = 08:00-09:00; gap overlaps -> allowed -> no gap. Why: window falls within UTC day D.

3. Negative UTC offset, date same (America/New_York winter): zone `America/New_York`, maintenance `17:00-18:00`, bars `2026-01-15T21:00Z`, `2026-01-15T23:30Z`, `2026-01-16T00:00Z`. Maintenance UTC = 22:00-23:00; gap 21:00->23:30 overlaps -> allowed -> no gap. Why: existing DST winter test; unchanged.

4. Local date differing from UTC date (Pacific/Honolulu): zone `Pacific/Honolulu`, maintenance `17:00-18:00`, bars `2026-01-15T03:00Z`, `2026-01-15T04:30Z`, `2026-01-16T00:00Z`. Corrected maintenance UTC = Jan 15 03:00-04:00; gap overlaps -> allowed -> no gap. Why: this is the defect case; current code emits a gap.

5. Cross-midnight maintenance window: zone `America/New_York`, maintenance `22:00-02:00`, bars crossing the window on the same local evening, e.g. `2026-01-15T02:30Z`? Better: bars `2026-01-16T02:30Z`, `2026-01-16T04:30Z` with preceding bound `2026-01-17T00:00Z`. Maintenance UTC = Jan 16 03:00-07:00; gap 02:30->04:30 overlaps -> allowed -> no gap. Why: cross-midnight local window converted correctly and candidate set includes the window starting Jan 16 UTC.

6. DST spring transition (seasonal offset handling): zone `America/New_York`, maintenance `17:00-18:00`, date `2026-03-08` (spring forward), bars `2026-03-08T21:00Z`, `2026-03-08T22:30Z`, `2026-03-09T00:00Z`. Maintenance UTC = 21:00-22:00 (EDT) -> gap overlaps -> no gap. Why: verifies the EDT offset is used after the spring transition; the 17:00 maintenance time is not an ambiguous or nonexistent local time on this date.

7. DST autumn transition (seasonal offset handling): zone `America/New_York`, maintenance `17:00-18:00`, date `2026-11-01`, bars `2026-11-01T22:00Z`, `2026-11-01T23:30Z`, `2026-11-02T00:00Z`. Maintenance UTC = 22:00-23:00 (EST) -> no gap. Why: verifies the EST offset is used after the autumn transition; the 17:00 maintenance time is not an ambiguous or nonexistent local time on this date.

8. Existing ordinary UTC sessions unchanged: re-run `tests/test_sessions.py` (all 9) and DST tests `test_dst_summer_no_false_gap`, `test_dst_winter_no_false_gap` expect still green. Why: UTC zone / NY qualifying window unchanged.

Additional negative case: a gap that does not overlap any candidate window must still fire (e.g., Honolulu bars `2026-01-15T00:00Z`, `2026-01-15T02:00Z`) -> gap fires. Ensures correction does not over-suppress.

9. Maintenance window immediately adjacent to a UTC-day boundary (30-minute allowance): zone `America/New_York` (EST), maintenance `00:00-00:30` local, date `2026-01-15`. Maintenance UTC = Jan 15 05:00-05:30. Bars `2026-01-15T05:00Z`, `2026-01-15T06:10Z`, `2026-01-16T00:00Z`. The 70-minute gap overlaps the window by exactly 30 minutes (05:00-05:30) -> overlap heuristic (>= 30 min) allows it -> no gap. Why: exercises a window at the very start of the UTC day and confirms the 30-minute overlap threshold is applied unchanged and that candidate selection retains a window whose raw span begins at the UTC-day boundary. A second check with bars `2026-01-15T05:15Z`, `2026-01-15T06:25Z` (overlap 15 min) -> gap fires, confirming the threshold is not relaxed.

## 7. Potential behavioral impact

- Non-UTC (especially far-west, offset <= -7h relative to maintenance time) sessions: some previously reported `intra_session_gap` events across the intended maintenance window will no longer be emitted. This is the intended correction.
- UTC-zone and fixed-UTC sessions: no change.
- Moderate-offset zones (NY, London, Tokyo, Auckland): no change in qualifying windows for typical 17:00 maintenance; existing tests remain green.
- Event counts/ordering: unchanged except for specifically removed false gaps in far-west zones.
- No change to session grouping (still UTC date), anomaly detection, event_ts, boundaries, stub/sun tolerance, gap thresholds, schema.

## 8. Files that would change during implementation

- `scanline/sessions.py`: `_maintenance_utc_interval` (candidate windows) and `_intra_session_gap_events` (OR across candidates).
- `tests/test_sessions.py`: add regression tests per section 6 (new test class, e.g. `TestScan016B`).
- No changes to config, fixtures, schema, validator, or other modules.

## 9. Risks and unresolved questions

- Risk: over-suppression if candidate set too broad. Mitigated by intersecting each candidate with the UTC day before use; only windows actually occurring during `D` qualify.
- Risk: changing return shape of `_maintenance_utc_interval` if any hidden callers exist. Mitigated: grep shows only internal use; tests do not call it. Confirm before implementation.
- Risk: cross-midnight windows combined with candidate set may yield two qualifying windows; gap check uses OR, which is more permissive. Acceptable and more correct.
- Ambiguous/nonexistent local times during DST: `fold=0` default retained; maintenance at a nonexistent local time (spring gap) resolves to pre-transition offset. Whether to use `fold=1` for autumn ambiguous times is unresolved; recommend keeping current `fold=0` for minimal change and adding a test only if approved.
- Whether to derive candidates from UTC day boundaries vs. from bar timestamps: both yield the same set for a UTC-date group in practice; UTC-day-boundary derivation is simpler and deterministic. Unresolved whether per-gap (prev bar local date) would be more precise; recommend day-level candidate set to keep one window-set per UTC date.
- Whether fixed-UTC mode should also gain candidate handling: no — fixed UTC windows are already in UTC and date-correct.
- Approval needed before implementation; this document is reconnaissance only.
PY
echo done