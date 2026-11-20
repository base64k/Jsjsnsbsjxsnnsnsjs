#!/usr/bin/env bash
#
# The port's build, from the player's disc image to the APK. The steps are the
# engine's (engine/tools): the executable is taken out of the disc, analysed,
# decompiled to C++, checked against the original machine code, and compiled
# for Android.
#
#   scripts/build_apk.sh                # everything
#   scripts/build_apk.sh --stage apk    # only the last stage
#   scripts/build_apk.sh --jobs 4       # how many processes to work in parallel
#
# Stages: disc, extract, analyze, derive, lift, host, apk. Each one is skipped
# when its result is already there, so a second run only does what is missing
# (and the CI's cache keeps the slow ones between runs).

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

GAME="games/up"
ENGINE="engine"
ISO="${UP_ISO:-disc/up.iso}"
JOBS="${UP_JOBS:-$(nproc 2>/dev/null || echo 2)}"
STAGES="disc extract analyze derive lift host apk"
ABI="${UP_ABI:-arm64-v8a}"

while [ $# -gt 0 ]; do
    case "$1" in
        --stage) STAGES="$2"; shift 2 ;;
        --jobs)  JOBS="$2"; shift 2 ;;
        --iso)   ISO="$2"; shift 2 ;;
        --abi)   ABI="$2"; shift 2 ;;
        -h|--help) sed -n '2,20p' "$0"; exit 0 ;;
        *) echo "unknown option: $1" >&2; exit 2 ;;
    esac
done

log()  { printf '\033[1;34m[build]\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m[build]\033[0m %s\n' "$*"; }
die()  { printf '\033[1;31m[build]\033[0m %s\n' "$*" >&2; exit 1; }
has()  { case " $STAGES " in *" $1 "*) return 0 ;; *) return 1 ;; esac; }

[ -d "$ENGINE" ] || die "the engine submodule is missing: git submodule update --init --recursive"

# The executable's name, as the disc's SYSTEM.CNF has it - and as the port's
# game.json must have it.
EXECUTABLE="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["executable"])' "$GAME/game.json")"

# --------------------------------------------------------------- 1. the disc ---

if has disc; then
    bash scripts/fetch_disc.sh
fi
[ -f "$ISO" ] || die "no disc image at $ISO (run scripts/fetch_disc.sh)"

log "the disc image: $ISO"

# The disc's SYSTEM.CNF: the name of its program. Compared with game.json's, so
# that a wrong image is caught here and not three hours later.
SYSTEM_CNF="$(python3 - "$ISO" <<'PY'
import re, sys
sys.path.insert(0, "engine")
try:
    from ps2decomp.iso9660 import Iso9660
    with Iso9660.open(sys.argv[1]) as iso:
        text = iso.read_file(iso.find("SYSTEM.CNF")).decode("ascii", "replace")
except Exception as exc:
    print("NOT-A-DISC: %s" % exc)
    raise SystemExit(0)
m = re.search(r"BOOT2\s*=\s*cdrom0?:\\?([^;\s]+)", text, re.I)
print(m.group(1).lstrip("\\/") if m else "")
PY
)"
case "$SYSTEM_CNF" in
    NOT-A-DISC:*)
        die "$ISO is not a PS2 disc image: ${SYSTEM_CNF#NOT-A-DISC:}" ;;
esac
if [ -n "$SYSTEM_CNF" ] && [ "$SYSTEM_CNF" != "$EXECUTABLE" ]; then
    die "the disc's program is '$SYSTEM_CNF', but $GAME/game.json says '$EXECUTABLE'.
      Fix the 'executable' field in $GAME/game.json and commit it."
fi
log "the disc's program: $SYSTEM_CNF"

# ------------------------------------------------------------ 2. the program ---

if has extract; then
    [ -f "$GAME/extracted/$EXECUTABLE" ] || {
        log "taking the program out of the disc"
        python3 "$ENGINE/tools/isotool.py" extract "$ISO" "$EXECUTABLE" -o "$GAME/extracted/"
    }
fi
[ -f "$GAME/extracted/$EXECUTABLE" ] || die "the program was not extracted"

# -------------------------------------------------------------- 3. analysis ---

