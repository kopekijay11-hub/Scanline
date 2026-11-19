# Freeze record: level_proximity 1.0.0

## Frozen values

- param_version: `1.0.0`
- frozen_at: `2026-11-19T03:25:04Z`
- proximity_bands_atr: `[0.5]`
- grid_steps:
  - GOLD: `25`
  - EURUSD: `0.0050`
  - USDCAD: `0.0050`
  - GER40: `100`
  - USOIL: `1.00`
- atr_window: `14`
- atr_basis: `closed_bars_only`
- universe: `GOLD`, `EURUSD`, `USDCAD`, `GER40`, `USOIL`
- emission_timeframes: `H1`, `H4`
- definition_timeframe: `D1`
- level_types: `d1_prior_high`, `d1_prior_low`, `d1_session_structure`, `grid_round`

## Param file hash

Consumers bind to the raw bytes of `config/scanner_params.level_proximity.json`:

- sha256: `e6da10333947c007ae55ad6764dbc89fa1c448bd61ffbc3cdd84b436837a754c`

## Band provenance

`0.5` ATR is the value the synthetic proof was built on. No claim of optimality is made. The density prediction below is its falsifier.

## Grid steps

Grid steps are price-level-independent and are expressed in quote-currency price units matching the bar prices. The price scale is asserted per series at the data layer in the scan.

## Recorded expectations

- Grid_round events will be sparse on H1 by construction, because the grid step is a multiple of the band width in price terms. Sparsity is a property, not a defect.
- d1_session_structure events fire mainly on gap days, because the prior close sits inside the prior range most days. This is a rare class by construction.

## Recorded ATR-gap behavior

Under array-previous semantics, a Monday bar's true range includes the weekend gap, so ATR runs high early each week. On H1 the effect washes out within the day (14 bars ≈ 14 hours); on H4 it persists roughly 2–3 days (14 bars ≈ 56 hours), widening bands and suppressing crossings early in the week. Known and intended under the pinned semantics; not a defect.

## Coverage definition

A symbol's trading day is a day with a D1 bar for that symbol in the corpus. A window of 30 consecutive calendar days is FULLY COVERED for a symbol iff on every trading day in it, the H1 bar count is at least 90% of that symbol's modal H1 count per trading day within the window, the H4 count likewise, and no intra-day run of missing H1 bars exceeds 2 (H4: 1). Coverage counts bars per trading day, never hours, so DST days are neither penalized nor credited for their length. A day on which at least 4 of the other symbols trade but this symbol has no D1 bar is flagged as a suspected D1 hole and disqualifies the window (it is not silently a holiday). The scan window is the most recent 30-day window fully covered for all five symbols, applied mechanically with no manual exceptions; if no window qualifies, the outcome is "no scan; report". Relaxing this definition is a new freeze-record entry, never an edit.

## Pre-registered density prediction

For the 30-day scan window:

- combined H1 total events: 35–180
- combined H4 total events: 20–80
- grid_round events on H1: 0–10
- per-symbol sub-predictions (recorded for fault localization; only the combined totals trigger review):
  - H1 per symbol: 5–40
  - H4 per symbol: 3–20

The scan also records the weekly distribution of events. A combined total outside its range triggers a definition review in the order carried by SCAN-005: ATR distribution first, near-miss diagnosis second, level construction third, the band last — never a silent parameter change.
PYEOF
echo written