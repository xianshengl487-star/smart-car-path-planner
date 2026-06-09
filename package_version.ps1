param(
    [Parameter(Mandatory = $true)]
    [string]$Version
)

$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$TargetDir   = Join-Path $ProjectRoot "versions\$Version"

# ── create version folder ──
if (Test-Path $TargetDir) {
    Write-Error "Folder '$TargetDir' already exists. Remove it first or choose another version."
    exit 1
}
New-Item -ItemType Directory -Path $TargetDir -Force | Out-Null
Write-Host "Created: $TargetDir"

# ── copy planner/*.py (skip __pycache__) ──
$PlannerSrc = Join-Path $ProjectRoot "planner"
$PlannerDst = Join-Path $TargetDir "planner"
New-Item -ItemType Directory -Path $PlannerDst -Force | Out-Null

Get-ChildItem -Path $PlannerSrc -Filter "*.py" -File | Where-Object {
    $_.DirectoryName -notmatch "__pycache__"
} | ForEach-Object {
    $DestFile = Join-Path $PlannerDst $_.Name
    Copy-Item $_.FullName $DestFile
    Write-Host "  planner/$($_.Name)"
}

# ── copy top-level files ──
$FilesToCopy = @(
    "main.py",
    "mcp_server.py",
    "export_stm32.py"
)
foreach ($f in $FilesToCopy) {
    $Src = Join-Path $ProjectRoot $f
    if (Test-Path $Src) {
        Copy-Item $Src (Join-Path $TargetDir $f)
        Write-Host "  $f"
    } else {
        Write-Warning "Source file not found: $Src"
    }
}

# ── copy embedded/ directory ──
$EmbeddedSrc = Join-Path $ProjectRoot "embedded"
$EmbeddedDst = Join-Path $TargetDir "embedded"
if (Test-Path $EmbeddedSrc) {
    Copy-Item $EmbeddedSrc $EmbeddedDst -Recurse
    Write-Host "  embedded/"
} else {
    Write-Warning "embedded/ directory not found, skipping."
}

# ── create run.bat ──
$RunBat = Join-Path $TargetDir "run.bat"
@"
@echo off
python main.py --all --no-gui
"@ | Out-File -FilePath $RunBat -Encoding ascii -NoNewline
Write-Host "  run.bat"

Write-Host "`nVersion '$Version' packaged successfully -> $TargetDir"
