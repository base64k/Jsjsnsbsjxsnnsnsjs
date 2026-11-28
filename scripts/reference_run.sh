#!/usr/bin/env bash
#
# The reference run: the original game on PCSX2 (the official Linux AppImage),
# with the player's own BIOS dump (bios/, from scripts/fetch_bios.sh) and the
# player's own disc (disc/up.iso, from scripts/fetch_disc.sh). It shows what
# the real console does - the screens the port has to reach - and its EE / IOP
# console output is the first thing to compare the port's trace with.
#
#   scripts/reference_run.sh           # needs bios/ and disc/up.iso
#   UP_REFERENCE_SECONDS=900 scripts/reference_run.sh
#
# Output (reference/ - git-ignored, and only ci-results/reference/ is kept):
#   reference/shots/t<seconds>.png   screenshots of the whole display
#   reference/logs/pcsx2.log         the emulator's output (EE and IOP consoles)
#   reference/logs/xvfb.log          the virtual display
# The screenshots are the game's pictures: they are artifacts only, never
# committed. The BIOS is copied into reference/ and never printed.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

VERSION="${PCSX2_VERSION:-v2.8.2}"
ASSET="pcsx2-${VERSION}-linux-appimage-x64-Qt.AppImage"
URL="https://github.com/PCSX2/pcsx2/releases/download/${VERSION}/${ASSET}"
SECONDS_TOTAL="${UP_REFERENCE_SECONDS:-600}"
DISC="$REPO_ROOT/disc/${UP_DISC_IMAGE:-up.iso}"
REF="$REPO_ROOT/reference"

log() { printf '\033[1;34m[reference]\033[0m %s\n' "$*"; }
die() { printf '\033[1;31m[reference]\033[0m %s\n' "$*" >&2; exit 1; }

[ -f "$DISC" ] || die "no disc image at $DISC (run scripts/fetch_disc.sh)"

# ------------------------------------------------------------ the BIOS set ---
# The dump's own folder: the ROM0 with its ROM1, NVM, MEC and INF, as the
# dumper wrote them. PCSX2 reads the set from one folder.
ROM0="$(find "$REPO_ROOT/bios" -type f -iname '*.ROM0' | head -n 1 || true)"
[ -n "$ROM0" ] || die "no *.ROM0 under bios/ (run scripts/fetch_bios.sh with the secret set)"
BIOS_SRC="$(dirname "$ROM0")"

rm -rf "$REF"
mkdir -p "$REF/bios" "$REF/shots" "$REF/logs"
cp "$BIOS_SRC"/* "$REF/bios/"
BIOS_NAME="$(basename "$ROM0")"
log "BIOS set: $(ls "$REF/bios" | wc -l) files, main ROM $BIOS_NAME"

# ------------------------------------------------------------- the emulator ---
log "downloading PCSX2 $VERSION (the official Linux build)"
curl -fL --retry 3 --retry-delay 5 -o "$REF/$ASSET" "$URL" || die "the PCSX2 download failed"
chmod +x "$REF/$ASSET"
(cd "$REF" && "./$ASSET" --appimage-extract >/dev/null)
APP="$REF/squashfs-root"
BINDIR="$APP/usr/bin"
[ -x "$APP/AppRun" ] || die "no AppRun in the extracted AppImage"

# Portable mode: the settings and the BIOS live next to the binary.
touch "$BINDIR/portable.txt"
mkdir -p "$BINDIR/inis"
cat > "$BINDIR/inis/PCSX2.ini" <<EOF
[UI]
SettingsVersion = 1
SetupWizardIncomplete = false
ConfirmShutdown = false
StartPaused = false
PauseOnFocusLoss = false

[Folders]
Bios = $REF/bios

[Filenames]
BIOS = $BIOS_NAME

[EmuCore]
EnableFastBoot = true

[EmuCore/GS]
Renderer = 12

[Logging]
EnableEEConsole = true
EnableIOPConsole = true
EnableTimeStamps = true

[Audio]
OutputModule = nullout

[SPU2/Output]
OutputModule = nullout
EOF
log "settings written to $BINDIR/inis/PCSX2.ini"

# ------------------------------------------------------------- the display ---
export DISPLAY=:99
Xvfb :99 -screen 0 1280x1024x24 -nolisten tcp >"$REF/logs/xvfb.log" 2>&1 &
XVFB_PID=$!
sleep 3
kill -0 "$XVFB_PID" 2>/dev/null || die "Xvfb did not start (see $REF/logs/xvfb.log)"

# ------------------------------------------------------------------ the run ---
log "starting PCSX2 with the disc, for ${SECONDS_TOTAL}s"
(cd "$APP" && exec ./AppRun -portable -batch -fastboot -- "$DISC") \
    >"$REF/logs/pcsx2.log" 2>&1 &
PCSX2_PID=$!

# The first minutes: the logos and the intro movies wait for Start (Return by
# default on the keyboard), so press it now and then. After that the game is
# left alone and the screens are the record.
t=0
while [ "$t" -lt "$SECONDS_TOTAL" ]; do
    sleep 15
    t=$((t + 15))
    if ! kill -0 "$PCSX2_PID" 2>/dev/null; then
        log "PCSX2 exited at ${t}s"
        break
    fi
    if [ "$t" -le 180 ]; then
        WID="$(xdotool search --name 'PCSX2' 2>/dev/null | head -n 1 || true)"
        if [ -n "$WID" ]; then
            xdotool windowfocus --sync "$WID" key Return 2>/dev/null || true
        fi
    fi
    if [ $((t % 60)) -eq 0 ]; then
        import -window root "$REF/shots/t${t}.png" 2>/dev/null || true
    fi
done

if kill -0 "$PCSX2_PID" 2>/dev/null; then
    kill "$PCSX2_PID" 2>/dev/null || true
    sleep 5
    kill -9 "$PCSX2_PID" 2>/dev/null || true
    log "stopped PCSX2 after ${SECONDS_TOTAL}s"
fi
kill "$XVFB_PID" 2>/dev/null || true

log "log lines: $(wc -l < "$REF/logs/pcsx2.log")"
log "screenshots: $(ls "$REF/shots" | wc -l)"
