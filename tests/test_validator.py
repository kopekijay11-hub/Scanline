"""Tests for the Scanline validator."""

import json
import os
from pathlib import Path

import pytest

from scanline.validator import validate_batch

# Path to fixtures directory
FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def clean_batch():
    """Load clean batch fixture."""
    with open(FIXTURES_DIR / "clean_batch.json", "r") as f:
        data = json.load(f)
    return data["events"], data["header"]


@pytest.fixture
def frozen_params_bytes():
    """Load frozen params file bytes."""
    with open(FIXTURES_DIR / "frozen_params.json", "rb") as f:
        return f.read()


@pytest.fixture
def frozen_params_noncanonical_bytes():
    """Load non-canonical frozen params file bytes."""
    with open(FIXTURES_DIR / "frozen_params_noncanonical.json", "rb") as f:
        return f.read()


@pytest.fixture
def frozen_params_late_bytes():
    """Load frozen params with late frozen_at."""
    with open(FIXTURES_DIR / "frozen_params_late.json", "rb") as f:
        return f.read()


@pytest.fixture
def production_params_bytes():
    """Load production params file (unfrozen)."""
    with open(Path(__file__).parent.parent / "config" / "scanner_params.level_proximity.json", "rb") as f:
        return f.read()


def load_batch(file_name):
    """Load a batch fixture from file."""
    with open(FIXTURES_DIR / file_name, "r") as f:
        data = json.load(f)
    return data["events"], data["header"]


class TestCleanBatch:
    """Tests for clean batch validation."""

    def test_clean_batch_is_valid(self, clean_batch, frozen_params_bytes):
        """Clean batch passes all 5 rules."""
        events, header = clean_batch
        result = validate_batch(events, header, frozen_params_bytes)
        
        assert result["valid"] is True
        assert all(r == "pass" for r in result["rule_results"].values())
        assert len(result["violations"]) == 0


