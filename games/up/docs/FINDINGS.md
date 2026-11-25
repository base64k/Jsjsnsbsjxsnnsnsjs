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

Everything below about call 6 comes from the previous session's runs against
the player's disc. It has **not** been re-verified in this checkout — no disc
image is present locally (`.gitignore` keeps `disc/` out; CI fetches it from
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

---

## What the engine actually provides for sound (verified from engine source)

The `engine/` submodule is now initialized (commit `65c46e975a0c7f2c2eef67d283c97fe856a8040e`). Reading
`engine/host/src/` shows the host's sound/IOP implementation:

**libsd (iop_libs.cpp)** — all 32 exports implemented:
- `sceSdInit`, `sceSdQuit`, `sceSdSetParam`, `sceSdGetParam`
- `sceSdSetSwitch`, `sceSdGetSwitch`, `sceSdSetAddr`, `sceSdGetAddr`
- `sceSdSetCoreAttr`, `sceSdGetCoreAttr`, `sceSdNote2Pitch`, `sceSdPitch2Note`
- `sceSdProcBatch`, `sceSdProcBatchEx` (batch voice parameter ops)
- `sceSdVoiceTrans`, `sceSdBlockTrans`, `sceSdVoiceTransStatus`, `sceSdBlockTransStatus`
- `sceSdSetTransCallback`, `sceSdSetIrqCallback`, `sceSdSetTransIntrHandler`, `sceSdSetSpu2IntrHandler`
- `sceSdSetEffectAttr`, `sceSdGetEffectAttr`, `sceSdClearEffectWorkArea`, `sceSdStopTrans`
- Plus argument getters for trans/SPU2 interrupt handlers

**SPU2 (spu2.cpp / spu2.h)** — full sound processor:
- 2 cores, 48 kHz mixing, ADPCM voice decoding with Gaussian interpolation
- ADSR envelopes, reverb unit (PS1 SPU algorithm), dry/wet mixes per core
- Sound-data input ring buffers (PCM streaming, 0x200 bytes left + 0x200 right per tick)
- SPU RAM (2 MiB), voice transfer (VoiceTrans/BlockTrans into SPU RAM)
- IRQA interrupts on transfer completion and half-buffer boundaries
- `EnableSound()` hooks the host's audio output callback

**IOP module execution (iop_vm.cpp / loadfile.cpp)**:
- `RunModule("NAME.IRX")` — port names IOP modules to run from the disc (iop_vm.cpp:472); modules are loaded from the disc image
- `LoadModule()` — loads ELF IRX images, applies R3000 relocations, patches import stubs to host HLE functions (iop_vm.cpp:483)
- Modules run as IOP threads under the IOP kernel scheduler; SIF commands go to/from the EE
- `--iop-trace` logs every IOP library call a module makes
- `RunsModule(path)` — checks if a module is named to run

**SIF/RPC (iop.cpp)**:
- Server 0x80000006 = loadfile (loads modules from disc or IOP memory)
- Server 0x80000009 = RPC bind, 0x8000000A = RPC call (answered with RPC-end packets)
- Servers with no host implementation still bind; calls are noted so the report says which IOP services the game needs

**Audio pipeline status** — verified from engine source, the pipeline IS wired:
- `EnableSound()` is called from `host.cpp` when `--audio` or `--audio-wav` is given, wiring `Spu2::SetOutput` to `AudioFrames()` (iop_libs.cpp)
- `SoundInterrupts()` is called in the IOP interpreter's scheduler loop (iop_vm.cpp:396) — handles transfer-complete and half-buffer interrupts, advances SPU2 playback
- `SdBlockTrans()` sets up streaming buffers at 48 kHz / 16-bit stereo (192,000 bytes/sec)
- `SdVoiceTrans()` writes voice data into SPU RAM
- So: when `--audio` is given, the SPU2 decodes, mixes, and plays output through `AudioFrames()`

**What the port still needs for sound**: the sound DRIVER handshake between EE and IOP. The IOP flag `0x1AEF8` must be set by the right RPC or EE-side write, and the sound modules (LIBSD, SDRDRV, CRI_ADXI) must run on the IOP via `RunModule()`.

---

## Reference ports and how they handled sound

**DQ8-Recompiled** (Sinan-Karakaya/DQ8-Recompiled, PR #1) — most relevant:
- Runs IOP modules LIBSD, SDRDRV, MODHSYN, MODMIDI, MODMSIN, SKSOUND, SKHSYNTH, SKMIDI, SKMSIN, PCMPLAY **unmodified** on an emulated IOP
- The game's own libsdr and Sound Kit code talks to them over SIF exactly as on console
- `sceSdRemoteInit`, `sceSdRemote`, `sceSdTransToIOP` are runtime placeholders (game's own versions run)
- `sceSifCallRpc` is bound to the runtime (not stubbed) — the game's copy needs the real SIF setup
- `--mute` keeps drivers running without playing

**Shinobi-PS2-Recomp** (TheRealAfsan/Shinobi-PS2-Recomp, issue #2):
- CRI ADX/Sofdec streams PCM from EE to CRI_ADXI.IRX via "RNA" output over SIF ring buffers
- Fix: HLE the RNA output on the host side instead of sending PCM to the IOP; play on host with exact sample accounting
- CRI_ADXI loses track of right-channel chunks under emulation; right-channel ranges never returned

**KOF XI recomp** (Tel-BR/kof-xi-recomp, issue #9):
- Brings PS2Recomp-Fixer's SPU2 into ps2xIOP, clocked by emulated IOP time
- Sound from original LIBSD, SDRDRV, CRI_ADXI modules through PCSX2-matched SPU2

**Known PS2 sound IRX modules** (retroreversing.com):
- `libsd.irx` — Sound Library (627 exports)
- `sdrdrv.irx` — Sound Driver (476 exports)
- `cri_adxi.irx` — CRI ADX streamed audio (73 exports)

---

## Disc download blocker (this checkout)

The player's disc file is on Google Drive:
`Disney-Pixar Up (USA) (EnFr).zip`, ID `1LIzZFzNoXUteK5fnJLT1P6vGoIxg1fDA`, ~916 MB.

All download methods fail in this sandbox with SSL/TLS connection resets:
- `gdown` (via `scripts/fetch_disc.sh`): `SSLZeroReturnError`
- `curl` to `drive.google.com` and `drive.usercontent.google.com`: `SSL_ERROR_SYSCALL`
- `wget`: `GnuTLS: The TLS connection was non-properly terminated`
- Python `urllib` with unverified SSL: same EOF error
- Google Drive connector `download_file`: file is 916 MB, exceeds the 100 MiB workspace limit

The `disc/up.iso` file exists but is 0 bytes. **CI (GitHub Actions runners) can fetch it** — `.github/workflows/android-apk.yml` uses `scripts/fetch_disc.sh` with `UP_DRIVE_FILE_ID=1LIzZFzNoXUteK5fnJLT1P6vGoIxg1fDA` and caches the result. The blocker is only in this sandbox's network. The disc must be obtained before the `analyze.py → signatures.py → lift.py` pipeline can run against `SLUS_218.64`.

---

## Next steps (blocked on the disc)

1. **Get the disc image** — the SSL/TLS blocker is only in this sandbox; CI runners can fetch it. Options:
   - Run CI (`.github/workflows/android-apk.yml`) which fetches via `scripts/fetch_disc.sh` and caches `disc/up.iso`
   - Resolve the sandbox's TLS block to `drive.google.com` / `drive.usercontent.google.com`
   - Google Drive connector: file is 916 MB, exceeds the 100 MiB workspace limit
2. **Extract the program**: `python engine/tools/isotool.py extract disc/up.iso SLUS_218.64 -o games/up/extracted/`
3. **Analyze**: `python engine/tools/analyze.py --game games/up`
4. **Name functions**: `python engine/tools/signatures.py --game games/up name`
5. **Lift to C++**: `python engine/tools/lift.py --game games/up --structure --emit --csv`
6. **Build and run**: `python engine/tools/port.py --game games/up` — the smoke test's report says where the game stops; that report is the bring-up measure.
7. **Find the sound handshake**: with the disc, re-verify call 6 / `0x1AEF8` against `SLUS_218.64`; check which RPC or EE-side write must set the flag, using `--iop-trace` to see which IOP library calls the sound modules make.
8. **Record verified entries** in `games/up/config/functions.csv`.

**Reference approach for sound**: follow the DQ8 port — name the game's IOP sound modules (likely LIBSD, SDRDRV, CRI_ADXI) to run via `ps2host::iop::RunModule()`, keep `sceSifCallRpc` bound to the runtime (not stubbed), and let the game's own sound code talk to them over SIF. The host's libsd and SPU2 implementations are already in place.

---

## Engine API verified from source (for port code in `games/up/port/overrides.cpp`)

**Override mechanism** (`host.h`, `host.cpp`):
- `ps2host::Override(u32 address, GuestFunction function, const char* name)` — replaces a guest function at an address; the original is callable as `F_<ADDRESS>(c)` via `GuestCall`
- `ps2host::RegisterGameOverrides()` — called from `engine/host/src/main.cpp` at start; implemented in the game's `port/overrides.cpp`
- `ps2host::ApplySdkOverrides()` — applies host implementations of SDK library routines by name (from the game's dispatch table)
- `ps2host::ApplySdkPatterns()` — finds SDK routines by instruction hash in the executable's bytes

**Sound API** (`run.h`, `audio.cpp`):
- `ps2host::OpenAudio()` / `CloseAudio()` — opens/closes the sound device
- `ps2host::AudioFrames(const short* frames, unsigned count)` — the SPU2 calls this with mixed 16-bit stereo at 48 kHz
- `ps2host::OpenWavDump(path)` / `AudioActive()` — WAV recording and activity check
- `ps2host::AudioVolume()` / `SetAudioVolume(percent)` — master volume

**IOP API** (`run.h`, `iop.cpp`, `iop_vm.h`):
- `ps2host::iop::RunModule(file_name)` — names an IOP module to run from the disc
- `ps2host::iop::RunsModule(path)` — checks if a module is named to run
- `ps2host::RegisterRpcServer(u32 server_id, RpcServer)` — registers a host RPC server
- `ps2host::InstallIopServers()` / `InstallLoadFile()` / `InstallFileIo()` / `InstallDbc()` / `InstallMcserv()` — installs IOP services

**Device/run API** (`run.h`):
- `ps2host::SetPath2Filter(filter)` — intercepts VIF1 DIRECT/PATH2 blocks before the GS (for 2D/HUD widescreen)
- `ps2host::AddIdleLoop(address)` — names a wait loop so virtual time skips to the next event
- `ps2host::SetFastForward(factor)` / `SetBlankRate(hz)` — real-time speed control
- `ps2host::SetFastDisc(bool)` / `SetFastLoadingDefault(bool)` — disc read timing
- `ps2host::SetVuFastDefault(bool)` / `SetFramePacingDefault(bool)` — VU1 and frame pacing defaults
- `ps2host::SetPadHook(hook)` / `SetControllerFilter(filter)` — input hooks
- `ps2host::SetKeyboardMapper(mapper)` — keyboard to pad mapping
- `ps2host::AddPortOptions(options)` — PC settings panel pages
- `ps2host::SetCaptureHook(hook)` — F12 capture hook

---

## Port code structure (what goes in `games/up/port/`)

| File | Purpose |
|------|---------|
| `CMakeLists.txt` | Build: links `engine/host`, lists `overrides.cpp`, generated sources |
| `overrides.cpp` | `RegisterGameOverrides()` — host implementations of game functions by address |
| `port/runs/<name>.args` | Scripted test runs (`--virtual-time`, `--press`, etc.) |
| `port/runs/README.md` | Documents each run: what it reaches, at which frames |
| `port/icon.ico` | The port's icon (original art, never from the disc) |
| `port/release/README.txt` | Player-facing README |
| `config/functions.csv` | Function name table (address, name, status, source, notes) |
| `docs/FINDINGS.md` | What the binary revealed (this file) |

---

## What the host already provides vs. what Up needs

**Already provided by `engine/host`:**
- EE kernel services (threads, semaphores, alarms, timers, SIF, syscalls)
- IOP: libsd (all 32 exports), SPU2 (full sound processor), module loading, SIF/RPC
- GS: software renderer, GPU renderer (Vulkan), VIF1/VU1
- Devices: CD/DVD, file I/O, memory card, pads, IPU (MPEG movies)
- Audio output pipeline fully wired: `EnableSound()` → `AudioFrames()` via SPU2 output callback; `SoundInterrupts()` called in IOP scheduler; `SdBlockTrans()` sets up 48 kHz streaming
- SDK library routines by name (GsSyncPath, KernelStore, TtyWrite, etc.)
- PC features: window, settings panel, texture pack, mouse, controller, rumble

**What Up's port must add (in `port/overrides.cpp`):**
- Function overrides discovered from the analysis (addresses from `functions.csv`)
- IOP sound modules to run (`RunModule("LIBSD.IRX")`, `RunModule("SDRDRV.IRX")`, etc.)
- Sound handshake: which RPC or EE-side write sets IOP flag `0x1AEF8`
- Any hardware-specific behavior the host doesn't model

---

## PCSX2 Wiki info on Up (SLUS-21864)

- Developer: Asobo Studio, Publisher: THQ, Released: 2026-05-26
- Status: Playable on PCSX2 Windows and Linux
- Known issue: TLB Miss crash when aiming the mirror (NTSC version only)
- Fixed issue: Bad text (garbled subtitles) — fixed in PCSX2 v1.7.5880
- Widescreen supported natively


## Where the port stands (latest)

**A real phone run** (Mali-G57, Vulkan 1.3, arm64, uploaded log `up.log`):
the game drew about 10,700 frames through the GPU renderer (`[gpu] frame`), with
`0 of 0 GPU pipelines made` (no `port/gpu_pipelines.h` then - now generated from
the run's keys, 8 of them). The ZNASND RPC server answered guessed replies: the
game polled procedure 772 20,929 times with the same request. The run ended with
`vkAcquireNextImageKHR failed (-1000000000)` (VK_ERROR_SURFACE_LOST_KHR) four
times: the engine's swapchain path gives up on that error (`vulkan_display.cpp`,
`Check` after the acquire), so a surface lost in the middle of a play ends the
display. That is the engine's to handle (recreate the surface), not the game's.
Patch `0015-surface-lost-made-again.patch` does that (`gpu/src/vulkan_display.cpp`): the
surface and the swapchain are made again from the window, and the lost picture is
not shown instead of ending the display.

**Device-specific data is not portable.** `gpu_pipeline_cache.bin` is the
driver's own pipeline cache (Mali's binary; the engine saves it as
`gpu_pipeline_cache.bin` and the driver ignores another GPU's). The upload
(`gpu_pipeline_cache.bin.txt`, 400,377 bytes) is the raw binary under a `.txt` name:
its bytes are not UTF-8, and its Vulkan header reads header size 0x20, version 1, vendor
0x13B5 (ARM), device 0x90910010 (the Mali-G57). The driver checks that header and
ignores a cache that is not its own. It is git-ignored (`*.bin`) and not committed:
the engine writes the file on the device itself. Adreno, Mali and Helio builds each
make their own.

**The sound driver is the game's own code now.** `ZNASND.IRX` used to be
"its services are the host's": the host answered its RPC with guesses, and the
driver never ran. Now `RunModule("ZNASND.IRX")` runs it in the IOP interpreter.
Two engine gaps stood in the way, kept as patches in `games/up/engine-patches/`
(applied to the engine checkout by CI; the submodule's commit is unchanged):

1. `0001-iop-hardware-registers.patch`: IOP hardware registers (0x1F80xxxx, seen
   as 0xBF80xxxx) are kept as written, not a stop. (`0xBF801404` was the stop.)
2. `0002-timrman-overflow-and-setters.patch`: `timrman#21` SetOverflowHandler,
   and the timer setters #7, #9, #10, #11.
3. `0003-strtok-cdstatus-cdbreak.patch`: `sysclib#35` strtok, `cdvdman#28`
   sceCdStatus, `cdvdman#39` sceCdBreak.
4. `0004-timer-clock-sifcmd-ioman-placeholders.patch`: `GetTimerCounter` counts
   with the clock while the timer runs (before it returned 0 every time, so
   the thread polling it never left its wait); `sceSifBindRpc` and
   `sceSifCallRpc` (sifcmd #15, #16) answer 0 ("not bound", "not called"); the
   file manager's `ioman` opens fail with -1. The placeholders are there so
   the trace shows what the module asks for; they are not the real calls.

5. `0005-sifrpc-client-bind-and-call.patch`: the IOP's SIF RPC client as
   ps2sdk's IOP library has it (`iop/system/sifcmd/src/sifrpc.c`, below):
   `sceSifBindRpc` sets the client's `server` (offset 36) to the module's
   server, or leaves it NULL when no module serves the id, and returns 0 in
   both cases. `sceSifCallRpc` sends the arguments to the server's queue, waits
   for the answer when blocking, runs the end function, then returns.
6. `0006-ioman-disc-files.patch`: `ioman_open`, `iomanX_read`, `iomanX_lseek`,
   `iomanX_close` read the disc's files (`GuestDisc().ReadFile`); a file the
   disc does not have is -2 (ENOENT), and the report names each file opened.

The patches apply in this order (0001 to 0006) on the engine checkout; CI
checks it (`ci-results/engine-build.txt`).

The trace of the run (CI, `--iop-trace`, `ci-results/iop-trace.txt`) shows the
driver's path: libsd init (`sceSdInit`, `sceSdSetCoreAttr`, `sceSdSetParam`),
its own thread registering RPC server `0x01000001` (`sceSifRegisterRpc`,
`sceSifRpcLoop`), `AllocHardTimer`, `SetupHardTimer`, `SetOverflowHandler`.

**Latest CI run, 45428902827** (patches 0001-0004, engine `65c46e9`): it no
longer stops at an unimplemented import (`0 'is not implemented'` lines in the
report; 633 distinct functions). It stops in a loop instead: the driver's
thread runs `sceSifBindRpc(client, 0x01000002, 0)` again and again, each time
answered 0 and printing `[IOP] Check that ZnaSnd.irx have been loaded...`
(about 4,600 times in the trace; the trace is capped at 20,000 lines). IOP time
is 90%, and the run ends with every thread waiting (`600 frames of interrupts
woke none`). The EE binds the IOP servers `0x80000001`, `0x80000592`,
`0x80000593`, `0x80000003` and `0x80000006`; nothing binds or registers
`0x01000002`. So the blocker is that server: the sound driver waits for a
partner that never appears, and the placeholder 0 for `sceSifBindRpc` keeps it
waiting. Which side serves `0x01000002` (the EE, or a second module the EE
loads) is not known yet. The real `sceSifBindRpc` return convention and the
client struct's layout are not confirmed; they need the driver's disassembly
(from the disc, which is only available in CI).

**The SIF RPC client, as ps2sdk's IOP library does it (proven reference).**
`sceSifBindRpc` does not fail when no server has the id. It returns 0 and
leaves `cd->server` NULL; the caller's loop waits for it (`Check that ZnaSnd.irx
have been loaded...` is that loop). A bound client's `cd->server` is what
`sceSifCallRpc` sends to. The end function runs on the reply, whether the call
blocks or not. The `SifRpcClientData_t` layout: header 16 bytes (pkt_addr,
rpc_id, sema_id, mode), then command (16), buf (20), cbuf (24), end_function
(28), end_param (32), server (36). The source is ps2sdk's
`iop/system/sifcmd/src/sifrpc.c` and `common/include/sifrpc-common.h`.
So the trace's loop means: no module registers server `0x01000002` in this
port. Who should (the EE, a second module, or the disc's own file) is what
`ci-results/disc-modules.txt` answers: a CI step scans the disc's `MODULES`
folder and the program for the `ZnaSnd` string and the server ids
(`scripts/disc_modules.py`).

**What the disc's own files say (CI, `ci-results/disc-modules.txt`, run 45441846187).**
The EE loads exactly six modules: `SIO2MAN`, `PADMAN`, `MCMAN`, `MCSERV`,
`LIBSD`, `ZNASND` (the program's strings). `SDRDRV.IRX` is on the disc but the
EE never loads it. (The first reading of this scan counted the bytes
`02 00 00 01` wherever they occur: LIBSD, SDRDRV, the EE program. Those hits
are not literal words: every one is at an odd or unaligned offset, so they
are bytes across instruction boundaries. No aligned `0x01000002` word exists
in any disc module or in the EE program.) `ZNASND.IRX` itself has the strings "ZnaSnd.irx Loaded
Successfully...", "Error while init SifRpc" and "Check that ZnaSnd.irx have
been loaded...": that is its own load check. The sound driver's partner
server is therefore most likely the real `LIBSD.IRX`'s. In the port, LIBSD is
the host's (`RunModule` is not called for it), so no module serves 0x01000002.
ps2sdk's `sdrdrv` registers `0x80000701` (a later SDK); the game's is older, so
its ids are not ps2sdk's.

Run 45446669116 (`RunModule("LIBSD.IRX")`, patches 0001-0006): LIBSD now runs
as code (`running cdrom0:\\MODULES\\LIBSD.IRX;1 ... entry 0x000100B0`), and
ZNASND prints "ZnaSnd.irx Loaded Successfully...". But LIBSD's start only
registers its library and returns: it makes no `sceSifRegisterRpc`. The bind
for `0x01000002` still returns NULL, every time (the trace's loop). So server
`0x01000002` is not LIBSD's. Its only other IOP candidate is `SDRDRV`, which
the EE never loads.

The next candidate is the EE: an IOP client can bind a server the EE
registered (SIF is two-way; ps2sdk's EE `sifrpc.c` has `_request_bind`). The
EE program builds `0x01000002` in its code, and `disc-modules.txt` now counts
the `lui`+`ori` pairs that do that (in the EE program and in each module),
which says whether the EE registers it. Until the EE's registration is
served to the IOP, the bind waits: a host server would have to guess the
procedures, which is what the port's earlier guessed replies showed does not
move the game.

**Runs 45450438599, 45456522278, 45462705479 (the same code, plus the scan).**
- 45450438599 (`RunModule("LIBSD.IRX")`, patches 0001-0006): smoke stopped
  on "every thread is waiting", 633 distinct functions, 58.8 s, IOP 94.2%.
  LIBSD runs (`entry 0x000100B0`), ZNASND prints "Loaded Successfully", and
  the `sceSifBindRpc(…, 0x01000002)` loop continues.
- 45456522278 (same, with the module names in the scan): same stop, 61.4 s.
- 45462705479 (same code, the scan's code listing): same stop, 633 distinct,
  47.4 s, IOP 93.0%. The summary is `ci-results/smoke-summary.txt`.

**Who registers which server (from the trace, `ci-results/iop-trace.txt`).**
The only `sceSifRegisterRpc` in the run is
`sifcmd#17 sceSifRegisterRpc(…, 0x01000001, …) -> 0 from 0x00015EB8`, and the
bind is `sceSifBindRpc(…, 0x01000002, …) from 0x00016128`. Both addresses are
inside ZNASND (its `lui`+`ori` for `0x01000001` is at file offset 0x5A8 and
for `0x01000002` at 0x820; the call sites differ by the same amount). So
ZNASND registers its own server, `0x01000001`, and binds to `0x01000002`,
which another side must register.

**The EE registers server `0x01000002` (run 45467618323, `disc-modules.txt`).**
No module on the disc holds the id as data. The EE program does build it, in
code, at program address `0x24D5BC`:
`lui v0,0x0100; ori a1,v0,2; jal 0x003DFC38` with `a0`=sp+48 (the server
data), `a2`=0x0044D3A0 (a function), `a3`=0x007A8400 (a buffer), `t0`=`t1`=0,
and the queue on the stack. That is the seven arguments of
`sceSifRegisterRpc(sd, sid, func, buff, cfunc, cbuff, qd)`. So the EE serves
`0x01000002`, and ZNASND's bind for it is a client bind to the EE. The other
`lui 0x0100` hits in the EE program (0xE7634, 0xE7B48, 0xEE9A4, 0x261A6C) use
other constants (`0x101`, `0x6000_0002`) and are not this id.
The EE also binds `0x01000001` (ZNASND's own server) at `0x24CEE4`:
`lui v0,0x0100; ori a1,v0,1; jal 0x003DF798`, `a0`=0x007A7BC0, `a2`=0, which is
`sceSifBindRpc(sd, 0x01000001, 0)`.

**Why the port never gets there.** The EE binds only the `0x8000xxxx` IOP
servers in the port (`[host] SIF: bound to IOP server …` lines of
`port-report.txt`). It never binds `0x01000001`, so it never reaches `0x24CEE4`
or `0x24D5BC`. Its thread 1 waits in `sceSifCallRpc` → `WaitSema` (the
smoke summary), a call that is not to an unimplemented server (no `SIF: call
… no host implementation` line). So the stall is in an earlier EE call. The
IOP side's loop (`sceSifBindRpc(0x01000002)`) is the ZNASND's poll for the EE
server, which the EE would register only after that call returns.

**The EE's server table is not the IOP's.** The port's IOP bind
(`SifBindRpcClient` in `iop_libs.cpp`, patch 0005) looks only in the IOP's
`rpc_servers` and the host's table. An EE-registered server (`sceSifRegisterRpc`
on the EE) is in EE memory and never reaches it, so the IOP's bind returns 0
even once the EE has registered `0x01000002`. Patch 0005 needs a second look-up
into the EE's registrations (the EE's `sceSifRegisterRpc` call, `0x003DFC38`
in this program) when the EE is up; without it the EE registration does not
serve the IOP.

**Earlier reading of the same scan (corrected).** The first reading counted the
bytes `02 00 00 01` wherever they occur (LIBSD, SDRDRV, the EE program). Every
such hit is at an unaligned offset, so they are bytes across instruction
boundaries, not literals. No aligned `0x01000002` word exists in any disc module
or in the EE program.

**Patches 0007-0010 and the EE's load (runs 45530173257, 45534355291, 45537324174, 45541066304, 45543826201, 45547139945).**
- 0007 (log): every distinct EE `sceSifCallRpc` with its server, procedure, and
  EE callers. The EE's calls in the port are: `0x80000001` (SIO2MAN-era
  server), `0x80000592` CdInit, `0x80000593`, `0x80000006` LoadFile (procedure
  0, 512 bytes: the module's path). The last one is the load of ZNASND. The
  EE never calls `0x01000001`, so `0x24CEE4` and `0x24D5BC` are not reached.
- 0008 (fix, the one real bug found): a bind for a server that is not there
  returned 0 at once, so ZNASND's loop (about 4,600 binds) never let the IOP
  run return to the load. Now the bind waits 1 ms (as the library's bind does).
  Smoke: 60 s and IOP 94% before; 12.7 s and IOP 9-11% after. The stop is now
  the same "every thread is waiting".
- 0009 (log): the SIF replies queued and delivered. LIBSD's load returns
  (`start returned 0`, `loaded`) and its reply reaches the EE. ZNASND's start
  does not return: after its `[IOP] ZnaSnd.irx Loaded Successfully...` the
  loader thread makes no more calls, so no "start returned" line appears.
- 0010 (log): would print the loader's pc after 0.2 s of waiting in
  `LoadModule`, but it does not fire: the spin is not in the loop that checks
  the time. So the place where ZNASND's start spins is still unknown.

**The EE's server table.** The IOP's bind (patch 0005) looks in the IOP's
servers only. Even once the EE has registered `0x01000002`, the IOP's bind
returns 0 unless the port reads the EE's registrations. That is still open.

**Runs 45554406369 and 45557930345 (patch 0011: a probe in the IOP's run loop).**
The probe prints the thread states and the loader's code 0.2 s (then 20 ms)
after a module's start begins. It never printed, in either run. Every run now
stops at exactly 12.7 s, which looks like the smoke's "600 frames of
interrupts woke none" watchdog (about 47 frames a second), not like the
loader's own time. So the watchdog may stop the run before the loader's start
has run long enough to show. Also, `Execute` runs a thread with its interrupts
off past its quantum, up to 1,000,000 instructions per call (`kInterruptsOffMax`),
so a spin with interrupts off returns to `Run` only every 1,000,000 instructions.

Next: stamp the wall clock on "running ZNASND" and on the stop, to see how long
the start had before the stop; if it is short, make the watchdog count only
the EE's frames that really advance.

**Next steps (updated):**
1. Find where ZNASND's start spins after "Loaded Successfully": log the
   loader's pc from inside `Run` (for example at each slice, after 0.2 s), and
   decode the words around it (the code is in the loaded image; the dump is
   what 0010 was meant to print).
2. Once the start returns, check that the EE's call to `0x80000006` gets its
   answer, and then whether the EE reaches `0x24CEE4` (bind `0x01000001`) and
   `0x24D5BC` (register `0x01000002`).
3. Make the IOP's bind see the EE's registrations for `0x01000002`.

**Open questions for the port (not yet in the code):**
- The menu has not been seen on any run. What the EE waits for is the sound
  driver's status (procedure 772 polling); whether the module now answers it
  is what the next CI run shows.
- The engine's `AddIdleLoop` overrides (five wait loops) are still in place;
  they skip virtual time in waits the real driver should now resolve. Remove
  them if the menu needs the real waits.
- FPS counter: on by default now (`fps_counter`, F1 toggles, the choice kept
  in the settings file). `fps_detail` in the engine adds CPU.

**Next steps:**
1. Find the EE call the EE waits on before `0x24CEE4`: log each EE
   `sceSifCallRpc` with its server id, procedure, and the EE's caller (the host
   note for the kRpcCall case in `iop.cpp` logs only unimplemented servers).
   That call's reply is what stops the EE and so the registration.
2. Make the IOP's `sceSifBindRpc` see the EE's registered servers (the EE's
   `sceSifRegisterRpc` for `0x01000002` in the program's `0x003DFC38`), so the
   IOP's bind returns the server once the EE has registered it.
3. Patches 0005 and 0006 are in place; their effect is in the trace's `ioman`
   lines and the bind loop. The trace is capped at 20,000 lines.
4. Do not publish the APK until the menu appears (the user's condition).

**Runs 45569467257, 45573559671 and 45581017566 (patch 0013; the full host trace).**

*A correction to the notes above.* `ci-results/port-report.txt` keeps only the
first 4,500 and the last 4,500 lines of the report ("... lines left out ..."),
so the middle of a run is missing from it. The conclusions "ZNASND's start never
returns" and "no `LOADER` / `every thread waits` line" were drawn from that cut
file and are wrong. `ci-results/host-trace.txt` (new in 45581017566) holds every
`[host]` line; it is short (126 lines), so it is not cut. `iop-trace.txt` is the
`[iop]` lines, capped at 20,000.

*Patch 0013 had two faults, both fixed.* The first diff held the whole 0001–0012
chain (`git diff` compares with the pristine engine), so it did not apply on top
of 0012. The probe patch 0011 also clears `g_probe_thread` before `Run()`, so the
dump printed nothing. 0013 keeps its own `g_loader_thread`.

*The run, from host-trace.txt (45581017566):*
1. LIBSD: `start returned 0`, `loaded` at 1060347 ms.
2. ZNASND: `start returned 0`, `loaded` at 1060359 ms. It registers the IOP server
   `0x01000001` (its thread 3 runs `sceSifRpcLoop`, trace line 5638).
3. EE: `SIF: bound to IOP server 0x01000001`, then `SIF: EE call, server 0x00000000
   (at 0x0002E1EC), procedure 513, 32 bytes sent`, from `0x0044CEE0`.
4. IOP: `RPC 0x01000001 procedure 513 ... served by a module`. The handler (IOP
   thread 3) calls `sceSifBindRpc(…, 0x01000002, mode 0)`, which returns "waits"
   and is retried about 1,050 times (`[IOP] Check that ZnaSnd.irx have been
   loaded...` between the tries). No reply to 513 is ever delivered.
5. EE: `every thread waits` at 1061430 ms, then after 601 frames it gives up.

*What blocks it (working hypothesis, not verified):* a deadlock. The handler for
513 waits for the EE to register the server `0x01000002`. The EE is waiting for
the reply to 513, so the registration (`sceSifRegisterRpc`, `0x24D5BC` in the
program, `9120ca7`) has not run. Either it runs after the 513 call in the
program's own order (then the handler must not block there, and the question is
why the port's bind waits), or it runs in an EE thread that never runs in the
engine (EE thread 2, entry `0x003DD2A0`, ran once, waits on a semaphore).

*Added to the workflow (not yet run):* `ci-results/ee-code.txt`, the EE functions
at `0x24CEE4` (the bind of 0x01000001), `0x24D5BC` (the registration of
0x01000002), `0x44CEE0` (the caller of 513) and `0x3DD2A0` (EE thread 2's entry),
from `engine/tools/disasm.py --game games/up --addr …`.

**Next steps:**
1. Read `ci-results/ee-code.txt`: the order of the bind, the 513 call, and the
   registration; and whether `0x24D5BC` is reached from the main thread before
   the 513 call.
2. If it is reached only after the 513 reply, the program expects the IOP handler
   not to wait for `0x01000002`: check the `sceSifBindRpc` mode and the port's
   bind behaviour (patch 0008 makes a bind wait 1 ms when no server exists).
3. If it is reached in EE thread 2, log that thread's wait (semaphore id, who
   signals it) with a new log-only patch.

**Runs 45585891104 and 45595639376 (the EE code the run stops at).**
- `ci-results/ee-code.txt`: the caller of the RPC 513 is `func_0044CEE0`. It first
  waits while `func_003DFB60(0x7A7BC0)` is nonzero (sleeping 10 ms each time), then
  sends 32 bytes from `0x7A7C00`. The trace's `0x007A7C00` is that buffer.
- `ci-results/ee-code.txt`: EE thread 2 is `func_003DD2A0`, a worker for a queue of
  one-byte commands. It waits on the semaphore at `[0x7A0000 - 0x53A0]`
  (`0x79AC60`). It is not the thread that registers `0x01000002`.
- **Correction:** the addresses `0x24CEE4` and `0x24D5BC` from `9120ca7` are not
  call sites in this analysis. `0x24CEE4` is a `nop` and `0x24D5BC` is a `daddu`
  (`ci-results/ee-code-24.txt`, lines 1033 and 1501). They were probably wrong, or
  they were return addresses from another run. The EE's `sceSifRegisterRpc` and
  `sceSifBindRpc` calls for `0x01000002` and `0x01000001` must be found by their
  constants (`lui`/`ori` of `0x0100`/`0x0002` and `0x0100`/`0x0001`), not by these
  addresses.

**Next steps (replace the earlier ones):**
1. Find every EE call that loads `0x01000002` or `0x01000001` as an argument
   (a scan of `disasm.py --all` in CI, saved as a grep result), and which of them
   is a `sceSifRegisterRpc` (`jal` to the same target as the other registrations).
2. Check whether that registration is reached before the RPC 513 call.
3. If it comes only after the reply, the bind in the IOP handler must not wait.
   If it is in a thread that does not run, log that thread's wait.

**Runs 45606669485, 45611623898, 45617023584 (the RPC ids in the EE program).**
- `scripts/ee_rpc_ids.py` (new) tracks the constants a function loads (lui, addiu,
  ori) and prints the calls after each load. In `ci-results/ee-rpc-ids.txt`:
  - `func_0044CDC0` at `0x44CDEC` loads `0x01000001`, then `func_003DF798` (the bind).
  - `func_0044D4A0` at `0x44D4CC` loads `0x01000002`, then `func_003DFC38` (the
    registration: `sceSifRegisterRpc(…, 0x01000002, handler 0x44D3A0, …)`) and
    `func_003E0050` (`sceSifRpcLoop`). So `0x44D4A0` is the body of the EE's RPC
    server thread for `0x01000002`.
- `func_0044D4A0` has no direct caller (`ci-results/ee-callers.txt`): it is only
  reachable as a thread's entry. So the thread is created somewhere, and the stop
  report lists only two EE threads (1: the main one, entry `0x200008`; 2: the
  command worker, entry `0x3DD2A0`). The registration thread never ran.
- `func_0044CDC0` (the client's start): `func_003DF000`, then `func_0044D190`, then a
  loop `sceSifBindRpc(0x7A7BC0, 0x01000001, 0)` until the client's `server` field
  (`0x7A7BE4`, offset 36) is set, then `func_003DC820`, then `func_0044CEE0(1, 0x201)`
  (the RPC 513). `func_0044D190` runs before the bind and is the next thing to read:
  it is the likely place of the thread creation for `0x44D4A0`.
- The earlier addresses `0x24CEE4` / `0x24D5BC` are not in use (see above); the
  program's own addresses are `0x44CDEC` (bind) and `0x44D4CC` (registration).

**Disc download:** the Google Drive connector can read the zip's metadata (916,253,681
bytes, MD5 `c2bdf10f…`, the same as before), but it cannot put the file in the sandbox:
`download_file` returns at most 100 MB into the model's context, and the sandbox reaches
only github, npm and pypi. The CI downloads the disc.

**Next steps:**
1. Read `ci-results/ee-funcs/func_0044D190.s`: what it creates, with which entry, and
   whether the creation succeeds (the thread count at the stop says it does not).
2. Find the callers of `func_0044D190` and `func_0044CDC0` (the `ee-callers.txt`
   lists the callers of `0x44CDC0`: `func_002DEC40`, then `func_0032F250`).
3. Check `CreateThread` / `StartThread` in the engine's kernel for the case that
   silently drops the thread (no error in the log).

**Run 45620249406: the registration thread exists, and the bind cannot see it (the cause).**
- The stop report lists three EE threads, not two: `thread 3: sleeping, priority 4,
  entry 0x0044D4A0, ran 1 times`, sleeping in `sceSifRpcLoop` (`func_003E0050`). So
  the EE's server for `0x01000002` is created and registered. (`func_0044D190` creates
  it: `CreateThread` with `{entry 0x44D4A0, stack from func_002DCB70 (AllocSysMemory-like,
  0x2800 bytes), priority 4}`, then `StartThread`. Thread 2 is created the same way.)
- The IOP's `sceSifBindRpc(0x01000002)` (patch 0005, `SifBindRpcClient` in
  `iop_libs.cpp`) looks only in `vm.rpc_servers`, the IOP's own servers. The EE's
  registration is not in any table the IOP side reads. So the bind returns "no server"
  and the handler for RPC 513 waits, forever (patch 0008 only makes it wait 1 ms).
- So the port is missing one path: an IOP bind (and the calls after it) for a server
  that the EE registered. On the real console the EE's SIF library answers the bind
  from its own server table. Options for the engine (not yet chosen):
  (a) on a bind with no IOP server, forward the bind to the EE as a SIF message and let
      the game's own EE sifrpc code answer it (faithful; needs the SIF path IOP→EE);
  (b) override the EE's `sceSifRegisterRpc` (`func_003DFC38`) to record `sid → server`
      in a host table, and let the bind use that table (smaller; the calls after the bind
      must then also reach the EE thread, which needs the same IOP→EE delivery).
- Engine state: the `engine/` submodule was not initialised in this session; it is
  now (`65c46e9`). The patch chain 0001–0013 applies cleanly on it (checked).

**Next steps:**
1. Choose (a) or (b) above. Both need the IOP's call to reach an EE thread, so the
   next patch is the IOP→EE delivery of a call and its reply.
2. Log that delivery first (log-only patch): the IOP's bind and call for `0x01000002`,
   and whether the EE thread 3 wakes.

**Decision: option (a), the EE's own sifrpc answers (patch 0014).** Option (b) would
still need the IOP→EE delivery for calls, so the delivery is built once, for both.

What patch 0014 does (`engine/host/src/iop_vm.cpp`, `iop_libs.cpp`, `iop.cpp`):
- `sceSifBindRpc` with no IOP server for the sid sends the EE a bind packet (0x80000009:
  `sid` at 32, `cd` = the IOP's client at 28), queued like the other SIF replies. A
  blocking bind waits (`Wait::RpcReply`) for the answer.
- The EE's sifrpc (ps2sdk's `_request_bind`, in the game's own code) answers with an
  RPC-end (0x80000008): `cid` 0x80000009 at 32, `sd` 36, `buf` 40, `cbuf` 44. The IOP
  copies `buf`, `cbuf`, `sd` into the client (20, 24, 36). With `sd` NULL (no server for
  the sid yet) the caller waits 1 ms before it asks again, as patch 0008 did.
- `sceSifCallRpc` on such a server sends a call packet (0x8000000A): `rpc_number` 32,
  `send_size` 36, `recvbuf` 40 (the IOP's receive address: the EE DMAs its data there),
  `recv_size` 44, `rmode` 1 (the answer's data arrives with its packet), `sd` 52. The
  arguments are written into the EE server's buffer (`buf` from the bind) first.
- The EE's answer to a call (cid 0x8000000A) runs the end function and wakes the caller.

Layouts: ps2sdk `common/include/sifrpc-common.h` (`SifRpcBindPkt_t`, `SifRpcCallPkt_t`,
`SifRpcRendPkt_t`), the same offsets `iop.cpp` already reads for the EE's requests.

Not verified yet: that the game's EE interrupt handler takes the bind packet (it does
for the replies the engine already sends), and that the EE's registration sets
`active_queue` (ps2sdk: `sceSifSetRpcQueue`). The log lines `[host] IOP: binds RPC…`,
`IOP: the EE's bind answer: server 0x…` and `IOP: RPC procedure … on the EE` show both.

### Where the EE main thread waits (runs 45657847582, 45670428784)

- Bind delivery is confirmed (run 45647073822): the IOP binds `0x01000002` on the
  EE, the EE's answer comes back, and RPC 513 is answered. The port now reaches
  the EE's wait in `0x0047DB38`, which is not the bind any more.
- The wait is on the word `0x007A982C` (`lw $v0,-0x67d4($v1)`, `$v1 = 0x7B0000`).
  The loop is in `func_0047DAE0` (CI `ci-results/ee-flag/func_0047DAE0.s`). The
  loop spins until the flag is nonzero, then sends one RPC-like request through
  `func_003DED88` (sceSifCallRpc wrapper) with server id/handle `-0x67e0` and a
  36-byte packet at `0x7A96F0`. It does up to 32 rounds.
- `func_0047C300` sets the handle to `0xB` and registers the EE command handler
  `func_0047BF98` for SIF command id `0xB` through `func_003DEB88` (sceSifAddCmdHandler:
  table at `0x7A4A28`, 12-byte entries). Then it clears the flag to 0. Only
  `func_0047BF98` writes the flag (it stores the result of `func_0047B8E8`).
  So the EE waits for an IOP command `0xB` before it sends anything.
- Write trace (45657847582 and again 45670428784): the flag is written once, as
  zero, by `0x47C300`. No nonzero write happens.
- IOP side (45670428784, `ci-results/iop-sendcmd.txt`): no `sceSifSendCmd` from
  the IOP at all, and no sifcmd#10/#12/#13 call in the trace. LIBSD and ZNASND do
  not send command `0xB`. SDRDRV is never loaded by the EE (see above).
- Conclusion: the EE blocks on a command from the IOP that no module in the port
  sends. Which IOP module sends `0xB` on the console is not yet known. Candidates to
  check: the IOP side of the sound-driver handshake (LIBSD/SDRDRV), or a
  `sceSifSendCmd` from another IOP module that is not run.
- Open: the result of the `AddIdleLoop(0x0047DB38)` run (45651299149) is unknown
  (the watch timed out; no result was read). The loop at `0x47DB38` is the flag wait
  above, not INTC polling.

- Run 45683487799 (`3a24cdb`, patches 0001-0015): the APK builds (`success`). The PC
  smoke still stops at the time limit in the loop at `0x0047DB38`, with the same guest stack
  (`0x0047DAE0` ... `0x00200008`), 689 functions. Patch 0015 is not reached in the smoke
  (no surface is lost there); its effect is the phone's, and is not yet read from a phone run.
