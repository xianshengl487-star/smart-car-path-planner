# ProGuard rules for SmartCarPlannerNative
# Currently minify is disabled for both debug and release in build.gradle.
# Add keep rules here if you enable minifyEnabled true in the future.

# Keep the main entry point and planner core
-keep public class com.smartcar.planner.MainActivity { *; }
-keep public class com.smartcar.planner.planner.** { *; }

# The custom View uses reflection-free drawing
-keep public class com.smartcar.planner.MapEditorView { *; }
