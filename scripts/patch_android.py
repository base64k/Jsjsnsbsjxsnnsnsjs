#!/usr/bin/env python3
"""Give the APK the access to the phone's shared storage it needs.

The port reads the game's disc image from the player's own storage. The
system's file picker (the engine's Android activity) already grants that
access for the file the player chooses, but the player may keep the image
anywhere - in the Downloads folder, say - and a port that is allowed to see
the shared storage can find it there itself.

The engine's Android build (engine/tools/android.py and
engine/android/java/org/ps2port/PortActivity.java) is the engine's own and
stays as it is upstream: this script patches the copy in the build tree, so
the pinned commit of the submodule does not change. It is idempotent: run it
twice and the second run does nothing.

    python scripts/patch_android.py
"""

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENGINE = os.path.join(ROOT, "engine")

PERMISSIONS = """    <!-- The player's disc image: the shared storage, where it is kept -->
    <uses-permission android:name="android.permission.READ_EXTERNAL_STORAGE" android:maxSdkVersion="32" />
    <uses-permission android:name="android.permission.WRITE_EXTERNAL_STORAGE" android:maxSdkVersion="29" />
    <uses-permission android:name="android.permission.MANAGE_EXTERNAL_STORAGE" />
"""

JAVA_METHOD = """
    /* The shared storage, whole: the player's disc image may be anywhere on
       it (the Downloads folder, say). The system's file picker works without
       this - it grants the file the player chooses - so this is an offer, not
       a demand: asked once, and never again. */
    private void askForAllFiles() {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.R) return;   // before Android 11
        if (Environment.isExternalStorageManager()) return;          // already asked
        SharedPreferences prefs = getPreferences(MODE_PRIVATE);
        if (prefs.getBoolean(KEY_ALL_FILES, false)) return;
        prefs.edit().putBoolean(KEY_ALL_FILES, true).apply();
        try {
            startActivity(new Intent(Settings.ACTION_MANAGE_APP_ALL_FILES_ACCESS_PERMISSION,
                                     Uri.parse("package:" + getPackageName())));
        } catch (Exception e) {
            try {
                startActivity(new Intent(Settings.ACTION_MANAGE_ALL_FILES_ACCESS_PERMISSION));
            } catch (Exception other) {
                Log.w(TAG, "no screen to ask for all files: " + other);
            }
        }
    }
"""


def patch(path, edits, what):
    """edits: a list of (anchor, replacement) - the anchor must be there."""
    if not os.path.isfile(path):
        sys.exit("patch_android: %s is missing (the engine submodule?)" % path)
    with open(path, encoding="utf-8") as handle:
        text = handle.read()
    changed = False
    for anchor, replacement in edits:
        if replacement in text:
            continue                      # already patched
        if anchor not in text:
            sys.exit("patch_android: %s: cannot find the place to patch (%s)" % (path, what))
        text = text.replace(anchor, replacement, 1)
        changed = True
    if changed:
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(text)
        print("patch_android: %s patched" % what)
    else:
        print("patch_android: %s already patched" % what)


def main():
    patch(os.path.join(ENGINE, "tools", "android.py"),
          [("""    <uses-permission android:name="android.permission.VIBRATE" />
""", """    <uses-permission android:name="android.permission.VIBRATE" />
""" + PERMISSIONS)],
          "the APK's permissions")

    patch(os.path.join(ENGINE, "android", "java", "org", "ps2port", "PortActivity.java"),
          [("""import android.os.Bundle;
""", """import android.os.Build;
import android.os.Bundle;
import android.os.Environment;
import android.provider.Settings;
"""),
           ("""    private static final String KEY_TOUCH = "touch_controls";
""", """    private static final String KEY_TOUCH = "touch_controls";
    private static final String KEY_ALL_FILES = "all_files_asked";
"""),
           ("""    private void launchPicker() {
""", JAVA_METHOD + """
    private void launchPicker() {
"""),
           ("""        tellKeyboard(getResources().getConfiguration());
""", """        tellKeyboard(getResources().getConfiguration());
        askForAllFiles();
""")],
          "the activity's request for the shared storage")
    return 0


if __name__ == "__main__":
    sys.exit(main())
