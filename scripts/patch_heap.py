#!/usr/bin/env python3
"""Log the game's SetupHeap(start, size) calls, for the heap's range.

The engine's kernel returns start + size as the heap's end and does not say
where the heap is. A run's bad pointer (a free-list link into another region)
can only be read against that range, so each call prints it to stderr:

    [heap] SetupHeap start=0x... size=0x... end=0x...

Idempotent, guarded by a marker, like the other patches (scripts/patch_trace.py).

    python scripts/patch_heap.py
"""

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KERNEL = os.path.join(ROOT, "engine", "host", "src", "kernel.cpp")

ANCHOR = "            k.heap_end = size == 0xFFFFFFFFu ? k.stack_base : start + size;\n"
MARKER = "// port: SetupHeap's range (scripts/patch_heap.py)"
BLOCK = ANCHOR + (
    "            " + MARKER + "\n"
    "            std::fprintf(stderr, \"[heap] SetupHeap start=0x%08X size=0x%08X end=0x%08X\\n\",\n"
    "                         unsigned(start), unsigned(size), unsigned(k.heap_end));\n"
)


def main():
    if not os.path.isfile(KERNEL):
        sys.exit("patch_heap: %s is missing (the engine submodule?)" % KERNEL)
    with open(KERNEL, encoding="utf-8") as handle:
        text = handle.read()
    if MARKER in text:
        print("patch_heap: kernel.cpp already patched")
        return
    if text.count(ANCHOR) != 1:
        sys.exit("patch_heap: %s: the place to patch is there %d times (once it must be)"
                 % (KERNEL, text.count(ANCHOR)))
    text = text.replace(ANCHOR, BLOCK, 1)
    if "#include <cstdio>" not in text:
        text = text.replace("#include", "#include <cstdio>\n#include", 1)
    with open(KERNEL, "w", encoding="utf-8") as handle:
        handle.write(text)
    print("patch_heap: kernel.cpp patched")


if __name__ == "__main__":
    main()
