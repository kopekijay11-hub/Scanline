DELIVERY NOTE (Jarvis, 2026-11-18): filed in-repo by Jarvis; operator-approved. This docs commit changes no code.

WORK ORDER SCAN-005 — Scanline: the corpus survey and window selection for the first real scan. (Tower, Kilo session — Beam. Repo ~/scanline, on top of current main. This order SURVEYS real data and selects the scan window; it runs NO scan and produces NO events. The scan itself is SCAN-006, gated on this survey's grade and on the bridge spot-check below.)

FROZEN INSTRUMENT (of record): config/scanner_params.level_proximity.json, param_version 1.0.0, frozen_at 2026-11-19T03:25:04Z, sha256 e6da10333947c007ae55ad6764dbc89fa1c448bd61ffbc3cdd84b436837a754c. The coverage definition this survey applies is the one in docs/freezes/level_proximity-1.0.0.md — apply it exactly as written; do not paraphrase it into code that loosens it.

READ-ONLY BOUNDARIES (hard): ~/corpus-store is READ-ONLY — no writes, no renames, no "cleanup," ever. ~/hiai may be READ (corpus conventions may be documented there) but never written and its code never executed. The only writes in this job are new files inside ~/scanline as specified below. The corpus is ~1.4 GB: stream or chunk every read, never load a whole file tree into memory, one heavy process at a time.

STEP 0 — SUITE AND STATE. Run the existing suite on the pulled main and quote the pytest -q tail verbatim in the report (expected 45 passed). Record git rev-parse HEAD. Any failure here is a STOP.

STEP 1 — CORPUS IDENTITY AND LAYOUT. Survey ~/corpus-store and report: its directory layout (how bars are stored — per symbol? per timeframe? file format?), its size and file count as found, any version/build marker it carries (a commit, a manifest, a README — quote what exists; if none exists, say so, that is a finding), and the extraction method you will use (the exact reader or commands; they must be read-only). If the corpus does not contain all 15 series (5 symbols × D1, H1, H4), STOP and report which are missing — do not substitute another source.

STEP 2 — PER-SERIES FACTS. For each of the 15 series, determine and record:
- bar count, first timestamp, last timestamp;
- TIMESTAMP CONVENTION: are the stored timestamps bar OPEN times or CLOSE times? State the evidence you determined it from (corpus docs, file structure, cross-timeframe alignment) — not a guess. If it cannot be determined, STOP: this is the most dangerous silent misread in the data path;
- monotonicity (strictly increasing timestamps) and duplicate count;
- PRICE SCALE sanity: GOLD in the thousands, EURUSD near 1, USDCAD near 1.4, GER40 in the tens of thousands, USOIL in the tens. A series off by an order of magnitude is a STOP finding (units), reported, not fixed;
- D1 BOUNDARY: the UTC instant at which D1 bars close in this corpus, and whether that instant lands exactly on an H1 bar boundary (this decides whether the birth-coincidence case is a daily case or a rare one on real data — report which);
- DST transitions inside the candidate span (Step 3), and how the corpus represents them (missing/extra bars on transition days).

STEP 3 — THE COVERAGE MATRIX AND WINDOW SELECTION. Apply the freeze record's coverage definition mechanically over candidate 30-day windows: every window ending on each of the last 120 days of corpus coverage (or the full span if shorter). Produce the FULL matrix — per symbol per window: qualifies or not, and if not, which criterion failed (modal fraction, intra-day gap, suspected D1 hole). Select the window by the rule: the most recent 30-day window fully covered for all five symbols. Report the chosen window's start and end dates and its end date's distance from frozen_at (2026-11-19T03:25:04Z) — if the window ends well before the freeze, that is a recorded finding, not a blocker. If NO window qualifies, the job completes as "no scan window; report" — a legitimate outcome; do not relax any criterion.
Commit the survey as records/surveys/survey-2026-11-18.json (structured JSON: corpus identity, extraction method, the 15 series' facts, the full coverage matrix, the chosen window), and report the sha256 of that file's bytes in your report.

STEP 4 — SPOT-CHECK PREPARATION (the comparison itself is a laptop step, not yours). From the corpus, extract GOLD bars for days 1–7 of the chosen window on D1, H1, and H4, using the Step 1 extraction method, and commit them as records/surveys/spotcheck-gold-week.json (raw corpus values, timestamps as stored, plus a note of the Step 2 timestamp convention). The operator will pull the same week through the MT5 bridge on the laptop and the two will be compared under this PRE-STATED disposition ladder (fixed now, before any comparison runs):
- Any timestamp mismatch, timezone offset, or price-scale difference: STRUCTURAL — STOP, the scan does not proceed;
- Corpus missing bars the bridge has inside that week: COVERAGE — STOP, and the coverage survey is re-run;
- Close prices differing by at most 0.05% on fewer than 3 bars, timestamps exact: DOCUMENT-AND-PROCEED (the differences are recorded in the manifest);
- Anything else: STOP and report — do not adjudicate in the moment.

STEP 5 — COMMIT AND PUSH. Commit the two records files on main with message "SCAN-005: corpus survey and window selection for the first real scan", staging by explicit path only, and push. Report: PUSH PROOF (git rev-parse HEAD and the git ls-remote origin main line, both verbatim), the Step 0 pytest tail verbatim, the survey file's sha256, the chosen window (or window=none), a short findings summary (timestamp convention + evidence, D1 boundary alignment, corpus identity, any STOP findings), a results block (survey=done, series_surveyed=<n>/15, window_start=<date or none>, window_end=<date or none>, spotcheck=prepared_pending_laptop, pushed=yes, head=<sha>), and the free -h line quoted verbatim.

RULES (standing, restated): no code changes anywhere (a needed code change is a STOP); no changes to the frozen param file or the freeze record; no cleanup deletions. If any STOP fires, commit and push whatever survey records exist so the finding is graded from origin, and report the STOP as the outcome.