class TestPoisonedBatches:
    """Tests for poisoned batch validation."""

    def test_poisoned_R1_fails_only_R1(self, frozen_params_bytes):
        """R1 poison: defined_at > event_ts."""
        events, header = load_batch("poisoned_R1.json")
        result = validate_batch(events, header, frozen_params_bytes)
        
        assert result["valid"] is False
        assert result["rule_results"]["R1"] == "fail"
        assert result["rule_results"]["R2"] == "pass"
        assert result["rule_results"]["R3"] == "pass"
        assert result["rule_results"]["R4"] == "pass"
        assert result["rule_results"]["R5"] == "pass"
        assert len(result["violations"]) == 1
        assert result["violations"][0]["rule"] == "R1"
        assert result["violations"][0]["event_index"] == 0

    def test_poisoned_R2_fails_only_R2(self, frozen_params_bytes):
        """R2 poison: invalid level_type."""
        events, header = load_batch("poisoned_R2.json")
        result = validate_batch(events, header, frozen_params_bytes)
        
        assert result["valid"] is False
        assert result["rule_results"]["R1"] == "pass"
        assert result["rule_results"]["R2"] == "fail"
        assert result["rule_results"]["R3"] == "pass"
        assert result["rule_results"]["R4"] == "pass"
        assert result["rule_results"]["R5"] == "pass"
        assert len(result["violations"]) == 1
        assert result["violations"][0]["rule"] == "R2"
        assert result["violations"][0]["event_index"] == 1

    def test_poisoned_R3_fails_only_R3(self, frozen_params_bytes):
        """R3 poison: atr_basis != 'closed_bars_only'."""
        events, header = load_batch("poisoned_R3.json")
        result = validate_batch(events, header, frozen_params_bytes)
        
        assert result["valid"] is False
        assert result["rule_results"]["R1"] == "pass"
        assert result["rule_results"]["R2"] == "pass"
        assert result["rule_results"]["R3"] == "fail"
        assert result["rule_results"]["R4"] == "pass"
        assert result["rule_results"]["R5"] == "pass"
        assert len(result["violations"]) == 1
        assert result["violations"][0]["rule"] == "R3"
        assert result["violations"][0]["event_index"] == 1

    def test_poisoned_R4a_fails_only_R4(self, frozen_params_late_bytes):
        """R4a poison: frozen_at after first event_ts."""
        events, header = load_batch("poisoned_R4a.json")
        result = validate_batch(events, header, frozen_params_late_bytes)
        
        assert result["valid"] is False
        assert result["rule_results"]["R1"] == "pass"
        assert result["rule_results"]["R2"] == "pass"
        assert result["rule_results"]["R3"] == "pass"
        assert result["rule_results"]["R4"] == "fail"
        assert result["rule_results"]["R5"] == "pass"
        assert len(result["violations"]) == 1
        assert result["violations"][0]["rule"] == "R4"

    def test_poisoned_R4b_fails_only_R4(self, frozen_params_bytes):
        """R4b poison: wrong param_sha256 in header."""
        events, header = load_batch("poisoned_R4b.json")
        result = validate_batch(events, header, frozen_params_bytes)
        
        assert result["valid"] is False
        assert result["rule_results"]["R1"] == "pass"
        assert result["rule_results"]["R2"] == "pass"
        assert result["rule_results"]["R3"] == "pass"
        assert result["rule_results"]["R4"] == "fail"
        assert result["rule_results"]["R5"] == "pass"
        assert len(result["violations"]) == 1
        assert result["violations"][0]["rule"] == "R4"

    def test_poisoned_R4c_fails_only_R4(self, frozen_params_bytes):
        """R4c poison: event param_version mismatch."""
        events, header = load_batch("poisoned_R4c.json")
        result = validate_batch(events, header, frozen_params_bytes)
        
        assert result["valid"] is False
        assert result["rule_results"]["R1"] == "pass"
        assert result["rule_results"]["R2"] == "pass"
        assert result["rule_results"]["R3"] == "pass"
        assert result["rule_results"]["R4"] == "fail"
        assert result["rule_results"]["R5"] == "pass"
        # R4c has one event with wrong version
        assert len(result["violations"]) == 1
        assert result["violations"][0]["rule"] == "R4"
        assert result["violations"][0]["event_index"] == 5

    def test_poisoned_R5_fails_only_R5(self, frozen_params_bytes):
        """R5 poison: extra field in event."""
        events, header = load_batch("poisoned_R5.json")
        result = validate_batch(events, header, frozen_params_bytes)
        
        assert result["valid"] is False
        assert result["rule_results"]["R1"] == "pass"
        assert result["rule_results"]["R2"] == "pass"
        assert result["rule_results"]["R3"] == "pass"
        assert result["rule_results"]["R4"] == "pass"
        assert result["rule_results"]["R5"] == "fail"
        assert len(result["violations"]) == 1
        assert result["violations"][0]["rule"] == "R5"
        assert result["violations"][0]["event_index"] == 0

    def test_poisoned_R2b_fails_only_R2(self, frozen_params_bytes):
        """R2b poison: invalid timeframe."""
        events, header = load_batch("poisoned_R2b.json")
        result = validate_batch(events, header, frozen_params_bytes)
        
        assert result["valid"] is False
        assert result["rule_results"]["R1"] == "pass"
        assert result["rule_results"]["R2"] == "fail"
        assert result["rule_results"]["R3"] == "pass"
        assert result["rule_results"]["R4"] == "pass"
        assert result["rule_results"]["R5"] == "pass"
        assert len(result["violations"]) == 1
        assert result["violations"][0]["rule"] == "R2"
        assert result["violations"][0]["event_index"] == 1

    def test_poisoned_R5b_fails_only_R5(self, frozen_params_bytes):
        """R5b poison: atr_window 0."""
        events, header = load_batch("poisoned_R5b.json")
        result = validate_batch(events, header, frozen_params_bytes)
        
        assert result["valid"] is False
        assert result["rule_results"]["R1"] == "pass"
        assert result["rule_results"]["R2"] == "pass"
        assert result["rule_results"]["R3"] == "pass"
        assert result["rule_results"]["R4"] == "pass"
        assert result["rule_results"]["R5"] == "fail"
        assert len(result["violations"]) == 1
        assert result["violations"][0]["rule"] == "R5"
        assert result["violations"][0]["event_index"] == 0


