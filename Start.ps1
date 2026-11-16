# Starts the web app and a Cloudflare quick tunnel to it, prints the https link and opens it.
# Double-click Start.cmd (or run:  powershell -ExecutionPolicy Bypass -File .\Start.ps1).
# Close this window, or press Ctrl+C, to stop both.

$ErrorActionPreference = "Stop"
Set-Location -Path $PSScriptRoot
$Cloudflared = "G:\Tools\cloudflared.exe"
$Port = 5000

function Stop-All {
    foreach ($p in @($script:tun, $script:app)) {
        if ($p -and -not $p.HasExited) { Stop-Process -Id $p.Id -Force -ErrorAction SilentlyContinue }
    }
}

# 1. Checks
if (-not (Test-Path ".venv\Scripts\python.exe")) { throw "No .venv found. Run Setup.ps1 first." }
if (-not (Test-Path $Cloudflared)) { throw "cloudflared.exe was not found at $Cloudflared" }
$pwLine = Get-Content ".env" -ErrorAction SilentlyContinue | Where-Object { $_ -match '^\s*YCC_ADMIN_PASSWORD\s*=' } | Select-Object -First 1
$pw = if ($pwLine) { ($pwLine -replace '^\s*YCC_ADMIN_PASSWORD\s*=\s*', '').Trim().Trim('"') } else { "" }
if ($pw.Length -lt 10) {
    throw "Set YCC_ADMIN_PASSWORD in .env (at least 10 characters) first. Anyone with the link reaches the login page."
}
if (Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue) {
    throw "Port $Port is already in use. Close the other copy of the app first."
}

# 2. Turn on the venv for this window
. ".\.venv\Scripts\Activate.ps1"
$env:YCC_HTTPS = "1"                  # secure cookies: the app is reached over https through Cloudflare
$env:SWARMS_GLOBAL_LOGGER_ON = "false"
$env:PYTHONUTF8 = "1"                 # UTF-8 output, so Swarms' emoji do not crash the app on Windows
$env:PYTHONIOENCODING = "utf-8"
New-Item -ItemType Directory -Force "logs" | Out-Null
$tunLog = "logs\cloudflared.log"
Remove-Item $tunLog, "logs\cloudflared.err.log" -ErrorAction SilentlyContinue

try {
    # 3. Start the web app (only listens on this PC: 127.0.0.1)
    Write-Host "Starting the web app..."
    $script:app = Start-Process -FilePath "python" -ArgumentList "-m", "ycc.run_week", "serve", "--port", "$Port" `
        -NoNewWindow -PassThru -RedirectStandardOutput "logs\webapp.log" -RedirectStandardError "logs\webapp.err.log"
    $up = $false
    for ($i = 0; $i -lt 60 -and -not $up; $i++) {
        try { Invoke-WebRequest "http://127.0.0.1:$Port/health" -UseBasicParsing -TimeoutSec 2 | Out-Null; $up = $true }
        catch { Start-Sleep -Milliseconds 500 }
        if ($script:app.HasExited) { break }
    }
    if (-not $up) { throw "The web app did not start. See logs\webapp.err.log" }

    # 4. Start the Cloudflare quick tunnel (https, no account needed)
    Write-Host "Starting the Cloudflare tunnel..."
    $script:tun = Start-Process -FilePath $Cloudflared `
        -ArgumentList "tunnel", "--no-autoupdate", "--loglevel", "info", "--logfile", $tunLog, "--url", "http://127.0.0.1:$Port" `
        -NoNewWindow -PassThru -RedirectStandardError "logs\cloudflared.err.log" -RedirectStandardOutput "logs\cloudflared.out.log"
    $url = $null
    for ($i = 0; $i -lt 120 -and -not $url; $i++) {
        Start-Sleep -Milliseconds 500
        if (Test-Path $tunLog) {
            $m = Select-String -Path $tunLog, "logs\cloudflared.err.log" -Pattern 'https://[a-z0-9-]+\.trycloudflare\.com' -ErrorAction SilentlyContinue | Select-Object -First 1
            if ($m) { $url = $m.Matches[0].Value }
        }
        if ($script:tun.HasExited) { break }
    }
    if (-not $url) { throw "Cloudflare did not give a link. See logs\cloudflared.log" }

    # Wait until Cloudflare has registered the tunnel, then give its new address a few
    # seconds to go live. Opening the link too early shows "can't be reached".
    Write-Host "Waiting for the link to go live..."
    for ($i = 0; $i -lt 60; $i++) {
        if (Select-String -Path $tunLog -Pattern 'Registered tunnel connection' -Quiet -ErrorAction SilentlyContinue) { break }
        Start-Sleep -Milliseconds 500
    }
    Start-Sleep -Seconds 15

    # 5. Show and open the link
    Write-Host ""
    Write-Host "  Review app:  $url" -ForegroundColor Green
    Write-Host "  Sign in with the password from .env. The link changes every time you start."
    Write-Host "  If the page says it can't be reached, wait 30 seconds and refresh."
    Write-Host "  Close this window (or press Ctrl+C) to stop the app and the tunnel."
    Write-Host ""
    Start-Process $url

    while (-not $script:app.HasExited -and -not $script:tun.HasExited) { Start-Sleep -Seconds 2 }
    if ($script:app.HasExited) { Write-Host "The web app stopped. See logs\webapp.err.log" -ForegroundColor Yellow }
    if ($script:tun.HasExited) { Write-Host "The tunnel stopped. See logs\cloudflared.log" -ForegroundColor Yellow }
}
finally {
    Stop-All
    Write-Host "Stopped the web app and the tunnel."
}
