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
    """Test production param file rejection."""

    def test_production_params_rejected_R4(self, clean_batch, production_params_bytes):
        """Production (unfrozen) params rejected under R4."""
        events, header = clean_batch
        # Use production params but clean batch expects frozen params
        # This should fail because frozen_at is null in production params
        result = validate_batch(events, header, production_params_bytes)
        
        # The production params have frozen_at: null, so R4 should fail
        assert result["valid"] is False
        assert result["rule_results"]["R4"] == "fail"
        # Check that the violation is about frozen_at being null
        r4_violations = [v for v in result["violations"] if v["rule"] == "R4"]
        assert len(r4_violations) >= 1


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
            "param_file": "frozen_params.json",
            "param_sha256": "d3f7fc0e396240c8bde0ccf0f0930794dcac6c8548f0f77f2d9474c6dfcb5eaa",
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
