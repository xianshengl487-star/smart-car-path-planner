# Android Native Smart-Car Planner

This is a native Android app source tree for on-phone map editing and planning.
It is not the previous PWA/browser version.

## What Runs On The Phone

- Custom 16x12 map editor.
- 101/102/103 templates.
- On-device recognition-route planning.
- On-device bounded A* push-box planner.
- Numbered boxes disappear after reaching their matching target, so playback and
  solver occupancy match the competition rule.
- Landscape playback with step-by-step driving animation.
- Playback controls: play/pause, single step, and x1/x2/x4/x8 fast-forward.
- STM32 performance simulation:
  - max expanded states
  - max frontier size
  - max actions
  - max wall-clock milliseconds

The app has two limit presets:

- `STM32 strict`: intentionally small frontier/expanded/time budgets. This is
  used to see whether a map is realistic for an STM32F304-class controller.
- `STM32 relaxed`: still bounded, but sized so phone-side testing can complete
  the default 101/102/103 maps.

## Build

Open `android_native/` in Android Studio and run the `app` configuration, or
build the debug APK from this machine with the bundled Gradle/JDK/Android SDK
paths used by the project scripts.

## Core Verification Without Android SDK

The planner core under `app/src/main/java/com/smartcar/planner/planner/` has no
Android imports and can be compiled with `javac`.

```powershell
cd <project-root>
javac -encoding UTF-8 -d android_native\build\core_classes android_native\app\src\main\java\com\smartcar\planner\planner\*.java android_native\SmokeCore.java
java -cp android_native\build\core_classes SmokeCore
```

Or run:

```powershell
android_native\run_core_smoke.ps1
```

## Packaging the APK (one-command)

From the project root (recommended):

```powershell
powershell -ExecutionPolicy Bypass -File .\package_android_app.ps1
```

Or from inside `android_native/`:

```powershell
powershell -ExecutionPolicy Bypass -File .\package_app.ps1
```

What the script does:
1. Runs the core smoke test first (gate – the Java planner must still produce the committed optimal costs for 101/102/103).
2. Invokes Gradle (`gradlew assembleDebug` + best-effort `assembleRelease`).
3. Copies the resulting APK(s) to `outputs/SmartCarPlannerNative-debug.apk` (and release variant if produced).
4. Prints adb install / WeChat transfer instructions.

Requirements:
- Android SDK + Gradle (or the Gradle wrapper checked out / generated via Android Studio).
- The script will fail early if the smoke test does not pass, ensuring you never ship an APK with a broken planner.

After packaging you can:
- `adb install -r outputs\SmartCarPlannerNative-debug.apk`
- Or transfer the APK via WeChat / file helper to a test device (the workflow used during the project's contest testing).

The packaged app is a self-contained landscape tool: map editor + on-device solver (with recognition phase + vanish-on-goal + bomb explosions) + animation playback, with presets that simulate the STM32 resource limits used in the embedded export.
