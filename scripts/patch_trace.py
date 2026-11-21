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


def main():
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
