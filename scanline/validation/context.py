"""Shared validation context for Scanline validator (SCAN-015)."""

from dataclasses import dataclass
from typing import Any, Dict, List


@dataclass(frozen=True)
class ValidationContext:
    events: List[Dict[str, Any]]
    header: Dict[str, Any]
    param_bytes: bytes
    param_data: Dict[str, Any]
    raw_module: Any
    module: str
