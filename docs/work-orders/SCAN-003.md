DELIVERY NOTE (Jarvis, 2026-11-18): this file was placed in the repo by Jarvis so it can be read in place — no clipboard step. It is the operator-approved SCAN-003. The code state it governs is commit 7c299a1480b707a28f7dca256aa31ad5398ad5be; the commit adding this file sits on top of it and changes no code.

WORK ORDER SCAN-003 — Scanline: the pre-freeze pins (param completeness with refusals, birth-coincidence and hole fixtures, alias cleanup). (Tower, Kilo session — Beam. Repo ~/scanline, on top of main @ 7c299a1480b707a28f7dca256aa31ad5398ad5be. Stack: Python 3, stdlib only, pytest. Synthetic data only; hermetic. Source of the pins: the DeepSeek consult on the consolidated Scanline update, graded STRONG and folded 2026-11-18, plus the operator's gap-semantics decision of the same evening.)

DECISIONS OF RECORD (operator, 2026-11-18).
- Gap semantics: ARRAY-PREVIOUS. "Previous bar" means the previous bar in the series; the ATR window is the previous atr_window bars in the series, holes and all. The predicate owns no session calendar and applies no wall-clock tolerance. Gap governance lives at the data layer (the scan's data manifest), not in the predicate.
- The param file is the definitional record: every choice that determines whether an event exists must be recoverable from event + params. SCAN-002 established this for atr_excludes_emission_bar; this order completes the token set and makes every token load-bearing via refusal.

STEP 1 — PARAM COMPLETENESS TOKENS, ENFORCED. The predicate (scanline/levels.py) must REFUSE (raise) a param file whose definitional tokens do not match the implemented semantics, exactly as it already refuses a multi-value band list and a missing/false atr_excludes_emission_bar. The full token set and required values:
- crossing_semantics == "close_distance_band_entry"
- band_edge == "inclusive"
- gap_through == "fires_if_landing_inside"
- state_key == "level_type+level_price+defined_at"
- gap_semantics == "array_previous"
- atr_excludes_emission_bar == true (already enforced; keep)
A token that is missing or holds any other value is a refusal. Update the test param fixture (tests/fixtures/predicate_params.json) to carry all tokens at their required values. Add ONE refusal test per token (six tests; a failure must name the token), each mutating exactly one token away from its required value on an otherwise-valid param file and asserting the predicate raises.

STEP 2 — PRODUCTION PARAM DRAFT COMPLETED (NOT FROZEN). Add the same six tokens, at their required values, to config/scanner_params.level_proximity.json. NOTHING else in that file changes: frozen_at stays null, proximity_bands_atr stays null, grid_steps stays null, version stays "0.1.0-draft". This is definitional completion of the draft, not the freeze — the freeze is SCAN-004, a separate act.

STEP 3 — TWO NEW FIXTURE CASES (synthetic, exact-arithmetic construction per SCAN-002's constraint; expected event lists asserted exactly and completely, all ten fields).
- Case (u) birth-coincidence: D1 bars on a UTC-midnight boundary with H1 emission bars aligned to it, so a structural level's defined_at EQUALS an emission bar's close time exactly. Assert: the level is active at that bar, NO event fires at that bar, and a band entry on the following bar fires normally. (This is a daily case under UTC-midnight D1, not an exotic one.)
- Case (v) hole: an emission series with a multi-day hole (several missing days mid-series). Assert the pinned array-previous behavior exactly: a crossing whose "previous bar" is the last bar before the hole is evaluated against that bar (an entry on the first bar after the hole fires if that pre-hole bar was outside the band), and distance_atr on bars after the hole is computed from the atr_window series bars spanning the hole. Both assertions with exact distances.

STEP 4 — ALIAS CLEANUP. Remove the alias block at the end of scanline/levels.py (the nine alternative names for compute_events added in SCAN-002). compute_events is the one name; the module exposes one implementation per job. No other code changes in this step.

STEP 5 — COMMIT AND PUSH. Full suite green on a clean run (expected 42 tests: the 35 of record, plus six token-refusal tests, plus cases (u) and (v) — if the count differs, the report names why). Commit on main with message "SCAN-003: pre-freeze pins — param completeness, birth-coincidence and hole fixtures", staging by explicit path only, and push. Report PUSH PROOF (git rev-parse HEAD and the git ls-remote origin main line, both verbatim), the pytest -q tail VERBATIM — the full tail, not only a count (this is restated because SCAN-002's report omitted it; a claimed count the reader cannot falsify from the report is the SCAN-001 reporting defect), a short summary, a machine-readable results block — tokens_enforced=6, cases_added=2, tests_passed=<n>, tests_failed=0, production_frozen=no, pushed=yes, head=<sha> — and the ACTUAL free -h output line, quoted verbatim.

RULES (standing, restated): synthetic data only; no schema changes; no changes to validator.py or schema.py; the production param file changes ONLY as Step 2 specifies (a value change in it is a STOP); no cleanup deletions beyond the alias block named in Step 4. Resource envelope: tower 16 GB, this job is light, one heavy process at a time.
