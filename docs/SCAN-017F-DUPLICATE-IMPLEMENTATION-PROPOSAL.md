# SCAN-017F — Duplicate Bar Integrity Implementation Proposal (Revised)

**Status: DESIGN AND PROPOSAL ONLY. No implementation authorized.**

**Policy B — approved in principle: reject repeated `(symbol, timeframe, open_ts)` keys**, including identical and conflicting OHLCV records. No silent deduplication. This document revises the original proposal (`docs/SCAN-017F-DUPLICATE-IMPLEMENTATION-PROPOSAL.md`) to resolve points (1)–(8) before implementation authorization. All architecture claims below are verified against the current source.

---

## 0. Baseline (verified against source)

- `scanline/scan.py::_extract_series` (scan.py:65-86) opens `{symbol}_{tf}.csv`, parses `time` as epoch seconds via `datetime.fromtimestamp(ts, tz=timezone.utc)` (scan.py:73-74), stores `open_ts` as an ISO string (scan.py:79), sorts bars by `open_ts` (scan.py:85). Exactly one file per `(symbol, tf)` series. No duplicate detection.
- `scanline/scan.py::run_scan` (scan.py:103) builds `extracted[(symbol, tf)]` once per series — `seen_series` (scan.py:153-157) dedups series keys, not bars — then dispatches per symbol × emission timeframe to `compute_session_events(em_bars, params)` (scan.py:187) or `compute_level_events(d1_bars, em_bars, params)` (scan.py:197) with `d1_bars = extracted[(symbol, "D1")]` **shared across all emission timeframes** for the symbol.
- `scanline/sessions.py::compute_events` (sessions.py:533) uses `_normalize_args` (sessions.py:502) accepting list, dict (`symbol → bars`), list-of-`(symbol, bars)`, and `(symbol, bars, params)` shapes. Dict and list-of-tuples paths call `_core_compute` per symbol (sessions.py:535-547). `_core_compute` (sessions.py:458) returns `[]` for empty bars (sessions.py:462-463), rejects mixed-symbol/mixed-timeframe lists (sessions.py:465-476), defaults `timeframe` to `"H1"` (sessions.py:474), then groups by UTC date (sessions.py:487).
- `scanline/levels.py::compute_events` (levels.py:160) takes `(d1_bars, emission_bars, params)`; derives `symbol`/`timeframe` from the first emission bar (levels.py:169-172).
- `_parse_ts` exists identically in scan.py:32-38, sessions.py:15-21, levels.py:21-27: trailing `Z` → `+00:00`, `datetime.fromisoformat`, naive → `timezone.utc`.
- `scanline/validation/` exists (event rules R1-R5) but has **no** duplicate module; no `scanline/validation/duplicate.py` yet.

---

## 1. Metadata and contextual defaults

### 1.1 Shared helper signature

```
validate_unique_bar_keys(bars, symbol=None, timeframe=None, source=None) -> None
```

- `bars`: iterable of bar dicts (each expected to carry `symbol`, `timeframe`, `open_ts`).
- `symbol`: optional contextual default, applied to bars missing `symbol`. This is how function-argument-supplied metadata (e.g. `compute_events("GOLD", bars, params)`) becomes effective.
- `timeframe`: optional contextual default, applied to bars missing `timeframe`. Defaults to `"H1"` when absent and no argument is given, matching `_core_compute`'s existing default (sessions.py:474).
- `source`: optional identifier used only in error messages (e.g. file path).

Per-bar resolution order:
1. `sym = bar.get("symbol")`; if absent, use the `symbol` argument.
2. `tf = bar.get("timeframe")`; if absent, use the `timeframe` argument (default `"H1"`).
3. If either is still absent → `ValueError` (missing bar metadata), distinct from `DuplicateBarKeyError`.
4. Canonicalize: `str(sym).strip().upper()`, `str(tf).strip().upper()` (see §2).
5. Parse `bar["open_ts"]` (see §2); build key `(canonical_symbol, canonical_timeframe, canonical_utc_datetime)`.
6. On first repeated key → raise `DuplicateBarKeyError` naming the key and both occurrence positions.

### 1.2 Existing call interfaces covered

