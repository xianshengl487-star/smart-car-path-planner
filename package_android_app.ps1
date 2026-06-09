# Convenience wrapper: run from project root (G:\路径规划)
# Delegates to android_native/package_app.ps1

$androidNative = Join-Path $PSScriptRoot "android_native"
$script = Join-Path $androidNative "package_app.ps1"

if (-not (Test-Path $script)) {
    Write-Error "android_native/package_app.ps1 not found."
    exit 1
}

Write-Host "Delegating to $script ..." -ForegroundColor Cyan
& $script @args
exit $LASTEXITCODE