class TestViolationCounts:
    """Regression tests for honest violation counts."""

    def test_r4_duplicate_wrong_versions_not_deduped(self, clean_batch, frozen_params_bytes):
        """Two events with same wrong param_version yield two R4 violations."""
        events, header = clean_batch
        events = [dict(e) for e in events]
        events[0]["param_version"] = "2.0.0"
        events[3]["param_version"] = "2.0.0"
        result = validate_batch(events, header, frozen_params_bytes)

        r4 = [v for v in result["violations"] if v["rule"] == "R4"]
        assert len(r4) == 2
        assert sorted(v["event_index"] for v in r4) == [0, 3]


class TestByteHashVariant:
    """Test that byte-level hash is used, not parsed content."""

    def test_byte_hash_variant_passes(self, frozen_params_noncanonical_bytes):
        """Non-canonical param file with matching byte hash passes."""
        events, header = load_batch("byte_hash_variant.json")
        result = validate_batch(events, header, frozen_params_noncanonical_bytes)
        
        assert result["valid"] is True
        assert all(r == "pass" for r in result["rule_results"].values())
        assert len(result["violations"]) == 0


class TestProductionParams:
    """Test production param file rejection/acceptance."""
    
    def test_production_params_rejected_R4(self, clean_batch, production_params_bytes):
        """Production params rejected under R4 because header hash mismatch."""
        events, header = clean_batch
        # header is built from frozen_params fixture; production file bytes differ
        result = validate_batch(events, header, production_params_bytes)
        
        assert result["valid"] is False
        assert result["rule_results"]["R4"] == "fail"
        r4_violations = [v for v in result["violations"] if v["rule"] == "R4"]
        assert len(r4_violations) >= 1
        # mechanism pinned: hash/sha mismatch
        assert any(("sha" in v["detail"].lower()) or ("hash" in v["detail"].lower()) for v in r4_violations)
    
    def test_production_params_accepted_with_own_header(self, clean_batch, production_params_bytes):
        """Positive counterpart: header built from production file validates R4."""
        import hashlib, json
        from datetime import datetime, timedelta
        events = [dict(e) for e in clean_batch[0]]
        pdata = json.loads(production_params_bytes)
        frozen_dt = datetime.fromisoformat(pdata["frozen_at"].replace("Z", "+00:00"))
        bs = frozen_dt + timedelta(hours=1)
        be = frozen_dt + timedelta(hours=2)
        ev_ts = frozen_dt + timedelta(hours=1, minutes=30)
        fmt = lambda d: d.strftime("%Y-%m-%dT%H:%M:%SZ")
        batch_start = fmt(bs)
        batch_end = fmt(be)
        event_ts = fmt(ev_ts)
        for e in events:
            e["param_version"] = pdata["param_version"]
            e["defined_at"] = batch_start
            e["event_ts"] = event_ts
        header = {
            "module": pdata["module"],
            "scan_mode": "forward",
            "evidence_tier": "forward_asof",
            "param_file": "scanner_params.level_proximity.json",
            "param_sha256": hashlib.sha256(production_params_bytes).hexdigest(),
            "param_version": pdata["param_version"],
            "frozen_at": pdata["frozen_at"],
            "universe": pdata["universe"],
            "emission_timeframes": pdata["emission_timeframes"],
            "definition_timeframe": pdata["definition_timeframe"],
            "batch_start_ts": batch_start,
            "batch_end_ts": batch_end,
        }
        result = validate_batch(events, header, production_params_bytes)
        assert result["valid"] is True
        assert result["rule_results"]["R4"] == "pass"



