# SCAN-017E — Duplicate Bar Integrity Reconnaissance & Policy

**Status: IMPLEMENTED under Policy B (SCAN-017F). Repeated `(symbol, timeframe, open_ts)` keys are rejected at the input boundary, including identical and conflicting OHLCV records. No silent deduplication.**

**Baseline:** `152 passed, 1 skipped` pre-implementation; `172 passed, 1 skipped` post-implementation (net +20 tests). Commits on `main`: `9a91e22` (SCAN-017), `75f78a2` (SCAN-014), `42cef18` (SCAN-015), `a3b90ca` (docs). Implementation is uncommitted, pending review.

---

## 1. Executive summary

SCANLINE currently has **no duplicate-bar detection, rejection, or deduplication anywhere in the ingestion, extraction, normalization, or detection pipeline.** Duplicate market bars are preserved end-to-end: every CSV row is loaded, every bar is counted, and duplicates inflate `observed_bars`, which can suppress `missing_session` and `stub_session` anomalies or make an incomplete session appear complete/within tolerance.

A read-only scan of the available corpus (`/home/joshua/corpus-store`, 426 CSV files, 27,772,858 market rows) found **zero exact duplicates** and **zero conflicting duplicates** within any single symbol/timeframe file. Cross-symbol timestamp overlap is common and valid (different instruments trading at the same instant) and must not be treated as duplication. Duplicate anomaly *events* appearing in historical `records/scans/*/events.json` are distinct level-proximity events sharing an `event_ts` (different `level_type`/`level_price`), **not** duplicate bars.

Because the corpus is currently clean, the duplicate risk is **latent, not realized**. The value of this work is to establish an input-integrity contract *before* duplicate-bearing sources are introduced, and to document the existing characterization tests that pin current behavior.

No source, test, config, dataset, or repository file was modified during this reconnaissance. Nothing was committed or pushed.

---

## 2. Current duplicate-handling behavior

### 2.1 CSV loading — `scanline/scan.py::_extract_series` (scan.py:65-86)

- Opens `{symbol}_{tf}.csv` via `csv.DictReader`.
- Appends **every** row to the `bars` list.
- Sorts `bars` by `open_ts`.
- **No duplicate detection, no rejection, no dedup.** Duplicate rows in a CSV are preserved verbatim.

### 2.2 Extraction into per-(symbol, timeframe) series — scan.py:143-175

- `extracted[(symbol, tf)] = bars` stores the full bar list per series.
- `seen_series` de-duplicates the `(symbol, tf)` *series key* (so a symbol/timeframe is extracted once even if requested multiple times), but does **not** de-duplicate bars within a series.

### 2.3 Session detection — `scanline/sessions.py`

- `_core_compute` (sessions.py:458-499): rejects mixed-symbol and mixed-timeframe *lists* (SCAN-017C/D), but performs **no duplicate-bar handling**.
- `_group_bars_by_utc_date` (sessions.py:327-340): `counts[d] += 1` for every bar, including duplicates. Duplicate bars inflate `observed_bars`.
- `_intra_session_gap_events` (sessions.py:409-455): duplicate timestamps produce a gap of `0`, so no positive-duration `intra_session_gap` is emitted between them. Duplicates do not create spurious gaps.
- Duplicate bars can suppress `missing_session`/`stub_session` by inflating `observed_bars` (demonstrated in section 6).

### 2.4 Level proximity — `scanline/sessions.py` is H1-only; levels.py

- `levels.py::compute_events` (levels.py:160-237): iterates emission bars in sorted order, maintaining per-level state keyed by `(level_type, level_price, defined_at)`. Duplicate bars at the same timestamp produce duplicate state updates but no explicit duplicate-bar rejection.

### 2.5 Validation — `scanline/validator.py` + `scanline/validation/`

- `validate_batch` and rules R1-R5 validate events against schema/params, not input bars. **No duplicate-bar check.**

### 2.6 Existing tests pin current behavior

`tests/test_sessions.py::TestSessionCurrentBehavior` characterized (did not approve) duplicate behavior. Under Policy B (SCAN-017F) the four duplicate tests were updated to expect rejection:

