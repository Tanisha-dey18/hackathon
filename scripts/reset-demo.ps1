# Resets SENTINEL's local demo data so the next backend start re-seeds the synthetic world and
# retrains the models. Use it before recording a demo: every demo run adds history and shifts later scores.
# Only removes the local SQLite database and trained model files; never touches .env.
$ErrorActionPreference = "Stop"
$backend = Join-Path (Split-Path -Parent $PSScriptRoot) "backend"

$listening = Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue
if ($listening) {
    Write-Host "The backend is still running on port 8000. Stop it first (Ctrl+C in its terminal), then re-run this script." -ForegroundColor Yellow
    exit 1
}

$targets = @(Get-ChildItem -Path $backend -Filter "sentinel.db*" -File -ErrorAction SilentlyContinue)
$modelStore = Join-Path $backend "model_store"
foreach ($t in $targets) { Remove-Item $t.FullName -Force; Write-Host "removed $($t.Name)" }
if (Test-Path $modelStore) { Remove-Item $modelStore -Recurse -Force; Write-Host "removed model_store" }
if (-not $targets -and -not (Test-Path $modelStore)) { Write-Host "Nothing to remove; already clean." }

Write-Host "Done. Start the backend again; the first start re-seeds and retrains (about 30-60 s)." -ForegroundColor Green
