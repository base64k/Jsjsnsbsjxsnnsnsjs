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
| The copy | `kCopy` moved 0x740 bytes from 0x00714678 to 0x80076000 (the kernel's own segment) |

The loading screen the player saw is the PS2's own (drawn by the kernel's
overlay or by the game's first frame); the report counts no GS primitive, so
what was on the screen came from the engine's own path, not from the game's
graphics yet.

The phone it ran on: a **Mali-G57** (Vulkan 1.3.225, driver 171966464; the
renderer drew with Vulkan 1.3) - so the stop is not a driver or a GPU fault:
the engine got a device, a swapchain and a frame rate (120 Hz) and was already
presenting before the game stopped. The same code runs on Adreno and on the
other makers' parts - the renderer asks the driver what it can do (the logic
operations Mali does not have are asked for, not assumed).

The addresses `0x003E5778`, `0x003E5878 SetSyscall`, `0x003E5730 RFU083`,
`0x003E5D10 MachineType_or_rfu`, `0x003E5D58 GetMemorySize_or_rfu` and
`0x003DC820 FlushCache` are the PS2 kernel's own (they are in the kernel's
`0x003E0000` area, not in the game's code) - the EE's boot, before the
game's own entry point runs.

### The headless run's stop (CI report, commit 1d196a6)

The PC reference run reaches the game's title code and stops in
`sceSifCallRpc` on a thread that waits forever: the game binds IOP server
`0x01000001` (not an SDK id: the game's own sound driver's, from ZNASND.IRX)
and its calls (procedures 513, 768, 1797, 1808) were answered with zeros by
the host, which the game never accepts. The fix is to run the game's own
modules (`games/up/port/overrides.cpp`: ZNASND.IRX, LIBSD.IRX) in the IOP
interpreter, so that the server is the game's and answers as the driver does.

### Next stop (CI report, commit a69d5a0)

With only ZNASND.IRX run in the IOP interpreter, the game's own sound server
`0x01000001` is bound and served (`a module serves RPC 0x01000001`). The run
then stops at the first IOP library the host lacks:
`timrman#21 SetOverflowHandler`. The module also imports these, which the host
lacks: `ioman#4,5,6,8` (open, close, read, lseek: the sound bank read from the
disc), `sysclib#35` (strtok), `timrman#10` (GetTimerCounter), `cdvdman#28`
(sceCdStatus) and `cdvdman#39` (sceCdBreak). They belong in the engine's IOP
library table (`engine/host/src/iop_libs.cpp`), which is outside this port.

### The IOP functions the sound driver needs (scripts/patch_iop.py)

The engine's IOP library table is outside this repository, so the functions
the game's sound driver imports are added to the engine's build tree by
`scripts/patch_iop.py` (idempotent, like the other patches): ioman open, close,
read and lseek on the disc; strtok; GetTimerCounter and SetOverflowHandler;
sceCdStatus and sceCdBreak; and the IOP's sceSifBindRpc and sceSifCallRpc,
which log the server they are asked for. The next headless run shows where the
driver stops with them in place.

### The sound driver's poll (CI report, commit e1380f6)

With the functions in place, the driver runs and prints
`[IOP] Check that ZnaSnd.irx have been loaded...` over and over: it binds
server `0x01000002`, which no module here serves, and the bind left it
unbound, so it polls (the IOP at 93% of the time). The patch now binds such a
server to an empty record and answers calls to it with an error (patch_iop.py),
so the driver goes on; the next report shows what it does then.

### The bind's answer (CI report, commit 1221c3d)

