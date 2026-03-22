"""
pyjabcode – Python bindings for the JABCode C library.

Provides :func:`encode` and :func:`decode` for creating and reading
JAB Code colour barcodes (PNG images).

JABCode is a high-capacity 2D colour barcode that encodes more data than
traditional black-and-white symbols by using up to 256 colours.  A single
primary symbol can be extended with up to 60 secondary (slave) symbols to
increase capacity further.

Typical usage::

    import pyjabcode

    # Encode a string to a PNG file
    pyjabcode.encode("Hello, JABCode!", "hello.png")

    # Decode that file back to bytes
    payload = pyjabcode.decode("hello.png")
    print(payload.decode())          # Hello, JABCode!

Note
----
The JABCode C library stores payload data in a ``char[]`` array.  Null bytes
(``\\x00``) act as terminators in some internal paths, so binary payloads that
contain null bytes may not round-trip correctly.  Use non-zero byte sequences
for binary data.

CMYK output (``saveImageCMYK``) is not currently exposed because the TIFF
backend is compiled as a stub that always returns failure at runtime.
"""

from __future__ import annotations

import ctypes
import os
import platform
import site
from pathlib import Path

__all__ = ["encode", "decode", "JabCodeError"]
__version__ = "2.0.0"

# ---------------------------------------------------------------------------
# Locate the native shared library that ships inside the wheel
# ---------------------------------------------------------------------------

def _find_lib() -> ctypes.CDLL:
    """Locate and load the jabcode shared library bundled with the package.

    The function searches the package directory first, then every
    site-packages directory returned by :mod:`site`.  This covers both
    regular wheel installs (library next to ``__init__.py``) and editable
    installs (library in site-packages while source lives elsewhere).

    Returns
    -------
    ctypes.CDLL
        A loaded handle to ``libjabcode`` (or the platform-specific name).

    Raises
    ------
    OSError
        If the shared library cannot be found in any of the searched
        locations.
    """
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


def _make_jab_data(payload: bytes) -> ctypes.Structure:
    """Allocate a ``jab_data`` C struct with *payload* copied in.

    ``jab_data`` is a flexible-array struct::

        typedef struct {
            jab_int32 length;
            jab_char  data[];
        } jab_data;

    ctypes does not support flexible array members natively, so a concrete
    inner class is generated for each unique payload length.

    Parameters
    ----------
    payload:
        Raw bytes to store in the struct.

    Returns
    -------
    ctypes.Structure
        A concrete ctypes structure whose memory layout matches
        ``jab_data`` with ``length`` bytes of trailing data.
    """
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
    color_number: int = 8,
    symbol_number: int = 1,
    module_size: int | None = None,
    master_symbol_width: int = 0,
    master_symbol_height: int = 0,
    ecc_level: int | list[int] = 3,
    symbol_versions: list[tuple[int, int]] | None = None,
    symbol_positions: list[int] | None = None,
) -> Path:
    """Encode *data* into a JABCode and save it as a PNG image.

    Parameters
    ----------
    data:
        The payload to encode (bytes or UTF-8 string).
    filename:
        Destination path for the PNG image.
    color_number:
        Number of colours to use.  Must be one of 4, 8, 16, 32, 64, 128, or
        256.  Defaults to 8.
    symbol_number:
        Total number of JABCode symbols (1–61).  A value greater than 1
        produces a multi-symbol code with one primary and up to 60 secondary
        symbols.
    module_size:
        Size of one module (pixel) in the output image.  ``None`` uses the
        library default (12 pixels).  Ignored when *master_symbol_width* or
        *master_symbol_height* is set.
    master_symbol_width:
        Width of the primary symbol in pixels.  ``0`` means the width is
        derived from *module_size*.
    master_symbol_height:
        Height of the primary symbol in pixels.  ``0`` means the height is
        derived from *module_size*.
    ecc_level:
        Error-correction level(s).  Either a single integer applied to all
        symbols, or a list of integers with one entry per symbol (master
        first, then slaves in order).  Values range from 1 (lowest) to 10
        (highest); ``0`` uses the library default.  Defaults to 3 (≈ 6 %
        overhead).
    symbol_versions:
        Per-symbol side-version as a list of ``(x, y)`` tuples, ordered
        master-first.  Each value controls the number of modules along that
        axis and must be between 1 and 32.  **Required** for multi-symbol
        codes (*symbol_number* > 1); optional for single-symbol codes where
        ``(0, 0)`` lets the library choose the version automatically.  The
        list length must equal *symbol_number* if provided.
    symbol_positions:
        Position indices (0–60) for each symbol, ordered master-first, using
        the spiral layout defined in BSI TR-03137.  Only relevant for
        multi-symbol codes (*symbol_number* > 1); position 0 is always the
        master symbol.  The list length must equal *symbol_number* if
        provided.

    Returns
    -------
    Path
        The *filename* that was written.

    Raises
    ------
    ValueError
        If *module_size* is provided but less than 1.
    ValueError
        If any *ecc_level* value is outside the range 0–10.
    ValueError
        If *symbol_number* > 1 and *symbol_versions* is not provided.
    ValueError
        If *symbol_versions* or *symbol_positions* have the wrong length.
    ValueError
        If any value in *symbol_positions* is outside the range 0–60.
    JabCodeError
        If encoding or saving fails.

    Examples
    --------
    Simple encode::

        pyjabcode.encode("Hello!", "hello.png")

    High-ECC 4-colour code::

        pyjabcode.encode(b"important data", "safe.png", color_number=4, ecc_level=8)

    Two-symbol code with explicit versions and positions::

        pyjabcode.encode(
            "Long message",
            "multi.png",
            symbol_number=2,
            symbol_versions=[(4, 4), (4, 4)],
            symbol_positions=[0, 3],
        )
    """
    if isinstance(data, str):
        data = data.encode("utf-8")

    filename = Path(filename)

    # --- input validation (before touching C) ---
    if module_size is not None and module_size < 1:
        raise ValueError(
            f"module_size must be a positive integer, got {module_size!r}"
        )

    if isinstance(ecc_level, int):
        ecc_levels_list = [ecc_level] * symbol_number
    else:
        ecc_levels_list = list(ecc_level)
    for lvl in ecc_levels_list:
        if not (0 <= lvl <= 10):
            raise ValueError(
                f"ecc_level values must be between 0 and 10, got {lvl!r}"
            )

    if symbol_number > 1 and symbol_versions is None:
        raise ValueError(
            "symbol_versions is required when symbol_number > 1 — "
            "provide a list of (x, y) side-version tuples (values 1–32) "
            "with one entry per symbol"
        )

    if symbol_versions is not None and len(symbol_versions) != symbol_number:
        raise ValueError(
            f"symbol_versions length ({len(symbol_versions)}) must "
            f"equal symbol_number ({symbol_number})"
        )

    if symbol_positions is not None:
        if len(symbol_positions) != symbol_number:
            raise ValueError(
                f"symbol_positions length ({len(symbol_positions)}) must "
                f"equal symbol_number ({symbol_number})"
            )
        for pos in symbol_positions:
            if not (0 <= pos <= 60):
                # jab_symbol_pos[] has MAX_SYMBOL_NUMBER (61) entries at
                # indices 0–60.  The C library's own bounds check allows 61
                # through (off-by-one bug), which would crash at array access.
                raise ValueError(
                    f"symbol_positions values must be between 0 and 60, "
                    f"got {pos!r}"
                )

    # --- C call ---
    enc = _lib.createEncode(color_number, symbol_number)
    if not enc:
        raise JabCodeError("createEncode failed")

    try:
        if module_size is not None:
            enc.contents.module_size = module_size
        if master_symbol_width > 0:
            enc.contents.master_symbol_width = master_symbol_width
        if master_symbol_height > 0:
            enc.contents.master_symbol_height = master_symbol_height

        # ECC levels – accept a scalar or a per-symbol list
        for i, lvl in enumerate(ecc_levels_list):
            if lvl > 0 and i < symbol_number:
                enc.contents.symbol_ecc_levels[i] = lvl

        # Per-symbol side-version
        if symbol_versions is not None:
            for i, (vx, vy) in enumerate(symbol_versions):
                enc.contents.symbol_versions[i].x = vx
                enc.contents.symbol_versions[i].y = vy

        # Per-symbol position indices
        if symbol_positions is not None:
            for i, pos in enumerate(symbol_positions):
                enc.contents.symbol_positions[i] = pos

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


