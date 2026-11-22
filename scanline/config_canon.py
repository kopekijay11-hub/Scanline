"""SCANLINE-config-canon-v1: strict, deterministic JSON canonicalization.

Reusable, independently testable component for SCAN-018C-I1.
"""

from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass
from typing import Any

CANON_VERSION = "SCANLINE-config-canon-v1"
CONFIG_HASH_ALGORITHM = "sha256"
CONFIG_HASH_SUBJECT = "effective_validated_config"

MAX_RAW_BYTES = 1024 * 1024
MAX_DEPTH = 64
MAX_COEFF_DIGITS = 128
MAX_ABS_EXPONENT = 308
MAX_EXPANDED_NUMBER_LEN = 437  # excluding sign, derived
MAX_DEFENSIVE_NUMBER_LEN = 512  # unreachable guard only


class CanonicalizationError(ValueError):
    """Raised when input cannot be canonicalized under SCANLINE-config-canon-v1."""


@dataclass(frozen=True)
class _NumberToken:
    raw: str
    sign: str  # '' or '-'
    digits: str  # coefficient digits, no sign, no dot
    exp10: int  # value = sign * int(digits) * 10**exp10
    is_zero: bool


def canonicalize(raw_bytes: bytes) -> bytes:
    """Canonicalize JSON bytes per SCANLINE-config-canon-v1.

    Returns compact UTF-8 canonical JSON bytes with no trailing newline.
    """
    if not isinstance(raw_bytes, (bytes, bytearray)):
        raise CanonicalizationError("input must be bytes")
    raw_bytes = bytes(raw_bytes)
    if len(raw_bytes) > MAX_RAW_BYTES:
        raise CanonicalizationError(
            f"input exceeds MAX_RAW_BYTES ({MAX_RAW_BYTES})"
        )
    try:
        text = raw_bytes.decode("utf-8", errors="strict")
    except UnicodeDecodeError as e:
        raise CanonicalizationError(f"invalid UTF-8: {e}") from e
    parser = _Parser(text)
    value = parser.parse_value(depth=0)
    parser.skip_ws()
    if not parser.at_end():
        raise CanonicalizationError("trailing content after JSON value")
    out = _serialize(value)
    out_bytes = out.encode("utf-8")
    # Defensive unreachable guard; accepted inputs are bounded by coeff/exponent.
    if len(out_bytes) > MAX_RAW_BYTES:
        raise CanonicalizationError("canonical output exceeds MAX_RAW_BYTES")
    return out_bytes


def canonical_sha256(raw_bytes: bytes) -> str:
    """SHA-256 hex digest of SCANLINE-config-canon-v1 canonical bytes."""
    return hashlib.sha256(canonicalize(raw_bytes)).hexdigest()


def canonicalize_json_text(text: str) -> bytes:
    """Convenience wrapper for UTF-8 text input."""
    if not isinstance(text, str):
        raise CanonicalizationError("input must be str")
    return canonicalize(text.encode("utf-8"))


