#!/usr/bin/env python3
"""Run the game's LZ-style chunk decoder (EE 0x0032DFA0) in Python, on the
EE RAM dump of a run, with the arguments of its last call (from the watch).

A transcription of the MIPS listing in the run's report: if the Python copy
runs past the end of RAM too, the bytes or the arguments are wrong; if it
finishes, the engine's own run of the same call did something else (the
lifted code, or the arguments as the engine passed them).

    python3 scripts/decode_check.py <ram.bin> <summary.txt> [function]

Prints a few lines on stdout; the workflow appends them to the summary.
"""

import re
import sys

RAM_SIZE = 32 << 20
FUNCTION = "0x0032DFA0"


def s32(v):
    v &= 0xFFFFFFFF
    return v - (1 << 32) if v & 0x80000000 else v


def last_call(text, function):
    pattern = re.compile(
        r"\[watch\] %s a0=([0-9A-Fa-f]+) a1=([0-9A-Fa-f]+) a2=([0-9A-Fa-f]+) a3=([0-9A-Fa-f]+)"
        % re.escape(function))
    found = pattern.findall(text)
    if not found:
        return None
    a0, a1, a2, _ = found[-1]
    return int(a0, 16), int(a1, 16), int(a2, 16)


class Overflow(Exception):
    pass


trace = []


def decode(ram, a0, a1, a2):
    """The decoder's own loop, instruction by instruction (the MIPS listing)."""
    written = 0
    v1 = int.from_bytes(ram[(a0 + 4) & 0x1FFFFFF:(a0 + 8) & 0x1FFFFFF], "little")
    a1 = a1 + 8
    a3 = (a2 + v1) & 0xFFFFFFFF
    t4, t3 = 0x0E, 0x3FFF
    t0 = ram[a1 & 0x1FFFFFF]
    state = "L000"

    def rd(addr):
        return ram[addr & 0x1FFFFFF]

    def wr(addr, value):
        nonlocal written
        if addr >= RAM_SIZE:
            raise Overflow(addr)
        ram[addr] = value & 0xFF
        written += 1

    flag = s32(ram[(a0 + 13) & 0x1FFFFFF])  # lb (signed)
    out_start, src_start = a2, a1
    trace.clear()
    steps = 0
    while True:
        steps += 1
        if steps > 50_000_000:
            return "step limit", written, a2, a3
        if state == "L000":
            trace.append(("ctl", a1 - src_start, a2 - out_start))
            v1 = 0
            t5, t2, t1 = rd(a1 + 1), rd(a1 + 2), rd(a1 + 3)
            t0 = s32((((((t0 << 8) + t5) << 8) + t2) << 8) + t1)
            a1 += 4
            t1 = t0 & 3
            t6 = t4 - t1
            t7 = t3 >> t1
            state = "L001"
        elif state == "L001":
            if t0 >= 0:
                state = "L003"
                continue
            t2, t1 = rd(a1), rd(a1 + 1)
            t5 = (t2 << 8) | t1
            a1 += 2
            t1 = t5 & t7
            t2 = t5 >> t6
            t5 = t2 + 3
            t8 = t1 + 1
            count = t5
            t5 -= 1  # the branch's delay slot
            if count == 0:
                state = "L004"
                continue
            trace.append(("copy", count, t8, a2 - out_start, a1 - src_start, t0 & 0xFFFFFFFF))
            while True:  # L002
                src = (a2 - t8) & 0xFFFFFFFF
                byte = rd(src)
                old = t5
                wr(a2, byte)
                t5 -= 1
                a2 += 1
                if old == 0:
                    break
            state = "L004"
        elif state == "L003":
            trace.append(("lit", a2 - out_start, a1 - src_start))
            wr(a2, rd(a1))
            a1 += 1
            a2 += 1
            state = "L004"
        elif state == "L004":
            if a3 == a2:
                state = "L006"
                continue
            if flag != 0 and a1 < a2:
                state = "L006"
                continue
            state = "L005"
        elif state == "L005":
            v1 += 1
            cont = v1 < 0x1E
            t0 = s32(t0 << 1)
            if cont:
                state = "L001"
            else:
                t0 = rd(a1)
                state = "L000"
        elif state == "L006":
            return "completed", written, a2, a3


def main():
    ram_path, summary_path = sys.argv[1], sys.argv[2]
    function = sys.argv[3] if len(sys.argv) > 3 else FUNCTION
    text = open(summary_path, errors="replace").read()
    call = last_call(text, function)
    if call is None:
        print("decode check: no %s call in the summary" % function)
        return
    a0, a1, a2 = call
    ram = bytearray(open(ram_path, "rb").read())
    print("decode check: the last %s call: a0=0x%08X a1=0x%08X a2=0x%08X" % (function, a0, a1, a2))
    try:
        result, written, end, a3 = decode(ram, a0, a1, a2)
        print("decode check: %s, %d bytes written, a2 ended at 0x%08X (a3 = 0x%08X)"
              % (result, written, end, a3))
    except Overflow as over:
        print("decode check: the copy ran past the end of RAM, at 0x%08X" % over.args[0])
    size = int.from_bytes(ram[(a0 + 4) & 0x1FFFFFF:(a0 + 8) & 0x1FFFFFF], "little")
    print("decode check: the header's size %d (0x%X); the source bytes at a1+8: %s"
          % (size, size, bytes(ram[(a1 + 8) & 0x1FFFFFF:(a1 + 8 + 24) & 0x1FFFFFF]).hex()))
    print("decode check: the last operations (kind, ...):")
    for op in trace[-14:]:
        print("decode check:   " + " ".join(str(x) for x in op))


if __name__ == "__main__":
    main()
