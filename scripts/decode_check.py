#!/usr/bin/env python3
"""Run the game's LZ-style chunk decoder (EE 0x0032DFA0) in Python, on the
EE RAM dump of a run, with the arguments of its last call (from the watch).

A transcription of the MIPS listing in the run's report. It answers three things:
the copy as the engine ran it (does it overrun the RAM?), the copy stopped at the
chunk's end (how much of the input a chunk of this size uses, against the
header's compressed size), and the first operations, with the bytes just before
the output (the window the copies can reach back into).

    python3 scripts/decode_check.py <ram.bin> <report.txt> [function]
"""

import re
import sys

RAM_SIZE = 32 << 20
MASK = 0x1FFFFFF
FUNCTION = "0x0032DFA0"
trace = []


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


class Limit(Exception):
    pass


def decode(ram, a0, a1, a2, limit=None):
    """The decoder's loop, instruction by instruction (the MIPS listing).

    Returns (result, written, input_used, a2_end). With `limit`, it stops at the
    first byte at or past it (the chunk's end, for the analysis)."""
    trace.clear()
    written = 0
    v1 = int.from_bytes(ram[(a0 + 4) & MASK:(a0 + 8) & MASK], "little")
    a1 = a1 + 8
    a3 = (a2 + v1) & 0xFFFFFFFF
    t4, t3 = 0x0E, 0x3FFF
    out_start, src_start = a2, a1
    t0 = ram[a1 & MASK]
    flag = s32(ram[(a0 + 13) & MASK])          # lb: the flag of the source/destination guard
    state = "L000"

    def rd(addr):
        return ram[addr & MASK]

    def wr(addr, value):
        nonlocal written
        if addr >= RAM_SIZE:
            raise Overflow(addr)
        if limit is not None and addr >= limit:
            raise Limit(addr)
        ram[addr] = value & 0xFF
        written += 1

    steps = 0
    try:
        while True:
            steps += 1
            if steps > 50_000_000:
                return "step limit", written, a1 - src_start, a2
            if state == "L000":
                trace.append(("ctl", a1 - src_start, a2 - out_start, t0 & 0xFFFFFFFF))
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
                count = t2 + 3
                t8 = t1 + 1
                trace.append(("copy", count, t8, a2 - out_start, a1 - src_start))
                t5 = count - 1                  # the branch's delay slot
                if count != 0:
                    while True:                 # L002
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
                return "completed", written, a1 - src_start, a2
    except Overflow as over:
        return "overran the RAM at 0x%08X" % over.args[0], written, a1 - src_start, a2
    except Limit:
        return "reached the chunk's end", written, a1 - src_start, a2


def main():
    ram_path, report_path = sys.argv[1], sys.argv[2]
    function = sys.argv[3] if len(sys.argv) > 3 else FUNCTION
    call = last_call(open(report_path, errors="replace").read(), function)
    if call is None:
        print("decode check: no %s call in the report" % function)
        return
    a0, a1, a2 = call
    ram = bytearray(open(ram_path, "rb").read())
    size = int.from_bytes(ram[(a0 + 4) & MASK:(a0 + 8) & MASK], "little")
    comp = int.from_bytes(ram[(a0 + 8) & MASK:(a0 + 12) & MASK], "little")
    print("decode check: the last %s call: a0=0x%08X a1=0x%08X a2=0x%08X" % (function, a0, a1, a2))
    print("decode check: the struct: size %d (0x%X), compressed %d (0x%X)" % (size, size, comp, comp))
    window = bytes(ram[(a2 - 16) & MASK:a2 & MASK])
    print("decode check: the 16 bytes before the output: %s" % window.hex())
    if size <= 0x10000:
        copy = bytearray(ram)
        result, written, used, end = decode(copy, a0, a1, a2, limit=a2 + size)
        print("decode check: to the chunk's end (%d bytes): %s, %d written, input used %d (0x%X) of %d"
              % (size, result, written, used, used, comp))
    copy = bytearray(ram)
    result, written, used, end = decode(copy, a0, a1, a2)
    print("decode check: the engine's own run of the copy: %s, %d written, a2 ended at 0x%08X"
          % (result, written, end))
    print("decode check: the first operations (kind, ...):")
    for op in trace[:12]:
        print("decode check:   " + " ".join(str(x) for x in op))


if __name__ == "__main__":
    main()
