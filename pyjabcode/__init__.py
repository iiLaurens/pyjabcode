"""
pyjabcode – Python bindings for the JABCode C library.

Provides :func:`encode` and :func:`decode` for creating and reading
JAB Code colour barcodes (PNG images).
"""

from __future__ import annotations

import ctypes
import ctypes.util
import os
import platform
import site
import sys
import tempfile
from pathlib import Path
from typing import Optional

__all__ = ["encode", "decode", "JabCodeError"]
__version__ = "2.0.0"

# ---------------------------------------------------------------------------
# Locate the native shared library that ships inside the wheel
# ---------------------------------------------------------------------------

def _find_lib() -> ctypes.CDLL:
    """Return a loaded handle to the jabcode shared library."""
    pkg_dir = Path(__file__).resolve().parent

    system = platform.system()
    if system == "Linux":
        patterns = ["libjabcode.so"]
    elif system == "Darwin":
        patterns = ["libjabcode.dylib", "libjabcode.so"]
    elif system == "Windows":
        patterns = ["jabcode.dll", "libjabcode.dll"]
    else:
        patterns = ["libjabcode.so", "libjabcode.dylib"]

    # In editable installs the .so may live in site-packages while __file__
    # points to the source tree.  Search both locations.
    search_dirs = [pkg_dir]
    for sp in site.getsitepackages() + [site.getusersitepackages()]:
        candidate = Path(sp) / "pyjabcode"
        if candidate != pkg_dir:
            search_dirs.append(candidate)

    for d in search_dirs:
        for name in patterns:
            path = d / name
            if path.exists():
                return ctypes.CDLL(str(path))

    raise OSError(
        f"Cannot find the jabcode shared library. "
        f"Searched: {search_dirs}, patterns: {patterns}"
    )


_lib = _find_lib()

# ---------------------------------------------------------------------------
# C type definitions (mirrors jabcode.h)
# ---------------------------------------------------------------------------

_c_int32 = ctypes.c_int32
_c_byte = ctypes.c_ubyte
_c_char_p = ctypes.c_char_p


class _JabVector2d(ctypes.Structure):
    _fields_ = [("x", _c_int32), ("y", _c_int32)]


class _JabBitmap(ctypes.Structure):
    """Variable-length struct – pixel[] is accessed via pointer arithmetic."""
    _fields_ = [
        ("width", _c_int32),
        ("height", _c_int32),
        ("bits_per_pixel", _c_int32),
        ("bits_per_channel", _c_int32),
        ("channel_count", _c_int32),
        # pixel[] follows (flexible array member)
    ]


class _JabEncode(ctypes.Structure):
    _fields_ = [
        ("color_number", _c_int32),
        ("symbol_number", _c_int32),
        ("module_size", _c_int32),
        ("master_symbol_width", _c_int32),
        ("master_symbol_height", _c_int32),
        ("palette", ctypes.POINTER(_c_byte)),
        ("symbol_versions", ctypes.POINTER(_JabVector2d)),
        ("symbol_ecc_levels", ctypes.POINTER(_c_byte)),
        ("symbol_positions", ctypes.POINTER(_c_int32)),
        ("symbols", ctypes.c_void_p),
        ("bitmap", ctypes.POINTER(_JabBitmap)),
    ]


class _JabData(ctypes.Structure):
    """Fixed part – the flexible ``data[]`` member is read separately."""
    _fields_ = [
        ("length", _c_int32),
        # data[] follows
    ]


# ---------------------------------------------------------------------------
# Declare function signatures
# ---------------------------------------------------------------------------

_lib.createEncode.argtypes = [_c_int32, _c_int32]
_lib.createEncode.restype = ctypes.POINTER(_JabEncode)

_lib.destroyEncode.argtypes = [ctypes.POINTER(_JabEncode)]
_lib.destroyEncode.restype = None

_lib.generateJABCode.argtypes = [ctypes.POINTER(_JabEncode), ctypes.c_void_p]
_lib.generateJABCode.restype = _c_int32

_lib.saveImage.argtypes = [ctypes.POINTER(_JabBitmap), ctypes.c_char_p]
_lib.saveImage.restype = _c_byte

_lib.readImage.argtypes = [ctypes.c_char_p]
_lib.readImage.restype = ctypes.POINTER(_JabBitmap)

