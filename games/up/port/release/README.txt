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
3. The app also asks for access to the phone's shared storage (the "all files"
   permission). It is optional: the file picker above works without it, but
   with it the port can see an image you keep in the Downloads folder or
   anywhere else on the storage.
4. The on-screen controls appear over the picture - a small button shows and
   hides them. A controller (a DualShock 2 or an Xbox pad over USB or
   Bluetooth) works too.
5. The app's own words (the dialogs, the messages, the controls' labels) are
   in English or in Russian: the disc's dialog has a "Language" button, and
   the phone's own language is the default - a phone set to Russian gets a
   Russian app without asking anything.


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


Русский
=======

Это неофициальный порт игры Up (PS2) на Android, сделанный фанатами.
Программа игры переведена на C++ и собрана для ARM64: она работает нативно
на вашем телефоне, а не в эмуляторе.

В сборке НЕТ содержимого игры. Нужна ваша собственная копия: образ диска
Up (SLUS-21864) в виде .iso (или .bin с .cue). Все, что в игре, приходит с
вашего образа; ничего не скачивается.

Это АЛЬФА: ждите ошибок.

Что нужно
---------

* Android 10 (API 29) или новее
* 64-битный телефон (arm64-v8a) с Vulkan 1.1 или новее - почти у всех
* Свой образ диска Up (SLUS-21864)

Как начать
----------

1. Установите APK и запустите его. В первый раз приложение попросит образ
   диска: выберите .iso через файловый выборщик системы. Он запоминается.
2. Приложение также спросит доступ к общей памяти телефона (разрешение "все
   файлы"). Это необязательно: выборщик выше работает и без него, но с ним
   порт видит образ, который лежит в «Загрузках» или в любом другом месте.
3. На картинке появятся экранные кнопки - маленькая кнопка их показывает и
   прячет. Геймпад тоже работает.
4. Слова самого приложения (окна, сообщения, надписи на кнопках) - на
   английском или по-русски: в окне выбора диска есть кнопка "Язык". По
   умолчанию язык берётся у телефона: телефон с русским языком сразу
   получает русское приложение.

Файлы рядом с приложением
--------------------------

Приложение хранит свои файлы в своей папке на телефоне
(Android/data/io.github.base64k.up/files): pc_settings.ini, memcard/ (ваши
сохранения) и *.log (что делал последний запуск - приложите их к отчёту об
ошибке).

Лицензии
--------

Код порта - под лицензией MIT. Библиотеки, вшитые в APK (SDL 3, volk,
glslang, Vulkan-Headers), идут со своими лицензиями.
