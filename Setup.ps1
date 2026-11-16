# One-time setup for YouTube Content Creator on Windows.
# Run from this folder in PowerShell:
#   powershell -ExecutionPolicy Bypass -File .\Setup.ps1
# Safe to run again: each step skips what is already done.

$ErrorActionPreference = "Stop"
Set-Location -Path $PSScriptRoot
$Repo = "https://github.com/MCDR-Code/YouTube_Content_Creator.git"

Write-Host "1/6 Checking for Python 3.12..."
& py -3.12 --version
if ($LASTEXITCODE -ne 0) { throw "Python 3.12 not found. Install it from python.org, then run this again." }

Write-Host "2/6 Creating the virtual environment (.venv)..."
if (-not (Test-Path ".venv\Scripts\python.exe")) { & py -3.12 -m venv .venv }
$Py = ".\.venv\Scripts\python.exe"

Write-Host "3/6 Installing packages (Swarms and friends, takes a few minutes)..."
& $Py -m pip install --upgrade pip --quiet
& $Py -m pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) { throw "pip install failed." }

Write-Host "4/6 Creating .env from .env.example (if missing)..."
if (-not (Test-Path ".env")) { Copy-Item ".env.example" ".env" }

Write-Host "5/6 Running the setup check and tests..."
& $Py -m ycc.check_setup
& $Py -m pytest -q
if ($LASTEXITCODE -ne 0) { throw "Tests failed. Send me the output above." }

Write-Host "6/6 Setting up git..."
if (-not (Test-Path ".git")) {
    git init
    git branch -M main
}
$remotes = git remote
if ($remotes -notcontains "origin") { git remote add origin $Repo }
git add -A
$staged = git diff --cached --name-only
if ($staged) {
    git commit -m "Project setup"
}
if (git ls-files .env) { throw ".env is tracked by git. Stop and tell me." }

Write-Host ""
Write-Host "Done. To publish to GitHub, run:"
Write-Host "  git push -u origin main"
