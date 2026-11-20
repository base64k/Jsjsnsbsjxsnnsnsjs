#!/usr/bin/env bash
#
# The PC reference build, run headless: how far the port gets with the game.
# The Android build is the same code; this one runs on the CI's processor, so
# a failure here is a failure there too - and it says where the game stopped,
# which is what the porting work needs.
#
#   scripts/smoke_test.sh            # build and run
#   UP_SMOKE_SECONDS=180 scripts/smoke_test.sh
#
# The run's own report (games/up/build/port/report.txt) says why it stopped:
# an unimplemented syscall, a device register, a VIF or GS feature.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

GAME="games/up"
SECONDS_TO_RUN="${UP_SMOKE_SECONDS:-120}"
JOBS="${UP_JOBS:-$(nproc 2>/dev/null || echo 2)}"
BUILD="$GAME/build/linux/up"

log()  { printf '\033[1;34m[smoke]\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m[smoke]\033[0m %s\n' "$*"; }

ELF="$GAME/extracted/$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["executable"])' "$GAME/game.json")"
[ -f "$ELF" ] || { warn "no program extracted ($ELF) - run the extract stage first"; exit 1; }

GENERATED="$GAME/build/port/generated"
if [ ! -f "$GENERATED/dispatch.cpp" ]; then
    log "writing the dispatch table"
    python3 - <<'PY'
import sys
sys.path[:0] = ["engine/tools", "engine"]
from ps2decomp import game as game_config
import port
game = game_config.load("games/up")
print(port.generate(game))
PY
fi

log "building the PC reference build (clang, $JOBS jobs)"
# clang 19 or later: the VU code's calling convention (preserve_none) needs it.
CXX="clang++"
if command -v clang++-19 >/dev/null 2>&1; then CXX="clang++-19"; fi
CC="clang"
if command -v clang-19 >/dev/null 2>&1; then CC="clang-19"; fi
cmake -S "$GAME/port" -B "$BUILD" -G Ninja -DCMAKE_BUILD_TYPE=Release \
      -DCMAKE_C_COMPILER="$CC" -DCMAKE_CXX_COMPILER="$CXX" \
      -DPS2_GENERATED_DIR="$PWD/$GENERATED" -DPS2HOST_AVX2=OFF >/dev/null
cmake --build "$BUILD" -j "$JOBS" --target up

log "running the game headless for ${SECONDS_TO_RUN}s"
mkdir -p "$GAME/build/smoke"
set +e
SDL_VIDEODRIVER=dummy PS2HOST_RENDERER=sdl \
    xvfb-run -a "$BUILD/up" "$ELF" --disc "${UP_ISO:-disc/up.iso}" --no-memcard \
        --timeout "$SECONDS_TO_RUN" --frames "$GAME/build/smoke/frames" \
        > "$GAME/build/smoke/run.log" 2>&1
CODE=$?
set -e

log "the run ended with the code $CODE; its report:"
REPORT="$GAME/build/port/report.txt"
if [ -f "$REPORT" ]; then
    sed -n '/=== host report ===/,$p' "$REPORT" | head -80
else
    tail -40 "$GAME/build/smoke/run.log"
fi
log "the full log: $GAME/build/smoke/run.log"
