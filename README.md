# Scanline

**A standalone, deterministic market-condition event scanner.** Scanline sweeps price state across a symbol universe and emits an *as-of-validated* event stream — every event produced by explicit rules, checked by the validator before it is emitted. The output is an offline research feed, never a live-decision input.

The validator is the deliverable, and the modules are its evidence.

Sibling of [Feedline](https://github.com/kopekijay11-hub/feedline) and Watchline.

---

## Status

| Module | Scope | Status |
|---|---|---|
| **Module 1** | Core scan + validation baseline | ✅ Complete |
| **Module 2** | Persistence, manifests, configuration provenance (SCAN-018 series) | ✅ Complete |
| **Module 3** | Remaining detector families (volatility expansion, spread blowouts) | Not started |

## What it detects

- **Level proximity** — the first detector family (Module 1): price approaching, touching, or reacting at defined levels.
- **Session anomalies** — implemented for H1: missing/stub/Sunday/intra-gap detection with DST-aware maintenance windows.
- Planned subsequent families: **volatility expansion** and **spread blowouts**.

**Initial universe:** GOLD, EURUSD, USDCAD, GER40, USOIL · **Emission timeframes:** H1, H4 · **Definition timeframe:** D1

## Design principles

- **Deterministic by design** — explicit rules only; no model in the detection path. The same input bars always produce the same event stream.
- **Validation before emission** — bars are integrity-checked (including duplicate-bar enforcement) before any detector sees them; invalid input produces no events.
- **Provenance on every scan** — each run carries a configuration provenance manifest (v1.1.0) recording exactly which configuration produced it.
- **Standalone** — Scanline reads market data and writes its event stream. It is deliberately not wired into any trading or dashboard system.

## Module summary

**Module 1 — scan and validation baseline**
- Core scanner and event emission (SCAN-014)
- Validator decomposed into composable rule modules (SCAN-015)
- Session characterization and mixed-input protection tests (SCAN-017)
- Duplicate-bar integrity enforcement (SCAN-017F)

**Module 2 — SCAN-018: persistence, manifest, and configuration hardening**
- **018A** — scan identity hardening and atomic persistence
- **018B** — manifest versioning and validation
- **018C-I1** — configuration canonicalization
- **018C-I2** — authoritative configuration loading
- **018C-I3** — configuration provenance manifest v1.1.0, with dual snapshots

Configuration is loaded from versioned files under `config/` and stamped into every scan's provenance manifest.

## Documentation

Design and contract records live in `docs/`:

- [SCAN-017 Contract Decisions](docs/SCAN-017-CONTRACT-DECISIONS.md)
- [SCAN-017 Recon](docs/SCAN-017-RECON.md)
- [SCAN-017E Duplicate Policy](docs/SCAN-017E-DUPLICATE-POLICY.md)
- [SCAN-015 Closure / SCAN-016 Recon](docs/SCAN-015-CLOSURE-SCAN-016-RECON.md)

## Testing

A pytest suite (348 tests on main) covers the validator rule modules, persistence and manifest handling, and the configuration layers — including characterization tests that pin detector behavior against known sessions. Tests currently run locally; a GitHub Actions CI pipeline is in preparation (November 2026).
