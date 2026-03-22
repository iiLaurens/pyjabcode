#!/usr/bin/env bash
# build.sh — Build jabcode library, jabcodeReader, and jabcodeWriter on Linux
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "=== jabcode build script ==="
echo "Platform: $(uname -s) $(uname -m)"
echo "Compiler: $(gcc --version | head -1)"
echo ""

# ---------------------------------------------------------------------------
# 1. Ensure system dependencies are present
# ---------------------------------------------------------------------------
echo "--- Checking dependencies (Debian/Ubuntu) ---"
MISSING_PKGS=()
for pkg in libtiff-dev libpng-dev zlib1g-dev; do
    if ! dpkg -s "$pkg" &>/dev/null; then
        MISSING_PKGS+=("$pkg")
    fi
done

if [[ ${#MISSING_PKGS[@]} -gt 0 ]]; then
    echo "Installing missing packages: ${MISSING_PKGS[*]}"
    sudo apt-get update -qq
    sudo apt-get install -y "${MISSING_PKGS[@]}"
else
    echo "All dependencies already installed."
fi
echo ""

# ---------------------------------------------------------------------------
# 2. Build the core jabcode static library
# ---------------------------------------------------------------------------
echo "--- Building jabcode library (libjabcode.a) ---"
cd "$SCRIPT_DIR/src/jabcode"
make clean
make
echo ""

# ---------------------------------------------------------------------------
# 3. Build jabcodeReader using system libraries
#    Override LIBFLAGS so the system-installed libtiff/libpng/zlib are used
#    instead of the bundled static libraries (which lack -fPIE).
# ---------------------------------------------------------------------------
echo "--- Building jabcodeReader ---"
cd "$SCRIPT_DIR/src/jabcodeReader"
make clean
make LIBFLAGS="-L../jabcode/build -ljabcode -ltiff -lpng -lz -lm"
echo ""

# ---------------------------------------------------------------------------
# 4. Build jabcodeWriter using system libraries
# ---------------------------------------------------------------------------
echo "--- Building jabcodeWriter ---"
cd "$SCRIPT_DIR/src/jabcodeWriter"
make clean
make LIBFLAGS="-L../jabcode/build -ljabcode -ltiff -lpng -lz -lm"
echo ""

# ---------------------------------------------------------------------------
# 5. Report results
# ---------------------------------------------------------------------------
echo "=== Build successful! ==="
echo "Artifacts:"
echo "  Library : $SCRIPT_DIR/src/jabcode/build/libjabcode.a"
echo "  Reader  : $SCRIPT_DIR/src/jabcodeReader/bin/jabcodeReader"
echo "  Writer  : $SCRIPT_DIR/src/jabcodeWriter/bin/jabcodeWriter"
