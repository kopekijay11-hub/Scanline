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