- `test_duplicate_identical_keys_rejected` — 1 unique bar + 2 identical duplicates now raises `DuplicateBarKeyError` (previously suppressed `stub_session`).
- `test_duplicate_conflicting_keys_rejected` — conflicting OHLCV at the same timestamp now raises `DuplicateBarKeyError` (previously no `intra_session_gap`).
- `test_duplicate_bars_inflating_observed_counts_suppress_stub_rejected` — 1 unique bar + 1 duplicate now raises `DuplicateBarKeyError` (previously suppressed `stub_session`).
- `test_duplicate_timestamps_rejected` — duplicate timestamps now raise `DuplicateBarKeyError` (previously no positive-duration gap).

New rejection/acceptance tests live in `tests/test_sessions.py::TestScan017FDuplicateIntegrity` and `tests/test_levels.py::TestScan017FDuplicateIntegrity` (identical, conflicting, 3+ occurrences, combined direct-call inputs, cross-symbol, cross-timeframe, equivalent timestamp representations, unchanged outputs for duplicate-free inputs, contextual defaults, missing metadata).

All other SCAN-017B characterization tests (boundary, weekday, Sunday, Saturday/holiday) are unchanged.

---

## 3. Duplicate definitions and identity rules

### 3.1 Minimum identity key

```
(symbol, timeframe, open_ts)
```

Two bars are duplicate **keys** when all three components match.

### 3.2 Classifications

| Class | Identity match | OHLCV match | Interpretation |
|-------|---------------|-------------|----------------|
| A — Identical duplicates | Yes | Yes | Same bar recorded twice; likely source duplication or merge artifact. |
| B — Conflicting duplicates | Yes | No | Same key, differing open/high/low/close/volume. Conflicting source records, incorrect merge, or late revision. |
| C — Cross-symbol timestamps | No (symbol differs) | N/A | Valid independent observations (e.g., GOLD H1 10:00 and SILVER H1 10:00). **Not duplicates.** |
| D — Cross-timeframe timestamps | No (timeframe differs) | N/A | Valid independent observations (e.g., GOLD H1 10:00 and GOLD H4 10:00). **Not duplicates.** |

### 3.3 Equality semantics

- Duplicate determination must use **exact raw-value equality** on the parsed fields, not tolerance-based or normalized comparison.
- For conflicting duplicates (Class B), the conflicting field(s) must be reported so operators can decide which record is authoritative.

---

## 4. Actual corpus investigation and quantified findings

### 4.1 Methodology

- Corpus location: `/home/joshua/corpus-store` (read-only; CSVs are **not** in the git repository — the repo contains only scan-output manifests referencing them).
- 426 CSV files scanned; 27,772,858 market rows read.
- Per file, `symbol` and `timeframe` are derived from the filename `{SYMBOL}_{TIMEFRAME}.csv`; within a file, the duplicate key is `open_ts`.
- Exact duplicate = same `(symbol, timeframe, open_ts)` with identical `(open, high, low, close, volume)`.
- Conflicting duplicate = same key with differing OHLCV.
- Cross-symbol / cross-timeframe timestamp overlap sampled from H1 files (first 2,000 rows per file).

### 4.2 Quantified findings

| Finding | Count | Detail |
|---------|-------|--------|
| CSV files inspected | 426 | All `*.csv` in `/home/joshua/corpus-store` |
| Total market rows scanned | 27,772,858 | Read-only, no modification |
| Exact duplicate keys (Class A) | **0** | No file contains repeated `(symbol, tf, open_ts)` with identical OHLCV |
| Conflicting duplicate keys (Class B) | **0** | No file contains repeated key with differing OHLCV |
| Cross-symbol timestamp overlap (Class C) | Common/valid | e.g. 7 symbols share H1 timestamp `1136149200`; normal, not duplication |
| Cross-timeframe timestamp overlap (Class D) | Valid | H1 and H4 bars share timestamps; normal, not duplication |
| Test fixtures with duplicate event keys | 0 | `tests/fixtures/*.json` contain no duplicate `(symbol, timeframe, event_ts)` |

### 4.3 Scan output `events.json` — apparent duplicate events (not bar duplicates)

