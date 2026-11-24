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
 * Sound driver handshake - CONFIRMED from CI smoke test (run 45338174585):
 *   - ZNASND.IRX is loaded as IOP module 6 (the game's sound driver,
 *     NOT SDRDRV as previously guessed). LIBSD.IRX is module 5.
 *   - The game runs full 120s without crashing, draws pictures (562 GS
 *     primitives, 860160 pixels), but is stuck in an idle loop at
 *     0x0044E068 calling SifSetDChain ~45M times.
 *   - The EE calls RPC server 0x01000001 with procedures 513, 768, 1797,
 *     1808 (32 bytes each) via sceSifCallRpc -> SifSetDma.
 *   - Previously answered with zeros (no host implementation) - ZNASND
 *     never starts streaming, flag 0x1AEF8 never set.
 *   - Handler implemented in iop_servers.cpp (ZnasndRpcHandler). Currently
 *     logs calls and returns zeros; needs proper responses from --iop-trace.
 *
 * Known from the engine source:
 *   - libsd (iop_libs.cpp) implements all 32 exports: sceSdInit, SetParam,
 *     BlockTrans, VoiceTrans, ProcBatch, callbacks, IRQ handlers.
 *   - SPU2 (spu2.cpp) fully decodes/mixes ADPCM at 48 kHz; output wired via
 *     EnableSound() -> AudioFrames() when --audio is given.
 *   - SoundInterrupts() runs in the IOP scheduler loop (iop_vm.cpp:396).
 *
 * Reference (DQ8-Recompiled PR #1): run IOP sound modules unmodified on the
 * emulated IOP; the game's own sound code talks to them over SIF; keep
 * sceSifCallRpc bound to the runtime, not stubbed.
 */

#include "ps2host/host.h"
#include "ps2host/run.h"

void RegisterIopSoundServers();

void RegisterGameOverrides() {
    // Name the IOP sound modules to run from the disc. Confirmed from CI:
    // LIBSD.IRX (module 5) and ZNASND.IRX (module 6) are loaded from
    // cdrom0:\MODULES\IOPRP280.IMG. The interpreter loads each one when the
    // game's code asks for it (sceSifLoadModule), relocates it, and binds its
    // imports to the host's IOP library HLE (iop_libs.cpp).
    ps2host::iop::RunModule("LIBSD.IRX");   // Sound Library (627 exports)
    ps2host::iop::RunModule("ZNASND.IRX");  // The game's sound driver
    // CRI_ADXI.IRX may also be present - uncomment if found on the disc.
    // ps2host::iop::RunModule("CRI_ADXI.IRX"); // CRI ADX streamed audio

    // Register host RPC servers for IOP sound modules (LIBSD, ZNASND).
    // Called once at startup, before the IOP runs. Keep this minimal.
    RegisterIopSoundServers();

    // TODO: once --iop-trace reveals correct ZNASND RPC responses, refine
    // ZnasndRpcHandler in iop_servers.cpp. Also add function overrides here
    // for any EE functions that need host redirection.
    //
    // Expected overrides:
    //   - The EE function that writes IOP flag 0x1AEF8 (hook if the game's
    //     own write is wrong - address from the analysis).
    //   - Any function that the host needs to redirect for sound/hardware
    //     differences between PS2 and PC.
    //
    // Keep this minimal: the game's own code is the point.
}