class TestDeterminism:
    """Test that validator is deterministic."""

    def test_same_input_same_output(self, clean_batch, frozen_params_bytes):
        """Same input produces same output."""
        events, header = clean_batch
        
        result1 = validate_batch(events, header, frozen_params_bytes)
        result2 = validate_batch(events, header, frozen_params_bytes)
        
        assert result1 == result2


class TestViolationOrdering:
    """Test that violations are ordered correctly."""

    def test_violations_ordered_by_rule_then_index(self):
        """Violations are sorted by rule name, then event_index."""
        # Create a batch with multiple violations
        events = [
            {
                "symbol": "GOLD",
                "timeframe": "H1",
                "level_type": "h1_lower_high",  # R2 violation
                "level_price": 1950.50,
                "defined_at": "2026-01-02T01:30:00Z",  # R1 violation
                "distance_atr": 0.5,
                "atr_window": 14,
                "atr_basis": "closed_bars_only",
                "param_version": "1.0.0",
                "event_ts": "2026-01-02T01:00:00Z",
            },
        ]
        header = {
            "module": "module_1",
            "scan_mode": "forward",
            "evidence_tier": "forward_asof",
            "param_file": "frozen_params.json",
            "param_sha256": "0ca0696e775e2575e57ca3a076d8e75cfc6aafc647694bebe03e7c4dcd13ae67",
            "param_version": "1.0.0",
            "frozen_at": "2026-01-01T00:00:00Z",
            "universe": ["GOLD", "EURUSD", "USDCAD", "GER40", "USOIL"],
            "emission_timeframes": ["H1", "H4"],
            "definition_timeframe": "D1",
            "batch_start_ts": "2026-01-02T00:00:00Z",
            "batch_end_ts": "2026-01-02T12:00:00Z",
        }
        param_bytes = (FIXTURES_DIR / "frozen_params.json").read_bytes()
        
        result = validate_batch(events, header, param_bytes)
        
        # Should have violations for R1 and R2
        # R1 should come before R2 in ordering
        violation_rules = [v["rule"] for v in result["violations"]]
        assert "R1" in violation_rules
        assert "R2" in violation_rules
        # R1 comes before R2
        assert violation_rules.index("R1") < violation_rules.index("R2")


class TestContractV2Clauses:
    """Pin the three contract-v2 clauses not yet covered by the suite."""

    def test_grid_membership_fail_R1(self, frozen_params_bytes):
        """GRID-MEMBERSHIP FAIL: off-grid grid_round level_price fails R1."""
        events, header = load_batch("clean_batch.json")
        events = [dict(e) for e in events]
        header = dict(header)
        grid_idx = next(i for i, e in enumerate(events) if e["level_type"] == "grid_round")
        events[grid_idx]["level_price"] = 1.351  # not a multiple of USDCAD step 0.005
        header["scan_mode"] = "retrospective"
        header["evidence_tier"] = "retrospective_membership"
        result = validate_batch(events, header, frozen_params_bytes)

        assert result["valid"] is False
        assert result["rule_results"]["R1"] == "fail"
        assert result["rule_results"]["R2"] == "pass"
        assert result["rule_results"]["R3"] == "pass"
        assert result["rule_results"]["R4"] == "pass"
        assert result["rule_results"]["R5"] == "pass"
        r1 = [v for v in result["violations"] if v["rule"] == "R1"]
        assert len(r1) == 1
        assert r1[0]["event_index"] == grid_idx

    def test_retrospective_pass(self, frozen_params_bytes):
        """RETROSPECTIVE PASS: header frozen_at postdates events, scan_mode retrospective."""
        events, header = load_batch("clean_batch.json")
        events = [dict(e) for e in events]
        header = dict(header)
        header["scan_mode"] = "retrospective"
        header["evidence_tier"] = "retrospective_membership"
        header["frozen_at"] = "2026-12-31T00:00:00Z"  # postdates every event_ts
        result = validate_batch(events, header, frozen_params_bytes)

        assert result["valid"] is True
        assert all(r == "pass" for r in result["rule_results"].values())
        assert len(result["violations"]) == 0

    def test_scan_mode_required_R5(self, frozen_params_bytes):
        """SCAN_MODE REQUIRED: header omitting scan_mode fails R5."""
        events, header = load_batch("clean_batch.json")
        events = [dict(e) for e in events]
        header = dict(header)
        del header["scan_mode"]
        result = validate_batch(events, header, frozen_params_bytes)

        assert result["valid"] is False
        assert result["rule_results"]["R5"] == "fail"
        assert result["rule_results"]["R1"] == "pass"
        assert result["rule_results"]["R2"] == "pass"
        assert result["rule_results"]["R3"] == "pass"
        assert result["rule_results"]["R4"] == "pass"
        r5 = [v for v in result["violations"] if v["rule"] == "R5"]
        assert len(r5) == 1
        assert r5[0]["event_index"] is None