class _Parser:
    def __init__(self, text: str):
        self.text = text
        self.i = 0
        self.n = len(text)

    def at_end(self) -> bool:
        return self.i >= self.n

    def peek(self) -> str:
        if self.i >= self.n:
            return ""
        return self.text[self.i]

    def advance(self, k: int = 1) -> None:
        self.i += k

    def skip_ws(self) -> None:
        while self.i < self.n and self.text[self.i] in " \t\r\n":
            self.i += 1

    def parse_value(self, depth: int) -> Any:
        self.skip_ws()
        if self.i >= self.n:
            raise CanonicalizationError("unexpected end of input")
        if depth > MAX_DEPTH:
            raise CanonicalizationError(f"maximum nesting depth {MAX_DEPTH} exceeded")
        ch = self.text[self.i]
        if ch == "{":
            return self.parse_object(depth)
        if ch == "[":
            return self.parse_array(depth)
        if ch == '"':
            return self.parse_string()
        if ch == "t":
            return self.parse_literal("true", True)
        if ch == "f":
            return self.parse_literal("false", False)
        if ch == "n":
            return self.parse_literal("null", None)
        if ch == "-" or ("0" <= ch <= "9"):
            return self.parse_number()
        raise CanonicalizationError(f"unexpected character {ch!r} at offset {self.i}")

    def parse_literal(self, lit: str, value: Any) -> Any:
        end = self.i + len(lit)
        if self.text[self.i:end] != lit:
            raise CanonicalizationError(f"invalid literal at offset {self.i}")
        # Ensure literal is not followed by identifier char.
        if end < self.n:
            nxt = self.text[end]
            if nxt.isalnum() or nxt == "_":
                raise CanonicalizationError(f"invalid literal at offset {self.i}")
        self.i = end
        return value

    def parse_string(self) -> str:
        if self.text[self.i] != '"':
            raise CanonicalizationError("expected string")
        self.i += 1
        chars = []
        while self.i < self.n:
            ch = self.text[self.i]
            if ch == '"':
                self.i += 1
                s = "".join(chars)
                _reject_lone_surrogates(s)
                return s
            if ch == "\\":
                self.i += 1
                if self.i >= self.n:
                    raise CanonicalizationError("unterminated string escape")
                esc = self.text[self.i]
                self.i += 1
                if esc == '"':
                    chars.append('"')
                elif esc == "\\":
                    chars.append("\\")
                elif esc == "/":
                    chars.append("/")
                elif esc == "b":
                    chars.append("\b")
                elif esc == "f":
                    chars.append("\f")
                elif esc == "n":
                    chars.append("\n")
                elif esc == "r":
                    chars.append("\r")
                elif esc == "t":
                    chars.append("\t")
                elif esc == "u":
                    chars.append(self.parse_unicode_escape())
                else:
                    raise CanonicalizationError(f"invalid escape \\{esc}")
            else:
                o = ord(ch)
                if o < 0x20:
                    raise CanonicalizationError("unescaped control character in string")
                chars.append(ch)
                self.i += 1
        raise CanonicalizationError("unterminated string")

    def parse_unicode_escape(self) -> str:
        if self.i + 4 > self.n:
            raise CanonicalizationError("invalid unicode escape")
        hexpart = self.text[self.i:self.i + 4]
        if any(c not in "0123456789abcdefABCDEF" for c in hexpart):
            raise CanonicalizationError("invalid unicode escape")
        code = int(hexpart, 16)
        self.i += 4
        # Handle UTF-16 surrogate pairs as JSON requires.
        if 0xD800 <= code <= 0xDBFF:
            if self.i + 2 <= self.n and self.text[self.i:self.i + 2] == "\\u":
                self.i += 2
                if self.i + 4 > self.n:
                    raise CanonicalizationError("invalid unicode surrogate pair")
                hex2 = self.text[self.i:self.i + 4]
                if any(c not in "0123456789abcdefABCDEF" for c in hex2):
                    raise CanonicalizationError("invalid unicode surrogate pair")
                code2 = int(hex2, 16)
                if not (0xDC00 <= code2 <= 0xDFFF):
                    raise CanonicalizationError("invalid unicode surrogate pair")
                self.i += 4
                cp = 0x10000 + ((code - 0xD800) << 10) + (code2 - 0xDC00)
                return chr(cp)
            raise CanonicalizationError("lone surrogate in unicode escape")
        if 0xDC00 <= code <= 0xDFFF:
            raise CanonicalizationError("lone surrogate in unicode escape")
        return chr(code)

    def parse_number(self) -> _NumberToken:
        start = self.i
        if self.text[self.i] == "-":
            sign = "-"
            self.i += 1
        else:
            sign = ""
        if self.i >= self.n:
            raise CanonicalizationError("invalid number")

        int_part = self._parse_int_part()
        frac_part = ""
        if self.i < self.n and self.text[self.i] == ".":
            self.i += 1
            frac_part = self._parse_digits(required=True, what="fraction")
        exp_part = 0
        if self.i < self.n and self.text[self.i] in "eE":
            self.i += 1
            exp_sign = 1
            if self.i < self.n and self.text[self.i] in "+-":
                if self.text[self.i] == "-":
                    exp_sign = -1
                self.i += 1
            exp_digits = self._parse_digits(required=True, what="exponent")
            # Exponent value can be large; parse safely as int.
            exp_part = exp_sign * int(exp_digits)

        raw = self.text[start:self.i]
        # Reject invalid trailing chars that can form literals in non-strict modes? JSON parser handles.
        # Build coefficient digits
        coeff = int_part + frac_part
        if not coeff:
            raise CanonicalizationError("invalid number")
        coeff_digits_count = len(coeff.lstrip("0")) or 1
        if coeff_digits_count > MAX_COEFF_DIGITS:
            raise CanonicalizationError(
                f"number coefficient exceeds {MAX_COEFF_DIGITS} digits"
            )
        if abs(exp_part) > MAX_ABS_EXPONENT:
            raise CanonicalizationError(
                f"number exponent magnitude exceeds {MAX_ABS_EXPONENT}"
            )

        # Effective exponent in base10 for integer coefficient (int_part+frac_part)
        exp10 = exp_part - len(frac_part)
        is_zero = all(c == "0" for c in coeff)
        token = _NumberToken(raw=raw, sign=sign, digits=coeff, exp10=exp10, is_zero=is_zero)
        _validate_number_token(token)
        return token

    def _parse_int_part(self) -> str:
        if self.i >= self.n or not ("0" <= self.text[self.i] <= "9"):
            raise CanonicalizationError("invalid number")
        if self.text[self.i] == "0":
            self.i += 1
            if self.i < self.n and ("0" <= self.text[self.i] <= "9"):
                raise CanonicalizationError("leading zero in number")
            return "0"
        digits = []
        while self.i < self.n and ("0" <= self.text[self.i] <= "9"):
            digits.append(self.text[self.i])
            self.i += 1
        return "".join(digits)

    def _parse_digits(self, required: bool, what: str) -> str:
        if self.i >= self.n or not ("0" <= self.text[self.i] <= "9"):
            if required:
                raise CanonicalizationError(f"invalid {what} in number")
            return ""
        start = self.i
        while self.i < self.n and ("0" <= self.text[self.i] <= "9"):
            self.i += 1
        return self.text[start:self.i]

    def parse_object(self, depth: int) -> dict:
        if depth >= MAX_DEPTH:
            raise CanonicalizationError(f"maximum nesting depth {MAX_DEPTH} exceeded")
        if self.text[self.i] != "{":
            raise CanonicalizationError("expected object")
        self.i += 1
        self.skip_ws()
        obj = {}
        if self.i < self.n and self.text[self.i] == "}":
            self.i += 1
            return obj
        while True:
            self.skip_ws()
            if self.i >= self.n or self.text[self.i] != '"':
                raise CanonicalizationError("expected object key string")
            key = self.parse_string()
            if key in obj:
                raise CanonicalizationError(f"duplicate key: {key!r}")
            self.skip_ws()
            if self.i >= self.n or self.text[self.i] != ":":
                raise CanonicalizationError("expected ':' after object key")
            self.i += 1
            value = self.parse_value(depth + 1)
            obj[key] = value
            self.skip_ws()
            if self.i >= self.n:
                raise CanonicalizationError("unterminated object")
            ch = self.text[self.i]
            if ch == ",":
                self.i += 1
                self.skip_ws()
                if self.i < self.n and self.text[self.i] == "}":
                    raise CanonicalizationError("trailing comma in object")
                continue
            if ch == "}":
                self.i += 1
                return obj
            raise CanonicalizationError("expected ',' or '}' in object")

    def parse_array(self, depth: int) -> list:
        if depth >= MAX_DEPTH:
            raise CanonicalizationError(f"maximum nesting depth {MAX_DEPTH} exceeded")
        if self.text[self.i] != "[":
            raise CanonicalizationError("expected array")
        self.i += 1
        self.skip_ws()
        arr = []
        if self.i < self.n and self.text[self.i] == "]":
            self.i += 1
            return arr
        while True:
            value = self.parse_value(depth + 1)
            arr.append(value)
            self.skip_ws()
            if self.i >= self.n:
                raise CanonicalizationError("unterminated array")
            ch = self.text[self.i]
            if ch == ",":
                self.i += 1
                self.skip_ws()
                if self.i < self.n and self.text[self.i] == "]":
                    raise CanonicalizationError("trailing comma in array")
                continue
            if ch == "]":
                self.i += 1
                return arr
            raise CanonicalizationError("expected ',' or ']' in array")


