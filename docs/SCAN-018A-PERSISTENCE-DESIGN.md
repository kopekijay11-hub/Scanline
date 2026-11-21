# SCAN-018A — Scan Identity & Atomic Persistence Design

**Status: IMPLEMENTED (SCAN-018A implementation authorized).**

**Scanline** — `docs/SCAN-018A-PERSISTENCE-DESIGN.md`

Milestone SCAN-018A implements scan identity, atomic output publication, exclusive destination creation, and a manifest-as-completion-marker protocol in `scanline/scan.py`, with regression tests in `tests/test_scan.py`. Historical records, configuration, detection logic, validator rules, and event schemas are unchanged.

---

## 0. Baseline (verified against source)

- `scanline/scan.py::run_scan` (scan.py:103-285) is the single scan driver. It takes `corpus_path` and `output_dir` and writes exactly two artifacts into `output_dir`:
  - `events.json` — `{"events": [...], "header": {...}}` (scan.py:220-231).
  - `scanner_data_manifest.json` — execution metadata, series manifest, param hashes, code state (scan.py:239-261).
- `output_dir.mkdir(parents=True, exist_ok=True)` (scan.py:109) is the only pre-write filesystem operation; it silently creates/accepts any existing directory.
- Writes are direct: `open(path, "w")` + `json.dump` + `f.write("\n")` with no temp file, no flush, no fsync, no atomic rename (scan.py:228-231, 258-261).
- Event `defined_at` values are wall-clock freeze timestamps from params, not execution time; `execution_start` in the manifest is `datetime.now(timezone.utc)` (scan.py:238) — the only wall-clock artifact field.
- Existing records live in `records/scans/<module>-<param_version>-window-<start>_<end>/` containing exactly `events.json` and `scanner_data_manifest.json` (e.g. `level_proximity-1.1.0-window-2026-08-08_2026-09-06/`).
- `tests/test_scan.py` asserts byte-identical `events.json` across two `run_scan` calls into separate output dirs (test_scan.py:67-74). Determinism of event content is an existing, tested contract.
- `records/ledger/scan-ledger.jsonl` keys each line by `(corpus file hashes, window, symbol set, module, params hash, code commit, scan_mode)` — deterministic, no per-run identifier.
- No scan identifier, no manifest `status`, no completion marker, and no overwrite protection exist anywhere (grep for scan_id/status/RUNNING/COMPLETE found nothing).

---

## 1. Current write sequence (exact)

For each `run_scan(corpus_path, output_dir, ...)` call:

1. `output_dir.mkdir(parents=True, exist_ok=True)` — create/accept destination directory (scan.py:109).
2. For each needed `(symbol, tf)`: open `{symbol}_{tf}.csv`, read bars, compute `_sha256_file(path)` and `_size_file(path)` — read-only corpus access; build `series_manifest` (scan.py:143-175).
3. Run detectors per symbol × emission timeframe; collect `all_events` filtered to batch window (scan.py:178-201).
4. Build `header` and `batch = {"events": all_events, "header": header}` (scan.py:205-221).
5. `validate_batch(all_events, header, params_bytes)` — raise `RuntimeError` on invalid (scan.py:223-225).
6. Open `output_dir / "events.json"` for write; `json.dump(batch, f, indent=2)`; `f.write("\n")` (scan.py:228-231).
7. Compute `_git_head(repo_root)`, `_driver_sha256()`, `execution_start = _fmt_ts(datetime.now(timezone.utc))` (scan.py:234-238).
8. Build `manifest` dict; open `output_dir / "scanner_data_manifest.json"` for write; `json.dump`; `f.write("\n")` (scan.py:239-261).
9. Return `None` — caller has no signal of success except absence of exception.

**Filesystem operations documented:** one `mkdir`, two direct `open(w)` truncating writes, zero fsyncs, zero temp files, zero renames. No operation is atomic; a crash between steps 6 and 8 leaves `events.json` without a manifest; a crash during step 6 leaves a truncated `events.json`.

---

