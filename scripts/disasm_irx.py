#!/usr/bin/env python3
"""Disassemble a range of an IOP module (an IRX: a MIPS I ELF) at its load address.

    python scripts/disasm_irx.py MODULE.IRX START END [BASE]
    python scripts/disasm_irx.py MODULE.IRX --find TEXT [BASE]

--find prints every instruction whose text contains TEXT (say "-0x5108(" for
a word the module reads or writes at -0x5108 from a lui $at,1), with the twelve
instructions before it.

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
    find = None
    if sys.argv[2] == "--find":
        find = sys.argv[3]
        start, end = 0, 0
        base = int(sys.argv[4], 0) if len(sys.argv) > 4 else 0x10000
    else:
        start, end = int(sys.argv[2], 0), int(sys.argv[3], 0)
        base = int(sys.argv[4], 0) if len(sys.argv) > 4 else 0x10000
    with open(path, "rb") as handle:
        elf = ELFFile(handle)
        entry = elf["e_entry"]
        # The ELF is linked at 0 (its entry is small) or at the base already.
        offset = base if entry < base else 0
        print("entry 0x%08X, load offset 0x%08X" % (entry, offset))
        md = Cs(CS_ARCH_MIPS, CS_MODE_MIPS32 | CS_MODE_LITTLE_ENDIAN)
        decoded, shown, first, listing = 0, 0, [], []
        for segment in elf.iter_segments():
            print("segment %s at 0x%08X, %d bytes in the file" % (
                segment["p_type"], segment["p_vaddr"] + offset, segment["p_filesz"]))
            if segment["p_type"] != "PT_LOAD":
                continue
            address = segment["p_vaddr"] + offset
            data = segment.data()
            # One word at a time: a word the decoder does not know (data, or an
            # encoding it lacks) is skipped, not the rest of the segment.
            for at in range(0, len(data) - 3, 4):
                for ins in md.disasm(data[at:at + 4], address + at):
                    decoded += 1
                    text = "%08X: %-8s %s" % (ins.address, ins.mnemonic, ins.op_str)
                    listing.append(text)
                    if len(first) < 40:
                        first.append(text)
                    if start <= ins.address <= end:
                        shown += 1
                        print(text)
        if find is not None:
            hits = [i for i, text in enumerate(listing) if find in text]
            print("%d instructions contain %r" % (len(hits), find))
            for i in hits[:12]:
                print("---")
                print("\n".join(listing[max(0, i - 12):i + 3]))
        print("decoded %d instructions, %d in the range" % (decoded, shown))
        if not shown:
            print("the first instructions decoded, for the layout:")
            print("\n".join(first))


if __name__ == "__main__":
    main()
