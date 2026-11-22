#!/usr/bin/env python3
"""Decode every call of the unpacker (EE 0x0032DFA0) in Python, from the bytes the run saw.

The host's trace (patch_trace.py) prints, at each call of the unpacker, its
argument block (a0, 64 bytes) and its whole input (a1, 0x400 bytes) as
`[watch-src]` lines, and the call's registers as `[watch]` lines. This takes
those bytes, runs the transcription of the MIPS listing (decode_check.py) on
them in a RAM of its own, and says whether each call ends exactly at its
output size, and how much of its input it used.

It answers one question: is the fault in the game's bytes (the decoder run on
its own input stops wrong) or in the engine's run of the same code (the Python
run stops at the size and the engine's does not)? The output window before the
output is not in the trace; it starts as zeros here, so a match that reaches
back past the output may differ.

    python3 scripts/decode_src.py <report.txt>
"""

import importlib.util
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
RAM_SIZE = 32 << 20
FUNCTION = "0x0032DFA0"


def load_decoder():
    spec = importlib.util.spec_from_file_location("decode_check", os.path.join(HERE, "decode_check.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def calls(text):
    """Each call's (a0, a1, a2, a3) from the [watch] entry lines, in order."""
    pattern = re.compile(r"\[watch\] %s a0=([0-9A-Fa-f]+) a1=([0-9A-Fa-f]+) a2=([0-9A-Fa-f]+) a3=([0-9A-Fa-f]+)"
                         % re.escape(FUNCTION))
    return [tuple(int(v, 16) for v in m) for m in pattern.findall(text)]


def sources(text):
    """Each call's (a0 bytes, a1 bytes) from the [watch-src] lines, in order."""
    a0s, a1s = [], []
    for line in text.splitlines():
        if line.startswith("[watch-src] a0 "):
            a0s.append(bytes(int(v, 16) for v in line.split()[4:]))
        elif line.startswith("[watch-src] a1 "):
            a1s.append(bytes(int(v, 16) for v in line.split()[4:]))
    return list(zip(a0s, a1s))


def main():
    text = open(sys.argv[1], errors="replace").read()
    decoder = load_decoder()
    entries = calls(text)
    inputs = sources(text)
    if not inputs:
        print("decode src: no [watch-src] lines in the report (the trace needs --watch %s)" % FUNCTION)
        return
    print("decode src: %d call(s) with their input in the report" % len(inputs))
    plausible = skipped = reached = overran = 0
    shown = 0
    for k, ((arg, src), entry) in enumerate(zip(inputs, entries or [])):
        a0, a1, a2, a3 = entry
        size = int.from_bytes(arg[4:8], "little")
        comp = int.from_bytes(arg[8:12], "little")
        # The decoder reads only the size (a0+4) and the flag (a0+13), and the
        # stream from a1+8. A size of 0 or past 64 KB is not a chunk to decode.
        if not (0 < size <= 0x10000):
            skipped += 1
            continue
        plausible += 1
        ram = bytearray(RAM_SIZE)
        ram[a0:a0 + 64] = arg
        ram[a1:a1 + len(src)] = src
        copy = bytearray(ram)
        result, written, used, end = decoder.decode(copy, a0, a1, a2, limit=a2 + size)
        if result == "reached the chunk's end":
            reached += 1
        copy = bytearray(ram)
        full, fwritten, fused, fend = decoder.decode(copy, a0, a1, a2)
        if fend != a2 + size:
            overran += 1
        if shown < 30:
            shown += 1
            print("decode src: call %d a1=0x%08X a2=0x%08X size %d comp %d | to the end: %s, input %d/%d | "
                  "no limit: %s, a2 ended %+d from the output end"
                  % (k, a1, a2, size, comp, result, used, comp, full, fend - (a2 + size)))
    print("decode src: %d calls with a chunk header, %d skipped (not a header), %d reached their end exactly, "
          "%d ran past their end" % (plausible, skipped, reached, overran))
    if shown == 0 and plausible:
        print("decode src: no call was shown")

if __name__ == "__main__":
    main()
