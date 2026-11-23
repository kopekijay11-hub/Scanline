# SCAN-021 Derivations (survey + proposal, no freeze)

## (a) Maintenance re-derivation from measured hole (fixed-UTC)

Method: for each symbol, over full H1 history interior weekdays, count missing UTC hours where adjacent hours are present. A systematic hole is a missing hour occurring on >=30% of weekdays. Proposed 1.1.0 maintenance window is the contiguous systematic hole range in fixed UTC. This is a survey/proposal only; no freeze.

| Symbol | Weekdays | Frozen maint (local NY) | Frozen maint (UTC intent) | Measured systematic holes (UTC hour:count/share) | Proposed 1.1.0 maint (fixed UTC) |
|---|---:|---|---|---|---|
| AUDCAD | 6848 | 04:00-06:00 America/New_York | see config | none | NONE |
| AUDUSD | 4295 | 00:00-02:00 America/New_York | see config | none | NONE |
| CADCHF | 5193 | 12:00-14:00 America/New_York | see config | none | NONE |
| CADJPY | 5132 | 12:00-14:00 America/New_York | see config | none | NONE |
| CADNOK | 756 | 04:00-06:00 America/New_York | see config | none | NONE |
| CADSEK | 756 | 04:00-06:00 America/New_York | see config | none | NONE |
| COPPER | 1262 | 20:00-22:00 America/New_York | see config | 21:00Z:455(36.1%) | 20:00-22:00Z |
| CORN | 1265 | 03:00-05:00 America/New_York | see config | none | NONE |
| EURCAD | 5279 | 12:00-14:00 America/New_York | see config | none | NONE |
| EURUSD | 5424 | 00:00-14:00 America/New_York | see config | none | NONE |
| FEEDBEEF | 303 | 20:00-22:00 America/New_York | see config | none | NONE |
| GASOLINE | 1258 | 20:00-22:00 America/New_York | see config | 21:00Z:455(36.2%) | 20:00-22:00Z |
| GBPCAD | 4990 | 12:00-14:00 America/New_York | see config | none | NONE |
| GBPUSD | 5424 | 00:00-14:00 America/New_York | see config | none | NONE |
| GER40 | 1242 | 20:00-22:00 America/New_York | see config | 21:00Z:445(35.8%) | 20:00-22:00Z |
| GOLD | 1248 | 20:00-22:00 America/New_York | see config | 21:00Z:455(36.5%) | 20:00-22:00Z |
| HEATOIL | 319 | 20:00-22:00 America/New_York | see config | 21:00Z:227(71.2%) | 20:00-22:00Z |
| JPN225 | 1249 | 20:00-22:00 America/New_York | see config | 21:00Z:453(36.3%) | 20:00-22:00Z |
| LEANHOGS | 304 | 20:00-22:00 America/New_York | see config | none | NONE |
| LIVEBEEF | 303 | 20:00-22:00 America/New_York | see config | none | NONE |
| LSGOIL | 317 | 14:00-18:00 America/New_York | see config | none | NONE |
| NDAQ100 | 1249 | 20:00-22:00 America/New_York | see config | 21:00Z:430(34.4%) | 20:00-22:00Z |
| NZDCAD | 1172 | 04:00-06:00 America/New_York | see config | none | NONE |
| NZDUSD | 976 | 04:00-06:00 America/New_York | see config | none | NONE |
| PALLADIUM | 1248 | 20:00-22:00 America/New_York | see config | 21:00Z:455(36.5%) | 20:00-22:00Z |
| PLATINUM | 1248 | 20:00-22:00 America/New_York | see config | 21:00Z:455(36.5%) | 20:00-22:00Z |
| SILVER | 1248 | 20:00-22:00 America/New_York | see config | 21:00Z:455(36.5%) | 20:00-22:00Z |
| SOYBEAN | 1263 | 12:00-18:00 America/New_York | see config | none | NONE |
| SPX500 | 1249 | 20:00-22:00 America/New_York | see config | 21:00Z:430(34.4%) | 20:00-22:00Z |
| UK100 | 1250 | 20:00-22:00 America/New_York | see config | 21:00Z:441(35.3%) | 20:00-22:00Z |
| UKOIL | 1244 | 15:00-18:00 America/New_York | see config | none | NONE |
| US2000 | 344 | 20:00-22:00 America/New_York | see config | 21:00Z:243(70.6%) | 20:00-22:00Z |
| US30 | 1249 | 20:00-22:00 America/New_York | see config | 21:00Z:430(34.4%) | 20:00-22:00Z |
| USDCAD | 4295 | 20:00-22:00 America/New_York | see config | none | NONE |
| USDCHF | 4295 | 00:00-18:00 America/New_York | see config | none | NONE |
| USDJPY | 4808 | 00:00-02:00 America/New_York | see config | none | NONE |
| USNATGAS | 1248 | 20:00-22:00 America/New_York | see config | 21:00Z:453(36.3%) | 20:00-22:00Z |
| USOIL | 1248 | 20:00-22:00 America/New_York | see config | 21:00Z:455(36.5%) | 20:00-22:00Z |
| WHEAT | 1264 | 12:00-18:00 America/New_York | see config | none | NONE |

