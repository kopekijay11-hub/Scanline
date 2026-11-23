# SCAN-022 session_anomalies 1.1.0 Confirmatory Publication

## Status
- module: session_anomalies
- param_version: 1.1.0
- scan_id: 20261123T081126751440Z_852b86b3fcc1134079fa71923e07d342
- window: 2025-09-02T00:00:00Z -> 2026-01-19T23:59:59Z (140 days inclusive)
- extraction: 2025-08-26T00:00:00Z -> 2026-01-27T00:00:00Z (end exclusive)
- universe n=33, E_A=4620; E_B=1170, alpha=0.0125
- calendar: v2 sha256 d958a74296302612066a160d259de26bb6b8cbb29138594aad10c542eaffcea4 (additive, missing/stub only)

## Preregistered ceilings and verdicts
| anomaly_type | k_B | k_A | C | rate_A/100sd | rho_floor/100sd | material | breach | verdict |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| intra_session_gap | 18 | 22 | 124 | 0.476190 | 0.500 | False | False | WITHIN_CEILING |
| missing_session | 1 | 8 | 27 | 0.173160 | 0.100 | True | False | WITHIN_CEILING |
| stub_session | 2 | 13 | 35 | 0.281385 | 0.100 | True | False | WITHIN_CEILING |
| sunday_anomaly | 4 | 1 | 48 | 0.021645 | 0.200 | False | False | WITHIN_CEILING |

## Event/cluster totals
- events: 164
- clusters: 44 (rule scan021-cluster-v1)
- intra_session_gap: 35 events / 22 clusters
- missing_session: 25 events / 8 clusters
- stub_session: 103 events / 13 clusters
- sunday_anomaly: 1 events / 1 clusters

## Calendar attribution (v2, additive; missing/stub only)
- matches: 5
- ['missing_session', '2025-11-27'] rule=US_THANKSGIVING_CME_GRAINS_LIVESTOCK_CLOSED_OR_EARLY severity=None note=
- ['missing_session', '2025-12-25'] rule=US_CHRISTMAS_CME_GRAINS_LIVESTOCK_CLOSED severity=None note=
- ['stub_session', '2025-12-25'] rule=US_CHRISTMAS_CME_EQUITY_ENERGY_METALS_CLOSED_OR_EARLY severity=None note=
- ['missing_session', '2025-12-25'] rule=EU_CHRISTMAS_EUREX_EQUITY_INDEX_CLOSED severity=None note=
- ['missing_session', '2025-12-25'] rule=UK_CHRISTMAS_LSE_ICE_EQUITY_INDEX_CLOSED severity=None note=

