#!/usr/bin/env python3
"""Find a byte pattern in the disc image and say where it is (LBA, file offset).

The unpacker's chunks on the disc are the bank data's own bytes: a chunk's
header (size, compressed size) and its first control word locate it. Prints
the sector, the offset in the sector, and the bytes around it, so the file can
be read from the disc's own file system.

    python3 scripts/find_chunk.py disc/up.iso 00000800000002CE A7171050
"""

import sys

SECTOR = 2048


def main():
    image = sys.argv[1]
    pattern = bytes.fromhex("".join(sys.argv[2:]))
    data = open(image, "rb").read()
    found, start = 0, 0
    print("find chunk: %d bytes of image, pattern %s" % (len(data), pattern.hex()))
    while found < 12:
        at = data.find(pattern, start)
        if at < 0:
            break
        lba, off = divmod(at, SECTOR)
        print("find chunk: at byte %d (LBA %d, offset %d in the sector)" % (at, lba, off))
        print("find chunk:   bytes: %s" % data[at:at + 48].hex())
        found += 1
        start = at + 1
    if not found:
        print("find chunk: not found")


if __name__ == "__main__":
    main()