### 16-symbol gap cohort defect
Frozen maintenance for cohort: 20:00-22:00 America/New_York. Observed corpus hole: missing 21:00Z bar (20:00Z->22:00Z) daily on trading days. Proposed fixed-UTC maintenance: 20:00-22:00Z (or 21:00Z hole window) per measured data; exact 1.1.0 encoding to be decided at freeze.

- COPPER: 21:00Z:455(36.1%) -> proposed 20:00-22:00Z
- GASOLINE: 21:00Z:455(36.2%) -> proposed 20:00-22:00Z
- GER40: 21:00Z:445(35.8%) -> proposed 20:00-22:00Z
- GOLD: 21:00Z:455(36.5%) -> proposed 20:00-22:00Z
- HEATOIL: 21:00Z:227(71.2%) -> proposed 20:00-22:00Z
- JPN225: 21:00Z:453(36.3%) -> proposed 20:00-22:00Z
- NDAQ100: 21:00Z:430(34.4%) -> proposed 20:00-22:00Z
- PALLADIUM: 21:00Z:455(36.5%) -> proposed 20:00-22:00Z
- PLATINUM: 21:00Z:455(36.5%) -> proposed 20:00-22:00Z
- SILVER: 21:00Z:455(36.5%) -> proposed 20:00-22:00Z
- SPX500: 21:00Z:430(34.4%) -> proposed 20:00-22:00Z
- UK100: 21:00Z:441(35.3%) -> proposed 20:00-22:00Z
- US2000: 21:00Z:243(70.6%) -> proposed 20:00-22:00Z
- US30: 21:00Z:430(34.4%) -> proposed 20:00-22:00Z
- USNATGAS: 21:00Z:453(36.3%) -> proposed 20:00-22:00Z
- USOIL: 21:00Z:455(36.5%) -> proposed 20:00-22:00Z

## (b) Sunday rule proposal (1.1.0)

Proposed 1.1.0 template-fit rule: templates fit on history strictly BEFORE the confirmatory window's start. Provenance (fit span start/end, corpus snapshot identity as available, exclusion windows) must be stated in the freeze record. Sunday expected counts/tolerances derived by the same modal/percentile rules as 1.0.0 Step 1a, applied to the pre-confirmatory fit span only. No A/B in-sample fitting.

## (c) Baseline rule proposal (1.1.0)

All 1.1.0 baselines computed through the driver's published-batch semantics: extraction span = window ± 7 days; interior-only rule as implemented in `scanline.sessions`. No ad-hoc exploratory extractions. Lesson of record: 1.0.0 exploratory B Sunday count 28 vs driver-semantics recount 21. Any baseline used for pre-registration ceilings must be reproducible from a driver-produced/published batch or an explicitly documented driver-equivalent run with identical extraction/window semantics, recorded with hash/provenance.