## 2. Scan identity recommendation

### 2.1 Requirement summary

| Requirement | Rationale |
|---|---|
| Unique across repeated executions | Distinguish two scans of identical inputs executed at different times. |
| Safe for filenames/directory names | No `/`, spaces, or shell-metacharacters; bounded length. |
| Collision-resistant | Two concurrent scans must not pick the same ID except with negligible probability. |
| Stable throughout one scan execution | All artifacts of one scan share one ID. |
| Shared by all artifacts | Directory name, manifest, event metadata all reference the same ID. |
| Not part of deterministic event contents | `events.json` payloads must remain byte-identical across repeated identical scans (preserves test_scan.py and ledger keying). |

### 2.2 Options compared

| Option | Uniqueness | Collision resistance | Filename-safe | Deterministic-event impact | Verdict |
|---|---|---|---|---|---|
| **UUID4** (random 122-bit) | High (random) | Strong (122 bits random) | Yes (hex, with dashes stripped or kept) | None if kept out of events.json | Acceptable |
| **Timestamp-only** (`%Y%m%dT%H%M%S%fZ`) | Weak — collisions within same microsecond across concurrent/rapid executions | None | Yes | None | Rejected |
| **Timestamp + random suffix** (`%Y%m%dT%H%M%S%fZ_<8-hex>`) | High | Strong (timestamp orders, random suffix disambiguates) | Yes | None if kept out of events.json | Recommended |

### 2.3 Recommendation (implemented)

**Scan ID = `<utcnow(%Y%m%dT%H%M%S%fZ)>_<secrets.token_hex(16)>`.**

Format example: `20261121T013740123456Z_<32-hex-chars>`.

- Timestamp component gives human readability, coarse ordering, and local debuggability.
- 32-hex-char random suffix (128 bits, `secrets.token_hex(16)`) makes collision probability negligible for concurrent scans and distinguishes repeated identical scans. (The proposal originally floated 8 hex chars; the requirement specifies 32.)
- Entire ID is `[0-9TZ_0-9a-f]` — safe for directory and file names on all common filesystems (ext4, XFS, NTFS, APFS).
- **Never included in `events.json` event objects or the `header`.** Event contents remain a pure function of corpus, params, and windows. The scan ID is publication metadata only.

Implementation: `scanline/scan.py::generate_scan_id()` (scan.py). The ID is generated once per `run_scan` execution and retained throughout.

### 2.4 Where the scan ID appears

| Location | Form | Rationale |
|---|---|---|
| **Output directory name** | `<scan_id>/` under a parent scans root (e.g. `records/scans/<scan_id>/`) | All artifacts of one scan share one directory; the directory name *is* the scan ID, enabling collision detection by existence check. |
| **Manifest** | Top-level `"scan_id": "<id>"` field | Manifest is the completion marker; it must name the scan it certifies. |
| **Event file metadata** | **Not in event objects.** Optional top-level envelope field `"scan_id"` only if SCAN-018B approves an envelope contract; otherwise `events.json` schema is unchanged and the scan ID is recoverable from the containing directory name. | Preserves deterministic event contents and existing schemas without an explicit contract decision. |

The output parent directory is a scans root (default `records/scans/`). A scan writes to `<scans_root>/<scan_id>/`, never into an existing versioned directory like `level_proximity-1.1.0-window-.../`. Historical directories remain untouched.

---

## 3. Atomic publication design

### 3.1 Core principle

A multi-file scan is **not** atomic merely because each file is replaced atomically. Consumers must be able to distinguish a complete scan from a partial one. The manifest is the single completion marker and is published **last**, only after every required output is durable.

### 3.2 Approach A — Per-file atomic publish + manifest completion marker

Each required file is written to a temp file in the destination directory, fsync'd, then atomically renamed into place with `os.replace`. The manifest is written last, via the same temp+fsync+rename sequence, and its presence with `status == "COMPLETE"` certifies the scan.

