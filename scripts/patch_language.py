#!/usr/bin/env python3
"""The app's own words in Russian (the port speaks English and Russian).

The player chooses the language - the disc's dialog has the choice - and the
app's own texts follow it at once: the dialogs, the messages and the touch
controls' labels. The system's own language is the default, so a phone set to
Russian gets a Russian app without asking anything.

The engine's Android build (engine/android/java/org/ps2port) is the engine's
own and stays as it is upstream: this script patches the copy in the build
tree, so the pinned commit of the submodule does not change. It is idempotent:
run it twice and the second run does nothing.

    python scripts/patch_language.py
"""

import os
import shutil
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENGINE = os.path.join(ROOT, "engine")
# The port's own Java (this repository's), copied into the engine's tree: the
# APK's build takes the Java from there.
PORT_JAVA = os.path.join(ROOT, "games", "up", "port", "android", "java", "org", "ps2port")
ENGINE_JAVA = os.path.join(ENGINE, "android", "java", "org", "ps2port")


def patch(path, edits, what):
    """edits: a list of (anchor, replacement) - the anchor must be there."""
    if not os.path.isfile(path):
        sys.exit("patch_language: %s is missing (the engine submodule?)" % path)
    with open(path, encoding="utf-8") as handle:
        text = handle.read()
    changed = False
    for anchor, replacement in edits:
        if replacement in text:
            continue                      # already patched
        if anchor not in text:
            sys.exit("patch_language: %s: cannot find the place to patch (%s)" % (path, what))
        text = text.replace(anchor, replacement, 1)
        changed = True
    if changed:
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(text)
        print("patch_language: %s patched" % what)
    else:
        print("patch_language: %s already patched" % what)


def copy(source, target):
    """The port's own Java, into the engine's tree (the APK's build's place)."""
    if not os.path.isfile(source):
        sys.exit("patch_language: %s is missing" % source)
    with open(source, encoding="utf-8") as handle:
        text = handle.read()
    if os.path.isfile(target):
        with open(target, encoding="utf-8") as handle:
            if handle.read() == text:
                print("patch_language: %s already there" % os.path.basename(target))
                return
    os.makedirs(os.path.dirname(target), exist_ok=True)
    with open(target, "w", encoding="utf-8") as handle:
        handle.write(text)
    print("patch_language: %s copied" % os.path.basename(target))


ACTIVITY = os.path.join(ENGINE_JAVA, "PortActivity.java")
CONTROLS = os.path.join(ENGINE_JAVA, "TouchControls.java")


