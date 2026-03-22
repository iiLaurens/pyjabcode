/**
 * Minimal stubs for the libtiff functions referenced by image.c.
 *
 * The Python wrapper only uses the PNG encode / decode path, so these
 * stubs are never called at runtime.  They exist solely to let the
 * linker resolve the symbols when building the shared library.
 */

#include <stddef.h>

/* Forward-declare opaque TIFF handle */
typedef struct tiff TIFF;

/* Minimal type aliases used by the stubs */
typedef unsigned int   uint32;
typedef unsigned short uint16;
typedef int            tmsize_t;
typedef unsigned int   ttag_t;
typedef unsigned int   tstrip_t;

TIFF *TIFFOpen(const char *filename, const char *mode) {
    (void)filename; (void)mode;
    return NULL;
}

void TIFFClose(TIFF *tif) {
    (void)tif;
}

int TIFFSetField(TIFF *tif, ttag_t tag, ...) {
    (void)tif; (void)tag;
    return 0;
}

uint32 TIFFDefaultStripSize(TIFF *tif, uint32 request) {
    (void)tif; (void)request;
    return 0;
}

tmsize_t TIFFWriteScanline(TIFF *tif, void *buf, uint32 row, uint16 sample) {
    (void)tif; (void)buf; (void)row; (void)sample;
    return -1;
}
