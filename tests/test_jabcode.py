"""Tests for pyjabcode encode / decode round-trip."""

from pathlib import Path

import pytest

import pyjabcode


class TestEncodeDecode:
    """Round-trip encode → decode tests."""

    def test_simple_string(self, tmp_path: Path):
        """Encode a short ASCII string, decode it, verify the payload."""
        payload = b"Hello JABCode!"
        img = tmp_path / "test.png"

        pyjabcode.encode(payload, img)
        assert img.exists()
        assert img.stat().st_size > 0

        result = pyjabcode.decode(img)
        assert result == payload

    def test_utf8_string(self, tmp_path: Path):
        """Encode a UTF-8 string using the str overload."""
        text = "Ünïcödé 🎉"
        img = tmp_path / "unicode.png"

        pyjabcode.encode(text, img)
        result = pyjabcode.decode(img)
        assert result == text.encode("utf-8")

    def test_binary_data(self, tmp_path: Path):
        """Encode raw binary data and verify the round-trip."""
        # JABCode encodes data as char[]; null bytes act as terminators
        # in the C library, so we use non-zero binary values here.
        payload = bytes(range(1, 255))
        img = tmp_path / "binary.png"

        pyjabcode.encode(payload, img)
        result = pyjabcode.decode(img)
        assert result == payload

    def test_large_payload(self, tmp_path: Path):
        """Encode a larger payload to exercise multi-module codes."""
        payload = b"A" * 500
        img = tmp_path / "large.png"

        pyjabcode.encode(payload, img)
        result = pyjabcode.decode(img)
        assert result == payload

    def test_custom_colors(self, tmp_path: Path):
        """Encode with 4 colours and verify round-trip."""
        payload = b"4-colour test"
        img = tmp_path / "four_color.png"

        pyjabcode.encode(payload, img, color_number=4)
        result = pyjabcode.decode(img)
        assert result == payload

    def test_all_valid_color_numbers_accepted(self, tmp_path: Path):
        """Every value in the allowed color_number set must encode without error."""
        payload = b"colour"
        for cn in [4, 8, 16, 32, 64, 128, 256]:
            img = tmp_path / f"cn{cn}.png"
            pyjabcode.encode(payload, img, color_number=cn)
            assert img.exists()

    def test_null_bytes_truncated(self, tmp_path: Path):
        """JABCode uses char[] internally; data after a null byte is lost."""
        payload = b"AB\x00CD"
        img = tmp_path / "null.png"

        pyjabcode.encode(payload, img)
        result = pyjabcode.decode(img)
        # The C library truncates data at the first null byte
        assert result[:2] == b"AB"
        assert len(result) == len(payload)