class TestContractV3Clauses:
    """Pin the contract-v3 clauses (evidence tier)."""

    def test_evidence_tier_required_R5(self, clean_batch, frozen_params_bytes):
        """EVIDENCE_TIER REQUIRED: header omitting evidence_tier fails R5."""
        events, header = clean_batch
        events = [dict(e) for e in events]
        header = dict(header)
        header["scan_mode"] = "retrospective"
        header["evidence_tier"] = "retrospective_membership"
        # baseline valid
        result = validate_batch(events, header, frozen_params_bytes)
        assert result["valid"] is True
        # omit evidence_tier
        del header["evidence_tier"]
        result = validate_batch(events, header, frozen_params_bytes)
        assert result["valid"] is False
        assert result["rule_results"]["R5"] == "fail"
        r5 = [v for v in result["violations"] if v["rule"] == "R5"]
        assert len(r5) == 1
        assert r5[0]["event_index"] is None
        assert "evidence_tier" in r5[0]["detail"]

    def test_evidence_tier_mode_mismatch_R4(self, clean_batch, frozen_params_bytes):
        """TIER-MODE MISMATCH: inconsistent pair fails R4."""
        events, header = clean_batch
        events = [dict(e) for e in events]
        # retrospective scan_mode with forward_asof tier
        h = dict(header)
        h["scan_mode"] = "retrospective"
        h["evidence_tier"] = "forward_asof"
        result = validate_batch(events, h, frozen_params_bytes)
        assert result["valid"] is False
        assert result["rule_results"]["R4"] == "fail"
        r4 = [v for v in result["violations"] if v["rule"] == "R4"]
        assert any("evidence_tier" in v["detail"] and "inconsistent" in v["detail"] for v in r4)
        # forward scan_mode with retrospective_membership tier
        h2 = dict(header)
        h2["scan_mode"] = "forward"
        h2["evidence_tier"] = "retrospective_membership"
        result2 = validate_batch(events, h2, frozen_params_bytes)
        assert result2["valid"] is False
        assert result2["rule_results"]["R4"] == "fail"

    def test_widened_grid_membership(self):
        """WIDENED GRID: real 2.0.0 params validate on-grid prices; off-grid fails R1."""
        from pathlib import Path
        import hashlib, json
        root = Path(__file__).resolve().parents[1]
        param_path = root / "config" / "scanner_params.level_proximity-2.0.0.json"
        param_bytes = param_path.read_bytes()
        params = json.loads(param_bytes)
        frozen_at = params["frozen_at"]
        # Build a retrospective batch with grid_round events at on-grid prices
        # for one widened FX (AUDCAD), one widened index (NDAQ100), one agricultural (CORN).
        events = [
            {
                "symbol": "AUDCAD",
                "timeframe": "H1",
                "level_type": "grid_round",
                "level_price": 0.90,
                "defined_at": frozen_at,
                "distance_atr": 0.25,
                "atr_window": 14,
                "atr_basis": "closed_bars_only",
                "param_version": "2.0.0",
                "event_ts": "2026-05-27T01:00:00Z",
            },
            {
                "symbol": "NDAQ100",
                "timeframe": "H1",
                "level_type": "grid_round",
                "level_price": 15000.0,
                "defined_at": frozen_at,
                "distance_atr": 0.25,
                "atr_window": 14,
                "atr_basis": "closed_bars_only",
                "param_version": "2.0.0",
                "event_ts": "2026-05-27T01:00:00Z",
            },
            {
                "symbol": "CORN",
                "timeframe": "H1",
                "level_type": "grid_round",
                "level_price": 400.0,
                "defined_at": frozen_at,
                "distance_atr": 0.25,
                "atr_window": 14,
                "atr_basis": "closed_bars_only",
                "param_version": "2.0.0",
                "event_ts": "2026-05-27T01:00:00Z",
            },
        ]
        header = {
            "module": params["module"],
            "scan_mode": "retrospective",
            "evidence_tier": "retrospective_membership",
            "param_file": param_path.name,
            "param_sha256": hashlib.sha256(param_bytes).hexdigest(),
            "param_version": params["param_version"],
            "frozen_at": frozen_at,
            "universe": params["universe"],
            "emission_timeframes": params["emission_timeframes"],
            "definition_timeframe": params["definition_timeframe"],
            "batch_start_ts": "2026-05-27T00:00:00Z",
            "batch_end_ts": "2026-05-27T12:00:00Z",
        }
        result = validate_batch(events, header, param_bytes)
        assert result["valid"] is True
        assert all(r == "pass" for r in result["rule_results"].values())
        # knock one agricultural grid price off-grid
        bad = [dict(e) for e in events]
        bad[2]["level_price"] = 402.5  # not a multiple of CORN step 5.0
        result2 = validate_batch(bad, header, param_bytes)
        assert result2["valid"] is False
        assert result2["rule_results"]["R1"] == "fail"
        r1 = [v for v in result2["violations"] if v["rule"] == "R1"]
        assert len(r1) == 1
        assert r1[0]["event_index"] == 2