- Crash behavior: a crash before the manifest rename leaves zero or more data files replaced but no COMPLETE manifest → scan is incomplete; consumers reject it. Orphaned temp files (`*.tmp.<pid>`) may remain and are cleaned on next scan to that destination or by a sweeper.
- Partial writes: confined to temp files; destination files are either fully old or fully new.
- Recovery: on re-run, a new scan ID is chosen; the incomplete destination is left as evidence (not overwritten per §4). A separate recovery path may adopt an orphaned temp file only under explicit opt-in.
- Existing-file collisions: `os.replace` overwrites — **not acceptable as the default** without a pre-check; combined with the §4 existence rejection, the destination is known absent before any rename, so overwrite cannot occur from concurrent same-ID attempts (the ID check itself races; see §5).
- Filesystem portability: `os.replace` is atomic on POSIX and Windows for same-filesystem renames; temp file must be created on the same filesystem as the destination (same directory guarantees this).
- Concurrent execution: two scans writing different IDs to different directories never conflict; two scans attempting the same ID race on the existence check (handled in §5).

### 3.3 Approach B — Staging directory + atomic directory publish

Build all outputs in a staging dir `<dest>.stage.<pid>/`, fsync files, then attempt to rename the staging dir to `<dest>`. Directory rename is atomic only if `<dest>` does not exist; on most systems renaming onto an existing non-empty directory fails (`ENOTEMPTY`/`EEXIST`), so there is no safe no-overwrite directory rename without a prior existence check and an `rmdir` of an empty target.

- Crash behavior: orphaned staging dirs remain; easily identified by `.stage.<pid>` suffix and removable by a sweeper.
- Partial writes: confined to staging.
- Recovery: re-run picks a new scan ID and fresh staging; orphaned staging dirs accumulate unless swept.
- Existing-file collisions: no atomic "rename directory if absent" primitive exists portably; requires `mkdir(dest)` with `exist_ok=False` then move contents, which is not atomic and leaves a non-atomic window.
- Concurrent execution: same race on destination creation as Approach A.
- **Verdict:** heavier, less portable, and does not provide a true atomic directory publish. The manifest-completion-marker approach (A) is simpler and gives consumers a precise completion signal.

### 3.4 Recommended design (Approach A)

Per-scan destination: `<scans_root>/<scan_id>/`.

Publication protocol:
1. Compute `scan_id`. Destination `dest = scans_root / scan_id`.
2. **Existence rejection:** if `dest` exists → fail (see §4).
3. Create `dest.mkdir()` (not `exist_ok=True`).
4. For each required output (`events.json`, `scanner_data_manifest.json`):
   - Serialize to bytes in memory.
   - Write temp file `dest / f"<name>.tmp.<pid>"` (same directory, same filesystem).
   - `f.flush(); os.fsync(f.fileno())`.
   - `os.replace(temp, dest / name)`.
5. Manifest last: serialize manifest with `"scan_id": scan_id` and `"status": "COMPLETE"`, then temp+fsync+rename as above.
6. `os.fsync(dest_dir_fd)` after the final rename to durably record the directory entry (best-effort; ignore where unsupported).
7. Return `scan_id` (or a result object) so the caller knows publication succeeded.

Order within step 4: `events.json` first, manifest second and last. The manifest lists required outputs and their hashes/sizes so consumers can verify durability.

**Manifest fields added:**
- `"scan_id": str` — names the scan.
- `"status": "RUNNING" | "COMPLETE" | "FAILED" | "INTERRUPTED"` — publication lifecycle state (see §5).
- `"outputs": [{"name": "events.json", "sha256": ..., "size_bytes": ...}, ...]` — consumer verification list.

Crash points and resulting state:
- Crash before any rename: `dest` may exist (empty or partially populated via mkdir) but no manifest → incomplete.
- Crash after `events.json` rename, before manifest rename: `events.json` present, no COMPLETE manifest → incomplete.
- Crash during temp write: only `*.tmp.<pid>` present → incomplete; temp is garbage.
- Crash after manifest rename: COMPLETE manifest present → complete; all required outputs were renamed before it.

