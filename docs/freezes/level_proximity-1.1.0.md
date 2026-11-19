# Freeze record: level_proximity 1.1.0

## What changed

- Grid steps (big-figure-only): GOLD 100, EURUSD 0.0100, USDCAD 0.0100, GER40 500, USOIL 5.00 (was GOLD 25, EURUSD 0.0050, USDCAD 0.0050, GER40 100, USOIL 1.00).
- Band representation: `proximity_bands_atr` is now a per-kind slot `{structural: 0.5, grid: 0.5}`. Values are unchanged (0.5 for both level kinds).
- Validator contract v2: `scan_mode` header field; R1 grid-membership rule for `grid_round`; modal R4 by scan_mode.

## What did not change

- Band values (0.5 ATR for both structural and grid).
- Structural construction (D1 prior high/low/session structure).
- ATR (window 14, closed bars only).
- Trigger (close_distance_band_entry, inclusive edge, gap-through fires if landing inside).
- Gap semantics (array_previous).
- Route B convention (Mon-Thu D1; Friday/Sunday handling).
- Universe, timeframes, definitional tokens.

## Calibration-consumed window

The 2026-09-22 to 2026-10-21 window is declared CALIBRATION-CONSUMED. Its 1.0.0 results are descriptive, never confirmatory.

## Held-out window

2026-08-08 to 2026-09-06 (selected mechanically per clause v2; most recent qualifying window entirely before the calibration window).

## Retrospective limit

For a historical window, untuned-ness is credible (canonical steps, hash freeze, git commit order) but not provable.

## Pre-registration (held-out window)

30 days, five symbols. Margin formula x/÷1.5 fixed in advance, derived from 1.0.0 calibration actuals (structural 382/159, grid 549/291) with grid mechanism ratio 0.2 for step widening.

- structural H1: [255, 573]
- structural H4: [106, 239]
- grid H1: [73, 165]
- grid H4: [39, 87]
- totals are the class sums.

Dispersion rule: no symbol above 40% of its class-and-timeframe total.

Non-count invariant: structural Tue-Thu count exceeds Fri+Mon.

A breach is reported as a breach, never tuned away inside this order.

## Falsification rule

If 1.1.0 is falsified on the held-out window, 1.2.0 requires a fresh window. Every version stays in the freeze log.
