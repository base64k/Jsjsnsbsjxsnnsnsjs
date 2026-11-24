/*
 * Up's host RPC servers for IOP modules.
 *
 * IOP modules the game loads from its disc (LIBSD.IRX, SDRDRV.IRX, CRI_ADXI.IRX)
 * register RPC servers via sceSifRegisterRpc. When the EE calls such a server,
 * the host runs the module's handler in the R3000 interpreter. If a module's
 * server has no host implementation, the call is answered with zeros and noted
 * in the report - that's how we discover which IOP services the game needs.
 *
 * Register host RPC servers here with ps2host::RegisterRpcServer(sid, handler).
 * The handler receives (procedure, data) and returns the reply bytes.
 *
 * Sound driver handshake (NOT yet verified - needs the disc image):
 *   The EE probably calls an RPC server/procedure to tell the IOP sound
 *   driver to start streaming, which sets flag 0x1AEF8. Find the server id
 *   and procedure from --iop-trace output, then implement the handler here
 *   if the host needs to participate.
 *
 *   Override as little as possible: the game's own code is the point.
 */

#include "ps2host/host.h"
#include "ps2host/run.h"

namespace {

// Example RPC server handler - remove when not needed.
// std::vector<u8> SoundRpcHandler(u32 procedure, const std::vector<u8>& data) {
//     // Handle the EE's RPC call to the IOP sound driver.
//     // procedure: the function number within the server
//     // data: the arguments the EE sent
//     return {};  // empty reply (all zeros)
// }

}  // namespace

void RegisterIopSoundServers() {
    // TODO: once the disc is available and analyzed, register RPC servers here.
    // Example:
    //   ps2host::RegisterRpcServer(0x01000002, SoundRpcHandler);
    //
    // The server id 0x01000002 was mentioned in earlier findings as a guess
    // - it needs verification from the actual disc.
    //
    // Keep this minimal: the game's own code is the point.
}