## Cluster details
- C0001 ['intra_session_gap', '2025-09-03', '2025-09-03T04'] size=1 symbols=['CORN']
- C0002 ['intra_session_gap', '2025-09-12', '2025-09-12T05'] size=1 symbols=['CORN']
- C0003 ['intra_session_gap', '2025-09-18', '2025-09-18T07'] size=1 symbols=['CORN']
- C0004 ['intra_session_gap', '2025-09-24', '2025-09-24T05'] size=1 symbols=['CORN']
- C0005 ['intra_session_gap', '2025-09-29', '2025-09-29T06'] size=1 symbols=['CORN']
- C0006 ['intra_session_gap', '2025-10-03', '2025-10-03T05'] size=1 symbols=['CORN']
- C0007 ['intra_session_gap', '2025-10-13', '2025-10-13T06'] size=1 symbols=['CORN']
- C0008 ['intra_session_gap', '2025-10-28', '2025-10-28T05'] size=1 symbols=['CORN']
- C0009 ['intra_session_gap', '2025-11-06', '2025-11-06T05'] size=1 symbols=['CORN']
- C0010 ['intra_session_gap', '2025-11-28', '2025-11-28T05'] size=5 symbols=['NDAQ100', 'SPX500', 'UK100', 'US30', 'USNATGAS']
- C0011 ['intra_session_gap', '2025-11-28', '2025-11-28T12'] size=10 symbols=['COPPER', 'GASOLINE', 'JPN225', 'NDAQ100', 'PALLADIUM', 'PLATINUM', 'SPX500', 'US30', 'USNATGAS', 'USOIL']
- C0012 ['intra_session_gap', '2025-11-28', '2025-11-28T20'] size=1 symbols=['GASOLINE']
- C0013 ['intra_session_gap', '2025-12-03', '2025-12-03T05'] size=1 symbols=['CORN']
- C0014 ['intra_session_gap', '2025-12-15', '2025-12-15T04'] size=1 symbols=['CORN']
- C0015 ['intra_session_gap', '2025-12-22', '2025-12-22T04'] size=1 symbols=['CORN']
- C0016 ['intra_session_gap', '2025-12-23', '2025-12-23T04'] size=1 symbols=['CORN']
- C0017 ['intra_session_gap', '2025-12-24', '2025-12-24T04'] size=1 symbols=['CORN']
- C0018 ['intra_session_gap', '2025-12-31', '2025-12-31T04'] size=1 symbols=['CORN']
- C0019 ['intra_session_gap', '2025-12-31', '2025-12-31T06'] size=1 symbols=['CORN']
- C0020 ['intra_session_gap', '2026-01-08', '2026-01-08T05'] size=1 symbols=['CORN']
- C0021 ['intra_session_gap', '2026-01-12', '2026-01-12T03'] size=1 symbols=['CORN']
- C0022 ['intra_session_gap', '2026-01-14', '2026-01-14T02'] size=1 symbols=['CORN']
- C0023 ['missing_session', '2025-09-08'] size=3 symbols=['CORN', 'SOYBEAN', 'WHEAT']
- C0024 ['missing_session', '2025-11-27'] size=3 symbols=['CORN', 'SOYBEAN', 'WHEAT']
- C0025 ['missing_session', '2025-12-24'] size=1 symbols=['GER40']
- C0026 ['missing_session', '2025-12-25'] size=6 symbols=['CORN', 'GER40', 'SOYBEAN', 'UK100', 'UKOIL', 'WHEAT']
- C0027 ['missing_session', '2025-12-26'] size=2 symbols=['GER40', 'UK100']
- C0028 ['missing_session', '2025-12-31'] size=1 symbols=['GER40']
- C0029 ['missing_session', '2026-01-01'] size=6 symbols=['CORN', 'GER40', 'SOYBEAN', 'UK100', 'UKOIL', 'WHEAT']
- C0030 ['missing_session', '2026-01-19'] size=3 symbols=['CORN', 'SOYBEAN', 'WHEAT']
- C0031 ['stub_session', '2025-09-08'] size=1 symbols=['UKOIL']
- C0032 ['stub_session', '2025-09-18'] size=1 symbols=['CORN']
- C0033 ['stub_session', '2025-09-29'] size=1 symbols=['CORN']
- C0034 ['stub_session', '2025-11-27'] size=1 symbols=['UKOIL']
- C0035 ['stub_session', '2025-11-28'] size=17 symbols=['COPPER', 'CORN', 'GASOLINE', 'GOLD', 'JPN225', 'NDAQ100', 'PALLADIUM', 'PLATINUM', 'SILVER', 'SOYBEAN', 'SPX500', 'UK100', 'UKOIL', 'US30', 'USNATGAS', 'USOIL', 'WHEAT']
- C0036 ['stub_session', '2025-12-23'] size=1 symbols=['CORN']
- C0037 ['stub_session', '2025-12-24'] size=17 symbols=['COPPER', 'CORN', 'GASOLINE', 'GOLD', 'JPN225', 'NDAQ100', 'PALLADIUM', 'PLATINUM', 'SILVER', 'SOYBEAN', 'SPX500', 'UK100', 'UKOIL', 'US30', 'USNATGAS', 'USOIL', 'WHEAT']
- C0038 ['stub_session', '2025-12-25'] size=27 symbols=['AUDCAD', 'AUDUSD', 'CADCHF', 'CADJPY', 'CADNOK', 'CADSEK', 'COPPER', 'EURCAD', 'EURUSD', 'GASOLINE', 'GBPCAD', 'GBPUSD', 'GOLD', 'JPN225', 'NDAQ100', 'NZDCAD', 'NZDUSD', 'PALLADIUM', 'PLATINUM', 'SILVER', 'SPX500', 'US30', 'USDCAD', 'USDCHF', 'USDJPY', 'USNATGAS', 'USOIL']
- C0039 ['stub_session', '2025-12-26'] size=3 symbols=['CORN', 'SOYBEAN', 'WHEAT']
- C0040 ['stub_session', '2025-12-31'] size=3 symbols=['CORN', 'UK100', 'UKOIL']
- C0041 ['stub_session', '2026-01-01'] size=27 symbols=['AUDCAD', 'AUDUSD', 'CADCHF', 'CADJPY', 'CADNOK', 'CADSEK', 'COPPER', 'EURCAD', 'EURUSD', 'GASOLINE', 'GBPCAD', 'GBPUSD', 'GOLD', 'JPN225', 'NDAQ100', 'NZDCAD', 'NZDUSD', 'PALLADIUM', 'PLATINUM', 'SILVER', 'SPX500', 'US30', 'USDCAD', 'USDCHF', 'USDJPY', 'USNATGAS', 'USOIL']
- C0042 ['stub_session', '2026-01-02'] size=3 symbols=['CORN', 'SOYBEAN', 'WHEAT']
- C0043 ['stub_session', '2026-01-08'] size=1 symbols=['CORN']
- C0044 ['sunday_anomaly', '2025-10-12'] size=1 symbols=['SILVER']

## Notes
- All four anomaly types within preregistered ceilings; no breaches.
- Holiday closures in window (Thanksgiving, Christmas/New Year) appear as missing/stub clusters and are calendar-attributed where v2 rules apply; attribution is additive and does not alter detector events.
- Validation: scanner_data_manifest.json status COMPLETE, validation_status valid, violation_count 0.