def decode(filename: str | os.PathLike, *, compatible: bool = False) -> bytes:
    """Decode a JABCode from a PNG image and return its payload.

    Parameters
    ----------
    filename:
        Path to the PNG image containing a JABCode.
    compatible:
        When ``True`` the library uses *compatible decode* mode
        (``COMPATIBLE_DECODE``), which is more tolerant of partial or
        damaged codes — it returns whatever data could be recovered even if
        some secondary symbols failed.  When ``False`` (the default) the
        stricter *normal decode* mode (``NORMAL_DECODE``) is used, which
        requires all symbols to decode successfully.

    Returns
    -------
    bytes
        The decoded payload.

    Raises
    ------
    FileNotFoundError
        If *filename* does not exist.
    JabCodeError
        If the image cannot be read or no valid JABCode is found.
    """
    filename = Path(filename)
    if not filename.exists():
        raise FileNotFoundError(filename)

    bmp = _lib.readImage(str(filename).encode("utf-8"))
    if not bmp:
        raise JabCodeError(f"readImage failed for {filename}")

    status = _c_int32(0)
    mode = 1 if compatible else 0
    jab_data_ptr = _lib.decodeJABCode(bmp, mode, ctypes.byref(status))

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

# Cache the C runtime library handle for free() calls
if platform.system() == "Windows":
    _crt = ctypes.CDLL("msvcrt")
else:
    _crt = ctypes.CDLL(None)  # default C library (libc on Linux/macOS)
_crt.free.argtypes = [ctypes.c_void_p]
_crt.free.restype = None


def _libc_free(ptr: ctypes.c_void_p) -> None:
    """Release *ptr* using the platform C runtime ``free()``.

    Memory returned by the jabcode library (bitmaps, decoded data) is
    allocated with the C ``malloc`` family and must be freed through the
    same runtime to avoid heap corruption.  This helper casts *ptr* to
    ``void *`` before calling ``free`` so callers can pass any ctypes
    pointer type.

    Parameters
    ----------
    ptr:
        Any ctypes pointer previously allocated by the jabcode library.
    """
    _crt.free(ctypes.cast(ptr, ctypes.c_void_p))
