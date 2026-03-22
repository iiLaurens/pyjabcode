<a href="https://jabcode.org">
    <img src="https://jabcode.org/wp-content/uploads/sites/96/2018/04/jabcode_logo.png" alt="JABCode logo" title="JABCode" align="right" height="80" />
</a>

# pyjabcode

**Python bindings for the [JABCode](https://jabcode.org) (Just Another Bar Code) C library.**

JABCode is a high-capacity 2D colour barcode capable of encoding significantly more data than traditional black-and-white codes by using up to 256 colours.  A single primary symbol can be linked to up to 60 secondary symbols to increase capacity further.

---

## Features

- Encode arbitrary bytes or UTF-8 strings to a JABCode PNG image.
- Decode a JABCode PNG image back to bytes.
- Control colour count, module size, error-correction level, symbol dimensions, and multi-symbol layout.
- Compatible-decode mode for recovering data from partially damaged codes.
- Pre-built wheels for Linux, macOS, and Windows — no C compiler required.

---

## Key Concepts

JABCode has its own terminology that differs from common barcodes such as QR codes.  The following definitions are helpful before reading the API reference.

**Module**  
The smallest unit of a JABCode image — a single coloured square in the grid.  Every module is rendered as a block of pixels in the output PNG; the `module_size` parameter controls how many pixels wide and tall each block is.

**Colour number**  
The size of the colour palette used to encode data.  JABCode supports palettes of 4, 8, 16, 32, 64, 128, or 256 distinct colours.  Using more colours allows each module to carry more bits, which increases data density for the same physical code size.  The default palette of 8 colours (Cyan, Magenta, Yellow, Black, Blue, Red, Green, White) is well-suited to most use cases.

**Symbol**  
A self-contained rectangular grid of modules.  A complete JABCode can consist of one or more symbols printed adjacently.

**Primary symbol (master)**  
The single, mandatory symbol in every JABCode.  It contains four finder patterns — one at each corner — that allow a scanner to locate, orient, and decode the code even when it is tilted or partially obscured.

**Secondary symbol (slave)**  
An optional extension symbol docked directly to the primary or to another secondary symbol.  Secondary symbols carry no finder patterns of their own; they rely on the primary for orientation.  Up to 60 secondary symbols may be attached, dramatically increasing the total data capacity.

**Version**  
A number from 1 to 32 that describes the size of one symbol along a single axis.  Version 1 corresponds to 21 modules; each increment adds 4 modules, so Version 32 is 145 modules on that side (formula: `4(v-1) + 21`).  Because JABCode symbols can be non-square, a version pair `(x, y)` is used — one value for the horizontal axis and one for the vertical axis.

**Symbol position**  
An integer index (0–60) that specifies where a symbol sits within a multi-symbol layout.  Position 0 is always the primary symbol.  Positions 1 and above follow the spiral placement order defined in the JABCode specification (BSI TR-03137), arranging secondary symbols around the primary and each other.

**ECC level (Error Correction Code level)**  
A value from 1 to 10 that controls how much of the code's area is dedicated to error-correction data.  Higher levels allow the code to be recovered even when a larger portion is damaged or unreadable, at the cost of reduced net data capacity.  Level 3 (the default) provides approximately 6% redundancy; Level 8 or above is recommended for codes that may suffer physical wear.

**Compatible decode mode**  
A lenient decoding strategy that returns whatever data could be recovered when one or more symbols in a multi-symbol code fail to decode.  Use this mode for damaged or partially obscured codes where a best-effort result is preferable to an outright failure.

---

## Installation

```bash
pip install pyjabcode
```

### Building from source

A C compiler, CMake ≥ 3.18, and Ninja are required.  The build system fetches
`zlib` and `libpng` automatically via CMake `FetchContent`.

```bash
git clone https://github.com/iiLaurens/pyjabcode.git
cd pyjabcode
pip install "scikit-build-core>=0.10" cmake ninja
pip install -e .
```

---

## Quick start

```python
import pyjabcode

# Encode a string and save to PNG
pyjabcode.encode("Hello, JABCode!", "hello.png")

# Decode the image back to bytes
payload = pyjabcode.decode("hello.png")
print(payload.decode())   # Hello, JABCode!
```

---

## Usage

### Encoding

```python
import pyjabcode

# Default settings (8 colours, module size 12 px, ECC level 3)
pyjabcode.encode("Hello!", "hello.png")

# 4-colour code with a higher error-correction level
pyjabcode.encode(b"critical data", "safe.png", color_number=4, ecc_level=8)

# Fix the master symbol to 300 × 300 pixels
pyjabcode.encode("Fixed size", "fixed.png", master_symbol_width=300, master_symbol_height=300)

# Two-symbol code with explicit versions and positions
pyjabcode.encode(
    "Long payload that needs two symbols",
    "multi.png",
    symbol_number=2,
    symbol_versions=[(4, 4), (4, 4)],  # each symbol: Version 4 × Version 4 (37 × 37 modules)
    symbol_positions=[0, 3],            # position 0 = primary; position 3 = first secondary
)

# Per-symbol ECC levels (primary gets level 5, secondary gets level 3)
pyjabcode.encode(
    "Mixed ECC",
    "mixed_ecc.png",
    symbol_number=2,
    ecc_level=[5, 3],
)
```

### Decoding

```python
import pyjabcode

# Normal decode (strict — all symbols must be readable)
payload = pyjabcode.decode("code.png")

# Compatible decode (lenient — returns partial data if some symbols fail)
payload = pyjabcode.decode("damaged.png", compatible=True)

print(payload.decode("utf-8"))
```

---

## API Reference

### `pyjabcode.encode`

```python
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
) -> Path
```

Encodes *data* and writes a PNG to *filename*.  Returns the `Path` that was written.

| Parameter | Default | Description |
|---|---|---|
| `color_number` | `8` | Size of the colour palette: 4, 8, 16, 32, 64, 128, or 256. More colours increase data density per module. |
| `symbol_number` | `1` | Total number of symbols (1–61): one primary plus up to 60 secondary symbols. |
| `module_size` | `None` (→ 12 px) | Pixel width and height of each module (must be ≥ 1). Overridden by `master_symbol_width/height`. |
| `master_symbol_width` | `0` (auto) | Desired width of the primary symbol in pixels; the library scales modules to fit. |
| `master_symbol_height` | `0` (auto) | Desired height of the primary symbol in pixels; the library scales modules to fit. |
| `ecc_level` | `3` | Error-correction level 1–10 (0 = library default), or a list with one value per symbol. Higher levels tolerate more damage but reduce net data capacity. |
| `symbol_versions` | `None` | Per-symbol size as `[(x, y), …]` version pairs (1–32 each), primary first. Version *v* gives `4(v-1) + 21` modules on that axis (e.g., Version 1 = 21, Version 4 = 33, Version 32 = 145 modules). **Required for multi-symbol codes.** |
| `symbol_positions` | `None` | Per-symbol position index (0–60), primary first, following the spiral layout in BSI TR-03137. Position 0 is always the primary symbol. |

Raises `ValueError` if `color_number` is not one of 4, 8, 16, 32, 64, 128, or 256,
if `symbol_number` is outside 1–61,
if `module_size` is less than 1, if any `ecc_level` value is outside 0–10,
if `symbol_number > 1` and `symbol_versions` is not provided, if `symbol_versions` or
`symbol_positions` have the wrong length, if any `symbol_versions` value is outside 1–32,
or if any `symbol_positions` value is outside 0–60.  
Raises `JabCodeError` if the C library reports an error.

### `pyjabcode.decode`

```python
def decode(
    filename: str | os.PathLike,
    *,
    compatible: bool = False,
) -> bytes
```

Decodes a JABCode PNG and returns the raw payload as `bytes`.

| Parameter | Default | Description |
|---|---|---|
| `compatible` | `False` | Enable compatible-decode mode: return partial data if one or more secondary symbols cannot be decoded, instead of raising an error. |

Raises `FileNotFoundError` if *filename* does not exist.  
Raises `JabCodeError` if decoding fails.

### `pyjabcode.JabCodeError`

A `RuntimeError` subclass raised when the underlying C library reports a failure.

---

## Known Limitations

| Limitation | Detail |
|---|---|
| Null bytes in payload | The C library stores data in `char[]`; `\x00` bytes act as terminators in some internal paths and will corrupt binary payloads that contain them. |

---

## Licensing

The Python wrapper code in `pyjabcode/` is licensed under the **Apache License 2.0** — see [`LICENSE-APACHE`](LICENSE-APACHE).

The JABCode C source code in `src/jabcode/` and the compiled `libjabcode` shared library bundled in the wheel are licensed under the **GNU Lesser General Public License v2.1 (LGPL-2.1)** — see [`LICENSE`](LICENSE).  The original library was developed by [Fraunhofer SIT](https://www.sit.fraunhofer.de/).

---

## Project structure

```
pyjabcode/
├── pyjabcode/          # Python package (Apache 2.0)
│   └── __init__.py
├── src/
│   ├── jabcode/        # JABCode C library (LGPL-2.1)
│   ├── jabcodeReader/  # CLI reader application
│   └── jabcodeWriter/  # CLI writer application
├── cmake/              # Build helpers
├── tests/              # pytest test suite
├── CMakeLists.txt
├── LICENSE             # LGPL-2.1
└── LICENSE-APACHE      # Apache 2.0
```

---

## Links

- JABCode specification: [BSI TR-03137 Part 2](https://www.bsi.bund.de/EN/Service-Navi/Publications/TechnicalGuidelines/TR03137/BSITR03137.html)
- C library API documentation: [jabcode.github.io/jabcode](https://jabcode.github.io/jabcode/)
- Live demo: [jabcode.org/create](https://jabcode.org/create)

