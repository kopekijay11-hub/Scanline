# Freeze record: level_proximity 2.1.0

## What changed

- Grid steps recalibrated for the 15 symbols whose 2.0.0 step_to_atr was below the healthy band (COPPER, LSGOIL, PLATINUM, NDAQ100, US30, CADNOK, PALLADIUM, JPN225, SILVER, HEATOIL, SOYBEAN, WHEAT, GASOLINE, USNATGAS, CORN), scaling their steps to the reference ratio (~9.29) derived from the 18 healthy symbols. All other 18 grid steps unchanged.
- param_version 2.1.0; frozen_at 2026-11-20T03:09:46Z.

## What did not change

- Band values (0.5 ATR structural and grid).
- ATR (window 14, closed bars only).
- Trigger, gap semantics, structural construction.
- Universe (33 symbols).
- The 18 already-healthy grid steps.

## Pre-registration (held-out window)

- grid_H1: [396, 1584]
- grid_H4: [175, 700]
- structural_H1: [1060, 4238]
- structural_H4: [403, 1610]
- Dispersion: max symbol share of grid_H1 < 20% AND max(grid_H1)/median(grid_H1) <= 3.5.

## Retrospective limit

For a historical window, untuned-ness is credible (canonical steps, hash freeze, git commit order) but not provable.
