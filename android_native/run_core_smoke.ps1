Set-StrictMode -Version Latest
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$out = Join-Path $root "build\core_classes"
Remove-Item -Recurse -Force $out -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Force -Path $out | Out-Null
javac -encoding UTF-8 -d $out `
  (Join-Path $root "app\src\main\java\com\smartcar\planner\planner\*.java") `
  (Join-Path $root "SmokeCore.java")
java -cp $out SmokeCore
