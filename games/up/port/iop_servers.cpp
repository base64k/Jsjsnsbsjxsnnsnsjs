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
 * Sound driver handshake - CONFIRMED from CI smoke test (run 45356200859):
 *   - ZNASND.IRX is loaded as IOP module 6 (the game's sound driver)
 *   - RPC server 0x01000001 is bound by the EE
 *   - Procedures observed: 513, 768, 1797 (init), 1808, 1809 (poll loop),
 *     1805, 1810, 1811 (setup), 772 (repeated notification)
 *   - Each call sends 32 bytes via sceSifCallRpc -> SifSetDma
 *   - Previously answered with zeros - ZNASND never starts streaming,
 *     flag 0x1AEF8 never set, game stuck in idle loop at 0x0044E068
 *   - Now answered with status=1 - game runs 122s, draws 3.3M primitives,
 *     but still not at the menu (loops at 0x0044AA50)
 *
 * Response format (32 bytes, matching request size):
 *   Bytes 0-3: status (1 = OK/ready, 0 = busy/error)
 *   Bytes 4-31: procedure-specific data
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

// Read a little-endian u32 from data at offset.
u32 ReadU32(const std::vector<u8>& data, std::size_t offset) {
    u32 value = 0;
    if (offset + 4 <= data.size()) {
        std::memcpy(&value, data.data() + offset, 4);
    }
    return value;
}

// ZNASND sound driver RPC server (server id 0x01000001).
// The EE calls procedures 513, 768, 1797, 1808 with 32-byte argument blocks.
// These are the sound driver's control interface - init, start streaming,
// buffer management, etc. Without a host handler, ZNASND receives zero
// answers and never sets IOP flag 0x1AEF8, so the game spins in its idle
// loop waiting for the sound driver to respond.
//
// Response strategy (derived from observed call patterns):
//   - 513 (init, two buffer ptrs):  return status=1 + echo of buffer info
//   - 768 (init, format params):   return status=1
//   - 1797 (init, volume):         return status=1
//   - 1808 (buffer submit):        return status=1 (accepted)
//   - 1809 (buffer poll):          return status=1 (buffer ready)
//   - 1805/1810/1811 (setup):      return status=1
//   - 772 (notification):          return status=1
//
// The first u32 of the reply is the status. Non-zero tells ZNASND the call
// succeeded and it can proceed. This should let ZNASND set flag 0x1AEF8 and
// start streaming, which should unblock the game's idle loop and let the
// menu appear.
static u32 g_poll_counter = 0;

std::vector<u8> ZnasndRpcHandler(u32 procedure, const std::vector<u8>& data) {
    std::fprintf(stderr,
                 "[iop] ZNASND RPC server 0x01000001: procedure %u, %zu bytes: %s\n",
                 procedure, data.size(), HexDump(data).c_str());

    // Build a response matching the request size. Echo the request back with
    // the first u32 replaced by the status - this gives ZNASND its own buffer
    // pointers, positions and sizes back, which it needs to know which buffer
    // is accepted/ready.
    std::vector<u8> reply = data;

    u32 status = 1;  // non-zero = OK

    // For the polling call (1809), return an incrementing counter so ZNASND
    // can see that the host is answering its polls and is not stuck. This
    // counter is part of the handshake that lets ZNASND set IOP flag 0x1AEF8.
    if (procedure == 1809) {
        g_poll_counter++;
        std::memcpy(reply.data() + 4, &g_poll_counter, sizeof(g_poll_counter));
    }

    std::memcpy(reply.data(), &status, sizeof(status));
    return reply;
}

}  // namespace

void RegisterIopSoundServers() {
    // Register host RPC server for ZNASND sound driver (server 0x01000001).
    // Confirmed from CI smoke test: the EE calls this server with procedures
    // 513, 768, 1797, 1808, 1809, 1805, 1810, 1811, 772. Implementing this
    // handler should let ZNASND start streaming and set IOP flag 0x1AEF8.
    ps2host::RegisterRpcServer(0x01000001u, ZnasndRpcHandler);
}
