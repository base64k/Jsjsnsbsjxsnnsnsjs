# Up: findings

What the binary revealed, as it is learned. Everything here was found from the
player's own disc image with the engine's tools; nothing of the game is in the
repository.

## The disc

| | |
|---|---|
| Title | Disney/Pixar Up (PS2) |
| Region | USA |
| Disc id | SLUS-21864 → the program is `SLUS_218.64` |
| The program's ELF | taken from the disc with `isotool.py extract` |

`game.json` names the program; `scripts/build_apk.sh` compares it with the
disc's `SYSTEM.CNF` on every build, so a wrong image is caught in seconds
instead of hours.

## The program (what the analysis says)

Not yet run on this game - the first CI run fills this in:

- the compiler (the ELF's `.comment` section) and the SDK version,
- the middleware (`RCS $Id:` strings, the SDK's module names),
- the VU regions (microcode in the image: `vudis.py --stats`),
- the size of the program and the number of functions (`analyze.py`),
- how much of it decompiles and verifies (`derive.py`, `lift.py`,
  `progress.py`).

## The subsystems the port has to understand

Each entry: what it is, the addresses, and how it was found. The game's own
code is the point - override as little as possible.

- **Boot** - what the program does before the first frame: the kernel's
  services it asks for, the IOP's modules it loads, the disc it reads.
- **The menus** - how they are drawn and what the port has to hook for the
  on-screen controls.
- **Streaming** - how the game's data is read (the disc's files it opens).
- **Audio** - the SPU2's use, the ADPCM/IRX it needs.
- **VU** - the microcode, if the game has any (VU1 for the geometry).

## The port's own findings

- The engine was built for Burnout 3 (RenderWare); Up's middleware is
  different, so what the host already provides and what it does not is the
  first thing the `smoke` run's report answers.

## Audio: the sound driver and call 6 (under investigation)

Everything below comes from the previous session's runs against the player's
disc. It was never committed here, and it has **not** been re-verified in this
checkout — the `engine/` submodule is empty (no analysis tools) and no disc
image is present locally (`.gitignore` keeps `disc/` out, CI fetches it from
the player's Drive file). Treat it as a hypothesis, not a confirmed fact.

**What was observed**

- RPC call 6 writes the decoder's output on top of call 83's input: the bytes
  `CF`, then `00`, at EE address `0x01F7FCF3`, between DMA streams to that same
  EE range. Confirmed across runs.
- The decoder (`UnPack_Z`) reproduces all 83 calls exactly from the disc
  image's data, so the disc data itself is not the problem.

**What is still unknown**

- The IOP poll flag at `0x1AEF8`: it is written by the host stand-in
  (`patch_iop.py`), not by the sound module itself (ZNASND). The program
  counter cited for the write, `pc 0x100C0`, points at data, not code — so the
  real driver handshake has not been found, and answers to RPCs sent to server
  `0x01000002` are guesses.
- Which RPC, or which EE-side write, should set flag `0x1AEF8`, and what the
  driver expects from the EE.

**Working hypothesis (unproven)**

The sound driver never gets the right answer from the EE, so the EE picks the
wrong buffers for the stream — a likely explanation for the crash around the
25-second mark, before the menu appears.

**Next step**

Find which RPC or EE-side write must set flag `0x1AEF8`, and check the
driver's expectation from the EE side. Once the `engine` submodule is
initialized and the disc has been fetched (`scripts/fetch_disc.sh`, then the
`analyze.py` → `signatures.py` → `lift.py` pipeline), this can be re-verified
against `SLUS_218.64` and the verified entries recorded in
`games/up/config/functions.csv`.
