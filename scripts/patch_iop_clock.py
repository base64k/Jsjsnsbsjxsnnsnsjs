#!/usr/bin/env python3
"""Make the IOP module loader's wait work on a virtual clock (--virtual-time).

On a virtual clock the IOP's time (Vm::NowUs) goes on only with the clock,
and the loader's wait (`while ... NowUs() < deadline`) never ends if nothing
moves it: the host spins in its own loop. The wait is a real-time bound (five
seconds of the host's time, measured with the steady clock), and on a virtual
clock each step of the wait moves the clock on by a millisecond, so the
IOP's delays still come due. Real-time runs are unchanged.

Idempotent: a file already patched is left alone. Run from the repository root:

    python3 scripts/patch_iop_clock.py
"""

import pathlib
import sys

TARGET = pathlib.Path("engine/host/src/iop_vm.cpp")
MARKER = "// port: the loader's wait (scripts/patch_iop_clock.py)"

OLD = """    const u64 deadline = vm.NowUs() + 5000000;      // it may wait on timers: real time
    while (vm.threads[loader.id].wait != Wait::Dormant && vm.NowUs() < deadline) {
        Run();
        if (vm.threads[loader.id].wait != Wait::Dormant)
            std::this_thread::sleep_for(std::chrono::microseconds(200));
    }
"""

NEW = """    // port: the loader's wait (scripts/patch_iop_clock.py). Five seconds of the host's
    // time; on a virtual clock each step of the wait moves the clock a millisecond on.
    const auto real_deadline = std::chrono::steady_clock::now() + std::chrono::seconds(5);
    while (vm.threads[loader.id].wait != Wait::Dormant &&
           std::chrono::steady_clock::now() < real_deadline) {
        Run();
        if (vm.threads[loader.id].wait != Wait::Dormant) {
            if (ps2host::VirtualClock()) ps2host::AdvanceClock(1000000);
            std::this_thread::sleep_for(std::chrono::microseconds(200));
        }
    }
"""


def main():
    if not TARGET.exists():
        print("patch_iop_clock: %s not found (run from the repository root)" % TARGET)
        return 1
    text = TARGET.read_text()
    if MARKER in text:
        print("patch_iop_clock: iop_vm.cpp already patched")
        return 0
    if text.count(OLD) != 1:
        print("patch_iop_clock: the loader's wait does not match (engine changed?)")
        return 1
    TARGET.write_text(text.replace(OLD, NEW))
    print("patch_iop_clock: iop_vm.cpp patched")
    return 0


if __name__ == "__main__":
    sys.exit(main())
