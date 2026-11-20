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

### The first run on a phone (the player's own report)

The first APK starts, shows the game's loading screen ("graphics loading")
and then stops with:

    The game stopped because of an error. What happened is in up.log, beside
    the game.

`up.log` (in the app's own folder on the phone:
`Android/data/io.github.base64k.up/files/up.log`) says where:

    stopped: a call to 0x80076000, code copied from 0x00714678 at run time,
    not translated yet (port.py translates it for the next build)
    ...
    discovered: code at 0x80076000 is a copy of 0x00714678

So the game does not stop on anything missing: it stops because the program
copies a piece of its own code to `0x80076000` (the kernel's address space)
at run time, and that copy is not in the translated set yet. The engine's own
loop is the answer: the run writes the copy down (`--discover`), the copy is
translated, the game is run again. The port's `scripts/smoke_test.sh` does
that (eight rounds), and the APK's stage builds the dispatch table with
everything the rounds found.

What the report says about the state of the port at that moment:

| | |
|---|---|
| Time to the stop | 2.2 s |
| Guest functions run | 14 |
| Kernel services used | `SetupThread`, `SetupHeap`, `CreateSema`, `kCopy`, `FlushCache`, `SetSyscall` and three the engine does not name yet (numbers 91, 131 and `?`) |
| GS | 0 primitives, 0 pixels - the game has not drawn anything yet |
| GPU | 1 submission, nothing drawn |

The loading screen the player saw is the PS2's own (drawn by the kernel's
overlay or by the game's first frame); the report counts no GS primitive, so
what was on the screen came from the engine's own path, not from the game's
graphics yet.

The addresses `0x003E5778`, `0x003E5878 SetSyscall`, `0x003E5730 RFU083`,
`0x003E5D10 MachineType_or_rfu`, `0x003E5D58 GetMemorySize_or_rfu` and
`0x003DC820 FlushCache` are the PS2 kernel's own (they are in the kernel's
`0x003E0000` area, not in the game's code) - the EE's boot, before the
game's own entry point runs.
