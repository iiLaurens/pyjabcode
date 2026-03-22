cmake_minimum_required(VERSION 3.18)
project(pyjabcode C)

include(FetchContent)

# All code (including dependencies) must be compiled with -fPIC because we
# link everything into a shared library.
set(CMAKE_POSITION_INDEPENDENT_CODE ON)

# ============================================================================
# 1. zlib  –  fetch, populate, add as subdirectory (EXCLUDE_FROM_ALL to
#    prevent its install() rules from interfering with our own).
# ============================================================================
FetchContent_Declare(
    zlib
    URL      https://github.com/madler/zlib/releases/download/v1.3.1/zlib-1.3.1.tar.gz
    URL_HASH SHA256=9a93b2b7dfdac77ceba5a558a580e74667dd6fede4585b91eefb60f03b72df23
)
set(ZLIB_BUILD_EXAMPLES OFF CACHE BOOL "" FORCE)
FetchContent_GetProperties(zlib)
if(NOT zlib_POPULATED)
    FetchContent_Populate(zlib)
    add_subdirectory(${zlib_SOURCE_DIR} ${zlib_BINARY_DIR} EXCLUDE_FROM_ALL)
endif()

# Tell libpng's find_package(ZLIB) where our zlib lives.
# The variables must be real paths (not target names / generator expressions)
# because FindZLIB.cmake stores them verbatim.
set(ZLIB_INCLUDE_DIR "${zlib_SOURCE_DIR}" CACHE PATH "" FORCE)
if(WIN32)
    set(ZLIB_LIBRARY "${zlib_BINARY_DIR}/zlibstatic.lib" CACHE FILEPATH "" FORCE)
else()
    set(ZLIB_LIBRARY "${zlib_BINARY_DIR}/libz.a" CACHE FILEPATH "" FORCE)
endif()

# ============================================================================
# 2. libpng  –  same pattern, EXCLUDE_FROM_ALL.
# ============================================================================
FetchContent_Declare(
    libpng
    URL      https://github.com/glennrp/libpng/archive/refs/tags/v1.6.43.tar.gz
    URL_HASH SHA256=fecc95b46cf05e8e3fc8a414750e0ba5aad00d89e9fdf175e94ff041caf1a03a
)
set(PNG_SHARED OFF CACHE BOOL "" FORCE)
set(PNG_STATIC ON  CACHE BOOL "" FORCE)
set(PNG_TESTS  OFF CACHE BOOL "" FORCE)
set(PNG_TOOLS  OFF CACHE BOOL "" FORCE)
FetchContent_GetProperties(libpng)
if(NOT libpng_POPULATED)
    FetchContent_Populate(libpng)
    add_subdirectory(${libpng_SOURCE_DIR} ${libpng_BINARY_DIR} EXCLUDE_FROM_ALL)
endif()

# ============================================================================
# 3. Tiny libtiff stub  –  satisfies the linker for TIFF symbols referenced
#    in image.c.  The Python wrapper only uses the PNG code-path, so these
#    stubs are never called at runtime.
# ============================================================================
add_library(tiff_stub STATIC "${CMAKE_SOURCE_DIR}/cmake/tiff_stub.c")
target_include_directories(tiff_stub PRIVATE
    "${CMAKE_SOURCE_DIR}/src/jabcode/include"
)

# ============================================================================
# 4. jabcode shared library
# ============================================================================
set(JABCODE_SRC_DIR "${CMAKE_SOURCE_DIR}/src/jabcode")

set(JABCODE_SOURCES
    ${JABCODE_SRC_DIR}/binarizer.c
    ${JABCODE_SRC_DIR}/decoder.c
    ${JABCODE_SRC_DIR}/detector.c
    ${JABCODE_SRC_DIR}/encoder.c
    ${JABCODE_SRC_DIR}/image.c
    ${JABCODE_SRC_DIR}/interleave.c
    ${JABCODE_SRC_DIR}/ldpc.c
    ${JABCODE_SRC_DIR}/mask.c
    ${JABCODE_SRC_DIR}/pseudo_random.c
    ${JABCODE_SRC_DIR}/sample.c
    ${JABCODE_SRC_DIR}/transform.c
)

add_library(jabcode SHARED ${JABCODE_SOURCES})

target_include_directories(jabcode PRIVATE
    ${JABCODE_SRC_DIR}
    ${JABCODE_SRC_DIR}/include
    # freshly-built headers
    ${libpng_SOURCE_DIR}
    ${libpng_BINARY_DIR}
    ${zlib_SOURCE_DIR}
    ${zlib_BINARY_DIR}
)

target_compile_definitions(jabcode PRIVATE _CRT_SECURE_NO_WARNINGS)

set_target_properties(jabcode PROPERTIES
    C_STANDARD 11
    C_STANDARD_REQUIRED ON
    POSITION_INDEPENDENT_CODE ON
)

if(WIN32)
    set_target_properties(jabcode PROPERTIES WINDOWS_EXPORT_ALL_SYMBOLS ON)
endif()

# Static-link image libraries.
# png_static already depends on zlibstatic so zlib is pulled in transitively.
target_link_libraries(jabcode PRIVATE png_static zlibstatic tiff_stub)
if(UNIX)
    target_link_libraries(jabcode PRIVATE m)
endif()

# ============================================================================
# 5. Install into the Python package tree  (scikit-build-core handles the
#    rest of the wheel layout).
# ============================================================================
install(TARGETS jabcode
    LIBRARY DESTINATION pyjabcode   # .so / .dylib
    RUNTIME DESTINATION pyjabcode   # .dll  (Windows)
)