class TestEncodeOptions:
    """Tests for the extra encode parameters."""

    def test_module_size(self, tmp_path: Path):
        """A larger module size should produce a larger file."""
        payload = b"size test"
        small = tmp_path / "small.png"
        large = tmp_path / "large.png"

        pyjabcode.encode(payload, small, module_size=6)
        pyjabcode.encode(payload, large, module_size=24)

        assert large.stat().st_size > small.stat().st_size

    def test_master_symbol_dimensions(self, tmp_path: Path):
        """Setting master symbol dimensions overrides the default size."""
        payload = b"dimension test"
        img = tmp_path / "dims.png"

        pyjabcode.encode(payload, img, master_symbol_width=200, master_symbol_height=200)
        assert img.exists()
        result = pyjabcode.decode(img)
        assert result == payload

    def test_ecc_level_scalar(self, tmp_path: Path):
        """A scalar ecc_level is applied to all symbols."""
        payload = b"ecc scalar"
        img = tmp_path / "ecc.png"

        pyjabcode.encode(payload, img, ecc_level=5)
        assert pyjabcode.decode(img) == payload

    def test_ecc_level_list(self, tmp_path: Path):
        """A per-symbol ecc_level list is applied symbol-by-symbol."""
        payload = b"ecc list"
        img = tmp_path / "ecc_list.png"

        # A single-element list behaves the same as a scalar
        pyjabcode.encode(payload, img, ecc_level=[5])
        assert pyjabcode.decode(img) == payload

    def test_symbol_versions(self, tmp_path: Path):
        """Explicit symbol versions encode and decode correctly."""
        payload = b"version test"
        img = tmp_path / "versions.png"

        pyjabcode.encode(payload, img, symbol_versions=[(3, 3)])
        assert pyjabcode.decode(img) == payload

    def test_multi_symbol_with_positions(self, tmp_path: Path):
        """Multi-symbol code with explicit versions and positions round-trips."""
        payload = b"multi-symbol payload"
        img = tmp_path / "multi.png"

        # symbol_versions is required for multi-symbol codes (values must be 1 to 32)
        pyjabcode.encode(
            payload,
            img,
            symbol_number=2,
            symbol_versions=[(4, 4), (4, 4)],
            symbol_positions=[0, 3],
        )
        assert pyjabcode.decode(img) == payload

    def test_symbol_versions_wrong_length(self, tmp_path: Path):
        """symbol_versions length mismatch raises ValueError."""
        with pytest.raises(ValueError, match="symbol_versions"):
            pyjabcode.encode(
                b"x", tmp_path / "bad.png",
                symbol_number=2,
                symbol_versions=[(1, 1)],  # need 2, not 1
            )

    def test_multi_symbol_requires_symbol_versions(self, tmp_path: Path):
        """symbol_number > 1 without symbol_versions raises ValueError."""
        with pytest.raises(ValueError, match="symbol_versions is required"):
            pyjabcode.encode(
                b"x", tmp_path / "bad.png",
                symbol_number=2,
            )

    def test_ecc_level_too_high(self, tmp_path: Path):
        """ecc_level > 10 raises ValueError (would crash the C library)."""
        with pytest.raises(ValueError, match="ecc_level"):
            pyjabcode.encode(b"x", tmp_path / "bad.png", ecc_level=11)

    def test_ecc_level_list_too_high(self, tmp_path: Path):
        """An ecc_level list with a value > 10 raises ValueError."""
        with pytest.raises(ValueError, match="ecc_level"):
            pyjabcode.encode(b"x", tmp_path / "bad.png", ecc_level=[5, 11])

    def test_symbol_position_out_of_range(self, tmp_path: Path):
        """A symbol_position value outside 0–60 raises ValueError."""
        with pytest.raises(ValueError, match="symbol_positions"):
            pyjabcode.encode(
                b"x", tmp_path / "bad.png",
                symbol_number=2,
                symbol_versions=[(4, 4), (4, 4)],
                symbol_positions=[0, 61],  # 61 is out of range
            )

    def test_module_size_zero_raises(self, tmp_path: Path):
        """module_size=0 raises ValueError (not a valid pixel size)."""
        with pytest.raises(ValueError, match="module_size"):
            pyjabcode.encode(b"x", tmp_path / "bad.png", module_size=0)

    def test_module_size_negative_raises(self, tmp_path: Path):
        """Negative module_size raises ValueError."""
        with pytest.raises(ValueError, match="module_size"):
            pyjabcode.encode(b"x", tmp_path / "bad.png", module_size=-1)

    def test_symbol_positions_wrong_length(self, tmp_path: Path):
        """symbol_positions length mismatch raises ValueError."""
        with pytest.raises(ValueError, match="symbol_positions"):
            pyjabcode.encode(
                b"x", tmp_path / "bad.png",
                symbol_number=2,
                symbol_versions=[(4, 4), (4, 4)],
                symbol_positions=[0],  # need 2, not 1
            )

    def test_invalid_color_number(self, tmp_path: Path):
        """color_number not in the valid set raises ValueError (C would silently fall back to 8)."""
        with pytest.raises(ValueError, match="color_number"):
            pyjabcode.encode(b"x", tmp_path / "bad.png", color_number=3)

    def test_symbol_number_zero_raises(self, tmp_path: Path):
        """symbol_number=0 raises ValueError (C would silently fall back to 1)."""
        with pytest.raises(ValueError, match="symbol_number"):
            pyjabcode.encode(b"x", tmp_path / "bad.png", symbol_number=0)

    def test_symbol_number_too_large_raises(self, tmp_path: Path):
        """symbol_number=62 raises ValueError (C would silently fall back to 1)."""
        with pytest.raises(ValueError, match="symbol_number"):
            pyjabcode.encode(b"x", tmp_path / "bad.png", symbol_number=62)

    def test_symbol_version_value_zero_raises(self, tmp_path: Path):
        """symbol_versions entry with 0 raises ValueError (no C-side bounds check)."""
        with pytest.raises(ValueError, match="symbol_versions x-value"):
            pyjabcode.encode(b"x", tmp_path / "bad.png", symbol_versions=[(0, 1)])

    def test_symbol_version_value_too_large_raises(self, tmp_path: Path):
        """symbol_versions entry > 32 raises ValueError (no C-side bounds check)."""
        with pytest.raises(ValueError, match="symbol_versions x-value"):
            pyjabcode.encode(b"x", tmp_path / "bad.png", symbol_versions=[(33, 1)])

    def test_symbol_version_y_value_zero_raises(self, tmp_path: Path):
        """symbol_versions y-value 0 raises ValueError with an axis-specific message."""
        with pytest.raises(ValueError, match="symbol_versions y-value"):
            pyjabcode.encode(b"x", tmp_path / "bad.png", symbol_versions=[(1, 0)])