if has analyze; then
    [ -f "$GAME/build/functions.json" ] || {
        log "analysing the program"
        python3 "$ENGINE/tools/analyze.py" --game "$GAME"
    }
    [ -f "$GAME/config/names.csv" ] || {
        log "naming the functions the evidence supports"
        python3 "$ENGINE/tools/signatures.py" --game "$GAME" name
    }
fi
[ -f "$GAME/build/functions.json" ] || die "the analysis is missing ($GAME/build/functions.json)"

# ----------------------------------------------------------- 4. derivation ---

if has derive; then
    if [ ! -d "$GAME/src/generated" ] || [ -z "$(ls -A "$GAME/src/generated" 2>/dev/null)" ]; then
        log "deriving the program's functions (this takes a while: $JOBS processes)"
        log "note: the derived tier is the readable one; the port runs on the lifted code, so this stage is optional"
        python3 "$ENGINE/tools/derive.py" --game "$GAME" --emit --csv --jobs "$JOBS"
    fi
fi

# --------------------------------------------------------------- 5. lifting ---

# The structured form of a function (loops, ifs, named locals) is a second
# translation of the machine code, checked like the first one - and the check
# needs the engine's C++ checker, which runs on MSVC (Windows) only. Where it
# cannot run, the plain lifted form is emitted anyway (marked NOT VERIFIED),
# so on Linux the structuring is skipped: it would cost the time and buy
# nothing. UP_STRUCTURE=1 forces it.
LIFT_ARGS="--emit --csv --jobs $JOBS"
if [ "${UP_STRUCTURE:-0}" = "1" ] || [ "$(uname -s)" = "MINGW"* ] || [ "$(uname -s)" = "MSYS"* ] || [ "$(uname -s)" = "Windows_NT" ]; then
    LIFT_ARGS="$LIFT_ARGS --structure"
else
    log "no C++ checker here (it needs MSVC): the lifted code is emitted unverified, as it stands"
fi

if has lift; then
    if [ ! -d "$GAME/src/lifted" ] || [ -z "$(ls -A "$GAME/src/lifted" 2>/dev/null)" ]; then
        log "lifting the functions to C++ (this takes a while: $JOBS processes)"
        # shellcheck disable=SC2086
        python3 "$ENGINE/tools/lift.py" --game "$GAME" $LIFT_ARGS
    fi
fi
[ -d "$GAME/src/lifted" ] && [ -n "$(ls -A "$GAME/src/lifted" 2>/dev/null)" ] \
    || die "no translated sources ($GAME/src/lifted) - the lift stage did not finish"

# ------------------------------------------------- 6. the host's build tools ---

# The Android build compiles the shaders with a glslang made for the PC (the
# cross build has no one), and takes SDL's Java sources from the same place:
# engine/tools/android.py looks for both in the PC build's folder.

if has host; then
    PC_BUILD="$GAME/build/port/cmake"
    if [ ! -x "$PC_BUILD/_deps/glslang-build/StandAlone/glslang" ]; then
        log "preparing the host's build tools (glslang, SDL's sources)"
        # Only glslang is built here (the shaders' compiler) and SDL's sources
        # are only read (the APK's Java comes from them), so SDL needs no
        # X11 or Wayland: SDL_UNIX_CONSOLE_BUILD skips the check for them.
        cmake -S "$ENGINE/host" -B "$PC_BUILD" -G Ninja -DCMAKE_BUILD_TYPE=Release \
              -DSDL_UNIX_CONSOLE_BUILD=ON >/dev/null
        cmake --build "$PC_BUILD" --target glslang-standalone -j "$JOBS"
    fi
    [ -d "$PC_BUILD/_deps/sdl3-src" ] || die "SDL's sources are missing ($PC_BUILD/_deps/sdl3-src)"
fi

# ------------------------------------------------------------------ 7. the APK ---

if has apk; then
    log "building the APK ($ABI)"
    python3 "$ENGINE/tools/android.py" --game "$GAME" apk --abi "$ABI"
    APK="$(find "$GAME/build/android" -name '*.apk' | head -1)"
    [ -n "$APK" ] || die "no APK was built"
    mkdir -p build
    cp "$APK" "build/up-android.apk"
    log "the APK: build/up-android.apk ($(du -h build/up-android.apk | cut -f1))"
fi