| Interface | Symbol/timeframe source | Coverage |
|---|---|---|
| `run_scan` → `compute_session_events(em_bars, params)` | scan.py tags `symbol` on bars missing it (scan.py:183-186); `timeframe` from file name | bar-level metadata present |
| `compute_events(bars, params)` | bar-level metadata | bar-level |
| `compute_events(symbol, bars, params)` | `_normalize_args` returns `symbol`; `compute_events` tags bars missing `"symbol"` before `_core_compute` (sessions.py:551-554) | bar-level after tagging |
| `compute_events({symbol: bars}, params)` | `_core_compute(bs, params)` per symbol (sessions.py:539) | bar-level |
| `compute_events([(symbol, bars), ...], params)` | per-item symbol; `_core_compute(item[1], params)` relies on bar metadata (sessions.py:545-546) | bar-level; helper `symbol` default available for future/direct call sites |
| `compute_level_events(d1_bars, em_bars, params)` | bar-level metadata; `symbol`/`timeframe` from first emission bar (levels.py:169-172) | bar-level |

No valid existing call is rejected merely because individual bars lack metadata: every current path either tags bars or carries metadata. The helper's `symbol`/`timeframe` arguments exist so direct or future calls can supply metadata at function-argument level without per-bar fields. Empty bar lists short-circuit (no check; `[]` is valid).

---

## 2. Canonicalization (verified against existing implementations)

### 2.1 Rules

- **Symbol:** strip whitespace, then uppercase (`gold` == `GOLD`). The codebase currently canonicalizes nothing (symbols flow raw from file names and tests); this only merges keys differing in case/whitespace, which no current behavior depends on.
- **Timeframe:** strip whitespace, then uppercase (`h1` == `H1`). Same compatibility reasoning.
- **Open timestamp:** parse to a single canonical UTC instant using the **existing** `_parse_ts` semantics (scan.py:32-38, sessions.py:15-21, levels.py:21-27 — identical copies):
  - trailing `Z` replaced with `+00:00`;
  - `datetime.fromisoformat`;
  - naive → `timezone.utc`.
- **Key on the parsed UTC `datetime` object itself (microsecond precision), not on integer seconds.** Integer-second truncation can collapse distinct instants (e.g. `10:00:00.400` vs `10:00:00.401`). Datetime equality/hash are UTC-instant-based, so `2006-01-03T09:00:00Z`, `2006-01-03T09:00:00+00:00`, and equivalent offset forms map to one key while subsecond distinctions are preserved.
- **Timezone:** naive → UTC; aware offsets retained and compared as UTC instants (aware `datetime` equality/hash are instant-based).
- **Epoch units:** existing convention is epoch **seconds** → `datetime.fromtimestamp(ts, tz=utc)` → ISO string (scan.py:73-74, 79). The helper accepts the same representations as `_parse_ts` (ISO strings); it does **not** accept raw epoch ints as `open_ts` — callers convert first, as `_extract_series` does. Accepting int epochs would be new normalization behavior and is out of scope.
- **Subsecond:** preserved via the datetime key; no rounding or truncation.

### 2.2 Missing / invalid metadata

- Missing `symbol`/`timeframe` (after applying contextual defaults) → `ValueError` (missing bar metadata), distinct from the duplicate error.
- Missing or unparseable `open_ts` → `ValueError` (invalid timestamp); `_parse_ts` raises `ValueError` for bad strings, non-string input wrapped into `ValueError`.

### 2.3 Exceptions (not duplicates)

- Same `open_ts`, different `symbol` → accepted (Class C).
- Same `symbol`, same `open_ts`, different `timeframe` → accepted (Class D).
- Same key, differing OHLCV → **rejected** (Class B); OHLCV values are never compared for key identity.

---

## 3. Performance and validation ownership

### 3.1 Repeated validation of shared D1 inputs

`run_scan` calls `compute_level_events(d1_bars, em_bars, params)` once per emission timeframe per symbol (scan.py:193-197), passing the **same** `d1_bars = extracted[(symbol, "D1")]` each time. If `levels.py` re-validates `d1_bars` on every call, the D1 series is validated once per emission timeframe. Each pass is O(n) over a hash set of at most the series' keys (~65k rows/file ≈ a few MB), small but avoidable in the scan path.

### 3.2 Recommended ownership — one authoritative implementation

**Single authoritative implementation:** `scanline/validation/duplicate.py` exports `DuplicateBarKeyError(ValueError)` and `validate_unique_bar_keys`. All enforcement calls this one helper; no module implements its own duplicate logic.

**Call sites:**
1. `scanline/scan.py::_extract_series` (scan.py:65-86) — per-file check while reading rows; fail-fast before dispatch; `reader.line_num` and the file path provide source-row metadata. Belt-and-suspenders for the scan path.
2. `scanline/sessions.py::_core_compute` (sessions.py:458) — start of computation, before `_group_bars_by_utc_date`; covers every `compute_events` call shape (all funnel through `_core_compute`). Direct session callers protected.
3. `scanline/levels.py::compute_events` (levels.py:160) — start, for both `d1_bars` and `emission_bars`, before sorting/state iteration. Direct level-proximity callers protected.

