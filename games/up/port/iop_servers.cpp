/*
 * Up's host RPC servers for IOP modules.
 *
 * IOP modules the game loads from its disc (LIBSD.IRX, ZNASND.IRX, ...)
 * register RPC servers via sceSifRegisterRpc. When the EE calls such a server,
 * the host runs the module's handler in the R3000 interpreter. If a module's
 * server has no host implementation, the call is answered with zeros and noted
 * in the report - that's how we discover which IOP services the game needs.
 *
 * Register host RPC servers here with ps2host::RegisterRpcServer(sid, handler).
 * The handler receives (procedure, data) and returns the reply bytes.
 *
 * Sound driver handshake - CONFIRMED from CI smoke test:
 *   - ZNASND.IRX is loaded as IOP module 6 (the game's sound driver)
 *   - The EE calls RPC server 0x01000001 with procedures 513, 768, 1797, 1808
 *   - Each call sends 32 bytes; previously answered with zeros (no host impl)
 *   - These calls go through sceSifCallRpc -> SifSetDma, call chain:
 *     0x003DF968 (sceSifCallRpc) -> 0x003DED88 -> 0x003DEC50 -> 0x003DC960 (SifSetDma)
 *   - Without a proper handler, ZNASND never starts streaming and flag 0x1AEF8
 *     is never set, leaving the game in an idle loop at 0x0044E068
 *
 * Override as little as possible: the game's own code is the point.
 */

#include <cstdio>
#include <cstdint>
#include <cstring>
#include <sstream>
#include <string>
#include <vector>

#include "ps2host/host.h"
#include "ps2host/run.h"

namespace {

std::string HexDump(const std::vector<u8>& data) {
    std::ostringstream oss;
    for (std::size_t i = 0; i < data.size(); ++i) {
        if (i > 0) oss << ' ';
        oss << std::hex << std::setw(2) << std::setfill('0')
            << static_cast<int>(data[i]);
    }
    return oss.str();
}

// ZNASND sound driver RPC server (server id 0x01000001).
// The EE calls procedures 513, 768, 1797, 1808 with 32-byte argument blocks.
// These are the sound driver's control interface - init, start streaming,
// buffer management, etc. Without a host handler, ZNASND receives zero
// answers and never sets IOP flag 0x1AEF8, so the game spins in its idle
// loop waiting for the sound driver to respond.
std::vector<u8> ZnasndRpcHandler(u32 procedure, const std::vector<u8>& data) {
    std::fprintf(stderr,
                 "[iop] ZNASND RPC server 0x01000001: procedure %u, %zu bytes: %s\n",
                 procedure, data.size(), HexDump(data).c_str());

    // TODO: implement proper responses based on ZNASND protocol discovered
    // from --iop-trace. For now, return zeros (same as no implementation).
    // The correct response likely contains status flags or buffer addresses
    // that tell ZNASND to start streaming and set flag 0x1AEF8.
    return std::vector<u8>(data.size(), 0);
}

}  // namespace

void RegisterIopSoundServers() {
    // Register host RPC server for ZNASND sound driver (server 0x01000001).
    // Confirmed from CI smoke test: the EE calls this server with procedures
    // 513, 768, 1797, 1808. Implementing this handler should let ZNASND
    // start streaming and set IOP flag 0x1AEF8.
    ps2host::RegisterRpcServer(0x01000001u, ZnasndRpcHandler);
}