---

## 4. Manifest completion protocol

### 4.1 Lifecycle states

| State | Persisted? | Meaning | Consumer interpretation |
|---|---|---|---|
| `RUNNING` | Optional (manifest written early with status RUNNING, then rewritten to COMPLETE) | Publication in progress | Treat as incomplete; do not consume. |
| `COMPLETE` | Yes — final manifest rename | All required outputs written and manifest durable | Valid completed scan; safe to consume. |
| `FAILED` | Optional — written on caught exception before re-raise | Scan failed validation or serialization | Incomplete; destination may hold partial outputs; do not consume. |
| `INTERRUPTED` | Optional — written on signal/KeyboardInterrupt handler | Publication interrupted | Incomplete; treat like FAILED. |

**Minimum viable contract for SCAN-018A:** only `COMPLETE` is persisted. The manifest is written once, last, with `"status": "COMPLETE"`. Absence of a manifest, or a manifest with any other status/missing status, means incomplete. `RUNNING`/`FAILED`/`INTERRUPTED` are reserved for SCAN-018B to avoid conflicting manifest designs; this document names them so SCAN-018B can adopt the same vocabulary without redefining it.

### 4.2 Consumer distinction rule

A scan is a valid completed scan **iff**:
- `<scans_root>/<scan_id>/` exists,
- `scanner_data_manifest.json` exists,
- manifest parses as JSON,
- `manifest["status"] == "COMPLETE"`,
- every entry in `manifest["outputs"]` exists on disk with matching `sha256` and `size_bytes`.

Any other condition ⇒ incomplete artifact; must not be consumed as a finished scan.

### 4.3 Coordination with SCAN-018B

SCAN-018B (event schema / manifest contract) must adopt:
- the same `status` vocabulary (`RUNNING`, `COMPLETE`, `FAILED`, `INTERRUPTED`),
- `"scan_id"` as the manifest's scan-identity field,
- `"outputs"` verification list,
- the rule that the manifest is published last and only `COMPLETE` certifies completion.

This document makes no event-schema changes; `events.json` keeps its existing `{"events": [...], "header": {...}}` shape.

## Manifest verification hardening (SCAN-018A-R1)

`is_scan_complete(dest)` in `scanline/scan.py` was hardened without changing the
atomic publication architecture. A scan is a valid completed scan only if all of
the following hold; any failure returns `False`:

- **Manifest structure:** `scanner_data_manifest.json` exists, parses as JSON, is
  an object, and has `status == "COMPLETE"`. Malformed JSON returns `False`.
- **Scan identity:** the manifest carries a `scan_id` that (a) exists, (b) is a
  string matching the generated SCAN-018A identifier format
  (`YYYYMMDDTHHMMSSffffffZ_<32-hex>`), and (c) equals the name of the
  containing scan directory. Mismatches return `False`.
- **Outputs:** `outputs` must be a nonempty list. Empty or missing `outputs`
  return `False` — empty collections are never accepted vacuously. Every entry
  must be an object with a valid simple relative filename, a valid lowercase
  SHA-256 hex digest, and a valid non-negative integer `size_bytes` (booleans
  rejected). Duplicate output names return `False`. `events.json` must be
  declared.
- **Path validation:** output names must be simple relative filenames. Absolute
  POSIX paths, Windows drive/UNC paths, `..` traversal components, nested
  paths, and `.`/`..` names are rejected. Each declared output is resolved
  (symlinks followed) and must resolve inside the scan directory; a symlink
  escaping the scan directory returns `False` and the external file is never
  treated as a valid scan output. Symlinks to files inside the scan directory
  are permitted.
- **Output verification:** every listed output exists as a regular file inside
  the scan directory and matches its recorded `sha256` and `size_bytes`.
- **Read-only:** `is_scan_complete()` never creates, modifies, or deletes
  files.

---

## 5. Overwrite prevention (default policy: rejection)

### 5.1 Default behavior

