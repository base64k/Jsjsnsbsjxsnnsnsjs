#!/usr/bin/env python3
"""The APK, from the library that is already built.

The engine's `android.py apk` builds the library and the package in one go.
This script only packages: it takes the library the Android build made (or
the one the cache kept from a run whose code had not changed) and makes the
APK of it - so that such a run does not compile the native code again.

    python scripts/package_apk.py [abi]      # arm64-v8a by default

The dispatch table is written first: it holds the code the runs found copied
at run time, which the smoke test's rounds translate.
"""

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)
sys.path[:0] = [os.path.join(ROOT, "engine", "tools"), os.path.join(ROOT, "engine")]

import android  # noqa: E402
import port  # noqa: E402
from ps2decomp import game as game_config  # noqa: E402

GAME = "games/up"
TARGET = "up"
# The directory the Android build puts the library in (engine/tools/android.py).
DIRECTORY = {"arm64-v8a": "arm64"}


def main(argv=None) -> int:
    abi = (argv or sys.argv[1:] or ["arm64-v8a"])[0]
    game = game_config.load(GAME)
    port.generate(game)                     # the dispatch table
    tools = android.tools()
    libraries = {}
    for name in abi.split(","):
        path = os.path.join("games", "up", "build", "port",
                            "android-" + DIRECTORY.get(name, name),
                            "lib%s.stripped.so" % TARGET)
        if not os.path.isfile(path):
            raise SystemExit("package_apk: no library at %s (build it first)" % path)
        libraries[name] = path
    out = android.apk(game, libraries, tools)
    print("the APK: %s" % out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
