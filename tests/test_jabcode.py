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


class TestModuleImport:
    """Basic sanity checks."""

    def test_version(self):
        assert pyjabcode.__version__ == "2.0.0"

    def test_public_api(self):
        assert callable(pyjabcode.encode)
        assert callable(pyjabcode.decode)
