#!/usr/bin/env python3
"""Print the EE functions that contain the given addresses.

The disassembler renders functions one per file (`disasm.py --all -o DIR`);
each file's header gives its address range. A call site is not a function
start, so `--addr` cannot show its function; this finds the file whose range
covers the address and prints it.

    python3 scripts/enclosing.py build/ee_all 0x00410DC0 0x00307ACC 0x004C4BD0
"""

import pathlib
import re
import sys

HEADER = re.compile(r"address\s*:\s*0x([0-9a-fA-F]+)\s*\.\.\s*0x([0-9a-fA-F]+)")


def main():
    folder = pathlib.Path(sys.argv[1])
    targets = [int(a, 16) for a in sys.argv[2:]]
    files = sorted(folder.rglob("*.s"))
    print("%d function files scanned" % len(files))
    for target in targets:
        print("\n== the function containing 0x%08X" % target)
        found = False
        for f in files:
            text = f.read_text(errors="replace")
            m = HEADER.search(text)
            if m and int(m.group(1), 16) <= target < int(m.group(2), 16):
                print("(%s)" % f.name)
                print(text)
                found = True
                break
        if not found:
            print("(no function file covers it)")


if __name__ == "__main__":
    main()
