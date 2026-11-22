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
    for k, ((arg, src), entry) in enumerate(zip(inputs, entries or [None] * len(inputs))):
        if entry is None:
            print("decode src: call %d: no entry line" % k)
            continue
        a0, a1, a2, a3 = entry
        ram = bytearray(RAM_SIZE)
        ram[a0:a0 + 64] = arg
        ram[a1:a1 + len(src)] = src
        size = int.from_bytes(arg[4:8], "little")
        comp = int.from_bytes(arg[8:12], "little")
        print("decode src: call %d: a0=0x%08X a1=0x%08X a2=0x%08X a3=0x%08X, size %d (0x%X), compressed %d (0x%X)"
              % (k, a0, a1, a2, a3, size, size, comp, comp))
        print("decode src:   header words at a1: %s" % " ".join("%08X" % int.from_bytes(src[i:i + 4], "little")
                                                             for i in range(0, 16, 4)))
        if a3 != (a2 + size) & 0xFFFFFFFF:
            print("decode src:   note: a3 (0x%08X) is not a2 + size (0x%08X)" % (a3, (a2 + size) & 0xFFFFFFFF))
        copy = bytearray(ram)
        result, written, used, end = decoder.decode(copy, a0, a1, a2, limit=a2 + size)
        print("decode src:   to the chunk's end (%d bytes): %s, %d written, input used %d of %d"
              % (size, result, written, used, comp))
        copy = bytearray(ram)
        result, written, used, end = decoder.decode(copy, a0, a1, a2)
        print("decode src:   with no limit: %s, %d written, a2 ended at 0x%08X (%d past the output)"
              % (result, written, end, end - a2 - size))


if __name__ == "__main__":
    main()