class TestWidened210GridMembership:
    """Pin contract grid membership for params 2.1.0."""

    def test_widened_210_grid_membership(self):
        from pathlib import Path
        import hashlib, json
        root = Path(__file__).resolve().parents[1]
        param_path = root / "config" / "scanner_params.level_proximity-2.1.0.json"
        param_bytes = param_path.read_bytes()
        params = json.loads(param_bytes)
        frozen_at = params["frozen_at"]
        events = [
            {
                "symbol": "COPPER",
                "timeframe": "H1",
                "level_type": "grid_round",
                "level_price": 2500.0,
                "defined_at": frozen_at,
                "distance_atr": 0.25,
                "atr_window": 14,
                "atr_basis": "closed_bars_only",
                "param_version": "2.1.0",
                "event_ts": "2026-07-10T01:00:00Z",
            },
            {
                "symbol": "CADNOK",
                "timeframe": "H1",
                "level_type": "grid_round",
                "level_price": 12.3,
                "defined_at": frozen_at,
                "distance_atr": 0.25,
                "atr_window": 14,
                "atr_basis": "closed_bars_only",
                "param_version": "2.1.0",
                "event_ts": "2026-07-10T01:00:00Z",
            },
            {
                "symbol": "NDAQ100",
                "timeframe": "H1",
                "level_type": "grid_round",
                "level_price": 15000.0,
                "defined_at": frozen_at,
                "distance_atr": 0.25,
                "atr_window": 14,
                "atr_basis": "closed_bars_only",
                "param_version": "2.1.0",
                "event_ts": "2026-07-10T01:00:00Z",
            },
        ]
        header = {
            "module": params["module"],
            "scan_mode": "retrospective",
            "evidence_tier": "retrospective_membership",
            "param_file": param_path.name,
            "param_sha256": hashlib.sha256(param_bytes).hexdigest(),
            "param_version": params["param_version"],
            "frozen_at": frozen_at,
            "universe": params["universe"],
            "emission_timeframes": params["emission_timeframes"],
            "definition_timeframe": params["definition_timeframe"],
            "batch_start_ts": "2026-07-10T00:00:00Z",
            "batch_end_ts": "2026-07-10T12:00:00Z",
        }
        from scanline.validator import validate_batch
        result = validate_batch(events, header, param_bytes)
        assert result["valid"] is True
        assert all(r == "pass" for r in result["rule_results"].values())
        bad = [dict(e) for e in events]
        bad[1]["level_price"] = 12.35  # not a multiple of CADNOK step 0.1
        result2 = validate_batch(bad, header, param_bytes)
        assert result2["valid"] is False
        assert result2["rule_results"]["R1"] == "fail"
        r1 = [v for v in result2["violations"] if v["rule"] == "R1"]
        assert len(r1) == 1
        assert r1[0]["event_index"] == 1