def main():
    copy(os.path.join(PORT_JAVA, "Strings.java"), os.path.join(ENGINE_JAVA, "Strings.java"))

    patch(ACTIVITY,
          [("""            runOnUiThread(() -> Toast.makeText(this, "This is not an image of the " + gameName + " disc.",
                                               Toast.LENGTH_LONG).show());
""", """            runOnUiThread(() -> Toast.makeText(this, Strings.get(this, "not_the_disc", gameName),
                                               Toast.LENGTH_LONG).show());
"""),
           ("""                    new AlertDialog.Builder(this)
                        .setTitle(gameName)
                        .setMessage("Choose your own " + gameName + " disc image (.iso) - it stays on your device; "
                                    + "the game reads it from there.")
                        .setCancelable(false)
                        .setPositiveButton("Choose", (d, w) -> launchPicker())
                        .setNegativeButton("Quit", (d, w) -> answer(null))
                        .show();
""", """                    showDiscDialog(gameName);
"""),
           ("""            Toast.makeText(this, "No file picker on this device.", Toast.LENGTH_LONG).show();
""", """            Toast.makeText(this, Strings.get(this, "no_picker"), Toast.LENGTH_LONG).show();
"""),
           ("""    private void launchPicker() {
""", """    /* The disc's dialog: the image the player chooses. The language of the
       app's own words is in it too (the third button), and the game is
       still waited for while it is open. */
    private void showDiscDialog(final String gameName) {
        waitingFor = gameName;
        new AlertDialog.Builder(this)
            .setTitle(gameName)
            .setMessage(Strings.get(this, "choose_disc", gameName))
            .setCancelable(false)
            .setPositiveButton(Strings.get(this, "choose"), (d, w) -> launchPicker())
            .setNegativeButton(Strings.get(this, "quit"), (d, w) -> answer(null))
            .setNeutralButton(Strings.get(this, "language"), (d, w) -> askLanguage())
            .show();
    }

    /* The language of the app's own words: the player's choice (the system's
       own when there is none), kept and used at once. */
    private void askLanguage() {
        final String[] items = new String[]{
            Strings.get(this, "system_language"),
            Strings.get(this, "english"),
            Strings.get(this, "russian")};
        AlertDialog dialog = new AlertDialog.Builder(this)
            .setTitle(Strings.get(this, "language"))
            .setItems(items, (d, which) -> {
                String code = which == 1 ? Strings.ENGLISH : which == 2 ? Strings.RUSSIAN : Strings.SYSTEM;
                Strings.setLanguage(this, code);
                if (touch != null) touch.setLanguage();
            })
            .setNegativeButton(Strings.get(this, "cancel"), null)
            .create();
        // (the disc's dialog is made again when this one is closed, however
        //  it is closed: the game is still waited for)
        dialog.setOnDismissListener(d -> {
            if (waitingFor != null) showDiscDialog(waitingFor);
        });
        dialog.show();
    }

    private void launchPicker() {
"""),
           ("""    private void answer(Uri uri) {
        synchronized (picking) {
""", """    private void answer(Uri uri) {
        waitingFor = null;
        synchronized (picking) {
"""),
           ("""    /* Called by the native side, on its own thread: the disc image as a path
""", """    /* The app's own words about the stop, in the player's language (the
       native side's, when the game stops). */
    public String stoppedText(String log) {
        return Strings.get(this, "stopped", log);
    }

    /* Whether this phone's Vulkan is new enough (1.1): the port needs it.
       The check is the system's own answer, not a list of makers - Adreno,
       Mali and the rest are all the same to it. */
    private boolean vulkanNewEnough() {
        try {
            android.content.pm.FeatureInfo info = getPackageManager()
                .getSystemFeature(PackageManager.FEATURE_VULKAN_HARDWARE_VERSION);
            return info != null && info.version >= 0x00401000;
        } catch (RuntimeException e) {
            return true;               // (not known: the native side says it better)
        }
    }

    /* Called by the native side, on its own thread: the disc image as a path
"""),
           ("""        if (mLayout == null) return;      // SDL refused to start (its own message shown)
""", """        if (mLayout == null) return;      // SDL refused to start (its own message shown)
        if (!vulkanNewEnough())
            Toast.makeText(this, Strings.get(this, "vulkan_needed"), Toast.LENGTH_LONG).show();
"""),
           ("""    private TouchControls touch;
""", """    private TouchControls touch;
    /* The game's name, while its dialog waits for the player (the language
       is chosen there, and the dialog is made again afterwards). */
    private String waitingFor;
""")],
          "the activity's own words")

    patch(os.path.join(ENGINE, "host", "src", "main.cpp"),
          [("""    env->DeleteLocalRef(type);
    env->DeleteLocalRef(activity);
    return path;
}
#elif defined(_WIN32)
""", """    env->DeleteLocalRef(type);
    env->DeleteLocalRef(activity);
    return path;
}

/* The app's own words about the stop, in the player's language (the
   activity's Strings: the log's name is put in). */
std::string AppText(const std::string& log) {
    const std::string fallback = "The game stopped because of an error. What happened is in " +
                                 log + ", beside the game.";
    JNIEnv* env = static_cast<JNIEnv*>(SDL_GetAndroidJNIEnv());
    jobject activity = static_cast<jobject>(SDL_GetAndroidActivity());
    if (!env || !activity) return fallback;
    jclass type = env->GetObjectClass(activity);
    jmethodID method = env->GetMethodID(type, "stoppedText", "(Ljava/lang/String;)Ljava/lang/String;");
    std::string text;
    if (method) {
        jstring name = env->NewStringUTF(log.c_str());
        auto answer = static_cast<jstring>(env->CallObjectMethod(activity, method, name));
        if (env->ExceptionCheck()) env->ExceptionClear();
        if (answer) {
            const char* chars = env->GetStringUTFChars(answer, nullptr);
            text = chars ? chars : "";
            env->ReleaseStringUTFChars(answer, chars);
            env->DeleteLocalRef(answer);
        }
        env->DeleteLocalRef(name);
    }
    env->DeleteLocalRef(type);
    env->DeleteLocalRef(activity);
    return text.empty() ? fallback : text;
}
#elif defined(_WIN32)
"""),
           ("""        const std::string text = "The game stopped because of an error. What happened is in " +
                                 g_log + ", beside the game.";
""", """#ifdef __ANDROID__
        const std::string text = AppText(g_log);            // (the app's own words)
#else
        const std::string text = "The game stopped because of an error. What happened is in " +
                                 g_log + ", beside the game.";
#endif
""")],
          "the native side's own words")

    patch(CONTROLS,
          [("""        final int bit; final String label; final boolean right; final float fx, fy, fw, fh;
""", """        final int bit; String label; final boolean right; final float fx, fy, fw, fh;
"""),
           ("""    public TouchControls(Context context) {
        super(context);
""", """    public TouchControls(Context context) {
        super(context);
        setLanguage();
"""),
           ("""    public void setListener(Listener listener) { this.listener = listener; }
""", """    public void setListener(Listener listener) { this.listener = listener; }

    /* The words on the buttons, in the language in use. */
    public void setLanguage() {
        Context context = getContext();
        if (context == null) return;
        buttons[8].label = Strings.get(context, "select");
        buttons[9].label = Strings.get(context, "start");
        invalidate();
    }
""")],
          "the touch controls' words")
    return 0


if __name__ == "__main__":
    sys.exit(main())
