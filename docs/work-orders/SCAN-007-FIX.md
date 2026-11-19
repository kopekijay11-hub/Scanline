DELIVERY NOTE (Jarvis, 2026-11-19): filed in-repo by Jarvis after grading SCAN-007 (PASS with a test-coverage gap). This docs commit changes no code.

WORK ORDER SCAN-007-FIX — Scanline: pin the three contract-v2 clauses the suite doesn't cover yet. (Tower, Kilo session — Beam. Repo ~/scanline, on top of current main. Tests ONLY — no production code changes; if a new test exposes a real validator defect, STOP and report it instead of fixing it here.)

CONTEXT. SCAN-007 graded PASS on behavior (Jarvis probed the committed validator directly: the held-out batch validates; an off-grid price fails R1; forward mode with a post-window freeze fails R4; a D1 lookahead fails R1; a missing scan_mode fails R5). But Step 1(d) of SCAN-007 required a test per clause, and three clauses have no pin in the suite: the existing poisons cover the D1 R1 clause and the forward R4 clause only. This order adds exactly the three missing pins to tests/test_validator.py (fixtures inline or as files, following that file's existing patterns; hermetic, corpus-absent-safe):

1. GRID-MEMBERSHIP FAIL: an otherwise-valid batch (scan_mode retrospective) containing one grid_round event whose level_price is NOT an integer multiple of its symbol's frozen step → the batch is invalid, R1 fails, and the flagged event is that one.
2. RETROSPECTIVE PASS: a batch whose header frozen_at postdates every event_ts, scan_mode retrospective, grid prices exactly on-grid, D1-defined events with defined_at ≤ event_ts → the batch is VALID. (This is the clause the whole contract repair rests on; pin it synthetically, not only via the real scan.)
3. SCAN_MODE REQUIRED: an otherwise-valid batch whose header omits scan_mode → invalid, R5 fails.

COMMIT AND REPORT. Run the full suite from the committed tree (expected 50 passed) and quote the pytest -q tail VERBATIM. One commit on main, message "SCAN-007-FIX: pin contract v2 clauses (grid membership, retrospective pass, scan_mode required)", staging the test changes by explicit path only, and push. Report PUSH PROOF (both lines verbatim), a results block (tests_added=3, tests_passed=50, tests_failed=0, production_code_changed=no, pushed=yes, head=<sha>), and the free -h line quoted verbatim.

RULES: no production code, param file, or freeze document is edited; no cleanup deletions; ~/corpus-store and ~/hiai read-only.