`records/scans/*/events.json` contains multiple level-proximity events sharing an `(symbol, timeframe, event_ts)`:
- 1.1.0 window: 616 events, 63 duplicate timestamp-keys
- 2.0.0 window: 9,060 events, 1,667 duplicate timestamp-keys
- 2.1.0 window: 4,624 events, 515 duplicate timestamp-keys
- Total: 14,300 events, 2,874 extra timestamp-keys

**Interpretation:** These are *distinct* events (different `level_type`/`level_price`, e.g. `grid_round` at price 4400 and `d1_prior_high` at 4402.61 both firing at `2026-08-11T03:00:00Z`) that legitimately share an `event_ts`. They are **not duplicate bars** and are not a data-integrity problem. A correct duplicate-key check on input bars would not flag them.

### 4.4 Coverage statement

The zero-duplicate result applies to the 426 CSV files present in `/home/joshua/corpus-store` at scan time. It does **not** establish global absence across all possible future corpus sources, external feeds, or hand-constructed test inputs. The pipeline must treat duplicates as a possible input condition.

---

## 5. Data-pipeline trace

Source → ingestion → extraction → normalization → event generation:

1. **CSV ingestion** (`scan.py::_extract_series`, scan.py:65-86): every row loaded, preserved, sorted. Duplicates survive. **Earliest practical detection point.**
2. **Per-series extraction** (scan.py:143-175): series keyed by `(symbol, tf)`; bars stored as-is. No bar-level dedup.
3. **Symbol/tagging** (scan.py:183-186): session bars tagged with symbol if missing; no collision introduced.
4. **Normalization** (`sessions.py::compute_events`/`_normalize_args`, sessions.py:502-555): accepts list, dict (symbol→bars), or list-of-tuples; dict/list-of-tuples paths call `_core_compute` per symbol. No cross-bar duplicate check.
5. **Mixed-symbol/timeframe rejection** (sessions.py:465-476): raises `ValueError` on mixed lists — a *different* integrity guard, not duplicate handling.
6. **Session counting** (`sessions.py::_group_bars_by_utc_date`, sessions.py:327-340): `counts[d] += 1` per bar; duplicates inflate `observed_bars`.
7. **Anomaly detection** (`sessions.py::_session_level_anomalies`, `_intra_session_gap_events`): operates on inflated counts; duplicates can suppress anomalies.
8. **Validation** (`validator.py`, `validation/r1..r5`): validates emitted events, not input bars; no duplicate-bar check.

**Repeated scans are deterministic** for identical source data (sorting is stable, no randomness), but if the source data changes (duplicates added/removed), outputs change accordingly — there is no self-healing.

---

## 6. Detection consequences

Duplicates inflate `observed_bars` and therefore affect every count-derived anomaly:

### 6.1 `observed_bars`
Each duplicate bar increments the per-UTC-date count by 1, directly raising `observed_bars`.

### 6.2 `missing_session` / `stub_session` suppression (concrete example)

Cluster config: `expected_bars=3`, `stub_tolerance=1`, interior Wednesday.

| Input bars on Wednesday | `observed_bars` | `missing_session`? | `stub_session`? |
|-------------------------|-----------------|--------------------|-----------------|
| 1 unique bar | 1 | No (observed>0) | **Yes** (`0 < 1 < 3-1`) |
| 1 unique + 1 identical duplicate | 2 | No | No (`2` is not `< 2`; at tolerance boundary, accepted) |
| 1 unique + 2 identical duplicates | 3 | No | No (`3 == expected`) |

**Demonstrated:** `1 unique + 2 identical duplicates` (observed=3) makes an under-supplied session appear complete and suppresses the `stub_session` anomaly. Confirmed by `test_duplicate_bars_inflating_observed_counts_suppress_stub` and `test_duplicate_identical_bars_inflate_count`.

### 6.3 `sunday_anomaly`
Sunday uses `abs(observed - expected_sun) > sun_tol`. Duplicate Sunday bars inflate `observed`, which can push a Sunday past tolerance (causing a false `sunday_anomaly` on over-count) or pull it within tolerance (suppressing a real one).

