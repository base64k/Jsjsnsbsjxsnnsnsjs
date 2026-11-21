#!/usr/bin/env python3
"""Print the EE functions where the run stopped, innermost first.

The host's summary lists the guest call stack at the stop ("guest call stack
where it stopped (innermost last):", one address per line). The innermost
frames are where the fault happened, so they are the ones to disassemble.
Printed one per line; nothing else on stdout.

    python3 scripts/stop_functions.py [summary.txt] [count]
"""

import pathlib
import re
import sys

HEADER = "guest call stack where it stopped"
ADDRESS = re.compile(r"^\s+0x([0-9A-Fa-f]{6,8})\s*$")
DEFAULT_SUMMARY = "games/up/build/smoke/summary.txt"


def main():
    path = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else DEFAULT_SUMMARY)
    count = int(sys.argv[2]) if len(sys.argv) > 2 else 4
    if not path.exists():
        return
    frames, inside = [], False
    for line in path.read_text(errors="replace").splitlines():
        if HEADER in line:
            inside = True
            continue
        if inside:
            m = ADDRESS.match(line)
            if not m:
                break
            frames.append("0x" + m.group(1).upper().zfill(8))
    seen, innermost = set(), []
    for addr in reversed(frames):
        if addr not in seen:
            seen.add(addr)
            innermost.append(addr)
    for addr in innermost[:count]:
        print(addr)


if __name__ == "__main__":
    main()