def _reject_lone_surrogates(s: str) -> None:
    for ch in s:
        o = ord(ch)
        if 0xD800 <= o <= 0xDFFF:
            raise CanonicalizationError("lone surrogate in string")


def _validate_number_token(tok: _NumberToken) -> None:
    # Reject NaN/Infinity not representable in JSON anyway, but be explicit.
    if tok.raw.lower() in {"nan", "infinity", "-infinity", "+infinity"}:
        raise CanonicalizationError("non-finite number")
    # Coefficient/exp limits already checked. Verify derived expanded length bound.
    # For accepted inputs (coeff<=128, abs(exp)<=308), canonical expanded length excluding sign <=437.
    canon = _canonical_number_string(tok)
    body = canon[1:] if canon.startswith("-") else canon
    if len(body) > MAX_EXPANDED_NUMBER_LEN:
        # Should be unreachable for accepted inputs; reject defensively.
        raise CanonicalizationError("canonical number exceeds derived length bound")
    if len(body) > MAX_DEFENSIVE_NUMBER_LEN:
        raise CanonicalizationError("canonical number exceeds defensive length bound")


def _canonical_number_string(tok: _NumberToken) -> str:
    if tok.is_zero:
        return "0"

    digits = tok.digits.lstrip("0")
    if not digits:
        return "0"
    exp10 = tok.exp10

    # Normalize to scientific form: d0.d1... * 10^k
    k = len(digits) - 1 + exp10

    # Plain integer if no fractional part and non-negative exponent in decimal form.
    # value = int(digits) * 10^exp10
    if exp10 >= 0:
        plain = digits + ("0" * exp10)
        plain = plain.lstrip("0") or "0"
        return ("-" if tok.sign == "-" else "") + plain

    # exp10 < 0: may be decimal or integer? integer only impossible since exp10 negative.
    frac_zeros = -exp10
    if k >= 0:
        # Decimal point within digits: digits has len(d)=k+1-exp10? Better construct by place value.
        # number of digits before decimal = k+1
        int_len = k + 1
        int_part = digits[:int_len]
        frac_part = digits[int_len:]
        # We must include any zeros implied by decimal shift: frac_part may be shorter than needed.
        needed_frac = frac_zeros - (len(digits) - int_len)
        if needed_frac > 0:
            frac_part = frac_part + ("0" * needed_frac)
        frac_part = frac_part.rstrip("0")
        if frac_part:
            out = int_part.lstrip("0") or "0"
            out = out + "." + frac_part
        else:
            out = int_part.lstrip("0") or "0"
        return ("-" if tok.sign == "-" else "") + out

    # k < 0: 0.000...digits
    leading_zeros = (-k) - 1
    frac_part = ("0" * leading_zeros) + digits
    frac_part = frac_part.rstrip("0")
    out = "0." + frac_part
    return ("-" if tok.sign == "-" else "") + out