**Minimizing repeated scanning:**
- The scan path validates each `(symbol, tf)` series once in `_extract_series`. Detector-level checks remain for direct-call protection; in the `run_scan` path they re-validate already-validated bars — a bounded second O(n) pass, accepted as the cost of one implementation protecting both paths.
- **No cross-call caching, no trusted-input bypass, no "already validated" flag.**
- Memory: one hash set per validation call holding only canonical keys, scoped to the collection being validated and discarded after — proportional to the collection, not the corpus.

---

## 4. Cross-source duplicates

### 4.1 Actual architecture

`run_scan` extracts exactly one CSV per `(symbol, tf)` series (`{SYMBOL}_{TIMEFRAME}.csv`, scan.py:66) and never merges two files into one detector input. Within a single `run_scan` dispatch, every detector input is one series from one file, so **duplicate keys across different CSV sources cannot enter a single detector input through `run_scan`**.

### 4.2 Supported multi-source aggregation (direct calls)

`compute_events` dict input (`symbol → bars`, sessions.py:535-540) and list-of-tuples input (sessions.py:541-547) are the **existing, supported** multi-symbol aggregation interfaces. A direct caller can combine bars originating from two CSV sources into one bar list for the same symbol/timeframe; duplicate keys across those sources are genuine duplicates and must be rejected. This capability is exercised only by direct/ad-hoc callers, not by `run_scan`.

### 4.3 Hypothetical future ingestion

A future ingestion API normalizing multiple feeds into one bar list would reuse the same shared helper; no such API exists in this milestone (out of scope).

### 4.4 Regression-test plan reflects the actual architecture

Cross-source duplicate rejection is tested at the **direct-detector level**: two bar lists (simulating two CSV sources) merged into one `compute_events`/`compute_level_events` input, asserting `DuplicateBarKeyError`. It is **not** tested through `run_scan`, since `run_scan` cannot produce a multi-source single-series input. Source-row metadata in errors is exercised where available (the `_extract_series` path).

---

## 5. Existing characterization tests (SCAN-017B)

### 5.1 The four duplicate tests

`tests/test_sessions.py::TestSessionCurrentBehavior` (labeled "NOT approval of those behaviors", test_sessions.py:286-289):
- `test_duplicate_identical_bars_inflate_count` (test_sessions.py:477) — 1 unique + 2 identical duplicates → observed=3 → `stub_session` suppressed.
- `test_duplicate_same_timestamp_differing_ohlcv_no_gap` (test_sessions.py:490) — conflicting OHLCV, same timestamp → no gap.
- `test_duplicate_bars_inflating_observed_counts_suppress_stub` (test_sessions.py:502) — 1 unique + 1 duplicate → observed=2 → `stub_session` suppressed.
- `test_duplicate_timestamps_no_positive_duration_gap` (test_sessions.py:514) — duplicate timestamps → no positive-duration gap.

These assert duplicates are **accepted**; under Policy B they raise `DuplicateBarKeyError`/`ValueError` and conflict with the new contract.

### 5.2 Transition (not done in this phase)

- Replace the old duplicate-counting assertions with rejection assertions (`pytest.raises(DuplicateBarKeyError)` / `ValueError`), keyed on `(symbol, timeframe, open_ts)`.
- Preserve the old behavior in historical documentation: `docs/SCAN-017E-DUPLICATE-POLICY.md` remains the record of pre-Policy-B tolerant behavior; these tests are reclassified as characterizing pre-change behavior.
- Keep all other SCAN-017B characterization tests (boundary, weekday, Sunday, Saturday/holiday) unchanged.
- **No test modifications in this proposal phase.**

---

## 6. Error handling

