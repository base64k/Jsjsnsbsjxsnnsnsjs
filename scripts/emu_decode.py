#!/usr/bin/env python3
"""Run the game's own machine code for the unpacker (EE 0x0032DFA0) in the engine's R5900
interpreter (engine/ps2decomp/emu.py), on the input each call saw in the run, and compare.

Three answers for each call: the interpreter (the original code, executed), the Python
transcription (scripts/decode_check.py), and the engine's translated run (the host's
[watch-ret] and [watch-out] lines). The interpreter is independent of the translator, so:
  - interpreter == Python, and the engine differs  -> the translator is wrong on that call;
  - interpreter != Python                         -> the transcription is wrong;
  - all three equal                               -> the code and the engine agree.

    python3 scripts/emu_decode.py <report.txt>

It reads the executable from games/up/game.json and games/up/extracted/. The lines it
prints start with "decode src:" so the report shows them with the other decode lines.
"""

import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "engine"))
sys.path.insert(0, HERE)

import decode_src  # noqa: E402  (the parsers of the report's lines, and the Python decoder)

from ps2decomp import elf as elf_mod  # noqa: E402
from ps2decomp import emu, layout  # noqa: E402

FUNCTION = 0x0032DFA0
RAM_TOP = 0x02000000          # the memory the interpreter covers: all of EE RAM
STACK_TOP = 0x01FF0000        # below the decoder's argument block at 0x01FFFA80
OUTPUT_LIMIT = 0x10000        # the output compared, whole (the engine's [watch-out] holds only the first 2 KB)


def executable():
    game = json.load(open(os.path.join(ROOT, "games", "up", "game.json")))
    return os.path.join(ROOT, "games", "up", "extracted", game["executable"])


def machine(path):
    layout.configure(stack_top=STACK_TOP)
    ef = elf_mod.ElfFile.load(path)
    section = ef.exec_sections[0]
    data = ef.section_data(section)
    return emu.Machine(section.addr, data, total_size=RAM_TOP - section.addr)

LOOP_HEADS = (0x0032DFB8, 0x0032DFF0, 0x0032E028)     # the unpacker's loop heads (the engine's [tick] lines)


def loop_trace(m, size):
    """Record the loop heads' registers of this call's run (the engine prints the same from its loop heads)."""
    trace = []
    step = m.step

    def traced():
        if m.pc in LOOP_HEADS:
            trace.append("[tick] 0x%08X a1=%08X a2=%08X a3=%08X t0=%08X t5=%08X t8=%08X"
                         % (m.pc, m.get32(5), m.get32(6), m.get32(7), m.get32(8), m.get32(13), m.get32(24)))
        step()

    m.step = traced
    return trace


def compare_ticks(interp, engine):
    """The first loop head where the engine's registers differ from the interpreter's, with the lines around it."""
    print("decode src: loop heads: the interpreter %d, the engine %d" % (len(interp), len(engine)))
    for i in range(min(len(interp), len(engine))):
        if interp[i] != engine[i]:
            print("decode src: the first difference at loop head %d:" % i)
            for j in range(max(0, i - 3), min(len(interp), len(engine), i + 3)):
                print("decode src:   interpreter %s" % interp[j])
                print("decode src:   engine      %s" % engine[j])
            return
    print("decode src: the loop heads agree on the %d they share" % min(len(interp), len(engine)))


def store_pcs(a0, arg, a1, src, a2, size, a3, target):
    """The PCs of the stores to `target` in a fresh interpreter run of this call (the instruction that wrote it)."""
    m = machine(executable())
    m.memory.write(a0, arg)
    m.memory.write(a1, src)
    m.memory.write(a2, bytes(min(size, OUTPUT_LIMIT)))
    hits = []
    real = m.memory.write_int

    def watch(addr, value, width):
        if addr <= target < addr + width:
            hits.append((m.pc, value, width))
        real(addr, value, width)

    m.memory.write_int = watch
    m.call(FUNCTION, args=(a0, a1, a2, a3), max_instructions=200_000_000)
    return hits


