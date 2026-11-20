#!/usr/bin/env bash
#
# The hash of what the library is made of: the engine, the translated code,
# the dispatch table, the port's own files and the toolchain.
#
# The same hash means the same library - so a run whose code has not changed
# can take the library from the cache instead of compiling it again (the
# workflow's "The library from the cache").
#
#   scripts/apk_inputs_hash.sh

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

# A file of the engine, as it is upstream: the patches this repository makes
# to the build tree are hashed themselves, so the hash does not depend on
# whether the patch has been applied yet.
engine_hash() {
    if git -C engine cat-file -e "HEAD:$1" 2>/dev/null; then
        printf '%s ' "$1"
        git -C engine show "HEAD:$1" | sha256sum | cut -d' ' -f1
    elif [ -f "engine/$1" ]; then
        sha256sum "engine/$1"
    else
        printf '%s missing\n' "$1"
    fi
}

{
    # The engine's own commit, and the patch this repository makes to it.
    git -C engine rev-parse HEAD 2>/dev/null || echo "no engine"
    # The translated code and the dispatch table (the code found at run time
    # is in the table: it changes when a run finds more).
    ( find games/up/src/lifted games/up/build/port/generated -type f 2>/dev/null || true ) \
        | sort | xargs -r sha256sum
    # The manifest, the activity and the game's own files.
    engine_hash engine/tools/android.py
    engine_hash engine/android/java/org/ps2port/PortActivity.java
    sha256sum scripts/patch_android.py scripts/patch_language.py \
              games/up/port/overrides.cpp \
              games/up/port/CMakeLists.txt \
              games/up/port/icon.ico \
              games/up/game.json
    # The toolchain: a different NDK makes a different library.
    ls "${ANDROID_HOME:-/usr/local/lib/android/sdk}/ndk" 2>/dev/null || true
} | sha256sum | cut -d' ' -f1
