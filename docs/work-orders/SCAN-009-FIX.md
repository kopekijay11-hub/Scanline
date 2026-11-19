DELIVERY NOTE (Jarvis, 2026-11-19): filed in-repo by Jarvis after grading SCAN-009 (PASS on behavior; test-pin gap, third occurrence). This docs commit changes no code.

WORK ORDER SCAN-009-FIX — Scanline: add the contract-v3 test pins as NEW tests. (Tower, Kilo session — Beam. Repo ~/scanline, on top of current main. Tests ONLY — no production code changes; if a new test exposes a real validator defect, STOP and report it instead of fixing it here.)

CONTEXT. SCAN-009 graded PASS on behavior (Jarvis probed the committed validator directly: the 2.0.0 batch validates; a tier/mode mismatch fails R4; a missing evidence_tier fails R5). But Step 1(d) required four tests, and the suite count stayed at 50 — the v3 clauses were folded into migrated fixtures and edited test bodies instead of being added. This is the third time this exact gap has occurred (SCAN-007, SCAN-009); the remedy is the same as SCAN-007-FIX, with the count made explicit so the gap cannot hide in a migration again: the tests below are NEW test functions, and the suite total must RISE.

ADD, in tests/test_validator.py (following that file's existing patterns; hermetic, corpus-absent-safe):
1. test_evidence_tier_required_R5 — an otherwise-valid batch (scan_mode retrospective, tier consistent) whose header omits evidence_tier → invalid, R5 fails.
2. test_evidence_tier_mode_mismatch_R4 — a batch with scan_mode=retrospective and evidence_tier=forward_asof (and, in the same test or a second one, the forward/retrospective_membership pairing) → invalid, R4 fails.
3. test_widened_grid_membership — under the REAL 2.0.0 param file (config/scanner_params.level_proximity-2.0.0.json, read as bytes), a retrospective batch carrying grid_round events at on-grid prices for at least one widened FX symbol, one widened index, and one agricultural symbol validates; and the same batch with one agricultural grid price knocked off-grid fails R1.

COMMIT AND REPORT. Run the full suite from the committed tree and quote the pytest -q tail VERBATIM — expected 53 passed (50 + 3 new); if the count is anything else, report what it is and why. One commit on main, message "SCAN-009-FIX: pin contract v3 clauses (evidence tier required, tier-mode binding, widened grid membership)", staging the test changes by explicit path only, and push. Report PUSH PROOF (both lines verbatim), a results block (tests_added=3, tests_passed=<n>, tests_failed=0, production_code_changed=no, pushed=yes, head=<sha>), and the free -h line quoted verbatim.

RULES: no production code, param file, freeze document, or ledger line is edited; no cleanup deletions; ~/corpus-store and ~/hiai read-only.