If `dest = scans_root / scan_id` already exists (a previous complete or incomplete scan with the same ID), `run_scan` raises before writing anything: `FileExistsError`-style rejection, message naming `dest`. No truncation, no deletion, no merge.

### 5.2 Concurrency

Two concurrent scans that independently compute the same `scan_id` (32-bit suffix collision, negligible but possible) race on the existence check:
- Both check `dest.exists()` → both `False` → both `mkdir(dest)`.
- `mkdir` on an existing directory raises `FileExistsError`; the loser aborts cleanly having written nothing.
- To narrow the window, use `os.mkdir(dest)` (which raises if exists) rather than `mkdir(exist_ok=True)`, and perform the existence check immediately before it. The `mkdir` itself is the serialization point.

### 5.3 Incomplete previous scans

An existing `dest` without a COMPLETE manifest (orphaned from a crashed run) is still "existing" → rejected by default. A separate, explicit recovery command (out of scope for SCAN-018A implementation) may adopt or remove an orphaned destination; it is never done implicitly by `run_scan`.

### 5.4 Orphaned temporary directories/files

- Temp files: `dest / "<name>.tmp.<pid>"` are cleaned only by an explicit sweeper or overwritten on a future scan to the same (new) ID — never auto-deleted mid-scan.
- Orphaned staging directories (if Approach B were ever adopted): identified by `.stage.<pid>` suffix; removable by sweeper; never touched by `run_scan`.

### 5.5 Recovery of interrupted scans

No implicit resume. Re-running the same inputs produces a **new** `scan_id` (new random suffix) and a **new** destination; the old interrupted destination is preserved as evidence. This preserves all historical results and satisfies "do not overwrite existing historical results."

---

## 6. Reproducibility constraints

- `events.json` payloads are unchanged: no `scan_id`, no execution timestamp, no random data in event objects or `header`.
- Event ordering unchanged (detector iteration order preserved).
- `execution_start` (wall clock) remains only in the manifest, not in `events.json`.
- Repeated identical scans receive different `scan_id`s (random suffix) but **identical** `events.json` bytes — satisfies test #9 in §8 and keeps `tests/test_scan.py` passing.
- Ledger keying (deterministic, no run ID) is unaffected.

---

## 7. Crash recovery strategy

| Crash point | On-disk state | Consumer sees | Recovery action |
|---|---|---|---|
| Before `dest.mkdir()` | nothing | absent | Nothing to clean; re-run creates new ID. |
| After `mkdir`, before first rename | empty `dest/` | incomplete (no manifest) | Re-run with new ID; orphaned empty dir remains until sweeper/manual removal. |
| After `events.json` rename, before manifest | `events.json` only | incomplete (no COMPLETE manifest) | Preserved as evidence; not consumed. |
| During temp write (any file) | `*.tmp.<pid>` only | incomplete | Temp file is garbage; sweeper removes. |
| After manifest rename | complete scan | COMPLETE | Valid; consumed normally. |

Recovery is **manual or sweeper-driven**, never implicit in `run_scan`. `run_scan` never deletes an existing destination.

---

## 8. Concurrency considerations

- Different scan IDs → different destination directories → no conflict; parallel execution safe.
- Same scan ID collision → `os.mkdir(dest)` serializes; loser gets `FileExistsError` and aborts before writing.
- Two scans to the same parent `scans_root` → independent `mkdir` calls on distinct names; no shared lock needed.
- `os.replace` onto `dest/<name>`: destination names are unique per scan ID, so no cross-scan rename conflict exists within one destination.
- `fsync` of the parent directory after final rename best-efforts durability of the directory entry across crashes.

---

## 9. Failure testing proposal (isolated, temporary directories)

All tests use `tmp_path`; no historical records are touched.