def main():
    text = open(sys.argv[1], errors="replace").read()
    entries = decode_src.calls(text)
    inputs = decode_src.sources(text)
    ends = decode_src.returns(text)
    outs = decode_src.outputs(text)
    decoder = decode_src.load_decoder()
    m = machine(executable())
    print("decode src: the interpreter runs the game's code at 0x%08X, %d calls in the report"
          % (FUNCTION, len(inputs)))
    same_all = same_engine = differs = 0
    shown = 0
    py_outputs = []              # (call, a2, size, Python's output) for the nesting test below
    for k, ((arg, src), entry) in enumerate(zip(inputs, entries)):
        a0, a1, a2, a3 = entry
        size = int.from_bytes(arg[4:8], "little")
        if not (0 < size <= 0x10000):
            continue
        # The Python answer, from the same bytes.
        ram = bytearray(decode_src.RAM_SIZE)
        ram[a0:a0 + 64] = arg
        ram[a1:a1 + len(src)] = src
        copy = bytearray(ram)
        _, _, _, py_end = decoder.decode(copy, a0, a1, a2)
        py_out = bytes(copy[a2:a2 + min(size, OUTPUT_LIMIT)])
        # Does this call's input lie inside an earlier call's output range (a nested stream, or a clash)?
        for j, ja2, jsize, jout in py_outputs:
            if ja2 <= a1 < ja2 + jsize:
                at = a1 - ja2
                same = jout[at:at + 16] == src[:16]
                print("decode src: call %d's input (0x%08X) lies in call %d's output (0x%08X + %d), the bytes %s"
                      % (k, a1, j, ja2, at, "equal to the output there" if same else "different from the output there"))
        py_outputs.append((k, a2, size, py_out))
        # The interpreter, on the same memory: the argument block, the input, a zeroed output.
        m = machine(executable())    # a fresh interpreter: a call's leftovers must not reach the next
        m.memory.write(a0, arg)
        m.memory.write(a1, src)
        m.memory.write(a2, bytes(min(size, OUTPUT_LIMIT)))
        ticks = loop_trace(m, size) if (a2 == 0x01F78100 and size == 0x800) else None
        try:
            m.call(FUNCTION, args=(a0, a1, a2, a3), max_instructions=200_000_000)
        except Exception as error:      # the interpreter's fault on this call: shown, the rest go on
            print("decode src: interpreter call %d (a2=0x%08X, size %d) faulted: %r" % (k, a2, size, error))
            differs += 1
            continue
        interp_end = m.get(6) & 0xFFFFFFFF
        if ticks is not None:
            compare_ticks(ticks, [l for l in text.splitlines() if l.startswith("[tick] ")])
        interp_out = bytes(m.memory.read(a2, min(size, OUTPUT_LIMIT)))
        engine_end = ends[k] if k < len(ends) else None
        engine_out = outs[k] if k < len(outs) and a2 == 0x01F78100 else None
        interp_matches_python = interp_end == py_end and interp_out == py_out
        if interp_matches_python:
            same_all += 1
        if engine_end is not None and engine_end == interp_end:
            same_engine += 1
        else:
            differs += 1
            # Where the engine's output first leaves the interpreter's: the instruction that wrote that byte.
            if engine_out is not None and engine_out[:len(interp_out)] != interp_out[:len(engine_out)]:
                d = next(i for i in range(min(len(engine_out), len(interp_out))) if engine_out[i] != interp_out[i])
                for pc, value, width in store_pcs(a0, arg, a1, src, a2, size, a3, a2 + d)[-3:]:
                    print("decode src: call %d, output byte %d (0x%08X): the interpreter's store at pc 0x%08X (value 0x%X, %d bytes); the engine wrote 0x%02X, the interpreter 0x%02X"
                          % (k, d, a2 + d, pc, value, width, engine_out[d], interp_out[d]))
        if shown < 12 or not interp_matches_python or (engine_end is not None and engine_end != interp_end):
            shown += 1
            if shown <= 40:
                first = next((i for i in range(len(py_out)) if interp_out[i] != py_out[i]), None)
                print("decode src: interpreter call %d a2=0x%08X size %d: end 0x%08X (Python 0x%08X, engine %s)%s%s"
                      % (k, a2, size, interp_end, py_end,
                         "0x%08X" % engine_end if engine_end is not None else "-",
                         "" if interp_matches_python else ", differs from Python at byte %s" % first,
                         "" if engine_out is None or engine_out[:len(interp_out)] == interp_out[:len(engine_out)]
                         else ", the engine's output differs from the interpreter's"))
    print("decode src: interpreter and Python agree on %d call(s); the engine agrees with the interpreter on %d, "
          "differs on %d" % (same_all, same_engine, differs))


if __name__ == "__main__":
    try:
        main()
    except Exception as error:      # shown in the report, not lost to a silent step
        import traceback
        print("decode src: interpreter failed: %r" % (error,))
        traceback.print_exc()