### 6.4 Intra-session gap detection
Duplicate bars at the same timestamp produce gap `0`, so no `intra_session_gap` is emitted between them. They do **not** create spurious gaps, but they can shift the sorted sequence such that a real gap is measured between a duplicate and a subsequent bar (same duration as the underlying gap — no change in detection outcome for same-timestamp duplicates).

### 6.5 Scan reproducibility
Deterministic for identical inputs. Duplicate-bearing sources produce reproducible-but-wrong outputs; there is no signal that duplicates were present.

### 6.6 Event counts and validation results
More observed bars → fewer session-level anomaly events → different validation outcome. No validator rule currently rejects duplicate input bars.

---

## 7. Policy comparison

| Policy | Description | Data integrity | Compatibility | Historical reproducibility | Detection consequences | Error reporting | Complexity | Location |
|--------|-------------|----------------|---------------|---------------------------|------------------------|-----------------|------------|----------|
| **A — Preserve current behavior** | Count every bar; no duplicate handling. | Weak — duplicates silently inflate counts. | Full — no behavior change. | Preserved exactly. | Duplicates can suppress/create anomalies silently. | None. | None (status quo). | None. |
| **B — Reject duplicate keys** | Reject repeated `(symbol, tf, open_ts)` at input boundary, regardless of OHLCV match. | Strong — no duplicates enter detection. | Breaking — any future duplicate-bearing source fails hard. | Changed for inputs that contain duplicates. | Duplicates cannot suppress anomalies; source error surfaced immediately. | Explicit `ValueError` naming the duplicate key. | Low. | Input boundary (`_extract_series` / `compute_events`). |
| **C — Dedup identical + reject conflicts** | Collapse identical OHLCV duplicates; reject conflicting OHLCV at same key. | Strong — identical duplicates removed, conflicts surfaced. | Breaking for conflicting inputs; silent change for identical-duplicate inputs (historical outputs may differ). | Changed for inputs containing identical duplicates. | Identical dups no longer inflate counts; conflicts error out. | Dedup count reported; conflicts rejected with detail. | Medium. | Normalization stage. |
| **D — Normalize upstream** | Resolve duplicates in a dedicated ingestion/normalization stage before SCANLINE receives data. | Depends on upstream implementation. | Full for SCANLINE (receives clean data). | Preserved for SCANLINE; upstream owns history. | Duplicates never reach SCANLINE. | Upstream reports rejections. | High (cross-system). | External ingestion/normalization, outside SCANLINE. |

### Assessment

- **Policy A** leaves a known latent defect: duplicates inflate counts and suppress anomalies with no signal. Not recommended as a long-term contract.
- **Policy B** (explicit rejection of duplicate keys) is the simplest strong guarantee and matches the stated preference ("explicit rejection of duplicate keys rather than silent deduplication"). It fails fast at the boundary with a clear error, avoiding silent data corruption.
- **Policy C** is more lenient but silently alters historical outputs for identical-duplicate inputs and requires deciding which OHLCV record to retain (or whether collapse is acceptable). It reintroduces silent data modification for Class A.
- **Policy D** is architecturally cleanest but out of scope for SCANLINE alone; it defers the problem and does not protect SCANLINE from direct/ad-hoc callers.

---

## 8. Recommended policy

**Policy B — Reject duplicate keys at the input boundary.**

Reject any repeated `(symbol, timeframe, open_ts)` record, regardless of whether OHLCV matches (covers both Class A identical and Class B conflicting duplicates). Raise an explicit `ValueError` naming the duplicate key and (for Class B) the conflicting field(s).

Rationale:
- Strongest data-integrity guarantee: no duplicate can silently inflate `observed_bars` or suppress anomalies.
- Fail-fast error reporting surfaces source problems immediately rather than producing wrong anomaly counts.
- Simplest implementation; avoids the silent-history-modification problem of Policy C.
- Protects all callers (scan driver, tests, direct/ad-hoc use), not just one pipeline stage.

Cross-symbol (Class C) and cross-timeframe (Class D) timestamp matches are explicitly **not** duplicates and must not be rejected.

---

## 9. Implementation (SCAN-017F)