1. **Successful scan publication:** run into fresh `tmp_path/scans`; assert `<scan_id>/` created, both files exist, manifest `status == "COMPLETE"`, manifest `scan_id` matches directory name, outputs verifiable via `manifest["outputs"]`.
2. **Failure during event serialization:** monkeypatch `json.dump`/inject unwritable event → assert exception, no manifest, no COMPLETE state, `dest` may exist but incomplete.
3. **Failure during manifest serialization:** events.json written, manifest dump fails → assert `events.json` present, no COMPLETE manifest.
4. **Failure during file replacement:** monkeypatch `os.replace` to raise → assert partial state, no COMPLETE manifest.
5. **Existing destination collision:** pre-create `dest/` (empty or with a COMPLETE manifest from a prior run) → run again → assert rejection, prior contents untouched.
6. **Interrupted publication:** simulate crash after `events.json` rename but before manifest → assert consumer rule classifies scan as incomplete.
7. **Orphaned staging/temp directory:** create `<scan_id>/events.json.tmp.<pid>` or a stale `.stage` dir → run new scan with different ID → assert new scan succeeds, orphans untouched (or swept only by explicit sweeper).
8. **Two concurrent scans, same destination:** force same `scan_id` (monkeypatch ID generator) in two threads/processes → assert exactly one succeeds, the other gets `FileExistsError`, no data loss or overwrite.
9. **Repeated identical scans:** run same inputs twice → assert different `scan_id`s, byte-identical `events.json`, both COMPLETE, coexist under distinct directories.

Non-destructive: all writes confined to `tmp_path`; `records/scans/` never modified.

---

## 10. Compatibility risks

- **Existing historical records** (`records/scans/<version>-window-.../`) lack `scan_id` and `status`. Consumers updated to require `status == "COMPLETE"` would treat them as incomplete unless a migration/backfill or consumer tolerance is added. Recommendation: consumers tolerate missing `status` for historical directories, or SCAN-018B defines a backfill. SCAN-018A does not modify historical records.
- **`run_scan` return value:** currently returns `None`. Proposal returns `scan_id` (or result object). Callers relying on `None` return are unaffected in behavior but should adopt the return for scan tracking. No existing caller in repo uses the return (grep showed none).
- **Output location:** scans no longer write directly into a caller-supplied `output_dir` if that dir is expected to be versioned-named; the new default is `<scans_root>/<scan_id>/`. Callers can still pass any `output_dir`; the scan-ID subdirectory logic applies inside it. This is a behavior change requiring caller awareness.
- **Manifest schema:** adding `scan_id`, `status`, `outputs` is additive; existing manifest readers that ignore unknown keys are unaffected.
- **Filesystem:** `os.fsync` on directories may raise on some platforms/fs (e.g. certain Linux fs, Windows); wrap in try/except and treat as non-fatal best-effort.

---

## 11. Exact files likely to change (if implemented)

- **`scanline/scan.py`** — `run_scan`: generate `scan_id`, build `<scans_root>/<scan_id>/`, temp+fsync+`os.replace` writes for `events.json` and manifest last with `status == "COMPLETE"`, `scan_id`, `outputs`; existence rejection via `os.mkdir`; return `scan_id`; add `secrets` import; helper for atomic file publish.
- **`scanline/scan.py`** — possibly a new `publish_outputs(dest, outputs)` helper shared by both file writes.
- **`tests/test_scan.py`** — may need update if return value or output path changes (reproducibility assertion `b1 == b2` still holds since events.json unchanged).
- **`docs/SCAN-018B-*`** — manifest contract alignment (to be coordinated).
- **`docs/SCAN-017E-DUPLICATE-POLICY.md`** / **`docs/SCAN-017-CONTRACT-DECISIONS.md`** — cross-reference only if a completion-policy section is added (optional).

No changes to `scanline/validator.py`, `levels.py`, `sessions.py`, schema, or `records/`.

---

## 12. Recommended implementation sequence

