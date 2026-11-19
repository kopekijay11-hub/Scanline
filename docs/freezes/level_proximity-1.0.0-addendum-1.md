# Freeze record addendum 1: level_proximity 1.0.0

## Finding

The corpus survey (survey-2026-11-18.json) selected window 2026-10-02 → 2026-10-31. Three of five symbols (GOLD, GER40, USOIL) have D1 series ending 2026-10-21 while their H1/H4 series run to 2026-10-31 (EURUSD/USDCAD D1 runs to 2026-10-30). The selected window therefore contained days on which those symbols had H1/H4 bars but no D1 bar, leaving their levels frozen at Oct 21 values for the last third of the scan.

The original coverage definition missed this twice: a "trading day" is defined by D1 presence, so H1/H4 coverage on D1-absent days was never evaluated; and the suspected-D1-hole guard required at least 4 other symbols to trade, which a correlated three-symbol truncation defeats by construction.

## Repaired clause (joins the coverage definition from this addendum forward)

A window is disqualified for a symbol if it contains ANY day on which that symbol has emission-timeframe (H1 or H4) bars but no D1 bar. A day present in one timeframe and absent in the other is a corpus hole by construction, regardless of what other symbols do that day.

## Superseded window

The original window 2026-10-02 → 2026-10-31 is superseded by the re-selection in SCAN-005-FIX (records/surveys/survey-2026-11-18-rev2.json): 2026-09-22 → 2026-10-21.

## Unchanged

The param file (config/scanner_params.level_proximity.json) and every frozen value in docs/freezes/level_proximity-1.0.0.md are unchanged. This addendum is a new freeze-record entry, not an edit to the original record.
