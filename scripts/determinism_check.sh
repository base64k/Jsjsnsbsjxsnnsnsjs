#!/usr/bin/env bash
# Determinism check: the same reference build, the same arguments, run twice.
# Where the two reports first differ is where the run stops being repeatable
# (the same method as the golden-trace diff: the first divergence is the lead).
#
# It needs the build of scripts/smoke_test.sh (games/up/build/linux/up) and the
# extracted program. It writes games/up/build/determinism/: the two reports, the
# report with the wall-clock lines taken out, and summary.txt.
#
#   UP_DET_SECONDS  how long each run goes (default 150)
#   UP_SMOKE_WATCH  the same watched addresses as the smoke run (optional)

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

GAME="games/up"
SECONDS_TO_RUN="${UP_DET_SECONDS:-150}"
BUILD="$GAME/build/linux/up"
OUT="$GAME/build/determinism"
ELF="$GAME/extracted/$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["executable"])' "$GAME/game.json")"

log() { printf '\033[1;34m[determinism]\033[0m %s\n' "$*"; }

[ -x "$BUILD" ] || { log "no build at $BUILD (the smoke run builds it)"; exit 1; }
[ -f "$ELF" ] || { log "no program at $ELF"; exit 1; }

rm -rf "$OUT"
mkdir -p "$OUT"

local_watch=()
for w in ${UP_SMOKE_WATCH//,/ }; do local_watch+=(--watch-write "$w"); done

headless=()
command -v xvfb-run >/dev/null 2>&1 && headless=(xvfb-run -a)

for i in 1 2; do
    # The same discovered list for both runs: the translated code they start with.
    if [ -f "$GAME/build/port/discovered.txt" ]; then
        cp "$GAME/build/port/discovered.txt" "$OUT/discovered-$i.txt"
    else
        : > "$OUT/discovered-$i.txt"
    fi
    log "run $i of 2: ${SECONDS_TO_RUN}s"
    set +e
    SDL_VIDEODRIVER=dummy PS2HOST_RENDERER=sdl \
        "${headless[@]+"${headless[@]}"}" "$BUILD" "$ELF" \
            --disc "${UP_ISO:-disc/up.iso}" --no-memcard \
            --audio --iop-trace ${local_watch[@]+"${local_watch[@]}"} \
            --timeout "$SECONDS_TO_RUN" --frames "$OUT/frames-$i" \
            --frames-every 1 --frames-limit 20 --discover "$OUT/discovered-$i.txt" \
            > "$OUT/run-$i.txt" 2>&1
    echo "exit $?" >> "$OUT/run-$i.txt"
    set -e
done

# The lines that differ run to run by the clock alone are taken out: the IOP's
# and the loader's "(wall)" times. What is left must be the same in every run.
for i in 1 2; do
    grep -v "(wall)" "$OUT/run-$i.txt" > "$OUT/run-$i.nowall.txt" || true
done

{
    echo "the two runs, the wall-clock lines taken out"
    echo "lines: run 1 $(wc -l < "$OUT/run-1.nowall.txt"), run 2 $(wc -l < "$OUT/run-2.nowall.txt")"
    echo "stop in run 1: $(grep -m1 '^stopped' "$OUT/run-1.txt" || echo '(none)')"
    echo "stop in run 2: $(grep -m1 '^stopped' "$OUT/run-2.txt" || echo '(none)')"
    if cmp -s "$OUT/run-1.nowall.txt" "$OUT/run-2.nowall.txt"; then
        echo "IDENTICAL: the runs are the same"
    else
        first="$(diff "$OUT/run-1.nowall.txt" "$OUT/run-2.nowall.txt" | head -n 1 || true)"
        echo "DIFFERENT: first difference at $first"
        echo "--- run 1 around it:"
        n="${first%%[acd,]*}"; n="${n%%[!0-9]*}"; n="${n:-1}"
        sed -n "$((n > 3 ? n - 3 : 1)),$((n + 3))p" "$OUT/run-1.nowall.txt"
        echo "--- run 2 around it:"
        sed -n "$((n > 3 ? n - 3 : 1)),$((n + 3))p" "$OUT/run-2.nowall.txt"
    fi
} > "$OUT/summary.txt"

cat "$OUT/summary.txt"