- `DuplicateBarKeyError(ValueError)` in `scanline/validation/duplicate.py` — catchable specifically, still matches `except ValueError` (consistent with sessions.py's existing `ValueError` input guards at sessions.py:466-473).
- Deterministic first-duplicate reporting: single left-to-right pass; the **second** occurrence of a key is the first duplicate reported; identical input order ⇒ identical error.
- Message identifies (where available): symbol, timeframe, normalized UTC open timestamp (ISO + epoch seconds), first-occurrence position, duplicate-occurrence position.
- Positions: input index within the supplied bar list (always available); source-row metadata (file path + row number) only where actually available — i.e. the `_extract_series` path (`reader.line_num`, scan.py:71). Direct detector calls report input index only.
- **No OHLCV values in error messages.**

Missing metadata / invalid timestamp raises a plain `ValueError` (not `DuplicateBarKeyError`), distinguishing key-formation errors from duplicate errors.

Example message:
```
DuplicateBarKeyError: duplicate bar key: symbol=GOLD, timeframe=H1, open_ts=2026-01-07T00:00:00Z (epoch 1767734400);
first occurrence at input index 3, duplicate at input index 7 (source: GOLD_H1.csv row 9)
```

---

## 7. Enforcement call sites (exact)

1. **`scanline/validation/duplicate.py`** (new) — `DuplicateBarKeyError(ValueError)`, `validate_unique_bar_keys(bars, symbol=None, timeframe=None, source=None) -> None`.
2. **`scanline/sessions.py::_core_compute`** (sessions.py:458) — call helper at the start, before `_group_bars_by_utc_date` (sessions.py:487); resolves effective symbol/timeframe from bars (contextual defaults if signature extended later).
3. **`scanline/levels.py::compute_events`** (levels.py:160) — call helper at the start for `d1_bars` and `emission_bars`, before sorting/state iteration (levels.py:163-164).
4. **`scanline/scan.py::_extract_series`** (scan.py:65-86) — optional per-file early check during row reading for immediate fail-fast with source-row metadata.

The helper is the single policy implementation; `run_scan` relies on it via the detectors (and optionally the early per-file check). No divergent duplicate logic in `scan.py`, `sessions.py`, or `levels.py`.

---

## 8. Updated test migration strategy

Planned new tests (additive; not written yet):

1. **Identical duplicates rejected** — repeated `(symbol, tf, open_ts)` with identical OHLCV → `DuplicateBarKeyError`.
2. **Conflicting duplicates rejected** — repeated key, differing OHLCV → error, message identifies the key.
3. **Three or more occurrences** — failure on the **second** occurrence (first duplicate reported), deterministic regardless of total count.
4. **Cross-source duplicates rejected** — two bar lists merged into one direct detector input → rejected (exercises source-row metadata where available).
5. **Same timestamps across symbols accepted** — GOLD H1 and SILVER H1 at the same instant → no error.
6. **Same timestamps across timeframes accepted** — GOLD H1 and GOLD H4 at the same instant → no error.
7. **Equivalent timestamp representations** — `Z`, offset, and naive-UTC forms of the same instant → one key.
8. **Regression: duplicate-free inputs unchanged** — duplicate-free inputs yield exactly the same events as before.

These are additive; they do not alter existing non-duplicate tests.

Transition of the four SCAN-017B duplicate tests: replace counting assertions with rejection assertions; preserve old behavior in `docs/SCAN-017E-DUPLICATE-POLICY.md`; keep other SCAN-017B tests unchanged. No test changes yet.

---

## 9. Exact files to change (if implemented)

- **`scanline/validation/duplicate.py`** (new) — shared helper + `DuplicateBarKeyError`.
- **`scanline/sessions.py`** — `_core_compute`: call helper before `_group_bars_by_utc_date`.
- **`scanline/levels.py`** — `compute_events`: call helper for `d1_bars` and `emission_bars`.
- **`scanline/scan.py`** — optional early per-file duplicate check in `_extract_series`.
- **`tests/test_sessions.py`** — new rejection tests; reconcile the four `TestSessionCurrentBehavior` duplicate tests (deferred).
- **`docs/SCAN-017E-DUPLICATE-POLICY.md`** — cross-reference SCAN-017F; mark implementation status.
- **`docs/SCAN-017-CONTRACT-DECISIONS.md`** — duplicate-policy section: Policy B decided (rejection over silent dedup).

---

## 10. Implementation sequence

1. Approve this revised proposal (Policy B + architecture).
2. Add planned rejection tests — fail before implementation, pass after.
3. Create `scanline/validation/duplicate.py` with helper + `DuplicateBarKeyError`.
4. Wire helper into `sessions.py::_core_compute` (before counting) and `levels.py::compute_events` (before processing).
5. Add optional early per-file check in `scan.py::_extract_series`.
6. Reconcile SCAN-017B duplicate characterization tests (reclassify or update to expect rejection).
7. Run full test suite; verify duplicate-free baseline preserved (152 passed, 1 skipped per SCAN-017E) and new tests pass.
8. Document input-integrity contract in `sessions.py`/`levels.py` docstrings and `docs/SCAN-017E-DUPLICATE-POLICY.md`.

---

## 11. Restrictions observed for this proposal

No source code, tests, configuration, or datasets modified. Nothing committed or pushed. This document is a proposal awaiting explicit implementation approval.
