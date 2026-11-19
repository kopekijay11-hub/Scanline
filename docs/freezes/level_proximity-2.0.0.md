# Freeze record: level_proximity 2.0.0

## What changed

- Universe widened from 5 to 33 symbols. CADMXN and FEEDBEEF are excluded by name — no D1 series exists for them.
- Grid steps for the 28 added symbols, exactly as surveyed (AUDCAD 0.01, AUDUSD 0.01, CADCHF 0.01, CADJPY 1.0, CADNOK 0.01, COPPER 1.0, CORN 5.0, EURUSD 0.01, GASOLINE 0.05, GBPCAD 0.01, GBPUSD 0.01, GER40 500, GOLD 100, HEATOIL 0.05, JPN225 500, LSGOIL 5.0, NDAQ100 100, NZDCAD 0.01, PALLADIUM 10.0, PLATINUM 10.0, SILVER 1.0, SOYBEAN 5.0, SPX500 100, UK100 100, UKOIL 5.0, US2000 100, US30 100, USDCAD 0.01, USDCHF 0.01, USDJPY 1.0, USNATGAS 0.05, USOIL 5.0, WHEAT 5.0).
- Contract v3: batch header gains `evidence_tier` ∈ {"forward_asof", "retrospective_membership"}, derived by the driver from `scan_mode` and recorded in the manifest.

## What did not change

- Band values (0.5 ATR for both structural and grid).
- ATR (window 14, closed bars only).
- Trigger (close_distance_band_entry, inclusive edge, gap-through fires if landing inside).
- Gap semantics (array_previous).
- Structural construction (D1 prior high/low/session structure).
- Route B convention (Mon-Thu D1; Friday/Sunday handling).

## Per-family D1 conventions

- Mon-Thu D1 for most symbols; the FX names carry the same two late-October Friday bars.
- Complete Mon-Fri D1 for CORN, SOYBEAN, WHEAT, LSGOIL — their structural events are convention-free (no weekday prediction registered for them).

## Capacity warning

At width 33 the corpus holds exactly 3 disjoint qualifying 30-day windows, all inside 2026-05-26 → 2026-07-27 — one regime slice. This freeze's confirmatory run spends one of the three.

## Run window (chosen mechanically)

Earliest disjoint qualifying 30-day window at width 33 per the SCAN-008 capacity computation: 2026-05-26 → 2026-06-24.

## Pre-registration (run window)

Derived from the 1.1.0 five-symbol held-out actuals (structural H1 321, H4 122; grid H1 120, H4 53) scaled per-symbol × 33, margin ×/÷2, widened from the usual 1.5 because the rate transfer is cross-symbol and symbol heterogeneity is unmeasured.

- structural H1: [1060, 4238]
- structural H4: [403, 1610]
- grid H1: [396, 1584]
- grid H4: [175, 700]
- totals are the class sums.

Dispersion tripwire: no symbol above 20% of its class-and-timeframe total.

Weekday invariants, per family: for the Mon-Thu-D1 symbols, structural Tue-Thu exceeds Fri+Mon. For the Mon-Fri-D1 symbols (CORN, SOYBEAN, WHEAT, LSGOIL), NO weekday prediction is registered.

A breach is reported as a breach, never tuned away inside this order.

## Retrospective limit

For a historical window, untuned-ness is credible (canonical steps, hash freeze, git commit order) but not provable.

## Falsification rule

A falsified 2.0.0 requires a fresh window for 2.1.0, of which at most two would remain at this width.
