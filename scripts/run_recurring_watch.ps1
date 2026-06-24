# run_recurring_watch.ps1
# Runs the recurring 30-minute optimization check.
# Stop anytime with Ctrl+C.
#
# Usage:
#   .\scripts\run_recurring_watch.ps1
#
# To check manifest health separately:
#   python scripts\watch_optimization.py --check-manifest
#   python scripts\watch_optimization.py --check-manifest --min-tracked-maps 43 --min-consecutive-solves 3

Write-Host "Starting recurring optimization check (interval=1800s, max-expanded=250000)..."
Write-Host "Press Ctrl+C to stop."
Write-Host ""

python scripts\watch_optimization.py --interval-seconds 1800 --max-expanded 250000

Write-Host ""
Write-Host "Stopped. To check manifest health:"
Write-Host "  python scripts\watch_optimization.py --check-manifest"
Write-Host "  python scripts\watch_optimization.py --check-manifest --min-tracked-maps 43 --min-consecutive-solves 3"
