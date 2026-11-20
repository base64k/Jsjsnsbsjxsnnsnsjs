#!/usr/bin/env bash
#
# The hash of what the APK is made of: the engine, the translated code, the
# dispatch table, the game's own files and the manifest.
#
# The same hash means the same library and the same APK - so a run whose code
# has not changed can take the library from the cache instead of compiling it
# again (the workflow's "The library from the cache").
#
#   scripts/apk_inputs_hash.sh

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

{
    # The engine's own commit, and the patch this repository makes to it.
    git -C engine rev-parse HEAD 2>/dev/null || echo "no engine"
    # The translated code and the dispatch table (the code found at run time
    # is in the table: it changes when a run finds more).
    ( find games/up/src/lifted games/up/build/port/generated -type f 2>/dev/null || true ) \
        | sort | xargs -r sha256sum
    # The manifest, the activity and the game's own files.
    sha256sum engine/tools/android.py \
              engine/android/java/org/ps2port/PortActivity.java \
              games/up/port/overrides.cpp \
              games/up/port/icon.ico \
              games/up/game.json
    # The toolchain: a different NDK makes a different library.
    ls "${ANDROID_HOME:-/usr/local/lib/android/sdk}/ndk" 2>/dev/null || true
} | sha256sum | cut -d' ' -f1
