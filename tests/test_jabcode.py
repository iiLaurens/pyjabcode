"""Tests for pyjabcode encode / decode round-trip."""

import os
import tempfile
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
