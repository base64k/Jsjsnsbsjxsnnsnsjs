#!/usr/bin/env python3
"""Traces of the EE's unpacker (EE 0x0032DFA0..0x0032E0A0) inside the engine.

Two prints, both guarded by the marker, idempotent like the other patches:

1. `[yield]`: a yield inside the unpacker (lifted::Tick -> BudgetSpent -> the loop
   head hook: other threads and interrupts run there, which the interpreter never does).
2. `[tick]`: the unpacker's loop heads for the call whose output ends at 0x01F78900
   (call 83), with the registers the loop reads (a1, a2, a3, t0, t5, t8). These are
   compared with the interpreter's run of the same loop heads (scripts/emu_decode.py).

    python scripts/patch_yield.py
"""

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SUPPORT = os.path.join(ROOT, "engine", "runtime", "src", "lifted_support.cpp")
LIFTED = os.path.join(ROOT, "engine", "runtime", "include", "ps2rt", "lifted.h")

MARKER = "// port: the yields inside the unpacker (scripts/patch_yield.py)"
TICK_MARKER = "// port: the unpacker's loop heads for call 83 (scripts/patch_yield.py)"

SUPPORT_ANCHOR = "void BudgetSpent(Context& c, u32 address) {\n"
SUPPORT_BLOCK = SUPPORT_ANCHOR + (
    "    " + MARKER + "\n"
    "    if (address >= 0x0032DF00u && address < 0x0032E100u)\n"
    "        std::fprintf(stderr, \"[yield] 0x%08X a0=%08X a1=%08X a2=%08X a3=%08X\\n\", unsigned(address),\n"
    "                     unsigned(c.r[4]), unsigned(c.r[5]), unsigned(c.r[6]), unsigned(c.r[7]));\n"
)

LIFTED_ANCHOR = "inline void Tick(Context& c, u32 address) {\n"
LIFTED_BLOCK = LIFTED_ANCHOR + (
    "    " + TICK_MARKER + "\n"
    "    static u32 ticks_printed = 0;\n"
    "    if (address >= 0x0032DF00u && address < 0x0032E100u && c.r[7] == 0x01F78900ull &&\n"
    "        c.r[5] >= 0x01F7FCF3ull && c.r[5] < 0x01F81B7Aull && ++ticks_printed <= 4000)\n"
    "        std::fprintf(stderr, \"[tick] 0x%08X a1=%08X a2=%08X a3=%08X t0=%08X t5=%08X t8=%08X\\n\", unsigned(address),\n"
    "                     unsigned(c.r[5]), unsigned(c.r[6]), unsigned(c.r[7]), unsigned(c.r[8]), unsigned(c.r[13]),\n"
    "                     unsigned(c.r[24]));\n"
)


def patch(path, marker, anchor, block, need_cstdio):
    if not os.path.isfile(path):
        sys.exit("patch_yield: %s is missing (the engine submodule?)" % path)
    with open(path, encoding="utf-8") as handle:
        text = handle.read()
    if marker in text:
        print("patch_yield: %s already patched" % os.path.basename(path))
        return
    if text.count(anchor) != 1:
        sys.exit("patch_yield: %s: the place to patch is there %d times (once it must be)"
                 % (path, text.count(anchor)))
    text = text.replace(anchor, block, 1)
    if need_cstdio and "#include <cstdio>" not in text:
        text = text.replace("#include", "#include <cstdio>\n#include", 1)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(text)
    print("patch_yield: %s patched" % os.path.basename(path))


def main():
    patch(SUPPORT, MARKER, SUPPORT_ANCHOR, SUPPORT_BLOCK, True)
    patch(LIFTED, TICK_MARKER, LIFTED_ANCHOR, LIFTED_BLOCK, True)


if __name__ == "__main__":
    main()