def _serialize(value: Any) -> str:
    if value is None:
        return "null"
    if value is True:
        return "true"
    if value is False:
        return "false"
    if isinstance(value, _NumberToken):
        return _canonical_number_string(value)
    if isinstance(value, str):
        return _serialize_string(value)
    if isinstance(value, list):
        return "[" + ",".join(_serialize(v) for v in value) + "]"
    if isinstance(value, dict):
        # Keys sorted by Unicode codepoint (Python str comparison is codepoint order).
        items = []
        for k in sorted(value.keys()):
            if not isinstance(k, str):
                raise CanonicalizationError("object keys must be strings")
            _reject_lone_surrogates(k)
            items.append(_serialize_string(k) + ":" + _serialize(value[k]))
        return "{" + ",".join(items) + "}"
    raise CanonicalizationError(f"unsupported type for canonicalization: {type(value)!r}")


def _serialize_string(s: str) -> str:
    _reject_lone_surrogates(s)
    out = ['"']
    for ch in s:
        o = ord(ch)
        if ch == '"':
            out.append('\\"')
        elif ch == "\\":
            out.append("\\\\")
        elif o == 0x08:
            out.append("\\b")
        elif o == 0x0C:
            out.append("\\f")
        elif o == 0x0A:
            out.append("\\n")
        elif o == 0x0D:
            out.append("\\r")
        elif o == 0x09:
            out.append("\\t")
        elif o < 0x20:
            out.append("\\u%04x" % o)
        else:
            out.append(ch)
    out.append('"')
    return "".join(out)