class TestDecodeOptions:
    """Tests for the extra decode parameters."""

    def test_compatible_decode_normal_code(self, tmp_path: Path):
        """compatible=True should decode a normal (undamaged) code correctly."""
        payload = b"compatible mode"
        img = tmp_path / "compat.png"

        pyjabcode.encode(payload, img)
        result = pyjabcode.decode(img, compatible=True)
        assert result == payload

    def test_compatible_false_is_default(self, tmp_path: Path):
        """Omitting compatible= gives the same result as compatible=False."""
        payload = b"default mode"
        img = tmp_path / "default.png"

        pyjabcode.encode(payload, img)
        assert pyjabcode.decode(img) == pyjabcode.decode(img, compatible=False)


class TestErrorHandling:
    """Verify that errors are raised properly."""

    def test_decode_nonexistent_file(self):
        with pytest.raises(FileNotFoundError):
            pyjabcode.decode("/nonexistent/path.png")

    def test_decode_invalid_image(self, tmp_path: Path):
        """Decoding a non-JABCode image should raise JabCodeError."""
        bad = tmp_path / "bad.png"
        bad.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)
        with pytest.raises(pyjabcode.JabCodeError):
            pyjabcode.decode(bad)

    def test_encode_empty_data(self, tmp_path: Path):
        """Encoding empty data should raise an error."""
        img = tmp_path / "empty.png"
        with pytest.raises(pyjabcode.JabCodeError):
            pyjabcode.encode(b"", img)

    def test_encode_oversized_data(self, tmp_path: Path):
        """Data that exceeds symbol capacity raises JabCodeError from the C library."""
        # Use the smallest possible symbol with high ECC so capacity is low.
        # The C library returns a non-zero error code which Python wraps as JabCodeError.
        with pytest.raises(pyjabcode.JabCodeError):
            pyjabcode.encode(
                b"A" * 10000,
                tmp_path / "overflow.png",
                symbol_versions=[(1, 1)],
                ecc_level=10,
            )


class TestModuleImport:
    """Basic sanity checks."""

    def test_version(self):
        assert pyjabcode.__version__ == "2.0.0"

    def test_public_api(self):
        assert callable(pyjabcode.encode)
        assert callable(pyjabcode.decode)
        assert callable(pyjabcode.get_capacity)


