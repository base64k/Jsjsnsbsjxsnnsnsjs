#!/usr/bin/env python3
"""A trace for the EE's watched functions: the memory behind their pointers.

`--watch ADDR` logs a function's argument registers at each call. A pointer
argument is only an address; what the function reads is at that address. This
adds, for watched functions, the 16 words at each pointer argument (a0, a1),
and the 16 words at the value those words point to (the cursor of a loader).
Idempotent, guarded by a marker, like the other patches.

    python scripts/patch_trace.py
"""

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HOST = os.path.join(ROOT, "engine", "host", "src", "host.cpp")

ANCHOR = "    Frame frame(address);\n    try {\n        entry->function(c);"
MARKER = "// port: the memory behind a watched function's pointers (scripts/patch_trace.py)"
BLOCK = """    // port: the memory behind a watched function's pointers (scripts/patch_trace.py)
    if (g_watching && std::find(g_watch.begin(), g_watch.end(), address) != g_watch.end()) {
        const u32 kRam = 32u << 20;
        auto dump = [&](const char* what, u32 p) {
            std::fprintf(stderr, "[watch-mem] %s %08X:", what, unsigned(p));
            for (u32 i = 0; i < 16; ++i)
                std::fprintf(stderr, " %08X", unsigned(GuestMemory().Read(p + 4 * i, 4)));
            std::fprintf(stderr, "\\n");
        };
        for (u32 k = 0; k < 2; ++k) {
            const u32 p = u32(c.r[4 + k]);
            if (p < kRam && p + 64 <= kRam) {
                dump(k ? "a1" : "a0", p);
                const u32 q = u32(GuestMemory().Read(p, 4));
                if (q < kRam && q + 64 <= kRam) dump(k ? "*a1" : "*a0", q);
            }
        }
    }
"""


# The reply of an RPC that a module served: its first words, traced (--iop-trace).
IOP_VM = os.path.join(ROOT, "engine", "host", "src", "iop_vm.cpp")
REPLY_ANCHOR = "            const u32 answer = best->c.r[2];\n"
REPLY_MARKER = "// port: the words of an RPC reply (scripts/patch_trace.py)"
REPLY_BLOCK = REPLY_ANCHOR + """            // port: the words of an RPC reply (scripts/patch_trace.py)
            if (vm.trace) {
                std::fprintf(stderr, "[iop] RPC reply 0x%08X procedure %u:", unsigned(vm.rpc_servers[best->serving.server].sid),
                             unsigned(best->serving.procedure));
                for (u32 i = 0; answer && i < 32 && i < best->serving.receive_size; i += 4)
                    std::fprintf(stderr, " %08X", unsigned(vm.Read(answer + i, 4)));
                std::fprintf(stderr, " (%u bytes out)\\n", unsigned(best->serving.receive_size));
            }
"""


def patch_iop_vm():
    if not os.path.isfile(IOP_VM):
        sys.exit("patch_trace: %s is missing (the engine submodule?)" % IOP_VM)
    with open(IOP_VM, encoding="utf-8") as handle:
        text = handle.read()
    if REPLY_MARKER in text:
        print("patch_trace: iop_vm.cpp already patched")
        return
    if text.count(REPLY_ANCHOR) != 1:
        sys.exit("patch_trace: %s: the reply's place is there %d times" % (IOP_VM, text.count(REPLY_ANCHOR)))
    text = text.replace(REPLY_ANCHOR, REPLY_BLOCK, 1)
    with open(IOP_VM, "w", encoding="utf-8") as handle:
        handle.write(text)
    print("patch_trace: iop_vm.cpp patched")


def main():
    patch_iop_vm()
    if not os.path.isfile(HOST):
        sys.exit("patch_trace: %s is missing (the engine submodule?)" % HOST)
    with open(HOST, encoding="utf-8") as handle:
        text = handle.read()
    if MARKER in text:
        print("patch_trace: host.cpp already patched")
        return
    if text.count(ANCHOR) != 1:
        sys.exit("patch_trace: %s: the place to patch is there %d times (once it must be)"
                 % (HOST, text.count(ANCHOR)))
    text = text.replace(ANCHOR, BLOCK + ANCHOR, 1)
    if text.count(MARKER) != 1:
        sys.exit("patch_trace: the patch is not in the file exactly once")
    with open(HOST, "w", encoding="utf-8") as handle:
        handle.write(text)
    print("patch_trace: host.cpp patched")


if __name__ == "__main__":
    main()
