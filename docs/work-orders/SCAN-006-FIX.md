DELIVERY NOTE (Jarvis, 2026-11-19): filed in-repo by Jarvis after grading the SCAN-006 STOP. This docs commit changes no code.

WORK ORDER SCAN-006-FIX — Scanline: commit the scan machinery only (the 1.0.0 batch failed validation and is NOT committed). (Tower, Kilo session — Beam. Repo ~/scanline, on top of current main. This order commits exactly two paths and nothing else.)

CONTEXT. SCAN-006 stopped correctly at gate 2: the batch fails the validator (R1 ×840 — every grid_round event, whose defined_at is the Nov 19 freeze, postdates the September–October window; R4 ×1 — frozen_at not strictly before the first event_ts). The machinery, however, is proven: the driver ran, replay was byte-identical across two runs (a664493c…), and the suite passes 47/47. The batch itself is deliberately not committed: it is invalid under 1.0.0, and determinism makes it regenerable at will — it never needs archiving. The contract and density questions go to a definition review; nothing in this order prejudges them.

STEP 1 — COMMIT THE MACHINERY. Stage by explicit path only: scanline/scan.py and its hermetic driver test (the test file added by SCAN-006). Commit on main with message "SCAN-006-FIX: scan driver and hermetic test (machinery only; 1.0.0 batch failed validation, not committed)" and push. The scan outputs in the working tree (records/scans/…) are left exactly as they are — uncommitted, undeleted; list them in the report so their state is on record.

STEP 2 — VERIFY. After the commit, run the full suite once more from the committed tree and quote the pytest -q tail VERBATIM (expected 47 passed). Report PUSH PROOF (both lines verbatim), the untracked-outputs list, a results block (driver_committed=yes, batch_committed=no, tests_passed=47, tests_failed=0, pushed=yes, head=<sha>), and the free -h line quoted verbatim.

RULES: no other file is staged, edited, or deleted; the frozen params and freeze documents are untouched; ~/corpus-store and ~/hiai read-only.
