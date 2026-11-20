import json
from pathlib import Path

from scanline.validation import r1, r2, r3, r4, r5
from scanline.validation.context import ValidationContext
from scanline.validator import validate_batch


def test_rule_modules_return_lists():
    ctx = ValidationContext(events=[], header={}, param_bytes=b"{}", param_data={}, raw_module="level_proximity", module="level_proximity")
    assert isinstance(r1.validate_r1(ctx), list)
    assert isinstance(r2.validate_r2(ctx), list)
    assert isinstance(r3.validate_r3(ctx), list)
    assert isinstance(r4.validate_r4(ctx), list)
    assert isinstance(r5.validate_r5(ctx), list)


def test_decomposed_matches_monolithic_clean():
    FIX = Path("tests/fixtures")
    data = json.loads((FIX / "clean_batch.json").read_text())
    pb = (FIX / "frozen_params.json").read_bytes()
    r = validate_batch(data["events"], data["header"], pb)
    assert r["valid"] is True
    assert r["violations"] == []
