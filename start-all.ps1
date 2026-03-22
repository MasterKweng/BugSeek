[CmdletBinding()]
param(
    [ValidateSet("dev", "test")]
    [string]$Env = "dev",

    [ValidateSet("all", "backend", "frontend", "worker")]
    [string]$Only = "all",

    [switch]$StartWorker,
    [switch]$NoInstall
)

$ErrorActionPreference = "Stop"

$rootDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$backendDir = Join-Path $rootDir "backend"
$frontendDir = Join-Path $rootDir "frontend"
$pythonExe = "python"
$backendPort = 8000
$frontendPort = 3000

function Write-Step {
    param([string]$Message)
    Write-Host "[BugSeek] $Message"
}

function Test-CommandExists {
    param([string]$CommandName)
    return $null -ne (Get-Command $CommandName -ErrorAction SilentlyContinue)
}

function Start-ServiceWindow {
    param(
        [string]$Title,
        [string]$WorkingDirectory,
        [string]$Command
    )

    $script = @"
Set-Location -LiteralPath '$WorkingDirectory'
`$env:APP_ENV = '$Env'
$Command
"@

    Start-Process powershell.exe -WorkingDirectory $WorkingDirectory -ArgumentList @(
        "-NoExit",
        "-ExecutionPolicy", "Bypass",
        "-Command", $script
    ) | Out-Null

    Write-Step "Started $Title window"
}

Write-Step "Env: $Env"
Write-Step "Mode: $Only"

if (($Only -eq "all" -or $Only -eq "backend" -or $Only -eq "worker") -and -not (Test-CommandExists $pythonExe)) {
    throw "Python was not found in PATH."
}

if (($Only -eq "all" -or $Only -eq "frontend") -and -not (Test-CommandExists "npm")) {
    throw "npm was not found in PATH."
}

if (($Only -eq "all" -or $Only -eq "backend" -or $Only -eq "worker") -and -not (Test-Path (Join-Path $backendDir ".env.$Env"))) {
    throw "Missing env file: backend/.env.$Env"
}

if (($Only -eq "all" -or $Only -eq "backend" -or $Only -eq "worker") -and -not $NoInstall) {
    Write-Step "Checking backend virtualenv"
    $venvActivate = Join-Path $backendDir "venv\Scripts\Activate.ps1"
    if (-not (Test-Path $venvActivate)) {
        Write-Step "Creating backend virtualenv"
        & $pythonExe -m venv (Join-Path $backendDir "venv")
    }

    Write-Step "Installing backend dependencies"
    powershell.exe -ExecutionPolicy Bypass -Command "Set-Location -LiteralPath '$backendDir'; . .\venv\Scripts\Activate.ps1; pip install -r requirements.txt"
}

if (($Only -eq "all" -or $Only -eq "frontend") -and -not $NoInstall) {
    Write-Step "Installing frontend dependencies"
    powershell.exe -ExecutionPolicy Bypass -Command "Set-Location -LiteralPath '$frontendDir'; npm install"
}

if ($Only -eq "all" -or $Only -eq "backend") {
    $backendCommand = @(
        ". .\venv\Scripts\Activate.ps1",
        "python -m uvicorn app.main:app --reload --host 0.0.0.0 --port $backendPort"
    ) -join "; "
    Start-ServiceWindow -Title "backend" -WorkingDirectory $backendDir -Command $backendCommand
    Write-Step "Backend: http://127.0.0.1:$backendPort"
    Write-Step "Docs: http://127.0.0.1:$backendPort/docs"
}

$shouldStartWorker = $StartWorker -or $Only -eq "worker"
if ($shouldStartWorker) {
    $workerCommand = @(
        ". .\venv\Scripts\Activate.ps1",
        "celery -A app.celery_config worker --loglevel=INFO --logfile=$backendDir\logs\celery_worker.log --pool=threads --without-mingle --without-gossip"
    ) -join "; "
    Start-ServiceWindow -Title "worker" -WorkingDirectory $backendDir -Command $workerCommand
}

if ($Only -eq "all" -or $Only -eq "frontend") {
    $frontendCommand = "npm run dev -- --host 0.0.0.0 --port $frontendPort"
    Start-ServiceWindow -Title "frontend" -WorkingDirectory $frontendDir -Command $frontendCommand
    Write-Step "Frontend: http://127.0.0.1:$frontendPort"
}
