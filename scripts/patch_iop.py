#!/usr/bin/env python3
"""The IOP library functions Up's own sound driver imports, that the host lacked.

The game ships its sound driver (ZNASND.IRX) and runs it in the IOP
interpreter. The driver imports library functions the engine's host does not
implement yet (its IOP library table is engine/host/src/iop_libs.cpp, outside
this repository). This script adds them to the engine's build tree, the same
way the other patches do: idempotent, guarded by a marker per patch.

  ioman    open / close / read / lseek: files on the disc (cdrom0:), the sound
           bank the driver reads
  sysclib  strtok
  timrman  GetTimerCounter, SetOverflowHandler (the timer's handler is called
           at its period, which is where an overflow lands)
  cdvdman  sceCdStatus, sceCdBreak
  sifcmd   sceSifBindRpc, sceSifCallRpc, for the IOP's own calls to a server:
           the bind and the call are logged, and a call to a server the host
           does not run answers with an error instead of blocking

The engine is not changed upstream. Run it before any build of the PC
reference or the Android library, and before the smoke test:

    python scripts/patch_iop.py
"""

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IOP_LIBS = os.path.join(ROOT, "engine", "host", "src", "iop_libs.cpp")

FUNCTIONS = r'''// ---------------------------------------------------------------- port: IOP library functions (scripts/patch_iop.py)
// What the game's own IOP modules import and the host lacked (see patch_iop.py).

struct PortIoFile {
    Disc::File file;
    u32 position = 0;
};

std::map<s32, PortIoFile>& PortIoFiles() {
    static std::map<s32, PortIoFile> files;
    return files;
}

// open(name, flags): a file on the disc ("cdrom0:\\DATA\\X.BIN;1"); the -2 of ENOENT if not.
Outcome IoOpen(Vm& vm, Context& c) {
    const std::string path = vm.String(A(vm, c, 0), 1024);
    const std::size_t colon = path.find(':');
    const std::string device = colon == std::string::npos ? "" : path.substr(0, colon);
    const std::string rest = colon == std::string::npos ? path : path.substr(colon + 1);
    Disc::File file;
    if (device.rfind("cdrom", 0) != 0 || !GuestDisc().IsOpen() || !GuestDisc().Find(rest, &file))
        return Ret(c, u32(-2));
    static s32 next = 3;
    PortIoFiles()[next] = PortIoFile{file, 0};
    return Ret(c, u32(next++));
}

Outcome IoClose(Vm& vm, Context& c) {
    return Ret(c, PortIoFiles().erase(s32(A(vm, c, 0))) ? 0u : u32(-9));
}

// read(fd, buffer, size): the bytes from the file's position, the count read.
Outcome IoRead(Vm& vm, Context& c) {
    auto found = PortIoFiles().find(s32(A(vm, c, 0)));
    if (found == PortIoFiles().end()) return Ret(c, u32(-9));
    PortIoFile& f = found->second;
    const u32 buffer = A(vm, c, 1), request = A(vm, c, 2);
    const u32 size = std::min(request, f.file.size > f.position ? f.file.size - f.position : 0u);
    if (!size) return Ret(c, 0);
    const u32 first = f.position / kSectorSize;
    const u32 last = (f.position + size + kSectorSize - 1) / kSectorSize;
    std::vector<u8> sectors(std::size_t(last - first) * kSectorSize);
    if (!GuestDisc().Read(f.file.lsn + first, last - first, sectors.data())) return Ret(c, u32(-5));
    u8* out = vm.At(buffer, size);
    if (!out) return Ret(c, u32(-5));
    std::memcpy(out, sectors.data() + (f.position - first * kSectorSize), size);
    f.position += size;
    return Ret(c, size);
}

// lseek(fd, offset, whence): SEEK_SET, SEEK_CUR, SEEK_END; the new position.
Outcome IoSeek(Vm& vm, Context& c) {
    auto found = PortIoFiles().find(s32(A(vm, c, 0)));
    if (found == PortIoFiles().end()) return Ret(c, u32(-9));
    PortIoFile& f = found->second;
    const s32 offset = s32(A(vm, c, 1));
    const u32 whence = A(vm, c, 2);
    const s64 base = whence == 0 ? 0 : whence == 1 ? s64(f.position) : s64(f.file.size);
    const s64 position = std::max<s64>(0, base + offset);
    f.position = u32(position);
    return Ret(c, u32(position));
}

// strtok(s, delimiters): the next token of a string in the IOP's memory; the
// string's place is kept between calls, as the C library keeps it.
u32 PortStrtokNext = 0;

Outcome Strtok(Vm& vm, Context& c) {
    u32 p = A(vm, c, 0) ? A(vm, c, 0) : PortStrtokNext;
    const std::string delimiters = vm.String(A(vm, c, 1), 256);
    auto byteAt = [&vm](u32 address) -> u8 {
        const u8* q = vm.At(address, 1);
        return q ? *q : 0;
    };
    auto isDelimiter = [&delimiters](u8 ch) { return delimiters.find(char(ch)) != std::string::npos; };
    if (!p) return Ret(c, 0);
    while (byteAt(p) && isDelimiter(byteAt(p))) ++p;
    if (!byteAt(p)) {
        PortStrtokNext = 0;
        return Ret(c, 0);
    }
    const u32 start = p;
    while (byteAt(p) && !isDelimiter(byteAt(p))) ++p;
    if (byteAt(p)) {
        vm.Write(p, 0, 1);
        PortStrtokNext = p + 1;
    } else {
        PortStrtokNext = 0;
    }
    return Ret(c, start);
}

// GetTimerCounter(id): the timer's count - the clock's ticks over its prescale.
Outcome GetTimerCounter(Vm& vm, Context& c) {
    HardTimer* t = TimerOf(vm, c);
    if (!t) return Ret(c, u32(KE_ILLEGAL_TIMERID));
    return Ret(c, u32(UsToClock(vm.NowUs()) / std::max(1u, t->prescale)));
}

// SetOverflowHandler(id, handler, common): the function the timer calls at its period.
Outcome SetOverflowHandler(Vm& vm, Context& c) {
    HardTimer* t = TimerOf(vm, c);
    if (!t) return Ret(c, u32(KE_ILLEGAL_TIMERID));
    t->handler = A(vm, c, 1);
    t->common = A(vm, c, 2);
    return Ret(c, KE_OK);
}

// The disc's drive: complete and at rest, as the driver finds it.
Outcome CdStatus(Vm&, Context& c) { return Ret(c, 2); }     // SCECdComplete
Outcome CdBreak(Vm&, Context& c) { return Ret(c, 1); }      // the break is made

// sceSifBindRpc(client, server, mode): a server the host does not run binds to
// an empty record and answers 1 (bound), so the module goes on - it prints and
// polls while the bind answers 0; a call to that record is answered with an
// error. Each server is logged once.
std::map<u32, bool> PortLoggedBinds;

Outcome SifBindRpc(Vm& vm, Context& c) {
    const u32 client = A(vm, c, 0), server = A(vm, c, 1);
    const u32 record = vm.Allocate(64);
    if (client) vm.Write(client, record, 4);
    if (!PortLoggedBinds[server]) {
        PortLoggedBinds[server] = true;
        Log("SIF: IOP binds the server " + std::to_string(server) + " (not run by the host: an empty record)");
    }
    return Ret(c, 1);                     // bound: the SIF's answer for a server that is there
}

// sceSifCallRpc(client, procedure, mode, ...): the call to an empty record is answered with an error at once.
Outcome SifCallRpc(Vm& vm, Context& c) {
    const u32 client = A(vm, c, 0), procedure = A(vm, c, 1);
    const u32 record = client ? vm.Read(client, 4) : 0;
    std::string sent;
    const u32 send = A(vm, c, 3);
    for (u32 i = 0; i < 8 && send; ++i) sent += " " + std::to_string(vm.Read(send + 4 * i, 4));
    Log("SIF: IOP calls procedure " + std::to_string(procedure) + " of a server the host does not run (from " +
        std::to_string(c.r[31]) + ", record " + std::to_string(record) + ", sends" + sent +
        "): answered with an error");
    return Ret(c, u32(-1));
}

'''