### 9.1 Authoritative implementation

`scanline/validation/duplicate.py` (new) exports `DuplicateBarKeyError(ValueError)` and `validate_unique_bar_keys(bars, symbol=None, timeframe=None, source=None)`. It is the single authoritative duplicate-validation implementation; no module implements its own duplicate logic.

### 9.2 Enforcement locations

Duplicate validation runs at the input boundary, before session counting, sorting/state processing, or event generation:

1. `scanline/sessions.py::_core_compute` — start of computation, before `_group_bars_by_utc_date`; covers every `compute_events` call shape (list, `symbol → bars` dict, list-of-`(symbol, bars)` tuples). Protects direct session detector calls and `run_scan` (scan.py:187).
2. `scanline/levels.py::compute_events` — start of computation, for both `d1_bars` and `emission_bars`, before sorting/state iteration. Protects direct level-proximity calls and `run_scan` (scan.py:197).

`scanline/scan.py` was **not** modified: `run_scan` dispatches exclusively through the two detectors above, so detector-level enforcement covers the scan path. Source-row metadata (`reader.line_num`, file path) is not available at the detector boundary; the helper's `source` parameter exists for callers that have it (e.g. a future `_extract_series` check).

### 9.3 Key identity and error contract

- Key: `(symbol, timeframe, open_ts)` with symbol/timeframe canonicalized (strip, upper) and `open_ts` parsed to a canonical UTC `datetime` using the existing `_parse_ts` convention (trailing `Z`, `datetime.fromisoformat`, naive → UTC). Microsecond precision is preserved; equivalent representations (`...Z`, `...+00:00`, naive UTC) map to one key.
- Contextual `symbol`/`timeframe` defaults are applied to bars missing those fields; missing metadata or an unparseable `open_ts` raises a plain `ValueError`, distinct from `DuplicateBarKeyError`.
- Deterministic first-duplicate reporting: single left-to-right pass; the second occurrence is reported with both input indices.
- Error message names the symbol, timeframe, canonical UTC `open_ts` (ISO + epoch seconds), and both occurrence positions, plus `source` where available. **No OHLCV values are included in error messages.**
- Cross-symbol (Class C) and cross-timeframe (Class D) timestamp matches are accepted.

### 9.4 Performance

No caching or trusted-input bypasses were introduced (per SCAN-017F milestone restrictions). Each validation call is one O(n) pass holding a hash set of canonical keys scoped to the collection. In `run_scan`, shared D1 input is re-validated once per emission timeframe (bounded second pass); measured overhead is documented in the SCAN-017F implementation report.

---

## 10. Compatibility and migration risks

- **Breaking change for duplicate-bearing inputs:** any future corpus/source containing repeated `(symbol, tf, open_ts)` will cause `compute_events`/`run_scan` to raise `ValueError` instead of producing output. Callers relying on silent duplicate counting will break.
- **No impact on current corpus:** the 426 scanned CSV files contain zero duplicates, so existing scans and historical `records/scans/` outputs are unaffected.
- **Test impact:** the four duplicate characterization tests in `TestSessionCurrentBehavior` were updated to expect rejection (renamed `*_rejected`); new tests in `TestScan017FDuplicateIntegrity` (sessions and levels). All other SCAN-017B characterization tests unchanged.
- **Scan ledger:** duplicate-induced scan failures would appear as new error lines; ledger append-only semantics preserved.

---

## 11. Required regression tests

If Policy B is approved, add tests under `tests/test_sessions.py`:

1. `test_duplicate_identical_keys_rejected` — repeated `(symbol, tf, open_ts)` with identical OHLCV raises `ValueError`.
2. `test_duplicate_conflicting_keys_rejected` — repeated key with differing OHLCV raises `ValueError`, message identifies conflicting field(s).
3. `test_duplicate_cross_symbol_not_rejected` — same `open_ts`, different symbols, accepted (Class C).
4. `test_duplicate_cross_timeframe_not_rejected` — same `open_ts`, same symbol, different timeframe, accepted (Class D).
5. `test_duplicate_rejection_before_counting` — a duplicate-bearing bar list that would otherwise suppress a `stub_session` instead raises, confirming counting never sees duplicates.
6. Scan-level test: `run_scan` on a duplicate-bearing CSV raises `ValueError` (if a fixture CSV with a duplicate is constructed for the test).

