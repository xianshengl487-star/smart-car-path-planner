param(
    [string]$VersionsDir = '',
    [string]$ProjectDir = '',
    [string]$OutputDir = '',
    [string]$ZipPath = '',
    [string]$GradleBat = 'C:\Users\maoyaowei\AppData\Local\BlockForgeStudio\gradle\gradle-8.14.4\bin\gradle.bat',
    [string]$JavaHome = 'C:\Program Files\Zulu\zulu-17',
    [string]$AndroidHome = 'C:\Users\maoyaowei\AppData\Local\Android\Sdk'
)

$ErrorActionPreference = 'Stop'

if ([string]::IsNullOrWhiteSpace($ProjectDir)) {
    $ProjectDir = $PSScriptRoot
}
$repoRoot = Split-Path -Parent $ProjectDir
if ([string]::IsNullOrWhiteSpace($VersionsDir)) {
    $VersionsDir = Join-Path $repoRoot 'versions'
}
if ([string]::IsNullOrWhiteSpace($OutputDir)) {
    $OutputDir = Join-Path (Join-Path $repoRoot 'outputs') 'version_apks'
}
if ([string]::IsNullOrWhiteSpace($ZipPath)) {
    $ZipPath = Join-Path (Join-Path $repoRoot 'outputs') 'SmartCarPlannerNative-version-apks.zip'
}
$baseAppName = -join ([char[]](0x667A, 0x80FD, 0x8F66, 0x8DEF, 0x5F84, 0x89C4, 0x5212))

$env:JAVA_HOME = $JavaHome
$env:ANDROID_HOME = $AndroidHome
$env:ANDROID_SDK_ROOT = $AndroidHome

New-Item -ItemType Directory -Force -Path $OutputDir | Out-Null
$versions = Get-ChildItem -LiteralPath $VersionsDir -Directory | Sort-Object Name
$results = @()
$index = 0

foreach ($version in $versions) {
    $index += 1
    $safeName = $version.Name.ToLower() -replace '[^a-z0-9_]+', '_'
    $suffix = ".$safeName"
    $apkName = "SmartCarPlannerNative-$($version.Name)-debug.apk"
    $dest = Join-Path $OutputDir $apkName

    Write-Host "[$index/$($versions.Count)] Building $($version.Name)"
    & $GradleBat -p $ProjectDir assembleDebug `
        "-PplannerAppIdSuffix=$suffix" `
        "-PplannerAppName=$baseAppName $($version.Name)" `
        "-PplannerVersionName=$($version.Name)" `
        "-PplannerVersionCode=$index"
    if ($LASTEXITCODE -ne 0) {
        throw "Gradle build failed for $($version.Name)"
    }

    Copy-Item -LiteralPath (Join-Path $ProjectDir 'app\build\outputs\apk\debug\app-debug.apk') -Destination $dest -Force
    $hash = (Get-FileHash -Algorithm SHA256 -LiteralPath $dest).Hash
    $results += [pscustomobject]@{
        Version = $version.Name
        Apk = $dest
        Sha256 = $hash
    }
}

$checksumPath = Join-Path $OutputDir 'checksums.csv'
$results | Export-Csv -LiteralPath $checksumPath -NoTypeInformation -Encoding UTF8
$results | Format-Table -AutoSize
Write-Host "Wrote $checksumPath"

Remove-Item -LiteralPath $ZipPath -Force -ErrorAction SilentlyContinue
Compress-Archive -Path (Join-Path $OutputDir '*') -DestinationPath $ZipPath -Force
$zipHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $ZipPath).Hash
Write-Host "Wrote $ZipPath"
Write-Host "ZIP SHA256: $zipHash"
