DELIVERY NOTE (Jarvis, 2026-11-18): filed in-repo by Jarvis; operator-approved. The code state it governs is 1caa8ee6b4f05407fc12e8b74d1dcb386ce6ae7a; this docs commit changes no code.

WORK ORDER SCAN-003-FIX — Scanline: rewrite fixture case (v) so it actually pins array-previous across the hole. (Tower, Kilo session — Beam. Repo ~/scanline, on top of main @ 1caa8ee6b4f05407fc12e8b74d1dcb386ce6ae7a. ONE test function changes; nothing else.)

WHY (graded from origin, Jarvis, 2026-11-18). SCAN-003 is accepted except case (v). As committed, (v) inserts an outside bar AFTER the hole (Jan 25, close 108) and fires on the second post-hole bar (Jan 26) — its "previous bar" is a post-hole bar, so the test passes without ever evaluating a crossing ACROSS the hole. And with every bar's true range equal to 1.0, the asserted distance is 0.5 under any window composition, so the ATR-spanning assertion discriminates nothing. The order specified: an entry on the FIRST bar after the hole fires because its previous bar is the last bar BEFORE the hole, and a distance only the hole-spanning window produces. Rewrite test_v_hole to that specification:

GEOMETRY (use the existing helpers and conventions — make_bar, d1_bar, evt — exactly as the current tests do):
- Level source: d1_bar() as now (d1_prior_high at 100.0).
- Pre-hole emission bars: 20 bars at close 108.0 with true range 4.0 each (high = close + 2, low = close − 2), on the current test's pre-hole dates.
- The hole: the current test's missing days.
- First bar after the hole: close 101.0, true range 1.0. At this bar the preceding 14 series bars are ALL pre-hole bars (the hole contributes no bars), so ATR = 4.0 exactly; distance = |101.0 − 100.0| / 4.0 = 0.25, inside the 0.5 band; the previous series bar is the last pre-hole bar at distance |108.0 − 100.0| / 4.0 = 2.0, outside. The crossing therefore fires ON THIS BAR, and the single expected event carries distance_atr exactly 0.25.
- One further bar after it at close 101.0 (dwelling inside): no second event.
- Assert res == [the one expected event], built with the evt helper under the fixture conventions, all ten fields exact.

WHY THIS DISCRIMINATES (the point of the rewrite): under any non-array semantics — a window that refuses to span the hole, or a crossing state that resets at the hole — the first post-hole bar is in warmup or has no previous bar, and NO event fires; under a window composed of only post-hole bars the distance would not be 0.25. The single asserted event at exactly 0.25 is producible only by the pinned semantics.

SCOPE AND RULES: tests/test_levels.py, test_v_hole only. No production code, no other test, no config, no fixture changes. Full suite green on a clean run — the count stays 43 (this is a rewrite, not an addition). Commit on main with message "SCAN-003-FIX: case (v) pins the cross-hole crossing", staging by explicit path only, and push. Report PUSH PROOF (both lines verbatim), the pytest -q tail VERBATIM, a results block (fix=case_v_only, tests_passed=43, tests_failed=0, pushed=yes, head=<sha>), and the free -h line quoted verbatim. No cleanup deletions.
