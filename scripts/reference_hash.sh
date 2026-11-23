#!/usr/bin/env bash
#
# The hash of what the PC reference build is made of: the engine, the port's
# own build files and the compiler.
#
# The same hash means the same build - so a run that only needs to translate
# the code the last run found (the discovery's rounds) takes the build from
# the cache instead of making it again from nothing: the build is the port's
# slowest part after the translation itself.
#
#   scripts/reference_hash.sh

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

{
    # The engine's own commit, and the port's own build files.
    git -C engine rev-parse HEAD 2>/dev/null || echo "no engine"
    # The patches that change the engine's build tree (scripts/patch_*.py).
    sha256sum scripts/patch_*.py 2>/dev/null || true
    # The debugging patches applied to the engine (scripts/engine_*.patch).
    sha256sum scripts/engine_*.patch 2>/dev/null || true
    sha256sum games/up/port/CMakeLists.txt games/up/port/overrides.cpp \
              games/up/game.json 2>/dev/null || true
    # The place the repository is in: the build's cache holds absolute paths (CMakeCache).
    echo "$REPO_ROOT"
    # The compiler (clang 19 or later: the VU code's calling convention).
    ( clang++ --version 2>/dev/null || clang++-19 --version 2>/dev/null || true ) | head -1
} | sha256sum | cut -d' ' -f1
