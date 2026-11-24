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


## CI smoke test results (latest runs)

The CI runner **can** fetch the disc from Google Drive and run the full pipeline.
Results saved to `ci-results/smoke-summary.txt` and `ci-results/port-report.txt`.

**Key findings (latest run, 301s timeout):**

- **Game runs for full 301 seconds (time limit) — does NOT crash at 25s**
  Runs stably with `--audio`, libsd/SPU2 wired, and ZNASND RPC handler.

- **Game draws pictures**: 6,704,434 GS primitives, 9,582,335,118 pixels written,
  22 frames captured. Massive improvement from 562 primitives / 860,160 pixels
  in the first run.

- **Not stuck in idle loop** — progressed through multiple loop addresses:
  `0x0044E068` → `0x0044AA50` → `0x00356AF0` → `0x0030CCB4` → `0x0045A738` →
  `0x003F4674` (after StringCopy) → `0x0044A9F8`. Game is actively rendering
  and processing interrupts (SPU2/DMA), not just spinning.

- **IOP sound modules loaded**: LIBSD (module 5), ZNASND (module 6 — the game's
  sound driver, NOT SDRDRV).

- **RPC server `0x01000001` has host implementation** (`ZnasndRpcHandler`):
  Observed procedures: 513, 768, 1797 (init), 1808/1809 (buffer submit/poll loop),
  1805/1810/1811 (setup), 772 (notification). Handler returns status=1 + echoed
  request data + incrementing counter for procedure 1809 (polling).
  Procedure 772 now sends varied data (was all zeros) — ZNASND is initializing.

- **RunModule calls disabled** in `overrides.cpp`: loading LIBSD/ZNASND via
  `RunModule` causes IOP crash on write to `0xBF801404` (SPU2 register). Game
  loads modules via `sceSifLoadModule` from disc instead.

**Current blocker:** Menu has not appeared yet. Game runs 301s and renders
millions of primitives but is still in a loop at `0x0044A9F8`. ZNASND RPC
handler responds with status=1 but ZNASND may need more specific responses
to set IOP flag `0x1AEF8` and start streaming. `--iop-trace` would reveal the
correct responses but crashes on IOP hardware write `0xBF801404` (needs
engine-side IOP hardware register HLE in `iop_vm.cpp`).

**Next steps:**
1. Get `--iop-trace` working: implement IOP hardware register handling
   (SPU2 `0xBF800000-0xBFFFFFFF`) in engine `iop_vm.cpp` `WriteFault`/`ReadFault`
   so `--iop-trace` doesn't crash on `0xBF801404`
2. Re-run with `--iop-trace` to capture exact RPC responses ZNASND expects
3. Refine `ZnasndRpcHandler` with proper responses so ZNASND sets flag `0x1AEF8`
4. Once menu appears, APK can be published (currently blocked per user constraint)

**What still needs the disc** (CI can fetch it):
- Re-verify call 6 / `0x1AEF8` against `SLUS_218.64`
- Record verified entries in `games/up/config/functions.csv`

