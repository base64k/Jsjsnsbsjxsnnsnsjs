# Up (PS2) → Android

`Disney/Pixar Up` (PS2, **SLUS-21864 / SLUS_218.64**) — нақты PS2 эмуляторы
емес, **нативты** Android порты: ойынның EE коды C++-қа айналдырылып,
ARM64 (arm64-v8a) үшін қайта жиналып, Vulkan арқылы сызылады.

Негізгі құрал — [ps2-port-engine](https://github.com/danielgomesvieira2000/ps2-port-engine)
(idanielgomesvieira2000, MIT): PS2 программасын тексерілген C++-қа айналдыратын
toolchain + нативты хост (EE ядросы, IOP, SPU2, GS/Vulkan, VU, диск, дыбыс).
Ол `engine/` ішіндегі submodule ретінде қосылған.

---

## Қазіргі күйі (шынымен, қысқаша)

| Бөлік | Күйі |
|---|---|
| Репозиторийдің құрылымы (`engine/`, `games/up/`, `scripts/`) | ✅ дайын |
| `ps2-port-engine` (v0.9.0-дан кейінгі commit, Android қолдауы бар) | ✅ submodule-ке қосылған |
| Ойынның конфигурациясы (`game.json`, иконка, `overrides.cpp`) | ✅ дайын |
| CI: диск → декомпиляция → APK (`android-apk.yml`) | ✅ **жүріп шықты**: шынайы диск, декомпиляция, `arm64-v8a` APK |
| Нақты APK (ойын ойнатылған күйі) | ✅ бар (артефакт, 36 МБ); ойын әлі толық істемейді |

> Бұл репозиторийде диск образы **жоқ** — CI оны жүріс кезінде сіздің Drive
> файлыңыздан алып, тек өз кэшінде ұстайды. Декомпиляция мен жинау сондықтан
> тек CI-да тексеріледі. Бірінші толық жүріс (2026-11-20) сәтті аяқталды:
> Android SDK, NDK, build-tools, **шынайы** диск, талдау, C++-қа айналдыру,
> ARM64 жинауы және APK — бәрі өтті.

### Не тексерілді

| Тексеру | Нәтиже |
|---|---|
| Engine-дің өз тесттері (`python -m unittest discover -s engine/tests`) | ✅ 444 өтті |
| Түйіндік pipeline (синтетикалық ELF-мен): analyze → signatures → lift → dispatch table | ✅ бәрі жұмыс істейді |
| Порттың CMake конфигурациясы (SDL3 + Vulkan + хост) | ✅ |
| PC reference build (437 мақсат, `up` орындалады: «Up, version 0.1.0-alpha») | ✅ |
| CI: Android SDK, NDK, build-tools, платформа (35) | ✅ өтті |
| CI: шынайы Drive дискін жүктеу, ашу, `SYSTEM.CNF`-тен программаны табу | ✅ өтті |
| CI: шынайы ойын кодын C++-қа айналдыру және `arm64-v8a` APK жинау | ✅ өтті (36 МБ APK) |
| Ойынның өзі (бірінші кадр) | ⛔ әлі жоқ — `smoke` жүрісінің хаты келесі қадамды көрсетеді |


---

## Қалай іске қосу керек (GitHub Actions — ең арзан жол)

Репозиторийде дайын workflow бар: **`.github/workflows/android-apk.yml`**.

1. **Actions → Android APK → Run workflow** (қолмен) немесе `main`ке push.
2. Workflow өзі:
   - диск образын сіздің Google Drive файлыңыздан алады (`scripts/fetch_disc.sh`,
     ~1 ГБ, еште қолмен жүктеу қажет емес);
   - `SYSTEM.CNF`-тен ойынның программасын (`SLUS_218.64`) алып, ISO-дан шығарады;
   - `analyze.py` → `signatures.py` → `lift.py` арқылы ойынның функцияларын
     C++-қа айналдырып, түпнұсқа кодпен салыстырып тексереді;
   - **PC reference build** жасайды да, ойынды headless іске қосады: хаты
     «ойын қай кезеңде тоқтайды» деп айтады, ал сызған кадрларын
     `up-smoke` артефактына сақтайды;
   - соңынан `android.py` арқылы `arm64-v8a` кітапханасын жасап, APK-ны жинайды
     (жүріс кезінде табылған код та APK-да болады);
   - APK-ны **артефакт** ретінде береді (жүктеп алып телефонға орнатуға болады).

Workflow-дың кіру параметрлері (`workflow_dispatch`):

| Параметр | Не істейді |
|---|---|
| `stages` | қай кезеңдерді орындау: `disc extract analyze derive lift host apk` |
| `abi` | `arm64-v8a` (телефон) немесе `x86_64` (эмулятор) |
| `cache` | диск образын және декомпиляция нәтижесін кэшта сақтау (әдепкі: қосулы) |
| `smoke` | PC reference build + headless жүріс (ойын қаншалықты ашылады); push-та әдепкі ол қосулы |
| `publish` | APK-ны GitHub release-ке жариялау (prerelease) |

**Экономия:** бір job, матрица жоқ, кэш бар жерде қарымды кезеңдер өткізіледі,
жаңа push ағымдағы жүрісті тоқтатады (`concurrency`), әр жүріс 300 минутпен
шектелген.

### Диск образы

Ол сіздің Google Drive файлыңызда:
`Disney-Pixar Up (USA) (EnFr).zip` (`1LIzZFzNoXUteK5fnJLT1P6vGoIxg1fDA`),
«кімде болса — оқу» деп ашылған. Workflow `gdown` арқылы сол сілтемеден
алады және ішінен `.iso`-ды тауып `disc/up.iso` жасайды.

Drive-да «жүктеулер көп» деген қате шықса — файлдың көшірмесін жасап,
жаңа сілтемені workflow-дың `env:` бөліміне (`UP_DRIVE_FILE_ID`) қою керек.

---

## Жергілікті (өз компьютеріңізде) жинау

CI жоқ болса да, бәрі жергілікті жұмады:

```sh
git clone --recursive <repo>
cd Up-android_port

# 1. диск образы (Drive-тан немесе локальді файлдан)
UP_DISC_FILE=/path/to/up.iso bash scripts/fetch_disc.sh

# 2. бәрі: талдау → декомпиляция → APK
bash scripts/build_apk.sh
```

Керек: Python 3.10+, Android SDK + NDK + build-tools 35, JDK 17, CMake, Ninja,
Pillow, gdown. `UP_JOBS` — параллел процесс саны (декомпиляция көп процесс
жұмыс істейді).

---

## Репозиторийдің құрылымы

```
Up-android_port/
├── engine/                    ps2-port-engine (submodule, 65c46e9)
├── games/up/                  ойынның каталогы (engine/tools/port.py init жасаған)
│   ├── game.json              ойынның аты, программасы (SLUS_218.64), Android пакеті
│   ├── config/functions.csv   порттың жетілуі (функциялардың кестесі)
│   ├── docs/FINDINGS.md       не табылды, не жасалды
│   └── port/
│       ├── CMakeLists.txt     порттың жинауы
│       ├── overrides.cpp       ойынның функцияларына астын салған хост-код
│       ├── icon.ico           порттың өз иконкасы (оЙыннан емес, скрипт сызған)
│       ├── release/README.txt ойыншыға арналған мәтін (APK үшін)
│       └── runs/              скрипттелген жүрістер (регресс тесттері)
├── scripts/
│   ├── fetch_disc.sh          Drive-тан дискты алу
│   ├── build_apk.sh           барлық кезеңдер (CI да осыны шақырады)
│   ├── smoke_test.sh          PC build + headless жүріс
│   └── make_icon.py           иконканы сызу
└── .github/workflows/android-apk.yml
```

**Ойынның коды репозиторийге кірмейді.** `lift.py` шығаратын C++ (`games/up/src/`)
— ойынның меншігі; ол `.gitignore`-де, CI-да қайта тудырылады. Мұрада
жарияланған кезде де осы ереже сақталады (см. `engine/.claude/skills/ps2-release`).

---

## Қандай мәселелер күтуге болады

`ps2-port-engine` **Burnout 3** үшін жасалған, ал Up — басқа middleware (Zouna/EA
немесе басқа) пайдаланады. Сондықтан:

- EE-дегі кейбір жүйелік қызмет (syscall) немесе IOP модулі Up-ке тән болуы
  мүмкін → оларды `engine/host`-та (қажет болса) немесе `games/up/port/overrides.cpp`-те
  іске асыру керек;
- VU микрокоды (VU1) болса — оны жазу және AOT жинау керек;
- `smoke` жүрісінің хаты айтады: ойын қай кезеңде тоқтайды (қай syscall,
  қай регистр) — ол келесі қадамның картасы.

Сондықтан алғашқы мақсат — **бірінші кадрды көрсету**, әлі толық ойын емес.

---

## Құқықтық жағы

Бұл ресми емес, әуесқан жасалған порт. Ойындың авторлары мен
таратушыларымен байланыстығы жоқ; «Up» — олардың белгісі. Репозиторийде
ойынның коды мен активтері **жоқ**: APK ойыншыдан өз диск образын сұрайды
(бірінші іске қосқанда жүйе файлын таңдау терезесі арқылы) және ойынды
сол дисктен оқиды. Құқықтық тұрғыдан: engine-дің MIT лицензиясы тек
құралға қатысты; ойынның коды — ойыншының өзінікі.

---

# Up (PS2) → Android (Русский)

`Disney/Pixar Up` (PS2, **SLUS-21864 / SLUS_218.64**) — **нативный** порт на
Android, а не эмулятор: код EE переписывается в C++ и собирается под ARM64
(arm64-v8a), картинка рисуется через Vulkan.

Основной инструмент — [ps2-port-engine](https://github.com/danielgomesvieira2000/ps2-port-engine)
(MIT): набор инструментов, превращающий программу PS2 в проверенный C++ плюс
нативный хост (ядро EE, IOP, SPU2, GS на Vulkan, VU, диск, звук). Он подключён
как submodule `engine/`.

## Где мы сейчас

| Часть | Состояние |
|---|---|
| Структура репозитория (`engine/`, `games/up/`, `scripts/`) | готово |
| `ps2-port-engine` закреплён (коммит с поддержкой Android) | готово |
| Конфигурация игры (`game.json`, иконка, `overrides.cpp`) | готово |
| CI: диск → декомпиляция → APK (`android-apk.yml`) | **прошло**: настоящий диск, декомпиляция, APK для `arm64-v8a` |
| Настоящий APK (в состоянии «играбельно») | есть (артефакт, 36 МБ); сама игра ещё не запускается |

Образ диска в этом репозитории **отсутствует**: CI скачивает его во время
запуска из вашего файла на Google Drive и держит только в своём кэше, поэтому
декомпиляция и сборка проверяются лишь там. Первый полный запуск (2026-11-20)
завершился успешно: Android SDK, NDK, build-tools, **настоящий** диск, анализ,
перевод в C++, сборка под ARM64 и упаковка APK — всё прошло.

### Что проверено

| Проверка | Результат |
|---|---|
| Собственные тесты движка (`python -m unittest discover -s engine/tests`) | 444 пройдено |
| Основной конвейер на синтетическом ELF: analyze → signatures → lift → dispatch table | работает |
| CMake-конфигурация порта (SDL3 + Vulkan + хост) | работает |
| PC reference build (437 целей; `up` запускается: «Up, version 0.1.0-alpha») | работает |
| CI: Android SDK, NDK, платформа и build-tools | проходит |
| CI: скачивание и распаковка настоящего диска, поиск программы в нём | проходит |
| CI: декомпиляция настоящей игры и сборка APK для `arm64-v8a` | проходит (APK 36 МБ) |
| Сама игра (первый кадр) | ещё нет — отчёт smoke-запуска укажет следующий шаг |

## Как запустить

**GitHub Actions (самый дешёвый способ).** Откройте вкладку Actions в
репозитории и запустите workflow *Android APK* (или сделайте push в `main`).
Он скачивает образ диска из вашего файла на Google Drive, достаёт из него
программу (`SLUS_218.64`), декомпилирует и сверяет каждую функцию с
оригинальным машинным кодом, собирает PC reference и запускает игру без
окна (отчёт говорит, где игра остановилась, а нарисованные кадры кладутся в
артефакт `up-smoke`), и наконец собирает APK для `arm64-v8a` — уже с кодом,
найденным во время запуска. APK выходит артефактом.

Параметры: `stages` (какие этапы выполнять), `abi` (`arm64-v8a` или `x86_64`),
`cache` (хранить диск и декомпилированный код в кэше раннера),
`smoke` (PC reference build и запуск без окна; при push он включён по
умолчанию), `publish` (прикрепить APK к pre-release).

**Локально:**

```sh
git clone --recursive <repo> && cd Up-android_port
UP_DISC_FILE=/path/to/up.iso bash scripts/fetch_disc.sh
bash scripts/build_apk.sh
```

Нужны Python 3.10+, Android SDK (NDK, платформа, build-tools 35), JDK 17,
CMake, Ninja, Pillow и gdown.

## Образ диска

Ваш собственный файл на Google Drive — `Disney-Pixar Up (USA) (EnFr).zip`
(`1LIzZFzNoXUteK5fnJLT1P6vGoIxg1fDA`), открытый «для всех, у кого есть
ссылка». `scripts/fetch_disc.sh` скачивает его через `gdown`, распаковывает и
оставляет образ в `disc/up.iso`. Если Drive пожалуется, что файл скачивают
слишком часто, сделайте копию и подставьте новый id в блок `env:` workflow'а
(`UP_DRIVE_FILE_ID`).

## Что ожидать

`ps2-port-engine` сделан для *Burnout 3*; *Up* работает на другом middleware.
Некоторые его системные вызовы, модули IOP или микрокод VU могут потребовать
работы — в `engine/host` (если это нужно каждой игре) или в
`games/up/port/overrides.cpp` (если только этой). Отчёт smoke-запуска говорит,
где игра останавливается, — это карта следующего шага. Первая цель — **один
кадр на экране**, а не вся игра.

## Право

Неофициальный порт, сделанный фанатами. Никакой связи с издателем и
разработчиком игры, одобрения или спонсорства с их стороны нет; «Up» — их
торговая марка. В репозитории нет ни кода, ни ресурсов игры: APK просит
игрока показать свой образ диска при первом запуске и читает игру с него.

---

# Up (PS2) → Android (English)

`Disney/Pixar Up` (PS2, **SLUS-21864 / SLUS_218.64**) as a **native** Android
port, not an emulator: the game's EE code is recompiled to C++ and built for
ARM64, drawn with Vulkan.

The tool is [ps2-port-engine](https://github.com/danielgomesvieira2000/ps2-port-engine)
(MIT): a toolchain that turns a PS2 program into verified C++ plus a native
host (EE kernel, IOP, SPU2, GS on Vulkan, VUs, disc, audio). It is vendored as
the `engine/` submodule.

## Where it stands

| Part | State |
|---|---|
| Repository layout (`engine/`, `games/up/`, `scripts/`) | done |
| `ps2-port-engine` pinned (a commit with the Android support) | done |
| The game's configuration (`game.json`, icon, `overrides.cpp`) | done |
| CI: disc → decompile → APK (`.github/workflows/android-apk.yml`) | **passed**: the real disc, the decompilation, the `arm64-v8a` APK |
| A real APK | yes (an artifact, 36 MB); the game itself does not run yet |

The disc image is not in this repository: the CI fetches it from your Drive
file at run time and keeps it in its own cache, so the decompilation and the
build are only ever exercised there. The first complete run (2026-11-20)
finished successfully: the Android SDK, the NDK, the build tools, the **real**
disc, the analysis, the translation to C++, the ARM64 build and the APK
packaging all passed.

### What has been checked

| Check | Result |
|---|---|
| The engine's own tests (`python -m unittest discover -s engine/tests`) | 444 pass |
| The core pipeline on a synthetic ELF: analyze → signatures → lift → dispatch table | works |
| The port's CMake configure (SDL3 + Vulkan + the host) | works |
| The PC reference build (437 targets; `up` runs: "Up, version 0.1.0-alpha") | works |
| CI: the Android SDK, the NDK, the platform and the build tools | passes |
| CI: fetching and unpacking the real Drive disc, and finding the program in it | passes |
| CI: decompiling the real game and building the `arm64-v8a` APK | passes (a 36 MB APK) |
| The game itself (one frame) | not yet - the smoke run's report names the next step |

## Running it

**GitHub Actions (the cheapest way).** Open the repository's Actions tab, run
the *Android APK* workflow (or push to `main`). It fetches the disc image from
your Google Drive file, takes the program out of it (`SLUS_218.64`), decompiles
and verifies every function against the original machine code, builds the PC
reference and runs the game headless (its report says where the game stops,
and the pictures it drew come out as the `up-smoke` artifact), and finally
builds the `arm64-v8a` APK - with the code the run found in it. The APK comes
out as an artifact.

Inputs: `stages` (which stages to run), `abi` (`arm64-v8a` or `x86_64`),
`cache` (keep the disc and the decompiled code in the runner's cache),
`smoke` (the PC reference build and the headless run; on a push it is on by
default), `publish` (attach the APK to a prerelease).

**Locally:**

```sh
git clone --recursive <repo> && cd Up-android_port
UP_DISC_FILE=/path/to/up.iso bash scripts/fetch_disc.sh
bash scripts/build_apk.sh
```

Needs Python 3.10+, the Android SDK (NDK, platform, build-tools 35), JDK 17,
CMake, Ninja, Pillow and gdown.

## The disc image

Your own Drive file, `Disney-Pixar Up (USA) (EnFr).zip`
(`1LIzZFzNoXUteK5fnJLT1P6vGoIxg1fDA`), shared with anyone who has the link.
`scripts/fetch_disc.sh` downloads it with `gdown`, unpacks it and leaves the
image at `disc/up.iso`. If Drive complains that the file is downloaded too
often, make a copy and put the new file id in the workflow's `env:` block
(`UP_DRIVE_FILE_ID`).

## What to expect

`ps2-port-engine` was built for *Burnout 3*; *Up* runs on different middleware.
Some of its kernel services, IOP modules or VU microcode may need work - in
`engine/host` (if every game needs it) or in `games/up/port/overrides.cpp` (if
only this game does). The `smoke` run's report says where the game stops, which
is the map for the next step. The first goal is **one frame on the screen**,
not the whole game.

## Legal

An unofficial, fan-made port. Not affiliated with, endorsed by or sponsored by
the game's publisher or developer; the trademark belongs to its owner. The
repository holds no game code and no assets: the APK asks the player for their
own disc image on the first run and reads the game from it.