_lib.decodeJABCode.argtypes = [
    ctypes.POINTER(_JabBitmap),
    _c_int32,
    ctypes.POINTER(_c_int32),
]
_lib.decodeJABCode.restype = ctypes.POINTER(_JabData)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

class JabCodeError(RuntimeError):
    """Raised when the C library reports an error."""


def _make_jab_data(payload: bytes) -> ctypes.Array:
    """Allocate a C ``jab_data`` struct with *payload* copied in."""
    length = len(payload)

    class _JabDataSized(ctypes.Structure):
        _fields_ = [
            ("length", _c_int32),
            ("data", ctypes.c_char * length),
        ]

    obj = _JabDataSized()
    obj.length = length
    obj.data = payload
    return obj


def encode(
    data: bytes | str,
    filename: str | os.PathLike,
    *,
    color_number: int = 0,
    symbol_number: int = 1,
    module_size: int = 0,
    ecc_level: int = 0,
) -> Path:
    """Encode *data* into a JABCode and save it as a PNG image.

    Parameters
    ----------
    data:
        The payload to encode (bytes or UTF-8 string).
    filename:
        Destination path for the PNG image.
    color_number:
        Number of colours (4 or 8).  ``0`` uses the library default (8).
    symbol_number:
        Number of JABCode symbols (1–61).
    module_size:
        Module (pixel) size.  ``0`` uses the library default (12).
    ecc_level:
        Error-correction level (1–10).  ``0`` uses the library default (3).

    Returns
    -------
    Path
        The *filename* that was written.

    Raises
    ------
    JabCodeError
        If encoding or saving fails.
    """
    if isinstance(data, str):
        data = data.encode("utf-8")

    filename = Path(filename)

    enc = _lib.createEncode(color_number, symbol_number)
    if not enc:
        raise JabCodeError("createEncode failed")

    try:
        if module_size > 0:
            enc.contents.module_size = module_size
        if ecc_level > 0:
            for i in range(symbol_number):
                enc.contents.symbol_ecc_levels[i] = ecc_level

        jab_data = _make_jab_data(data)
        rc = _lib.generateJABCode(enc, ctypes.byref(jab_data))
        if rc != 0:
            raise JabCodeError("generateJABCode failed")

        ok = _lib.saveImage(enc.contents.bitmap, str(filename).encode("utf-8"))
        if not ok:
            raise JabCodeError("saveImage failed")
    finally:
        _lib.destroyEncode(enc)

    return filename


def decode(filename: str | os.PathLike) -> bytes:
    """Decode a JABCode from a PNG image and return its payload.

    Parameters
    ----------
    filename:
        Path to the PNG image containing a JABCode.

    Returns
    -------
    bytes
        The decoded payload.

    Raises
    ------
    JabCodeError
        If the image cannot be read or no JABCode is found.
    """
    filename = Path(filename)
    if not filename.exists():
        raise FileNotFoundError(filename)

    bmp = _lib.readImage(str(filename).encode("utf-8"))
    if not bmp:
        raise JabCodeError(f"readImage failed for {filename}")

    status = _c_int32(0)
    jab_data_ptr = _lib.decodeJABCode(bmp, 0, ctypes.byref(status))

    # Free the bitmap (allocated with malloc in C)
    _libc_free(bmp)

    if not jab_data_ptr:
        raise JabCodeError(
            f"decodeJABCode failed (status={status.value})"
        )

    length = jab_data_ptr.contents.length
    # The data[] array starts right after the length field
    data_offset = ctypes.sizeof(_JabData)
    raw_ptr = ctypes.cast(jab_data_ptr, ctypes.c_void_p).value + data_offset
    result = (ctypes.c_ubyte * length).from_address(raw_ptr)
    payload = bytes(result)

    # Free the jab_data (allocated with malloc in C)
    _libc_free(jab_data_ptr)

    return payload


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _libc_free(ptr):
    """Call C free() on a ctypes pointer."""
    ctypes.pythonapi.PyMem_RawFree  # noqa – just checking availability
    # Use the C library's free() via ctypes
    if platform.system() == "Windows":
        # On Windows, use msvcrt.free
        _crt = ctypes.CDLL("msvcrt")
    else:
        _crt = ctypes.CDLL(None)  # loads the default C library
    _crt.free.argtypes = [ctypes.c_void_p]
    _crt.free.restype = None
    _crt.free(ctypes.cast(ptr, ctypes.c_void_p))
