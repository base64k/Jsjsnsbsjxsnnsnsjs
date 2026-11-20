Up (PS2) - native Android port, version {version}
==================================================

An unofficial, fan-made native port of Up (PS2) to Android. The game's PS2
program was translated to C++ and compiled for ARM64; it runs natively on your
phone, not in an emulator.

This download contains NO game content. You need your own copy of the game: an
ISO disc image you made from your own disc (SLUS-21864). Nothing of the game -
no textures, sounds, music, movies or data - is included, and none is
downloaded: everything comes from your disc image.

Not affiliated with, endorsed by or sponsored by the game's publisher or
developer. Its trademarks belong to their owners.

This is an ALPHA: expect bugs.


What you need
-------------

* Android 10 (API 29) or later
* A 64-bit phone (arm64-v8a) with Vulkan 1.1 or later - nearly all of them
* Your own disc image of Up (SLUS-21864), as an .iso (or a .bin with its .cue)


Getting started
---------------

1. Install the APK (it is unsigned with the developer's key: Android may ask
   you to allow installation from this source).
2. Start it. The first time, the app asks for your disc image: pick the .iso
   with the system's file picker. It is remembered; you can change it in the
   app's settings.
3. The on-screen controls appear over the picture - a small button shows and
   hides them. A controller (a DualShock 2 or an Xbox pad over USB or
   Bluetooth) works too.


Files beside the app
--------------------

The app keeps its files in its own folder on the phone
(Android/data/io.github.base64k.up/files):

  pc_settings.ini   your settings, and where your disc image is
  memcard/          your memory card: the game's saves
  *.log             what the last run did (useful in a bug report)

You can reach that folder over USB with a file manager.


Known issues
------------

(The game's own - fill in.)


Licences
--------

The port's own code is under the MIT licence. The libraries built into the
APK (SDL 3, volk, glslang, Vulkan-Headers) ship their own licences.