The trace names the poll: `sceSifBindRpc(client, 0x01000002, 0, ...) -> 0`, and
the driver prints `Check that ZnaSnd.irx have been loaded...` after each bind
that answers 0. A bound server answers 1 (the SIF's answer), so the empty
record now answers 1. The disc is read fine by then: the driver builds its
file system from the disc's sectors (sceCdRead) before this check.

### The poll's flag (CI report, commit 5e37510)

ZNASND.IRX's poll (IOP 0x10768-0x107C8) binds server 0x01000002, then reads the
word at 0x1AEF8 and, while it is zero, prints `Check that ZnaSnd.irx have been
loaded...` and retries after a delay. No instruction in the module stores to
that word by its literal address, so the handshake that sets it is not found
yet. A stand-in is in patch_iop.py: the bind of 0x01000002 sets the word. This
is a shim, not the driver's protocol; sound may stay silent until the protocol is known.

### The next stop (CI report, commit 56d302d)

With the stand-in, the sound driver's poll passes and the IOP runs its CD
streaming threads (disc reads through sceCdSync/sceCdStatus). The EE then stops
in its own code: `a write at 0x02000000, outside guest memory`, last EE call
0x00410F60 (its names are not in this checkout: they come from the derive/analyze
stage in CI). The likely cause is the EE expecting real answers from the sound
driver's servers (0x01000001, 0x01000002) and getting zeros. Next: name the EE
functions in the stack (the derive stage's names), and find what the EE reads
from the driver's replies before it writes through them.

### Where the 0x02000000 write comes from (runs 44892423771 .. 44898640089, checks 23-27)

The PC reference run with one round (`smoke_rounds=1`) stops in the EE with
`a write at 0x02000000, outside guest memory`. Traced with `--watch`,
`--watch-write` (host options, `UP_HOST_ARGS`) and `scripts/patch_trace.py`
(memory behind watched functions' pointers):

- The count reader `func_00410C60` is called by `func_003079C0` (through
  `func_00307AF0`'s caller chain). Its first calls read sane counts from the
  stream (1, 2, 3, ...). It is not the source.
- `func_003079C0` reads a 24-byte record header from the stream object `s2`
  (`lw a1,0(a1)` = cursor, copied by `func_002E05B0`), gets a table index from
  `func_0030B9A0`, then calls `func_0032DE80` with `a2 = s2[+4]` as the byte
  count.
- `func_0032DE80` is the `UnPack_Z.cpp` unpacker: it reads an 8-byte header
  (two little-endian words: unpacked size, packed size); it allocates only when
  `state[0] == 0`, then calls `func_0032DFA0` (the byte copy/decode loop) with
  `state[0]` as the count.
- The failing call has `s2[+4] = 0x01F78100`, a buffer base pointer, where a byte
  count belongs. The copy then runs past the end of guest RAM at 0x02000000.
- `s2[+4]` is written by `func_004C49A0` (`0x00AD753C <- 0x01F9F180`, then
  `0x01F8F180`; the two differ by 0x10000, one 64 KB stream block). The value
  comes from a table indexed by the slot at `s2+0x28`.
- `func_004C49A0` is a state machine. It calls methods through the object at
  `+0x154` (the sound driver's interface) and uses counters at `+0x2c`/`+0x30`.
  Its caller chain (`0x0041B550`, `0x00356A60`, `0x00426E00`, `0x00426350`,
  `0x0032EAA0`, `0x0032F1B0` "BSource User.tsc") is the sound/stream path.

Not yet established: which sound-driver reply (servers 0x01000001 and
0x01000002, procedures 513, 768, 1797, 1808) makes the state machine take the
branch that writes a pointer into the count field. The port answers the
driver's server 0x01000002 with the stand-in flag (patch_iop.py), so the replies
the EE reads may be wrong. Next: log the replies the host sends to the EE's
SifCallRpc for those servers, and check them against the driver's own code.

### The sound driver's RPC protocol, as the run shows it (checks 28-32)

The game's EE code calls its sound driver (IOP server 0x01000001, served by
ZNASND.IRX in the IOP interpreter) with 32-byte RPCs. The trace (`[iop] RPC`,
`[iop] RPC reply`, from `--iop-trace`) shows procedures 513, 768, 772, 1797,
1805, 1808, 1809, 1810 and their replies. Most replies are zeros; procedure
1808 answers 1. The dispatcher is a chain of compares at IOP 0x10528 (a0 =
procedure). Its handlers:

- 1808 (0x710) -> 0x10B0C: returns a sign-extended byte from helper 0x18F44.
- 1809 (0x711) -> 0x10B24: helper 0x18FC0, returns 0.
- 513 (0x201) -> 0x10768: prints a message (the driver's own text).

Helper 0x18F44 reads and writes the driver's state byte at IOP 0xC5FC/0xC5FD
(the stand-in flag, 0x1AEF8, is the same area): with the byte at 1 it clears
it and calls 0x9354; otherwise it returns 1.

Note for reading `disasm_irx.py` output: a `jal` target is printed relative to
the module's ELF base (add 0x10000 for the IOP address); `beq`/`b` targets are
already IOP addresses.

Not resolved: what the EE does with the replies, and what the driver's real
answers should be (its initialisation, which the stand-in skips). Without that,
the replies are a guess, and the stream's sizes that come from them are wrong.
