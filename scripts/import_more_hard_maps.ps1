# import_more_hard_maps.ps1
# Imports additional verified Boxoban hard maps.
# Existing maps are skipped automatically by the Python importer.
# This can take several minutes depending on --scan and --shards.
#
# Usage:
#   .\scripts\import_more_hard_maps.ps1
#
# After importing, run:
#   python -m pytest tests\test_hard_maps.py -v

$hardMapsDir = Join-Path $PSScriptRoot "..\hard_maps"
$hardMapCount = (Get-ChildItem -LiteralPath $hardMapsDir -Filter "*.txt").Count
Write-Host "Existing maps before import: $hardMapCount"

Write-Host "Importing more verified Boxoban hard maps..."
Write-Host "Existing maps are skipped automatically."
Write-Host "This may take several minutes."
Write-Host ""

python scripts\import_boxoban_hard_maps.py --limit 5 --scan 250 --shards 000,001,002 --max-expanded 180000 --min-expanded 1000

$hardMapCount = (Get-ChildItem -LiteralPath $hardMapsDir -Filter "*.txt").Count

Write-Host ""
Write-Host "Done. To verify new maps:"
Write-Host "  python -m pytest tests\test_hard_maps.py -v"
Write-Host "  python scripts\watch_optimization.py --check-manifest --min-tracked-maps $hardMapCount --min-consecutive-solves 3"
