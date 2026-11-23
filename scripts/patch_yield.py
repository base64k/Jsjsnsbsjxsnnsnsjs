#!/usr/bin/env python3
"""A trace of the EE's yields inside the unpacker (EE 0x0032DFA0..0x0032E0A0).

The translated code yields at each loop head when its budget is spent or the
scheduler asks (lifted::Tick -> BudgetSpent -> the loop head hook: other threads
and interrupts run there, which the interpreter never does). This prints, for a
yield inside the unpacker, the address and its arguments:

    [yield] 0x0032DFB8 a0=... a1=... a2=... a3=...

Idempotent, guarded by a marker, like the other patches.

    python scripts/patch_yield.py
"""

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SUPPORT = os.path.join(ROOT, "engine", "runtime", "src", "lifted_support.cpp")

ANCHOR = "void BudgetSpent(Context& c, u32 address) {\n"
MARKER = "// port: the yields inside the unpacker (scripts/patch_yield.py)"
BLOCK = ANCHOR + (
    "    " + MARKER + "\n"
    "    if (address >= 0x0032DF00u && address < 0x0032E100u)\n"
    "        std::fprintf(stderr, \"[yield] 0x%08X a0=%08X a1=%08X a2=%08X a3=%08X\\n\", unsigned(address),\n"
    "                     unsigned(c.r[4]), unsigned(c.r[5]), unsigned(c.r[6]), unsigned(c.r[7]));\n"
)


def main():
    if not os.path.isfile(SUPPORT):
        sys.exit("patch_yield: %s is missing (the engine submodule?)" % SUPPORT)
    with open(SUPPORT, encoding="utf-8") as handle:
        text = handle.read()
    if MARKER in text:
        print("patch_yield: lifted_support.cpp already patched")
        return
    if text.count(ANCHOR) != 1:
        sys.exit("patch_yield: %s: the place to patch is there %d times (once it must be)"
                 % (SUPPORT, text.count(ANCHOR)))
    text = text.replace(ANCHOR, BLOCK, 1)
    if "#include <cstdio>" not in text:
        text = text.replace("#include", "#include <cstdio>\n#include", 1)
    with open(SUPPORT, "w", encoding="utf-8") as handle:
        handle.write(text)
    print("patch_yield: lifted_support.cpp patched")


if __name__ == "__main__":
    main()