1. Approve this design (scan ID format, Approach A, COMPLETE-only manifest, rejection default).
2. Align with SCAN-018B on `status` vocabulary and `scan_id`/`outputs` manifest fields so the two milestones do not diverge.
3. Add tests in `tests/` for §9 cases 1–9 using `tmp_path` (fail before implementation, pass after).
4. Implement atomic publish helper + scan ID generation in `scanline/scan.py`.
5. Wire into `run_scan`: rejection check, staged writes, manifest last, return `scan_id`.
6. Run full suite: `pytest -q`; verify `tests/test_scan.py` byte-identity still passes.
7. Verify lint/typecheck per project tooling.
8. Document the completion protocol in `scanline/scan.py` docstring and cross-reference in `docs/SCAN-017-CONTRACT-DECISIONS.md`.
9. Request implementation approval before step 4 if not already granted.

---

## 13. Restrictions observed for this proposal

No source code, tests, configuration, or datasets modified. Nothing committed or pushed. This document is a proposal awaiting explicit implementation approval.

---

## Implementation status (as implemented)

**Files changed:**
- `scanline/scan.py` — `run_scan` now generates one scan ID per execution (`generate_scan_id()`), creates `<output_dir>/<scan_id>` with exclusive `os.mkdir` (no `exist_ok`), publishes `events.json` then `scanner_data_manifest.json` last via temp-file + flush + `os.fsync` + `os.replace` (Approach A), best-effort directory fsync, adds `scan_id`, `status: "COMPLETE"`, and `outputs` (name/sha256/size_bytes for `events.json`) to the manifest, and returns `scan_id`. `main()` prints a nonbreaking completion message identifying the new scan directory; `run_scan()` behavior is unchanged. `is_scan_complete(dest)` was hardened (SCAN-018A-R1): output names must be simple relative filenames (absolute, `..` traversal, Windows drive/UNC, nested, and escaping-symlink names are rejected); `scan_id` must exist, match the generated identifier format, and equal the containing scan directory name; `outputs` must be a nonempty list with valid filenames, SHA-256 digests, and non-negative integer sizes, no duplicates, `events.json` required, and every listed output must exist inside the scan directory and match its recorded hash and size. The function is read-only: it never creates, modifies, or deletes files. No changes to detection logic, validator rules, event schema, or configuration defaults.
- `tests/test_scan.py` — existing end-to-end test updated for scan-ID subdirectories plus 12 new isolated `tmp_path` regression tests under SCAN-018A, plus 16 new SCAN-018A-R1 hardening tests (absolute POSIX path, Windows absolute path, relative `../` traversal, symlink escaping the scan directory, symlink to an internal file, manifest scan ID mismatch, missing scan ID, invalid scan ID, empty outputs list, missing events.json entry, duplicate output entries, malformed SHA-256, invalid size fields, malformed JSON manifest, valid existing COMPLETE manifest, and a read-only verification test).
- `docs/SCAN-018A-PERSISTENCE-DESIGN.md` — this document; status moved from proposal to implemented, with a new SCAN-018A-R1 hardening section.

**Test results:** `pytest -q` → `216 passed, 1 skipped` (SCAN-018A baseline `196 passed, 1 skipped`; +20 new scan items, no regressions, skipped test unchanged).

**Compatibility implications:**
- `run_scan` return value changed from `None` to `scan_id` (str). No in-repo caller used the return.
- Outputs are now written into `<output_dir>/<scan_id>/` rather than directly into `<output_dir>/`; callers locate artifacts via the returned `scan_id`. `tests/test_scan.py` updated accordingly.
- Historical `records/scans/<version>-window-.../` directories are untouched and remain readable; they lack `scan_id`/`status` and consumers requiring `status == "COMPLETE"` treat them as incomplete (no historical records modified). `is_scan_complete()` returning `False` for a historical directory means it cannot be verified under the new completion protocol; it does not establish that the historical scan originally failed. No historical manifests are backfilled.
- `events.json` bytes are unchanged across repeated identical scans (no scan ID or execution timestamp in event contents).

**Failure handling:** no automatic deletion of incomplete destinations, no overwriting of historical results, no silent conversion of failed publication into success, and no automatic recovery or cleanup. Artifacts remaining after each failure are documented by the regression tests (orphaned temp files, partial event output without manifest, empty/incomplete destinations preserved as evidence).
