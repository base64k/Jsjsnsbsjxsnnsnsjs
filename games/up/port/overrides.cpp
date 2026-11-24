/*
 * Up's host implementations of guest functions.
 *
 * An override replaces the translated function at its address: the way a port
 * redirects code that drives hardware the host provides differently, and the
 * way the PC features hook in. Register them here with
 * ps2host::Override(address, function, "why"); the original stays callable as
 * F_<ADDRESS>(c). See the engine's docs/PORTING.md and the ps2-port skill.
 *
 * Override as little as possible: the game's own code is the point.
 *
 * Sound driver: ZNASND.IRX is the game's own sound driver (IOP module 6). It
 * runs for real in the IOP interpreter (RunModule below), with the sound
 * library's imports bound to the host's libsd. Its IOP hardware accesses
 * (0xBF80xxxx) need the engine's IOP hardware registers, which are in
 * games/up/engine-patches/0001-iop-hardware-registers.patch and applied to
 * the engine checkout before every build.
 *
 * Earlier attempts that are NOT here any more (see git history and
 * docs/FINDINGS.md): answering ZNASND's RPC server 0x01000001 with guessed
 * replies (iop_servers.cpp), which never unblocked the game.
 */

#include "ps2host/host.h"
#include "ps2host/iop_vm.h"
#include "ps2host/run.h"
#include "ps2host/settings.h"

#include "gpu_pipelines.h"

void RegisterGameOverrides() {
    // The game's own sound driver, from the disc, in the IOP interpreter. The
    // sound library (LIBSD.IRX) stays the host's: its exports are the host's
    // libsd, which ZNASND imports.
    ps2host::iop::RunModule("ZNASND.IRX");

    // The GPU pipelines this game draws with (scripted runs, the engine's own
    // keys): made in the background from the start, so the first race or menu
    // makes none in the middle of it. Regenerate with
    // engine/tools/make_pipeline_hints.py when the engine's pipeline keys change.
    ps2host::SetGpuPipelineHints(kGpuPipelineHints, sizeof(kGpuPipelineHints) / sizeof(kGpuPipelineHints[0]));

    // The FPS counter on by default (F1 turns it off, and the choice is kept in
    // the settings file). On a phone: the frame rate in the corner of the screen.
    if (ps2host::Setting("fps_counter", "").empty()) ps2host::RunSetting("fps_counter", "on");

    // Name the wait loops the game spins in while it waits for something the
    // host answers late (the sound driver's status, text loading). The host
    // skips virtual time in these loops so the game moves past them instead of
    // burning real time. Addresses seen in CI smoke runs.
    ps2host::AddIdleLoop(0x0044AA50u);
    ps2host::AddIdleLoop(0x00356AF0u);
    ps2host::AddIdleLoop(0x0030CCB4u);
    ps2host::AddIdleLoop(0x0045A738u);
    ps2host::AddIdleLoop(0x003F4674u);
}
