"""
pyjabcode – Python bindings for the JABCode C library.

Provides :func:`encode`, :func:`decode`, and :func:`get_capacity` for
creating, reading, and sizing JAB Code colour barcodes (PNG images).

Note
----
The JABCode C library stores payload data in a ``char[]`` array.  Null bytes
(``\\x00``) act as terminators in some internal paths, so binary payloads that
contain null bytes may not round-trip correctly.  Use non-zero byte sequences
for binary data.
"""

from __future__ import annotations

import ctypes
import os
import platform
import site
from pathlib import Path

__all__ = ["encode", "decode", "get_capacity", "JabCodeError"]
__version__ = "2.0.0"

# ---------------------------------------------------------------------------
# Locate the native shared library that ships inside the wheel
# ---------------------------------------------------------------------------

def _find_lib() -> ctypes.CDLL:
    """Locate and load the jabcode shared library bundled with the package."""
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


_VALID_COLOR_NUMBERS = {4, 8, 16, 32, 64, 128, 256}


def _validate_common_params(
    color_number: int,
    symbol_number: int,
    ecc_level: int | list[int],
    symbol_versions: list[tuple[int, int]] | None,
) -> list[int]:
    """Validate parameters shared by :func:`encode` and :func:`get_capacity`.

    Returns the normalised per-symbol ECC level list.
    """
    if color_number not in _VALID_COLOR_NUMBERS:
        raise ValueError(
            f"color_number must be one of {sorted(_VALID_COLOR_NUMBERS)}, "
            f"got {color_number!r}"
        )

    if not (1 <= symbol_number <= 61):
        raise ValueError(
            f"symbol_number must be between 1 and 61, got {symbol_number!r}"
        )

    if symbol_number > 1 and symbol_versions is None:
        raise ValueError(
            "symbol_versions is required when symbol_number > 1 — "
            "provide a list of (x, y) side-version tuples (values 1–32) "
            "with one entry per symbol"
        )

    if symbol_versions is not None:
        if len(symbol_versions) != symbol_number:
            raise ValueError(
                f"symbol_versions length ({len(symbol_versions)}) must "
                f"equal symbol_number ({symbol_number})"
            )
        for vx, vy in symbol_versions:
            if not (1 <= vx <= 32):
                raise ValueError(
                    f"symbol_versions x-value must be between 1 and 32, "
                    f"got {vx!r}"
                )
            if not (1 <= vy <= 32):
                raise ValueError(
                    f"symbol_versions y-value must be between 1 and 32, "
                    f"got {vy!r}"
                )

    if isinstance(ecc_level, int):
        ecc_levels_list = [ecc_level] * symbol_number
    else:
        ecc_levels_list = list(ecc_level)
        if len(ecc_levels_list) != symbol_number:
            raise ValueError(
                f"ecc_level list length ({len(ecc_levels_list)}) must "
                f"equal symbol_number ({symbol_number})"
            )
    for lvl in ecc_levels_list:
        if not (0 <= lvl <= 10):
            raise ValueError(
                f"ecc_level values must be between 0 and 10, got {lvl!r}"
            )

    return ecc_levels_list


