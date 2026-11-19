# Upstream finding — the corpus D1 series drops Friday sessions

**From:** the Scanline lane (bystander; this report assigns no work)
**To:** the owning lane (the trading system; ~/corpus-store is its data of record)
**Date:** 2026-11-18 · **Status:** reported, not adjudicated — intended convention or bug is the owning lane's call

## The measurement

- GOLD D1 holds 453 bars over a span of ~590 weekdays (≈77%); EURUSD's long D1 series shows the same ~4/5 ratio.
- In the week 2026-09-22 → 2026-09-28 (GOLD), the D1 bars that exist match their H1 days' aggregates EXACTLY — open, high, low, close, all four fields, for Tue/Wed/Thu/Mon.
- Friday 2026-09-25's full session (21 H1 bars, high 4315.71, close 4284.70 — the week's high is in it) appears in NO D1 bar. Thursday's D1 bar is Thursday only; Monday's is Monday only. Sunday evening's 2-bar stub is likewise absent (expected under most conventions).
- The same shape appears in GER40 and USOIL (D1 spans ending 2026-10-21 against H1/H4 running to 2026-10-31 — a separate truncation the Scanline survey also caught).

## The diagnostic

The H1 series contains Friday in full; the D1 artifact does not. The loss is therefore in the production of the D1 file — a derived-from-H1 aggregation with a weekday/session defect, or a pull filtered by one — not in the source feed. The actionable form: **re-derive, don't re-pull.** Where exactly the step sits is the owning lane's to find; the arithmetic above is the reproduction.

## The downstream implication

Any consumer of "the most recent completed D1 bar" on this corpus runs on Thursday's levels for all of Friday and all of Monday, every week, and Friday's range is never a level source. If any trading-system component reads D1 from this corpus, it inherits that behavior. Scanline reports this; it does not adjudicate whether it is intended.

## What Scanline is doing about it in its own lane

Holding its first scan until the pattern is fully measured (weekday histograms, all five symbols, full span), then deciding — with the operator — between accepting Mon–Thu D1 as a documented convention for its research feed, or sourcing D1 differently. The frozen parameters are unaffected under every route. If the corpus D1 is ever repaired, Scanline's convention and first scan are versioned records, not silently invalidated.

## Supplement — 2026-11-19 (SCAN-005-FIX2, full-span measurement)

The pattern is now measured over the full spans of all five Scanline symbols (records/surveys/d1-pattern-2026-11-18.json in this repo, sha256 afc9d7d1f4a7e9182c8b7f82366f9b16f0486c56566871e624121870225d15ed):

- **D1 weekday histograms.** GOLD Mon 109 / Tue 118 / Wed 116 / Thu 110 / Fri 0 (span 2024-07-02 → 2026-10-21); GER40 and USOIL the same shape (Fri 0). EURUSD Mon 1067 / Tue 1070 / Wed 1064 / Thu 1066 / Fri **2**; USDCAD the same shape (Fri **2**). The only two Friday D1 bars in either long series are **2026-10-23 and 2026-10-30** — the last two Fridays of those files, after the other three symbols' D1 end (2026-10-21). Whatever produces these files behaved differently in that final week, at least for the two long-history FX series.
- **In-window uniformity.** In 2026-09-22 → 2026-10-21, every symbol is missing exactly the same days: 4 full Fridays (21 H1 bars each; 20 for GER40) and 4 Sunday stubs — and no Mon–Thu day at all.
- **Isolated Mon–Thu holes exist at holiday frequency.** Over the 120 days before the window, each symbol shows a few H1-days with no D1 bar on Mon–Thu (no weekday more than 2 in ~17 weeks) — a second, much rarer absence class alongside the systematic Friday one.
- **Containment.** 3 of the 20 in-window Fridays are range-contained in an adjacent D1 bar (USOIL 2026-09-25 and 2026-10-09, in both neighbors; EURUSD 2026-10-02, in the previous bar). Range containment alone cannot distinguish a dropped Friday from one folded into Thursday's bar; a decisive combined-aggregate test for those three days is ordered in Scanline's lane (SCAN-005-FIX3 Step 0b) and its verdicts will be added here when graded. The original spot-check already proves GOLD does not fold (its Thursday bar is exactly Thursday).

Scanline's disposition (operator, Route B): the Mon–Thu pattern is accepted as a documented convention for its research feed under freeze-record addendum 2, with the weekly-cycle semantics stated there. This supplement changes nothing about the finding itself: the D1 production loses Fridays, and adjudication remains the owning lane's.


**Folding verdicts (SCAN-005-FIX3 Step 0b, graded 2026-11-19):** all three range-contained Fridays are DROPPED, not folded — for USOIL 2026-09-25, USOIL 2026-10-09, and EURUSD 2026-10-02, the previous D1 bar's OHLC equals that Thursday's own H1 aggregate exactly, and the combined Thu+Fri aggregate differs. Combined with the original spot-check (GOLD does not fold), the production behavior on every tested day is a clean drop: Friday sessions are simply absent from the D1 files, never merged into a neighbor.
