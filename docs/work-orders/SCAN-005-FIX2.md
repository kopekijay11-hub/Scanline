DELIVERY NOTE (Jarvis, 2026-11-18): filed in-repo by Jarvis; operator-approved measurement order. This docs commit changes no code.

WORK ORDER SCAN-005-FIX2 — Scanline: measure the corpus D1 weekday pattern before any window decision. (Tower, Kilo session — Beam. Repo ~/scanline, on top of main @ 0878e53932878c80b244330f280391b3e2b83756. MEASUREMENT ONLY: no window re-selection, no definition changes, no scan. The window question is HELD for an operator decision this measurement informs.)

THE FINDING THAT ORDERS THIS JOB (from the committed spot-check file, verified arithmetically by Jarvis). In the spot-check week (2026-09-22 → 2026-09-28), GOLD's D1 bars for Tue/Wed/Thu/Mon match their H1 days' aggregates EXACTLY (open, high, low, close) — the D1 series is a faithful daily aggregation where it exists. But Friday 2026-09-25's full session (21 H1 bars, high 4315.71, close 4284.70) appears in NO D1 bar, and neither do Sunday evening's 2 H1 bars. The corpus D1 series looks like a Mon–Thu series: GOLD D1 holds 453 bars over a span with ~590 weekdays (≈77%), and the chosen window (2026-09-22 → 2026-10-21) contains Fridays the rev2 matrix qualified anyway — addendum 1's clause was applied at the series-truncation boundary but not to interior days. Whether the pattern is exactly-Fridays, all symbols, all history, is what this job measures.

MEASURE, PER SYMBOL (all five), FROM THE CORPUS (read-only, as always):
1. The weekday histogram of the D1 series over its full span: bar count per weekday (Mon–Sun), plus the span's expected weekday counts for comparison.
2. For the currently chosen window (2026-09-22 → 2026-10-21): the exact list of days with H1 bars but no D1 bar, each with its H1 bar count (so a 2-bar Sunday stub and a 21-bar Friday session are distinguishable at a glance).
3. The same list over the most recent 120 days of each symbol's H1 span, summarized as counts by weekday.
4. Containment check, window-wide: for each listed Friday (or other full-session day) missing from D1, verify whether its H1 range is contained in any adjacent D1 bar (the spot-check week says no for 2026-09-25; confirm the pattern holds or name the exceptions).

DELIVERABLE: commit records/surveys/d1-pattern-2026-11-18.json carrying all four measurements per symbol, with message "SCAN-005-FIX2: corpus D1 weekday pattern measurement", staging by explicit path only, and push. Report PUSH PROOF (both lines verbatim), the pattern in one paragraph per symbol (e.g. "GOLD D1: Mon 92, Tue 93, Wed 92, Thu 91, Fri 0, Sat 0, Sun 0 — Fridays absent across the full span"), the deliverable's sha256, a results block (measurement=done, window=held, pushed=yes, head=<sha>), and the free -h line quoted verbatim.

RULES: ~/corpus-store and ~/hiai read-only; no code changes; no edits to any freeze record, survey, or param file; no cleanup deletions. If the pattern differs by symbol or era, report it exactly as measured — do not smooth it into a single story.
