#!/usr/bin/env python3
"""Disassemble a range of an IOP module (an IRX: a MIPS I ELF) at its load address.

    python scripts/disasm_irx.py MODULE.IRX START END [BASE]

START and END are IOP addresses (as the port's report names them: 0x00010778).
The module loads at BASE (0x10000 by default, where the IOP's modules load);
its ELF addresses are the IOP addresses less BASE when the ELF's entry point
says so. Needs capstone and pyelftools (pip install capstone pyelftools).
"""

import sys

from capstone import CS_ARCH_MIPS, CS_MODE_LITTLE_ENDIAN, CS_MODE_MIPS32, Cs
from elftools.elf.elffile import ELFFile


def main():
    if len(sys.argv) < 4:
        sys.exit(__doc__)
    path = sys.argv[1]
    start, end = int(sys.argv[2], 0), int(sys.argv[3], 0)
    base = int(sys.argv[4], 0) if len(sys.argv) > 4 else 0x10000
    with open(path, "rb") as handle:
        elf = ELFFile(handle)
        entry = elf["e_entry"]
        # The ELF is linked at 0 (its entry is small) or at the base already.
        offset = base if entry < base else 0
        print("entry 0x%08X, load offset 0x%08X" % (entry, offset))
        md = Cs(CS_ARCH_MIPS, CS_MODE_MIPS32 | CS_MODE_LITTLE_ENDIAN)
        for segment in elf.iter_segments():
            if segment["p_type"] != "PT_LOAD":
                continue
            address = segment["p_vaddr"] + offset
            data = segment.data()
            for ins in md.disasm(data, address):
                if start <= ins.address <= end:
                    print("%08X: %-8s %s" % (ins.address, ins.mnemonic, ins.op_str))


if __name__ == "__main__":
    main()
