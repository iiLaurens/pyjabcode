<a href="https://jabcode.org">
    <img src="docs/img/jabcode_logo.png" alt="JABCode logo" title="JABCode" align="right" height="80" />
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

# Two-symbol code with explicit side-versions and positions
pyjabcode.encode(
    "Long payload that needs two symbols",
    "multi.png",
    symbol_number=2,
    symbol_versions=[(4, 4), (4, 4)],
    symbol_positions=[0, 3],
)

# Per-symbol ECC levels (master gets level 5, slave gets level 3)
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
    color_number: int = 0,
    symbol_number: int = 1,
    module_size: int = 0,
    master_symbol_width: int = 0,
    master_symbol_height: int = 0,
    ecc_level: int | list[int] = 0,
    symbol_versions: list[tuple[int, int]] | None = None,
    symbol_positions: list[int] | None = None,
) -> Path
```

Encodes *data* and writes a PNG to *filename*.  Returns the `Path` that was written.

| Parameter | Default | Description |
|---|---|---|
| `color_number` | `0` (→ 8) | Number of colours: 2, 4, 8, 16, 32, 64, 128, or 256. |
| `symbol_number` | `1` | Total symbols (1–61). |
| `module_size` | `0` (→ 12 px) | Module size in pixels. Overridden by `master_symbol_width/height`. |
| `master_symbol_width` | `0` (auto) | Primary symbol width in pixels. |
| `master_symbol_height` | `0` (auto) | Primary symbol height in pixels. |
| `ecc_level` | `0` (→ 3) | ECC level 1–10, or a list with one value per symbol. |
| `symbol_versions` | `None` | Per-symbol side-version as `[(x, y), …]`, values 1–32. **Required for multi-symbol codes.** Must have `symbol_number` entries. |
| `symbol_positions` | `None` | Per-symbol position index (0–60). Must have `symbol_number` entries. |

Raises `ValueError` if `symbol_versions` or `symbol_positions` have the wrong length.  
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
| `compatible` | `False` | Use compatible-decode mode to tolerate partial failures. |

Raises `FileNotFoundError` if *filename* does not exist.  
Raises `JabCodeError` if decoding fails.

### `pyjabcode.JabCodeError`

A `RuntimeError` subclass raised when the underlying C library reports a failure.

---

## Known Limitations

| Limitation | Detail |
|---|---|
| Null bytes in payload | The C library stores data in `char[]`; `\x00` bytes act as terminators in some internal paths and will corrupt binary payloads that contain them. |
| CMYK output | `saveImageCMYK` is not exposed — the TIFF backend is compiled as a stub and always fails at runtime. |
| Colour count | Only powers of two between 2 and 256 are accepted; other values silently fall back to the library default (8). |

---

## Licensing

### pyjabcode (Python wrapper)

The Python wrapper code in `pyjabcode/` is licensed under the **Apache License 2.0** — see [`LICENSE-APACHE`](LICENSE-APACHE).

### JABCode C library (bundled)

The JABCode C source code in `src/jabcode/` and the compiled `libjabcode` shared library bundled in the wheel are licensed under the **GNU Lesser General Public License v2.1 (LGPL-2.1)** — see [`LICENSE`](LICENSE).  The original library was developed by [Fraunhofer SIT](https://www.sit.fraunhofer.de/).

### Compatibility analysis

The LGPL-2.1 library is compiled into a standalone **shared library** (`libjabcode.so` / `.dylib` / `.dll`) and loaded at runtime by the Python wrapper via `ctypes`.  This is *dynamic linking* as defined by LGPL-2.1 Section 6, which explicitly allows non-LGPL applications to use an LGPL library in this way provided:

1. **The library is distributed as a separate, replaceable file** — satisfied: the wheel contains `libjabcode.so` as an independent shared library. Users can replace it with a modified version compiled from the LGPL source.
2. **The library source or a written offer for it is available** — satisfied: the full source is in `src/jabcode/` and in the [upstream repository](https://github.com/jabcode/jabcode).

**There is no license conflict.** Apache 2.0 applies to the Python wrapper code; LGPL-2.1 applies to the C library. Dynamic linking through `ctypes` keeps them legally separate.  The only constraint is that any *modification to the C library itself* must remain under LGPL-2.1.

---

## Project structure

```
pyjabcode/
├── pyjabcode/          # Python package (Apache 2.0)
│   └── __init__.py     # encode(), decode(), JabCodeError
├── src/
│   ├── jabcode/        # JABCode C library (LGPL-2.1)
│   ├── jabcodeReader/  # CLI reader application
│   └── jabcodeWriter/  # CLI writer application
├── cmake/              # Build helpers (TIFF stub)
├── tests/              # pytest test suite
├── CMakeLists.txt      # scikit-build-core build definition
├── LICENSE             # LGPL-2.1 (JABCode C library)
└── LICENSE-APACHE      # Apache 2.0 (pyjabcode Python wrapper)
```

---

## Links

- JABCode specification: [BSI TR-03137 Part 2](https://www.bsi.bund.de/EN/Service-Navi/Publications/TechnicalGuidelines/TR03137/BSITR03137.html)
- C library API documentation: [jabcode.github.io/jabcode](https://jabcode.github.io/jabcode/)
- Live demo: [jabcode.org/create](https://jabcode.org/create)