These are additive; they do not alter existing non-duplicate tests.

---

## 12. Implementation sequence (completed)

1. Policy B approved; enforcement location agreed (sessions `_core_compute` + levels `compute_events`, shared helper in `validation/duplicate.py`).
2. Rejection tests added; they failed before implementation, pass after.
3. `scanline/validation/duplicate.py` created with `DuplicateBarKeyError` + `validate_unique_bar_keys`.
4. Helper wired into `sessions.py::_core_compute` (before counting) and `levels.py::compute_events` (before processing).
5. `scan.py` not modified: detector-level enforcement covers `run_scan`.
6. SCAN-017B duplicate characterization tests updated to expect rejection.
7. Full suite run: 172 passed, 1 skipped; duplicate-free baseline outputs unchanged.
8. Contract documented below and in `docs/SCAN-017-CONTRACT-DECISIONS.md`.

---

## 13. Files changed

- `scanline/validation/duplicate.py` (new) — shared helper + `DuplicateBarKeyError`.
- `scanline/sessions.py` — import + `_core_compute` validation call before sorting/counting.
- `scanline/levels.py` — import + `compute_events` validation calls for `d1_bars` and `emission_bars`.
- `tests/test_sessions.py` — four SCAN-017B duplicate tests updated to expect rejection; new `TestScan017FDuplicateIntegrity` class; `mk` accepts `timeframe`.
- `tests/test_levels.py` — new `TestScan017FDuplicateIntegrity` class.
- `docs/SCAN-017E-DUPLICATE-POLICY.md` — this document; status, enforcement, error contract, test impact.
- `docs/SCAN-017-CONTRACT-DECISIONS.md` — duplicate-policy section: Policy B rejection decided.

Not modified: `scanline/scan.py` (detector enforcement covers `run_scan`), corpus datasets, config defaults, historical scan records, event schemas, or any preserved behavior listed in section 14.

---

## 14. Decisions resolved by this implementation

1. **Policy selection:** Policy B (reject repeated `(symbol, timeframe, open_ts)` keys, including identical and conflicting OHLCV; no silent deduplication).
2. **Enforcement location:** `sessions.py::_core_compute` and `levels.py::compute_events`, both calling the single shared helper `scanline/validation/duplicate.py::validate_unique_bar_keys`; `scan.py` left unmodified because `run_scan` dispatches exclusively through those detectors.
3. **Scope:** rejection covers both the session-anomaly and level-proximity paths, direct calls and `run_scan`.
4. **Error message design:** `DuplicateBarKeyError(ValueError)` naming symbol, timeframe, canonical UTC `open_ts` (ISO + epoch seconds), first and duplicate input indices, and `source` where available; no OHLCV values in messages. Missing metadata / unparseable `open_ts` raises a distinct plain `ValueError`.
5. **Existing characterization tests:** the four SCAN-017B duplicate tests updated to expect rejection; historical duplicate-inflation behavior remains documented in this doc (sections 2, 6) but is no longer accepted runtime behavior.
6. **Control Center display:** out of scope for this milestone.
7. **Migration:** read-only corpus scan found zero duplicate keys in all 426 CSV files (27,772,858 rows), so no current corpus or historical `records/scans/` output is affected by the new rejection.

---

**Appendix: verification commands used (read-only)**

- Corpus duplicate scan: 426 CSV files, 27,772,858 rows, 0 exact/conflicting duplicates (script `/tmp/kilo/dup_recon.py`, no repo writes).
- Duplicate consequence demonstration: 1 unique bar (observed=1) → `stub_session` fires; 1 unique + 2 identical duplicates (observed=3) → `stub_session` suppressed; conflicting duplicate same timestamp → no `intra_session_gap`.
- Existing duplicate characterization tests: 4 passed (now assert `DuplicateBarKeyError` rejection; renamed `*_rejected` in `TestSessionCurrentBehavior`).

**No repository files were modified, committed, or pushed during this reconnaissance.**
