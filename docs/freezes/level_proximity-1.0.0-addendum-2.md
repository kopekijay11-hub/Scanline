# Freeze record addendum 2: level_proximity 1.0.0

## Decision of record (operator, 2026-11-18)

Route B — the corpus's Mon–Thu D1 is accepted as a documented convention for this research feed. The level definition ("most recent completed D1 bar") is unchanged; the convention and its full semantic consequences are stated here, never quietly absorbed. The upstream finding stands filed at `docs/upstream/corpus-d1-friday-finding-2026-11-18.md`.

## Convention

Corpus D1 exists Mon–Thu. FIX2's per-symbol D1 weekday histograms over the full span:

- GOLD: Mon 109, Tue 118, Wed 116, Thu 110, Fri 0, Sat 0, Sun 0
- GER40: Mon 106, Tue 116, Wed 115, Thu 105, Fri 0, Sat 0, Sun 0
- USOIL: Mon 109, Tue 118, Wed 116, Thu 110, Fri 0, Sat 0, Sun 0
- EURUSD: Mon 1067, Tue 1070, Wed 1064, Thu 1066, Fri 2, Sat 0, Sun 0
- USDCAD: Mon 837, Tue 839, Wed 832, Thu 834, Fri 2, Sat 0, Sun 0

Friday ranges never become levels. Thursday's D1 levels govern Friday and Monday. Monday's D1 becomes Tuesday's levels.

## Late-corpus note

EURUSD and USDCAD D1 do contain Friday bars for 2026-10-23 and 2026-10-30 (after the scan window; the other three symbols' D1 end 2026-10-21). The convention is stated for the corpus as surveyed for this scan; any future window reaching those dates re-examines the convention's application there rather than assuming it.

## Isolated holes

In the 120 days preceding the window, isolated Mon–Thu H1-days without a D1 bar occur at holiday frequency (no weekday more than 2 in ~17 weeks, none inside the chosen window). Clause v2's substance test below governs such days in window selection.

## Containment record

3 of the 20 window Fridays are range-contained in an adjacent D1 bar. Folding verdicts (Step 0b, exact arithmetic): all three are DROPPED, not folded — the previous D1 bar's OHLC equals that Thursday's own H1 aggregate exactly, while the combined Thu+Fri H1 aggregate differs:

- USOIL 2026-09-25 (previous D1 2026-09-24): dropped
- USOIL 2026-10-09 (previous D1 2026-10-08): dropped
- EURUSD 2026-10-02 (previous D1 2026-10-01): dropped

No day matched neither exactly; no third production behavior is modeled by this order.

## Session structure under the convention

The prior close is Thursday's close for both Friday and Monday. Friday's close never becomes a `d1_session_structure` level. The class still fires mainly on gap days — now specifically Friday-open vs Thursday-close and Monday-open vs Thursday-close.

## ATR interaction

Thursday's level is evaluated with Friday's ATR on Friday and with Monday's (weekend-gap-inflated) ATR on Monday, so its effective band differs across the two days. Known and intended under array-previous semantics.

## Weekend-persisting identity

Thursday's level identity (`level_type`, `level_price`, `defined_at`) persists across Friday and Monday. Price in-band at Friday's close and at Monday's open is a DWELL, not a crossing — no re-fire. The rollover re-fire property proven in SCAN-002 case (n) has this weekly exception (Fri→Mon, no D1 close intervenes). Property, not defect.

## grid_round

`grid_round` is unaffected by the convention (grid levels are param-defined, not D1-derived). Grid events remain comparable to a future fixed-corpus scan even though structural events will not be directly comparable.

## Density

The frozen combined ranges stand (H1 35–180, H4 20–80, grid_round H1 0–10, per-symbol as frozen). Add the per-weekday profile expectation: structural events concentrate Tue–Thu, with Friday+Monday's combined share markedly below Tue–Thu's, because Fri and Mon share Thursday's identity. A Friday-heavy distribution in the scan is a finding, not a surprise to be absorbed.

## Cross-reference

Upstream finding: `docs/upstream/corpus-d1-friday-finding-2026-11-18.md`. If the corpus D1 is repaired, this convention ends by a new addendum and a planned re-scan — the first scan is never silently invalidated.

## The clause, v2

Replacing addendum 1's literal any-day clause for all future window selections:

A day is SUBSTANTIAL for a symbol if its H1 bar count is at least 50% of that symbol's modal H1 count for that weekday within the window. Every substantial Mon–Thu day must have a D1 bar for that symbol or the window is disqualified. Substantial Fridays are D1-less BY THIS CONVENTION and are listed as convention days in the survey output. Non-substantial days (Sunday stubs, holiday closures) require no D1 bar and are listed per window in the survey output. The original clauses (modal fraction on trading days, intra-day gap limits, bars-not-hours DST neutrality, window-end reach via the substantial Mon–Thu requirement) remain in force.

Unchanged: the param file (`config/scanner_params.level_proximity.json`) and every frozen value in `docs/freezes/level_proximity-1.0.0.md` are unchanged. This addendum is a new freeze-record entry, not an edit to the original record.