class TestSessionAnomaliesModule:
    """Module 2 validator pins."""

    def _params_bytes(self, params):
        import json
        return json.dumps(params).encode()

    def _header(self, module="session_anomalies", scan_mode="forward", evidence_tier="forward_asof", frozen_at="2026-01-01T00:00:00Z", batch_end="2026-01-02T23:00:00Z"):
        return {
            "module": module,
            "scan_mode": scan_mode,
            "evidence_tier": evidence_tier,
            "param_file": "p.json",
            "param_sha256": None,
            "param_version": "1.0.0",
            "frozen_at": frozen_at,
            "universe": ["GOLD"],
            "emission_timeframes": ["H1"],
            "definition_timeframe": "H1",
            "batch_start_ts": "2026-01-02T00:00:00Z",
            "batch_end_ts": batch_end,
        }

    def test_unknown_module_fails_R5(self, frozen_params_bytes):
        import hashlib, json
        params = {"module": "nope", "param_version": "1.0.0", "frozen_at": "2026-01-01T00:00:00Z", "clusters": {"GOLD": {"expected_bars": 24}}}
        pb = self._params_bytes(params)
        h = self._header(module="nope")
        h["param_sha256"] = hashlib.sha256(pb).hexdigest()
        ev = [{
            "symbol": "GOLD", "timeframe": "H1", "anomaly_type": "missing_session",
            "session_date": "2026-01-02", "expected_bars": 24, "observed_bars": 0,
            "defined_at": "2026-01-01T00:00:00Z", "gap_hours": 0,
            "param_version": "1.0.0", "event_ts": "2026-01-02T23:00:00Z",
        }]
        from scanline.validator import validate_batch
        r = validate_batch(ev, h, pb)
        assert r["rule_results"]["R5"] == "fail"
        assert any("module" in v["detail"] for v in r["violations"])

    def test_unknown_anomaly_type_fails_R2(self):
        import hashlib, json
        params = {"module": "session_anomalies", "param_version": "1.0.0", "frozen_at": "2026-01-01T00:00:00Z", "clusters": {"GOLD": {"expected_bars": 24}}}
        pb = self._params_bytes(params)
        h = self._header()
        h["param_sha256"] = hashlib.sha256(pb).hexdigest()
        ev = [{
            "symbol": "GOLD", "timeframe": "H1", "anomaly_type": "bogus",
            "session_date": "2026-01-02", "expected_bars": 24, "observed_bars": 0,
            "defined_at": "2026-01-01T00:00:00Z", "gap_hours": 0,
            "param_version": "1.0.0", "event_ts": "2026-01-02T23:00:00Z",
        }]
        from scanline.validator import validate_batch
        r = validate_batch(ev, h, pb)
        assert r["rule_results"]["R2"] == "fail"

    def test_extra_event_field_fails_R5(self):
        import hashlib, json
        params = {"module": "session_anomalies", "param_version": "1.0.0", "frozen_at": "2026-01-01T00:00:00Z", "clusters": {"GOLD": {"expected_bars": 24}}}
        pb = self._params_bytes(params)
        h = self._header()
        h["param_sha256"] = hashlib.sha256(pb).hexdigest()
        ev = [{
            "symbol": "GOLD", "timeframe": "H1", "anomaly_type": "missing_session",
            "session_date": "2026-01-02", "expected_bars": 24, "observed_bars": 0,
            "defined_at": "2026-01-01T00:00:00Z", "gap_hours": 0,
            "param_version": "1.0.0", "event_ts": "2026-01-02T23:00:00Z",
            "extra": 1,
        }]
        from scanline.validator import validate_batch
        r = validate_batch(ev, h, pb)
        assert r["rule_results"]["R5"] == "fail"

    def test_tier_mismatch_fails_R4(self):
        import hashlib, json
        params = {"module": "session_anomalies", "param_version": "1.0.0", "frozen_at": "2026-01-01T00:00:00Z", "clusters": {"GOLD": {"expected_bars": 24}}}
        pb = self._params_bytes(params)
        h = self._header(scan_mode="retrospective", evidence_tier="forward_asof")
        h["param_sha256"] = hashlib.sha256(pb).hexdigest()
        # retrospective requires defined_at == frozen_at; fix
        ev = [{
            "symbol": "GOLD", "timeframe": "H1", "anomaly_type": "missing_session",
            "session_date": "2026-01-02", "expected_bars": 24, "observed_bars": 0,
            "defined_at": "2026-01-01T00:00:00Z", "gap_hours": 0,
            "param_version": "1.0.0", "event_ts": "2026-01-02T23:00:00Z",
        }]
        from scanline.validator import validate_batch
        r = validate_batch(ev, h, pb)
        assert r["rule_results"]["R4"] == "fail"

    def test_retrospective_r1_cluster_schedule(self):
        import hashlib, json
        params = {"module": "session_anomalies", "param_version": "1.0.0", "frozen_at": "2026-01-01T00:00:00Z", "clusters": {"GOLD": {"expected_bars": 24}}}
        pb = self._params_bytes(params)
        h = self._header(scan_mode="retrospective", evidence_tier="retrospective_membership", frozen_at="2026-01-01T00:00:00Z")
        h["param_sha256"] = hashlib.sha256(pb).hexdigest()
        ev = [{
            "symbol": "GOLD", "timeframe": "H1", "anomaly_type": "missing_session",
            "session_date": "2026-01-02", "expected_bars": 24, "observed_bars": 0,
            "defined_at": "2026-01-01T00:00:00Z", "gap_hours": 0,
            "param_version": "1.0.0", "event_ts": "2026-01-02T23:00:00Z",
        }]
        from scanline.validator import validate_batch
        r = validate_batch(ev, h, pb)
        assert r["valid"] is True, r["violations"]

    def test_r3_future_event_fails(self):
        import hashlib, json
        params = {"module": "session_anomalies", "param_version": "1.0.0", "frozen_at": "2026-01-01T00:00:00Z", "clusters": {"GOLD": {"expected_bars": 24}}}
        pb = self._params_bytes(params)
        h = self._header(batch_end="2026-01-02T12:00:00Z")
        h["param_sha256"] = hashlib.sha256(pb).hexdigest()
        ev = [{
            "symbol": "GOLD", "timeframe": "H1", "anomaly_type": "missing_session",
            "session_date": "2026-01-02", "expected_bars": 24, "observed_bars": 0,
            "defined_at": "2026-01-01T00:00:00Z", "gap_hours": 0,
            "param_version": "1.0.0", "event_ts": "2026-01-02T23:00:00Z",
        }]
        from scanline.validator import validate_batch
        r = validate_batch(ev, h, pb)
        assert r["rule_results"]["R3"] == "fail"
