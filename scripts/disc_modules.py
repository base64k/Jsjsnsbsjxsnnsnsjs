#!/usr/bin/env python3
"""What the disc's own files say about the SIF RPC servers the port's trace names.

The IOP trace shows a sound module binding RPC server 0x01000002 and waiting for
it ("Check that ZnaSnd.irx have been loaded"); nothing in the port registers it.
This reads the disc's MODULES folder and the program, and reports for each file
the strings that name a sound module and where the server ids (as little-endian
words) appear in it. The report says which file can serve 0x01000002.

usage: disc_modules.py ISO EXTRACTED_DIR ENGINE_DIR OUT
"""
import os
import re
import struct
import subprocess
import sys

SERVERS = {"0x01000001": 0x01000001, "0x01000002": 0x01000002,
           "0x80000001": 0x80000001, "0x80000006": 0x80000006}
NAMES = re.compile(rb"(?i)zna|znasnd|cri_adx|libsd|sdrdrv|\.irx|sifrpc|sifcmd")

lines = []


def say(text=""):
    lines.append(text)


def scan(path, label):
    with open(path, "rb") as f:
        data = f.read()
    say("== %s (%d bytes)" % (label, len(data)))
    names = []
    for m in re.finditer(rb"[\x20-\x7e]{4,}", data):
        if NAMES.search(m.group()):
            names.append(m.group().decode("ascii", "replace"))
    for name in names[:25]:
        say("  string: %s" % name)
    if len(names) > 25:
        say("  ... %d more strings" % (len(names) - 25))
    for label_sid, sid in SERVERS.items():
        needle = struct.pack("<I", sid)
        hits = []
        at = data.find(needle)
        while at >= 0 and len(hits) < 8:
            hits.append("0x%X" % at)
            at = data.find(needle, at + 1)
        total = data.count(needle)
        if total:
            say("  word %s (LE): %d times, first at %s" % (label_sid, total, ", ".join(hits)))


def walk(folder):
    found = []
    for root, _, files in os.walk(folder):
        for name in files:
            found.append(os.path.join(root, name))
    return sorted(found)


def main():
    iso, extracted, engine, out = sys.argv[1:5]
    work = os.path.join(os.path.dirname(out) or ".", "disc-modules")
    if not os.path.isfile(iso):
        say("no disc image at %s: nothing to scan" % iso)
    else:
        os.makedirs(work, exist_ok=True)
        tool = os.path.join(engine, "tools", "isotool.py")
        done = subprocess.run([sys.executable, tool, "extract", iso, "MODULES", "-o", work],
                              capture_output=True, text=True)
        say("isotool extract MODULES: exit %d %s" % (done.returncode,
                                                    (done.stderr or done.stdout).strip()[-300:]))
        for path in walk(work):
            scan(path, "MODULES/" + os.path.relpath(path, work))
    if os.path.isdir(extracted):
        for path in walk(extracted):
            scan(path, "program " + os.path.relpath(path, extracted))
    else:
        say("no extracted program in %s" % extracted)
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    with open(out, "w") as f:
        f.write("\n".join(lines[:4000]) + "\n")
    print("\n".join(lines[:200]))


if __name__ == "__main__":
    main()
