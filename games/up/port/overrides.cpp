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
 */

#include "ps2host/host.h"
#include "ps2host/iop_vm.h"
#include "ps2host/run.h"

void RegisterGameOverrides() {
    // Up's own sound driver (ZNASND.IRX) and the sound library it uses
    // (LIBSD.IRX) run in the IOP interpreter from the disc, as the game ships
    // them: the driver's RPC server (0x01000001) is then the game's own, not an
    // answer of zeros. The other modules (pads, memory cards) stay host-served
    // until their runs show the need.
    ps2host::iop::RunModule("ZNASND.IRX");
    ps2host::iop::RunModule("LIBSD.IRX");

    // ps2host::Override(0x00123456u, SomeHook, "what it does and why");
}