TABLE_ANCHOR = "const Map& Table() {"

ENTRIES_ANCHOR = '        {{"sifcmd", 23}, SifGetOtherData},\n'
ENTRIES = (
    '        {{"sifcmd", 23}, SifGetOtherData},\n'
    '        // port: IOP library functions (scripts/patch_iop.py)\n'
    '        {{"ioman", 4}, IoOpen}, {{"ioman", 5}, IoClose},\n'
    '        {{"ioman", 6}, IoRead}, {{"ioman", 8}, IoSeek},\n'
    '        {{"sysclib", 35}, Strtok},\n'
    '        {{"timrman", 10}, GetTimerCounter}, {{"timrman", 21}, SetOverflowHandler},\n'
    '        {{"cdvdman", 28}, CdStatus}, {{"cdvdman", 39}, CdBreak},\n'
    '        {{"sifcmd", 15}, SifBindRpc}, {{"sifcmd", 16}, SifCallRpc},\n'
)

FUNCTIONS_MARKER = "// What the game's own IOP modules import and the host lacked"
ENTRIES_MARKER = '{{"ioman", 4}, IoOpen}'


def main():
    if not os.path.isfile(IOP_LIBS):
        sys.exit("patch_iop: %s is missing (the engine submodule?)" % IOP_LIBS)
    with open(IOP_LIBS, encoding="utf-8") as handle:
        text = handle.read()

    edits = [
        (TABLE_ANCHOR, FUNCTIONS + TABLE_ANCHOR, FUNCTIONS_MARKER),
        (ENTRIES_ANCHOR, ENTRIES, ENTRIES_MARKER),
    ]
    changed = False
    for anchor, replacement, marker in edits:
        if marker in text:
            continue                      # already patched
        if text.count(anchor) != 1:
            sys.exit("patch_iop: %s: the place to patch is there %d times (once it must be)"
                     % (IOP_LIBS, text.count(anchor)))
        text = text.replace(anchor, replacement, 1)
        changed = True

    # The guard: each patch must be in the file exactly once.
    for _, _, marker in edits:
        if text.count(marker) != 1:
            sys.exit("patch_iop: %s: the patch is there %d times (once it must be): %s"
                     % (IOP_LIBS, text.count(marker), marker))

    if changed:
        with open(IOP_LIBS, "w", encoding="utf-8") as handle:
            handle.write(text)
        print("patch_iop: iop_libs.cpp patched")
    else:
        print("patch_iop: iop_libs.cpp already patched")


if __name__ == "__main__":
    main()
