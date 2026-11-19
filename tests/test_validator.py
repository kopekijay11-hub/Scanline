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
