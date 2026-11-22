import hashlib
import json
import unittest

from scanline.config_canon import (
    CANON_VERSION,
    MAX_ABS_EXPONENT,
    MAX_COEFF_DIGITS,
    MAX_DEPTH,
    MAX_DEFENSIVE_NUMBER_LEN,
    MAX_EXPANDED_NUMBER_LEN,
    MAX_RAW_BYTES,
    CanonicalizationError,
    canonical_sha256,
    canonicalize,
)


def sha256_hex(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


class TestConfigCanonVectors(unittest.TestCase):
    def assert_canon(self, input_bytes: bytes, expected_canon: bytes, expected_sha: str):
        got = canonicalize(input_bytes)
        self.assertEqual(got, expected_canon)
        self.assertEqual(sha256_hex(got), expected_sha)
        # no trailing newline
        self.assertFalse(got.endswith(b"\n"))

    def test_v1_recursive_object_key_ordering(self):
        self.assert_canon(b'{"b":1, "a":2}', b'{"a":2,"b":1}', "d3626ac30a87e6f7a6428233b3c68299976865fa5508e4267c5415c76af7a772")

    def test_v2_nested_object_ordering(self):
        self.assert_canon(
            b'{"z":{"b":1,"a":2},"y":0}',
            b'{"y":0,"z":{"a":2,"b":1}}',
            "00b04662c2a3a6e1f9ea1af59ec0fc4929e2e9671ad5e06e573319a962af9a4b",
        )

    def test_v3_array_order_preserved(self):
        self.assert_canon(b'{"a":[2,1]}', b'{"a":[2,1]}', "439e3fbf35fa867d156db2626f94efbd435852a97bbe16660ee529d9bda0e502")

    def test_v4_formatting_only_equivalent(self):
        inp = b'{"universe":["GOLD","EURUSD"],"atr_window":14,"frozen_at":"2026-11-19T03:25:04Z","param_version":"1.0.0","module":"level_proximity"}'
        exp = b'{"atr_window":14,"frozen_at":"2026-11-19T03:25:04Z","module":"level_proximity","param_version":"1.0.0","universe":["GOLD","EURUSD"]}'
        self.assert_canon(inp, exp, "4f9f75cf2d9dfb55e0aa74c0c1eb4b7cf1b9227a4641d877c571d190ec48272b")

    def test_v5_meaningful_change(self):
        inp = b'{"atr_window":14,"frozen_at":"2026-11-19T03:25:04Z","module":"level_proximity","note":"x","param_version":"1.0.0","universe":["GOLD","EURUSD"]}'
        exp = b'{"atr_window":14,"frozen_at":"2026-11-19T03:25:04Z","module":"level_proximity","note":"x","param_version":"1.0.0","universe":["GOLD","EURUSD"]}'
        self.assert_canon(inp, exp, "bcd955d0706c1f5cdfd6ee5f44fdffed29e467d1273694954d1c4de02edb1b77")

    def test_v6_numeric_equivalence(self):
        expected = b'{"x":1}'
        expected_sha = "5041bf1f713df204784353e82f6a4a535931cb64f1f4b4a5aeaffcb720918b22"
        for inp in [b'{"x":1}', b'{"x":1.0}', b'{"x":1e0}']:
            self.assert_canon(inp, expected, expected_sha)

    def test_v7_exponent_expansion(self):
        self.assert_canon(b'{"x":1e2}', b'{"x":100}', "6ae8ec2b1e8338f7511a7ea1366734f52ad540e10118fdb4a1221f10b9026f77")

    def test_v8_trailing_fractional_zero_removal(self):
        self.assert_canon(b'{"x":0.0050}', b'{"x":0.005}', "35229c9fd3ecdd0f753cffe2d26d76070cdfa81d2c72748890e65bb97ce53e98")

    def test_v9_v10_v11_negative_zero_variants(self):
        expected = b'{"x":0}'
        expected_sha = "5bff452c5ed93f2e87a23984db5a15050c6477335fdec955b70063bb2d692bf1"
        for inp in [b'{"x":-0}', b'{"x":-0.0}', b'{"x":-0e0}']:
            self.assert_canon(inp, expected, expected_sha)

    def test_v12_nfc_preserved(self):
        self.assert_canon('{"name":"café"}'.encode('utf-8'), '{"name":"café"}'.encode('utf-8'), "645fa443126a8954fc6d871912b8fc67bc2ee8feae417efe55546251962ca74d")

    def test_v13_boolean_null(self):
        self.assert_canon(b'{"a":true,"b":false,"c":null}', b'{"a":true,"b":false,"c":null}', "58ea9f23c715c4f8fee078efd41139485403f053775482d58b6f4f454b34ecf0")

    def test_v14_array_of_objects(self):
        self.assert_canon(b'{"a":[{"b":2,"a":1},3]}', b'{"a":[{"a":1,"b":2},3]}', "1528798bdb2ff2ad39d5a8afac006825970fddc1d9264a7fda325368e42f553e")

    def test_v15_idempotence(self):
        inp = b'{"b":[{"d":1.0,"c":2}],"a":-0.0}'
        once = canonicalize(inp)
        twice = canonicalize(once)
        self.assertEqual(once, b'{"a":0,"b":[{"c":2,"d":1}]}')
        self.assertEqual(once, twice)
        self.assertEqual(sha256_hex(once), "b95941771326fb7728bc2ab75cde2a4970238f83fab5a7e436adcb6bb83bf584")

    def test_v16_nfc_form(self):
        inp = '{"name":"café"}'.encode('utf-8')
        self.assert_canon(inp, inp, "645fa443126a8954fc6d871912b8fc67bc2ee8feae417efe55546251962ca74d")

    def test_v17_nfd_form(self):
        inp = b'{"name":"cafe\xcc\x81"}'
        got = canonicalize(inp)
        self.assertEqual(sha256_hex(got), "4b7186ff40a64bfae3cb4bd75ac13b0de5ee693190f20812aaff208a77560ca7")
        # idempotent and no normalization to NFC
        self.assertEqual(canonicalize(got), got)
        self.assertNotEqual(sha256_hex(got), "645fa443126a8954fc6d871912b8fc67bc2ee8feae417efe55546251962ca74d")

    def test_v18_nfc_nfd_distinct(self):
        nfc = canonical_sha256('{"name":"café"}'.encode('utf-8'))
        nfd = canonical_sha256(b'{"name":"cafe\xcc\x81"}')
        self.assertEqual(nfc, "645fa443126a8954fc6d871912b8fc67bc2ee8feae417efe55546251962ca74d")
        self.assertEqual(nfd, "4b7186ff40a64bfae3cb4bd75ac13b0de5ee693190f20812aaff208a77560ca7")
        self.assertNotEqual(nfc, nfd)


class TestConfigCanonTypedVectors(unittest.TestCase):
    def test_t1_typed_integer(self):
        inp = b'{"numeric_type":"integer","value":5}'
        exp = b'{"numeric_type":"integer","value":5}'
        got = canonicalize(inp)
        self.assertEqual(got, exp)
        self.assertEqual(sha256_hex(got), "2ac1f847d99827f1b6e5873759065fa719c183d71ed1fab076ddec78fee62b50")
        self.assertEqual(canonicalize(got), got)

    def test_t2_typed_binary64(self):
        inp = b'{"numeric_type":"binary64","value":"5.0"}'
        exp = b'{"numeric_type":"binary64","value":"5.0"}'
        got = canonicalize(inp)
        self.assertEqual(got, exp)
        self.assertEqual(sha256_hex(got), "2677df426ffd05d12b5ddd6567be5e168783c957a8549f5d0f3ddd720057f45f")
        self.assertEqual(canonicalize(got), got)

    def test_t1_t2_distinct(self):
        t1 = canonical_sha256(b'{"numeric_type":"integer","value":5}')
        t2 = canonical_sha256(b'{"numeric_type":"binary64","value":"5.0"}')
        self.assertNotEqual(t1, t2)

    def test_e1_module_alias_effective_vector(self):
        # Effective-config vector (normalization rule expressed as data expectation).
        inp = b'{"frozen_at":"2026-01-01T00:00:00Z","module":"level_proximity","param_version":"1.0.0"}'
        self.assertEqual(sha256_hex(canonicalize(inp)), "602f8adb883740858bb6ff8c7a7e8a23683d53a330927e8bf867759ef7bd8f67")

    def test_m1_local_maintenance(self):
        inp = b'{"mode":"local","start_hhmm":"17:00","end_hhmm":"18:00"}'
        got = canonicalize(inp)
        self.assertEqual(got, b'{"end_hhmm":"18:00","mode":"local","start_hhmm":"17:00"}')
        self.assertEqual(sha256_hex(got), "b57d8c35971017b2f6091b463f1d1b245ca8375a563e65a47ec78a2249fc102b")

    def test_m2_fixed_utc_maintenance(self):
        inp = b'{"mode":"fixed_utc","start_hhmm":"17:00","end_hhmm":"18:00"}'
        got = canonicalize(inp)
        self.assertEqual(got, b'{"end_hhmm":"18:00","mode":"fixed_utc","start_hhmm":"17:00"}')
        self.assertEqual(sha256_hex(got), "b635a6a0a2827917f28ca89d66afd1688787102dc6a7fa20118bb567f500b14f")

    def test_m1_m2_distinct(self):
        self.assertNotEqual(
            canonical_sha256(b'{"mode":"local","start_hhmm":"17:00","end_hhmm":"18:00"}'),
            canonical_sha256(b'{"mode":"fixed_utc","start_hhmm":"17:00","end_hhmm":"18:00"}'),
        )


class TestConfigCanonNegatives(unittest.TestCase):
    def assert_rejects(self, inp: bytes, msg_substr=None):
        with self.assertRaises(CanonicalizationError) as ctx:
            canonicalize(inp)
        if msg_substr:
            self.assertIn(msg_substr, str(ctx.exception))

    def test_n1_duplicate_key(self):
        self.assert_rejects(b'{"a":1,"a":2}', "duplicate key")

    def test_n2_nan(self):
        self.assert_rejects(b'{"x":NaN}')

    def test_n3_infinity(self):
        self.assert_rejects(b'{"x":Infinity}')

    def test_n4_neg_infinity(self):
        self.assert_rejects(b'{"x":-Infinity}')

    def test_n5_leading_plus(self):
        self.assert_rejects(b'{"x":+1}')

    def test_n6_leading_zero(self):
        self.assert_rejects(b'{"x":01}')

    def test_n7_trailing_comma(self):
        self.assert_rejects(b'{"a":1,}')

    def test_n8_comment(self):
        self.assert_rejects(b'{"a":1 /*c*/}')

    def test_n9_lone_surrogate_escape(self):
        self.assert_rejects(b'{"a":"\\ud800"}', "lone surrogate")

    def test_invalid_utf8(self):
        self.assert_rejects(b'{"a":"\xff"}', "invalid UTF-8")

    def test_top_level_non_object_allowed_by_generic_canon(self):
        # Generic canonicalizer can canonicalize valid JSON values; schema validation is separate.
        self.assertEqual(canonicalize(b'[1,2]'), b'[1,2]')
        self.assertEqual(canonicalize(b'"x"'), b'"x"')

    def test_invalid_json(self):
        self.assert_rejects(b'{"a":')

    def test_trailing_content(self):
        self.assert_rejects(b'{"a":1}{"b":2}', "trailing content")


class TestConfigCanonBoundaries(unittest.TestCase):
    def test_max_raw_bytes_boundary(self):
        # Build a valid JSON object just under/over 1MiB.
        prefix = b'{"a":"'
        suffix = b'"}'
        fill_len = MAX_RAW_BYTES - len(prefix) - len(suffix)
        ok = prefix + (b'a' * fill_len) + suffix
        self.assertEqual(len(ok), MAX_RAW_BYTES)
        canonicalize(ok)  # should pass

        over = prefix + (b'a' * (fill_len + 1)) + suffix
        self.assertEqual(len(over), MAX_RAW_BYTES + 1)
        with self.assertRaises(CanonicalizationError) as ctx:
            canonicalize(over)
        self.assertIn("MAX_RAW_BYTES", str(ctx.exception))

    def test_max_depth_boundary(self):
        # depth counted as nested object/array depth; MAX_DEPTH=64 allowed? reject >64.
        def nested(depth):
            # depth 1 => {"a":1}
            s = "1"
            for _ in range(depth):
                s = '{"a":' + s + '}'
            return s.encode('utf-8')

        canonicalize(nested(MAX_DEPTH))
        with self.assertRaises(CanonicalizationError):
            canonicalize(nested(MAX_DEPTH + 1))

    def test_max_coeff_digits_boundary(self):
        ok = ('{"x":1' + ('0' * (MAX_COEFF_DIGITS - 1)) + '}').encode()
        canonicalize(ok)
        bad = ('{"x":1' + ('0' * MAX_COEFF_DIGITS) + '}').encode()
        with self.assertRaises(CanonicalizationError) as ctx:
            canonicalize(bad)
        self.assertIn("coefficient", str(ctx.exception))

    def test_max_abs_exponent_boundary(self):
        ok = f'{{"x":1e{MAX_ABS_EXPONENT}}}'.encode()
        canonicalize(ok)
        bad = f'{{"x":1e{MAX_ABS_EXPONENT + 1}}}'.encode()
        with self.assertRaises(CanonicalizationError) as ctx:
            canonicalize(bad)
        self.assertIn("exponent", str(ctx.exception))

        ok_neg = f'{{"x":1e-{MAX_ABS_EXPONENT}}}'.encode()
        canonicalize(ok_neg)
        bad_neg = f'{{"x":1e-{MAX_ABS_EXPONENT + 1}}}'.encode()
        with self.assertRaises(CanonicalizationError):
            canonicalize(bad_neg)

    def test_derived_expanded_length_bound(self):
        # Accepted-input upper bound: 1 * 10^308 -> 1 followed by 308 zeros = 309 chars.
        inp = b'{"x":1e308}'
        got = canonicalize(inp)
        self.assertEqual(got, b'{"x":1' + b'0' * 308 + b'}')
        num = '1' + '0' * 308
        self.assertLessEqual(len(num), MAX_EXPANDED_NUMBER_LEN)
        self.assertLessEqual(len(num), MAX_DEFENSIVE_NUMBER_LEN)

        # Very small accepted exponent: 1e-308 -> "0." + 307 zeros + "1" length 310.
        got2 = canonicalize(b'{"x":1e-308}')
        num2 = got2.decode().split(':')[1][:-1]
        self.assertTrue(num2.startswith('0.'))
        self.assertLessEqual(len(num2), MAX_EXPANDED_NUMBER_LEN)

    def test_non_object_top_level_still_depth_checked(self):
        # arrays nest too
        s = '1'
        for _ in range(MAX_DEPTH + 1):
            s = '[' + s + ']'
        with self.assertRaises(CanonicalizationError):
            canonicalize(s.encode())

    def test_input_must_be_bytes(self):
        with self.assertRaises(CanonicalizationError):
            canonicalize('{"a":1}')  # type: ignore


class TestConfigCanonFixtures(unittest.TestCase):
    def test_repo_fixture_hashes(self):
        cases = [
            (
                'tests/fixtures/frozen_params.json',
                575,
                430,
                '0ca0696e775e2575e57ca3a076d8e75cfc6aafc647694bebe03e7c4dcd13ae67',
                '5ae44b2480bac9cbd227448be8b941716702de7dcbeb0ee0c5ae7a6a4bf4e671',
            ),
            (
                'tests/fixtures/frozen_params_noncanonical.json',
                575,
                430,
                '2ebf893175bc5585a33d9630c6db296d459703c23e03af4f41fb0aa1645552e3',
                '5ae44b2480bac9cbd227448be8b941716702de7dcbeb0ee0c5ae7a6a4bf4e671',
            ),
            (
                'tests/fixtures/byte_hash_variant.json',
                2649,
                1960,
                '9719db2048a0ddfd0f633187921bc124dcc5f7a8132a8a8d1465634246fef205',
                '1d50f8d5331acae61ec9bbaf16d1737a1988d260911df7abb1367f264f953770',
            ),
        ]
        for path, raw_len, canon_len, raw_sha, canon_sha in cases:
            raw = open(path, 'rb').read()
            self.assertEqual(len(raw), raw_len)
            self.assertEqual(sha256_hex(raw), raw_sha)
            canon = canonicalize(raw)
            self.assertEqual(len(canon), canon_len)
            self.assertEqual(sha256_hex(canon), canon_sha)
            self.assertFalse(canon.endswith(b'\n'))

    def test_frozen_fixtures_semantically_equal(self):
        a = open('tests/fixtures/frozen_params.json', 'rb').read()
        b = open('tests/fixtures/frozen_params_noncanonical.json', 'rb').read()
        self.assertNotEqual(sha256_hex(a), sha256_hex(b))
        self.assertEqual(canonicalize(a), canonicalize(b))
        self.assertEqual(canonical_sha256(a), canonical_sha256(b))


class TestConfigCanonMetadata(unittest.TestCase):
    def test_version_constants(self):
        self.assertEqual(CANON_VERSION, 'SCANLINE-config-canon-v1')
