#!/usr/bin/env bash
#
# Fetch the game's disc image - the player's own copy - and put it where the
# port expects it (disc/up.iso).
#
# The image is not in the repository and never will be: it is the player's
# property. This script gets it from the player's own Google Drive file (the
# link the player shared, read-only, with anyone who has it) so that a CI
# runner can do the work without the image ever entering the repository.
#
#   scripts/fetch_disc.sh                 # the shared Drive file
#   UP_DRIVE_FILE_ID=<id> scripts/fetch_disc.sh
#   UP_DISC_URL=<direct url> scripts/fetch_disc.sh
#   UP_DISC_FILE=/path/to/up.iso scripts/fetch_disc.sh   # a local copy
#
# What it does: downloads the archive, unpacks it, finds the disc image inside
# (a single .iso, a .cue with its .bin, or a split image - the parts joined),
# and leaves it at disc/up.iso. Already there? It is left alone.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

DRIVE_FILE_ID="${UP_DRIVE_FILE_ID:-1LIzZFzNoXUteK5fnJLT1P6vGoIxg1fDA}"
DISC_URL="${UP_DISC_URL:-}"
DISC_FILE="${UP_DISC_FILE:-}"
DISC_DIR="${UP_DISC_DIR:-disc}"
IMAGE="${UP_DISC_IMAGE:-up.iso}"

mkdir -p "$DISC_DIR"

log() { printf '\033[1;34m[disc]\033[0m %s\n' "$*"; }
die() { printf '\033[1;31m[disc]\033[0m %s\n' "$*" >&2; exit 1; }

# ---------------------------------------------------------------- the image ---

if [ -f "$DISC_DIR/$IMAGE" ]; then
    log "$DISC_DIR/$IMAGE is already there ($(du -h "$DISC_DIR/$IMAGE" | cut -f1))"
    exit 0
fi

if [ -n "$DISC_FILE" ]; then
    [ -f "$DISC_FILE" ] || die "UP_DISC_FILE: no such file: $DISC_FILE"
    log "copying the local image $DISC_FILE"
    cp "$DISC_FILE" "$DISC_DIR/$IMAGE"
    exit 0
fi

ARCHIVE="$DISC_DIR/disc-download"

if [ -n "$DISC_URL" ]; then
    log "downloading $DISC_URL"
    curl -fL --retry 3 --retry-delay 5 -o "$ARCHIVE" "$DISC_URL" || die "the download failed"
elif [ -f "$ARCHIVE" ]; then
    log "reusing the archive already downloaded ($ARCHIVE)"
else
    command -v gdown >/dev/null 2>&1 || python3 -m pip install --quiet --disable-pip-version-check gdown \
        || die "gdown is needed (pip install gdown) to read the Drive file"
    log "downloading the Drive file $DRIVE_FILE_ID (this is the big one: ~1 GB)"
    if ! gdown --continue --retries 3 -O "$ARCHIVE" "https://drive.google.com/uc?id=$DRIVE_FILE_ID"; then
        # Drive's "too many users have downloaded this file" page, or a quota
        # error: the fallback asks for the file directly.
        log "gdown failed - trying the direct download"
        curl -fL --retry 3 -c "$DISC_DIR/.cookies" \
             -o "$ARCHIVE" "https://drive.usercontent.google.com/download?id=$DRIVE_FILE_ID&export=download&confirm=t" \
            || die "the download failed - check the Drive link's permissions (anyone with the link: reader)"
    fi
fi

[ -s "$ARCHIVE" ] || die "the download produced no file"

# ----------------------------------------------------------------- unpack ----

log "unpacking $(du -h "$ARCHIVE" | cut -f1)"
UNPACKED="$DISC_DIR/unpacked"
rm -rf "$UNPACKED"
mkdir -p "$UNPACKED"
# What the download is, by its first bytes - not by its name (the name says
# nothing: the Drive file is called "something.zip" whatever it holds).
MAGIC="$(head -c 4 "$ARCHIVE" | od -An -tx1 | tr -d ' \n')"
case "$MAGIC" in
    504b0304*) unzip -q -o "$ARCHIVE" -d "$UNPACKED" ;;   # a zip
    377abcaf*) 7z x -y -o"$UNPACKED" "$ARCHIVE" >/dev/null ;;  # a 7z
    52617221*) unrar x -o+ "$ARCHIVE" "$UNPACKED/" >/dev/null ;;  # a rar
    *) cp "$ARCHIVE" "$UNPACKED/$IMAGE" ;;   # the image itself
esac

# ------------------------------------------------------------- find the ISO ---

ISO="$(find "$UNPACKED" -maxdepth 3 -type f -iname '*.iso' -size +100M | head -1 || true)"
if [ -n "$ISO" ]; then
    log "found $(basename "$ISO")"
    mv "$ISO" "$DISC_DIR/$IMAGE"
elif [ -n "$(find "$UNPACKED" -maxdepth 3 -type f -iname '*.iso' | head -1)" ]; then
    # A small .iso is not a PS2 disc image (it is a save or a demo); take it
    # anyway and let the tools complain with a better message.
    ISO="$(find "$UNPACKED" -maxdepth 3 -type f -iname '*.iso' | head -1)"
    log "found $(basename "$ISO") (small - is this the right file?)"
    mv "$ISO" "$DISC_DIR/$IMAGE"
else
    # A split image: the parts, joined.
    PART="$(find "$UNPACKED" -maxdepth 3 -type f \( -iname '*.iso.001' -o -iname '*.iso.001.bin' \) | head -1 || true)"
    if [ -n "$PART" ]; then
        BASE="${PART%.001}"
        log "joining the split image $(basename "$BASE").001 ..."
        cat "$BASE".* > "$DISC_DIR/$IMAGE"
    else
        # A raw track: the .cue sheet and the .bin it names.
        CUE="$(find "$UNPACKED" -maxdepth 3 -type f -iname '*.cue' | head -1 || true)"
        BIN=""
        if [ -n "$CUE" ]; then
            BASE="$(basename "$CUE" .cue)"
            BIN="$(find "$UNPACKED" -maxdepth 3 -type f -iname "$BASE.bin" | head -1 || true)"
        fi
        if [ -z "$BIN" ]; then
            BIN="$(find "$UNPACKED" -maxdepth 3 -type f -iname '*.bin' -size +100M | head -1 || true)"
        fi
        if [ -n "$BIN" ] && [ -n "$CUE" ]; then
            log "found a raw track: $(basename "$BIN") with $(basename "$CUE")"
            # Their names stay as they are: the cue sheet names its .bin.
            mv "$BIN" "$DISC_DIR/"
            mv "$CUE" "$DISC_DIR/"
            rm -rf "$UNPACKED" "$ARCHIVE"
            exit 0
        fi
        die "no disc image inside the archive - it holds: $(find "$UNPACKED" -maxdepth 2 -type f | head -5 | tr '\n' ' ')"
    fi
fi

rm -rf "$UNPACKED" "$ARCHIVE"
log "the image is at $DISC_DIR/$IMAGE ($(du -h "$DISC_DIR/$IMAGE" | cut -f1))"
