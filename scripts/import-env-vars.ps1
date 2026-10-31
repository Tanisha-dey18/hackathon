# Copies PayPal/Groq credentials from your Windows user environment (set with `setx`) into the
# project .env, without printing them. Writes scripts/.import-check.txt with non-secret
# diagnostics (account name and value lengths only).
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$envFile = Join-Path $root ".env"
if (-not (Test-Path $envFile)) { Copy-Item (Join-Path $root ".env.example") $envFile }

$keys = "PAYPAL_CLIENT_ID", "PAYPAL_CLIENT_SECRET", "PAYPAL_WEBHOOK_ID", "GROQ_API_KEY"
$lines = Get-Content $envFile
$report = @("account=$env:USERDOMAIN\$env:USERNAME", "profile=$env:USERPROFILE")
foreach ($k in $keys) {
    $v = [Environment]::GetEnvironmentVariable($k, "User")
    if ($v) {
        $v = $v.Trim().Trim('"').Trim("'")
        $found = $false
        $lines = $lines | ForEach-Object {
            if ($_ -match "^$k=") { $found = $true; "$k=$v" } else { $_ }
        }
        if (-not $found) { $lines += "$k=$v" }
    }
    $report += "$k length=" + $(if ($v) { $v.Length } else { 0 })
}
Set-Content -Path $envFile -Value $lines -Encoding ascii
$report | Set-Content -Path (Join-Path $PSScriptRoot ".import-check.txt") -Encoding ascii
Write-Host "Done. Credentials copied into .env (values not shown)."
