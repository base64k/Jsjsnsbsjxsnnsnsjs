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
 *   - Each call sends 32 bytes via sceSifCallRpc -> SifSetDma
 *   - Previously answered with zeros (no host implementation) - ZNASND never
 *     starts streaming, flag 0x1AEF8 never set, game stuck in idle loop at
 *     0x0044E068 calling SifSetDChain ~45M times
 *
 *   Handler logs each call and returns a status response. The correct
 *   responses still need to be determined from --iop-trace output (blocked by
 *   IOP hardware write 0xBF801404 which needs engine-side handling).
 *
 * Override as little as possible: the game's own code is the point.
 */

#include <cstdint>
#include <cstdio>
#include <cstring>
#include <iomanip>
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
        oss << std::hex << std::uppercase << std::setw(2) << std::setfill('0')
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
//
// The handler logs each call (procedure + data hex dump) and returns a
// response with a non-zero status (first u32 = 1) so ZNASND can proceed.
// The exact expected responses still need to be determined from --iop-trace,
// but that requires engine-side handling of IOP hardware write 0xBF801404
// (SPU2 register on the IOP side).
std::vector<u8> ZnasndRpcHandler(u32 procedure, const std::vector<u8>& data) {
    std::fprintf(stderr,
                 "[iop] ZNASND RPC server 0x01000001: procedure %u, %zu bytes: %s\n",
                 procedure, data.size(), HexDump(data).c_str());

    // Build a response: first u32 = status (1 = OK), rest mirrors the request.
    std::vector<u8> reply(data.size(), 0);
    u32 status = 1;  // non-zero status so ZNASND knows the call succeeded
    std::memcpy(reply.data(), &status, sizeof(status));
    return reply;
}

}  // namespace

void RegisterIopSoundServers() {
    // Register host RPC server for ZNASND sound driver (server 0x01000001).
    // Confirmed from CI smoke test: the EE calls this server with procedures
    // 513, 768, 1797, 1808. Implementing this handler should let ZNASND
    // start streaming and set IOP flag 0x1AEF8.
    ps2host::RegisterRpcServer(0x01000001u, ZnasndRpcHandler);
}
