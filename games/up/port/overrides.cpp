/*
 * Up's host implementations of guest functions.
 *
 * An override replaces the translated function at its address: the way a port
 * redirects code that drives hardware the host provides differently, and the
 * way the PC features hook in (a settings menu in the game's own menus,
 * widescreen, the mouse's targets). Register them here with
 * ps2host::Override(address, function, "why"); the original stays callable as
 * F_<ADDRESS>(c). See the engine's docs/PORTING.md and the ps2-port skill.
 *
 * Override as little as possible: the game's own code is the point.
 *
 * Sound driver handshake (NOT yet verified - needs the disc image):
 *   The IOP sound driver polls flag 0x1AEF8 in IOP RAM. The game's EE code
 *   must set it (via an RPC call or an SIF DMA write) before the driver
 *   starts streaming audio. Without it, the game crashes around the
 *   25-second mark, before the menu appears.
 *
 *   To fix:
 *   1. Run the disc through analyze.py → signatures.py → lift.py to get
 *      function addresses for SLUS_218.64.
 *   2. Use --iop-trace to see which IOP library calls the sound modules make,
 *      and which RPC server/procedure the EE calls to set flag 0x1AEF8.
 *   3. Add the override here: ps2host::Override(address, hook, "why").
 *   4. Register IOP sound modules via ps2host::iop::RunModule("LIBSD.IRX"),
 *      ps2host::iop::RunModule("SDRDRV.IRX") (names confirmed from the disc).
 *
 *   Known from the engine source:
 *   - libsd (iop_libs.cpp) implements all 32 exports: sceSdInit, SetParam,
 *     BlockTrans, VoiceTrans, ProcBatch, callbacks, IRQ handlers.
 *   - SPU2 (spu2.cpp) fully decodes/mixes ADPCM at 48 kHz; output wired via
 *     EnableSound() → AudioFrames() when --audio is given.
 *   - SoundInterrupts() runs in the IOP scheduler loop (iop_vm.cpp:396).
 *
 *   Reference (DQ8-Recompiled PR #1): run IOP sound modules unmodified on the
 *   emulated IOP; the game's own sound code talks to them over SIF; keep
 *   sceSifCallRpc bound to the runtime, not stubbed.
 */

#include "ps2host/host.h"
#include "ps2host/run.h"

void RegisterIopSoundServers();

void RegisterGameOverrides() {
    // Name the IOP sound modules to run from the disc. The interpreter loads
    // each one when the game's code asks for it (sceSifLoadModule), relocates
    // it, and binds its imports to the host's IOP library HLE (iop_libs.cpp).
    // Module file names are confirmed from the disc's IOP module list.
    //ps2host::iop::RunModule("LIBSD.IRX");   // Sound Library (627 exports)
    //ps2host::iop::RunModule("SDRDRV.IRX");  // Sound Driver (476 exports)
    //ps2host::iop::RunModule("CRI_ADXI.IRX"); // CRI ADX streamed audio (73 exports)
    // Uncomment once the actual module file names are known from the disc.

    // Register host RPC servers for IOP sound modules (LIBSD, SDRDRV, CRI_ADXI).
    // Called once at startup, before the IOP runs. Keep this minimal.
    RegisterIopSoundServers();

    // TODO: once the disc is available and analyzed, add function overrides here.
    // Example:
    //   ps2host::Override(0x00123456u, SomeHook, "what it does and why");
    //
    // Expected overrides for sound:
    //   - The EE function that writes IOP flag 0x1AEF8 (find its address
    //     from the analysis; hook it if the game's own write is wrong).
    //   - Any function that the host needs to redirect for sound/hardware
    //     differences between PS2 and PC.
    //
    // Keep this minimal: the game's own code is the point.
}
