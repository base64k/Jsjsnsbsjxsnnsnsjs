/*
 * The app's own words, in the two languages the port speaks: English and
 * Russian.
 *
 * The player chooses the language - the disc's dialog has the choice - and
 * the choice is kept. The system's own language is the default, so a phone
 * set to Russian gets a Russian app without asking anything.
 *
 * The texts are here rather than in the resources (the engine's build makes
 * the dex without the resource class the resources would need), so they are
 * looked up by their own name: Strings.get(this, "choose").
 */
package org.ps2port;

import android.content.Context;
import android.content.SharedPreferences;
import android.content.res.Configuration;

import java.util.HashMap;
import java.util.Locale;
import java.util.Map;

public final class Strings {
    /* The language the player chose: SYSTEM (the system's own), ENGLISH or
       RUSSIAN. */
    public static final String SYSTEM = "system";
    public static final String ENGLISH = "en";
    public static final String RUSSIAN = "ru";

    /* Where the choice is kept (the app's own file). */
    private static final String PREFS = "ps2port";
    private static final String KEY_LANGUAGE = "language";

    /* Every text: the English one first, the Russian one after. */
    private static final Map<String, String[]> TEXTS = new HashMap<String, String[]>();

    static {
        TEXTS.put("not_the_disc", new String[]{
            "This is not an image of the %s disc.",
            "Это не образ диска %s."});
        TEXTS.put("choose_disc", new String[]{
            "Choose your own %s disc image (.iso) - it stays on your device; the game reads it from there.",
            "Выберите свой образ диска %s (.iso) - он останется на устройстве, а игра прочитает его оттуда."});
        TEXTS.put("choose", new String[]{"Choose", "Выбрать"});
        TEXTS.put("quit", new String[]{"Quit", "Выход"});
        TEXTS.put("cancel", new String[]{"Cancel", "Отмена"});
        TEXTS.put("language", new String[]{"Language", "Язык"});
        TEXTS.put("system_language", new String[]{"System language", "Язык системы"});
        TEXTS.put("english", new String[]{"English", "Английский"});
        TEXTS.put("russian", new String[]{"Russian", "Русский"});
        TEXTS.put("no_picker", new String[]{"No file picker on this device.",
            "На этом устройстве нет выбора файлов."});
        TEXTS.put("stopped", new String[]{
            "The game stopped because of an error. What happened is in %s, beside the game.",
            "Игра остановилась из-за ошибки. Что произошло - в %s, рядом с игрой."});
        TEXTS.put("vulkan_needed", new String[]{
            "This phone's Vulkan is older than 1.1, which the port needs.",
            "На этом телефоне Vulkan старее 1.1, а порту нужна версия 1.1 или новее."});
        TEXTS.put("select", new String[]{"SELECT", "ВЫБОР"});
        TEXTS.put("start", new String[]{"START", "СТАРТ"});
    }

    /* The language in use now ("en" or "ru"); worked out when it is first
       needed and kept. */
    private static String language;

    private Strings() { }

    /* The language the app speaks now: the player's choice, or the system's
       own when there is none. */
    public static synchronized String language(Context context) {
        if (language == null) language = resolve(context, chosen(context));
        return language;
    }

    /* The text in the language in use (its own name, if it is unknown). */
    public static String get(Context context, String key) {
        String[] pair = TEXTS.get(key);
        if (pair == null) return key;
        int index = RUSSIAN.equals(language(context)) ? 1 : 0;
        return pair[index];
    }

    /* The text with the game's name in it. */
    public static String get(Context context, String key, String name) {
        return String.format(get(context, key), name);
    }

    /* The player's choice, kept; the app's words follow it at once. */
    public static synchronized void setLanguage(Context context, String code) {
        String wanted = code == null ? SYSTEM : code;
        if (context != null) {
            try {
                context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
                       .edit().putString(KEY_LANGUAGE, wanted).apply();
            } catch (RuntimeException e) {
                // (no room for the preferences: the language is used anyway)
            }
        }
        language = resolve(context, wanted);
    }

    /* The choice as it was kept (SYSTEM when there is none). */
    private static String chosen(Context context) {
        if (context == null) return SYSTEM;
        try {
            SharedPreferences prefs = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE);
            String code = prefs.getString(KEY_LANGUAGE, SYSTEM);
            return code == null ? SYSTEM : code;
        } catch (RuntimeException e) {
            return SYSTEM;
        }
    }

    /* The language a code means: the system's own when the code is SYSTEM
       (the phone's own language, Russian or anything else is English). */
    private static String resolve(Context context, String code) {
        String wanted = code;
        if (wanted == null || SYSTEM.equals(wanted)) {
            Locale locale = Locale.getDefault();
            if (context != null) {
                try {
                    Configuration config = context.getResources().getConfiguration();
                    if (!config.getLocales().isEmpty()) locale = config.getLocales().get(0);
                } catch (RuntimeException e) {
                    // (the system's own language it is)
                }
            }
            wanted = locale.getLanguage();
        }
        return RUSSIAN.equals(wanted) ? RUSSIAN : ENGLISH;
    }
}