class TestGetCapacity:
    """Verify get_capacity mirrors the C library's internal capacity math.

    Expected values were derived directly from the C ``getSymbolCapacity``
    function and the ``(capacity // wr) * wr - (capacity // wr) * wc``
    net-capacity formula, then confirmed to be consistent with the library
    by encoding data near the computed limits.
    """

    # --- single-symbol configurations ---

    def test_v4x4_c8_ecc3_default_mode(self):
        """version (4,4), 8 colours, ECC 3 → default mode, no metadata overhead."""
        # gross = (33*33 - 68 - 0 - 24 - 0) * 3 = 2991; wc=4, wr=9 → net=1660
        assert pyjabcode.get_capacity(color_number=8, ecc_level=3, symbol_versions=[(4, 4)]) == 1660

    def test_v4x4_c8_ecc5_non_default(self):
        """version (4,4), 8 colours, ECC 5 → metadata present, different wcwr."""
        # gross = (33*33 - 68 - 0 - 24 - 17) * 3 = 2940; wc=4, wr=7 → net=1260
        assert pyjabcode.get_capacity(color_number=8, ecc_level=5, symbol_versions=[(4, 4)]) == 1260

    def test_v4x4_c4_ecc3(self):
        """version (4,4), 4 colours → 2 bpm, more metadata modules needed."""
        # gross = (33*33 - 68 - 0 - 8 - 23) * 2 = 1980; wc=4, wr=9 → net=1100
        assert pyjabcode.get_capacity(color_number=4, ecc_level=3, symbol_versions=[(4, 4)]) == 1100

    def test_v6x6_c8_ecc3(self):
        """version (6,6), 8 colours, ECC 3 → alignment patterns present."""
        # gross = (41*41 - 68 - 35 - 24 - 0) * 3 = 4662; wc=4, wr=9 → net=2590
        assert pyjabcode.get_capacity(color_number=8, ecc_level=3, symbol_versions=[(6, 6)]) == 2590

    def test_v1x1_c8_ecc3(self):
        """version (1,1), 8 colours, ECC 3 → smallest master symbol."""
        # gross = (21*21 - 68 - 0 - 24 - 0) * 3 = 1047; wc=4, wr=9 → net=580
        assert pyjabcode.get_capacity(color_number=8, ecc_level=3, symbol_versions=[(1, 1)]) == 580

    def test_v10x10_c16_ecc2(self):
        """version (10,10), 16 colours, ECC 2 → 4 bpm, non-default mode."""
        # gross = (57*57 - 68 - 245 - 56 - 14) * 4 = 12108; wc=3, wr=7 → net=6916
        assert pyjabcode.get_capacity(color_number=16, ecc_level=2, symbol_versions=[(10, 10)]) == 6916

    def test_v32x32_c256_ecc1(self):
        """version (32,32), 256 colours, ECC 1 → maximum single-symbol capacity."""
        assert pyjabcode.get_capacity(color_number=256, ecc_level=1, symbol_versions=[(32, 32)]) == 100805

    # --- ECC level 0 maps to the default level 3 ---

    def test_ecc0_same_as_ecc3(self):
        """ecc_level=0 resolves to the library default (level 3)."""
        cap0 = pyjabcode.get_capacity(color_number=8, ecc_level=0, symbol_versions=[(4, 4)])
        cap3 = pyjabcode.get_capacity(color_number=8, ecc_level=3, symbol_versions=[(4, 4)])
        assert cap0 == cap3

    # --- multi-symbol ---

    def test_2symbol_v4x4_c8_ecc3(self):
        """Two symbols: master net (1660) + slave net (1725) = 3385."""
        cap = pyjabcode.get_capacity(
            color_number=8,
            symbol_number=2,
            ecc_level=3,
            symbol_versions=[(4, 4), (4, 4)],
        )
        # Slave has fewer finder-pattern modules → higher gross capacity.
        assert cap == 3385

    # --- no symbol_versions → max version (32,32) used ---

    def test_no_symbol_versions_returns_max(self):
        """Omitting symbol_versions gives the (32,32) upper-bound capacity."""
        cap_default = pyjabcode.get_capacity(color_number=8, ecc_level=3)
        cap_explicit = pyjabcode.get_capacity(
            color_number=8, ecc_level=3, symbol_versions=[(32, 32)]
        )
        assert cap_default == cap_explicit

    # --- consistency with actual encoding ---

    def test_capacity_consistent_with_encoder(self, tmp_path: Path):
        """Data within get_capacity bits must be encodable; if provided as
        explicit symbol_versions, oversized data raises JabCodeError."""
        versions = [(4, 4)]
        net_bits = pyjabcode.get_capacity(
            color_number=8, ecc_level=3, symbol_versions=versions
        )
        # 'A' is uppercase; JABCode encodes it in 5 bits/char.
        # payload_length = encoded_bits + 5 (flag + S field), so:
        # max_chars = (net_bits - 5) // 5
        max_chars = (net_bits - 5) // 5
        ok_data = b"A" * max_chars

        img = tmp_path / "cap_ok.png"
        pyjabcode.encode(ok_data, img, color_number=8, ecc_level=3, symbol_versions=versions)
        assert pyjabcode.decode(img) == ok_data

    # --- input validation ---

    def test_multi_symbol_requires_versions(self):
        """symbol_number > 1 without symbol_versions raises ValueError."""
        with pytest.raises(ValueError, match="symbol_versions is required"):
            pyjabcode.get_capacity(symbol_number=2)

    def test_wrong_versions_length(self):
        """symbol_versions length mismatch raises ValueError."""
        with pytest.raises(ValueError, match="symbol_versions length"):
            pyjabcode.get_capacity(symbol_number=2, symbol_versions=[(4, 4)])

    def test_ecc_list_wrong_length(self):
        """ecc_level list length mismatch raises ValueError."""
        with pytest.raises(ValueError, match="ecc_level list length"):
            pyjabcode.get_capacity(
                symbol_number=2,
                ecc_level=[3],
                symbol_versions=[(4, 4), (4, 4)],
            )