def _make_jab_data(payload: bytes) -> ctypes.Structure:
    """Allocate a ``jab_data`` C struct with *payload* copied in."""
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
        If *color_number* is not one of 4, 8, 16, 32, 64, 128, or 256.
    ValueError
        If *symbol_number* is outside the range 1–61.
    ValueError
        If *module_size* is provided but less than 1.
    ValueError
        If any *ecc_level* value is outside the range 0–10.
    ValueError
        If *symbol_number* > 1 and *symbol_versions* is not provided.
    ValueError
        If *symbol_versions* or *symbol_positions* have the wrong length.
    ValueError
        If any *symbol_versions* tuple value is outside the range 1–32.
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
    ecc_levels_list = _validate_common_params(
        color_number, symbol_number, ecc_level, symbol_versions
    )

    if module_size is not None and module_size < 1:
        raise ValueError(
            f"module_size must be a positive integer, got {module_size!r}"
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
            if lvl > 0:
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
    """Release *ptr* using the platform C runtime ``free()``."""
    _crt.free(ctypes.cast(ptr, ctypes.c_void_p))


# ---------------------------------------------------------------------------
# Capacity calculation (mirrors C getSymbolCapacity / ecclevel2wcwr logic)
# ---------------------------------------------------------------------------

# Number of alignment patterns per axis for symbol versions 1–32.
# Source: jab_ap_num[] in encoder.h.
_JAB_AP_NUM = [
    2, 2, 2, 2, 2,   # versions 1–5
    3, 3, 3, 3,      # versions 6–9
    4, 4, 4, 4,      # versions 10–13
    5, 5, 5, 5,      # versions 14–17
    6, 6, 6, 6,      # versions 18–21
    7, 7, 7, 7,      # versions 22–25
    8, 8, 8, 8,      # versions 26–29
    9, 9, 9,         # versions 30–32
]

# (wc, wr) LDPC parameters for ECC levels 0–10.
# Source: ecclevel2wcwr[][] in encoder.h.
_ECC_LEVEL_WCWR = [
    (4, 9),  # 0 (treated as default level 3)
    (3, 8),  # 1
    (3, 7),  # 2
    (4, 9),  # 3 (default)
    (3, 6),  # 4
    (4, 7),  # 5
    (4, 6),  # 6
    (3, 4),  # 7
    (4, 5),  # 8
    (5, 6),  # 9
    (6, 7),  # 10
]

# Metadata bit-lengths for the master symbol.
# Source: MASTER_METADATA_PART1_LENGTH / PART2_LENGTH / PART1_MODULE_NUMBER in decoder.h.
_META_PART1_BITS = 6
_META_PART2_BITS = 38
_META_PART1_MODULES = 4   # modules reserved for encoded Part I

_DEFAULT_ECC_LEVEL = 3    # DEFAULT_ECC_LEVEL in jabcode.h
_COLOR_PAL_NUMBER = 4     # COLOR_PALETTE_NUMBER in jabcode.h


def _symbol_capacity(
    color_number: int,
    effective_ecc: int,
    version_x: int,
    version_y: int,
    is_master: bool,
) -> tuple[int, int]:
    """Return *(gross_bits, net_bits)* for one symbol.

    Mirrors ``getSymbolCapacity`` in encoder.c plus the net-capacity
    formula from ``fitDataIntoSymbols``.
    """
    nb_modules_fp = 4 * 17 if is_master else 4 * 7
    nb_modules_palette = (min(color_number, 64) - 2) * _COLOR_PAL_NUMBER
    side_x = version_x * 4 + 17
    side_y = version_y * 4 + 17
    n_aps_x = _JAB_AP_NUM[version_x - 1]
    n_aps_y = _JAB_AP_NUM[version_y - 1]
    nb_modules_ap = (n_aps_x * n_aps_y - 4) * 7
    nb_bpm = color_number.bit_length() - 1  # integer log2

    nb_modules_metadata = 0
    if is_master:
        # Default mode (color_number==8 and ecc==3) needs no explicit metadata.
        is_default = color_number == 8 and effective_ecc == _DEFAULT_ECC_LEVEL
        if not is_default:
            nb_modules_metadata = (
                (_META_PART2_BITS + nb_bpm - 1) // nb_bpm + _META_PART1_MODULES
            )

    gross = (
        side_x * side_y
        - nb_modules_fp
        - nb_modules_ap
        - nb_modules_palette
        - nb_modules_metadata
    ) * nb_bpm

    wc, wr = _ECC_LEVEL_WCWR[effective_ecc]
    net = (gross // wr) * wr - (gross // wr) * wc
    return gross, net


def get_capacity(
    *,
    color_number: int = 8,
    symbol_number: int = 1,
    ecc_level: int | list[int] = 3,
    symbol_versions: list[tuple[int, int]] | None = None,
) -> int:
    """Return the net data capacity in bits for a JABCode configuration.

    The calculation mirrors the C library's internal ``getSymbolCapacity``
    function and the ECC net-capacity formula, so results are bit-perfect
    with what the library accepts.

    Parameters
    ----------
    color_number:
        Number of colours (4, 8, 16, 32, 64, 128, or 256).  Defaults to 8.
    symbol_number:
        Total number of symbols.  Defaults to 1.
    ecc_level:
        ECC level(s) (0–10; 0 maps to the library default of 3).
        Either a single integer applied to all symbols or a per-symbol list.
        Defaults to 3.
    symbol_versions:
        Per-symbol side versions as ``(x, y)`` tuples (1–32).  Required for
        multi-symbol codes.  For a single-symbol code with ``None`` the
        maximum version ``(32, 32)`` is used, giving an upper bound.

    Returns
    -------
    int
        Total net capacity in bits across all symbols.  This is the number
        of encoded bits available for data (before the small fixed per-symbol
        overhead of ~5 bits for mode flags).  Divide by 8 for a conservative
        byte estimate; plain ASCII text encodes more compactly (≈5 bits per
        uppercase character).

    Raises
    ------
    ValueError
        If *symbol_versions* is ``None`` and *symbol_number* > 1.
    ValueError
        If *symbol_versions* or *ecc_level* list length does not match
        *symbol_number*.

    Examples
    --------
    Maximum single-symbol capacity at default settings::

        pyjabcode.get_capacity()   # returns bits for version 32×32

    Capacity for a specific version::

        pyjabcode.get_capacity(color_number=8, ecc_level=3, symbol_versions=[(4, 4)])
    """
    ecc_levels = _validate_common_params(
        color_number, symbol_number, ecc_level, symbol_versions
    )

    # Resolve 0 → DEFAULT_ECC_LEVEL (mirrors C setMasterSymbolVersion logic).
    effective_eccs = [_DEFAULT_ECC_LEVEL if lvl == 0 else lvl for lvl in ecc_levels]

    versions = symbol_versions if symbol_versions is not None else [(32, 32)]

    total_net = 0
    for i, (vx, vy) in enumerate(versions):
        _, net = _symbol_capacity(color_number, effective_eccs[i], vx, vy, i == 0)
        total_net += net

    return total_net
