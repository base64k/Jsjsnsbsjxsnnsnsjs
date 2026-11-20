#!/usr/bin/env bash
#
# The hash of what the APK is made of, apart from the translated code: the
# library (the native code), the Java (the dex), the manifest's own files and
# the tools that make them.
#
# The same hash means the same APK - so a run whose package's inputs have not
# changed can take the APK from the cache instead of making it again (the
# workflow's "The APK from the cache").
#
#   scripts/apk_package_hash.sh

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

ABI="${UP_ABI:-arm64-v8a}"
case "$ABI" in
    arm64-v8a) DIR="arm64" ;;
    *)         DIR="$ABI" ;;
esac

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
    # The library: the native code itself (its bytes, not its name).
    LIB="games/up/build/port/android-$DIR/libup.stripped.so"
    if [ -f "$LIB" ]; then sha256sum "$LIB"; else echo "no library yet"; fi
    # The Java: the dex's own sources - the engine's (as they are upstream)
    # and the port's - and the patches this repository makes to them.
    if git -C engine rev-parse --git-dir >/dev/null 2>&1; then
        git -C engine ls-files 'android/java/*.java' | sort | while read -r f; do
            printf '%s ' "$f"
            git -C engine show "HEAD:$f" | sha256sum | cut -d' ' -f1
        done
    fi
    ( find games/up/port/android/java -name '*.java' -type f 2>/dev/null || true ) \
        | sort | xargs -r sha256sum
    sha256sum scripts/patch_android.py scripts/patch_language.py
    # The manifest's own files.
    engine_hash engine/tools/android.py
    sha256sum games/up/game.json games/up/port/icon.ico
    # The tools that make them (the build tools' version).
    ls "${ANDROID_HOME:-/usr/local/lib/android/sdk}/build-tools" 2>/dev/null || true
} | sha256sum | cut -d' ' -f1
