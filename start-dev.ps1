#Requires -Version 5.1
<#
.SYNOPSIS
  Local dev startup for MSR Map (backend + frontend).

.EXAMPLE
  .\start-dev.ps1

.EXAMPLE
  .\start-dev.ps1 -Stop
#>
param(
    [switch]$BackendOnly,
    [switch]$FrontendOnly,
    [switch]$Stop,
    [switch]$NoBrowser,
    [switch]$SkipInstall
)

$ErrorActionPreference = "Stop"
$Root = $PSScriptRoot
$BackendDir = Join-Path $Root "backend"
$FrontendDir = Join-Path $Root "frontend"
$VenvPython = Join-Path $BackendDir ".venv\Scripts\python.exe"
$VenvPip = Join-Path $BackendDir ".venv\Scripts\pip.exe"
$EnvFile = Join-Path $BackendDir ".env"
$EnvExample = Join-Path $BackendDir ".env.example"

function Write-Info([string]$Message) {
    Write-Host "[msr_map] $Message" -ForegroundColor Cyan
}

function Write-Ok([string]$Message) {
    Write-Host "[msr_map] $Message" -ForegroundColor Green
}

function Write-Warn([string]$Message) {
    Write-Host "[msr_map] $Message" -ForegroundColor Yellow
}

function Test-Command([string]$Name) {
    return $null -ne (Get-Command $Name -ErrorAction SilentlyContinue)
}

function Stop-Port([int]$Port) {
    $connections = @(Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue)
    foreach ($conn in $connections) {
        $procId = $conn.OwningProcess
        if ($procId -and $procId -ne 0) {
            $proc = Get-Process -Id $procId -ErrorAction SilentlyContinue
            if ($proc) {
                Write-Warn "Stopping $($proc.ProcessName) (PID $procId) on port $Port"
                Stop-Process -Id $procId -Force -ErrorAction SilentlyContinue
            }
        }
    }
}

function Ensure-Backend {
    if (-not (Test-Command "python")) {
        throw "Python not found. Install Python 3.11+ and add it to PATH."
    }

    if (-not (Test-Path $VenvPython)) {
        Write-Info "Creating backend virtual environment..."
        Push-Location $BackendDir
        try {
            python -m venv .venv
        }
        finally {
            Pop-Location
        }
    }

    if (-not $SkipInstall) {
        Write-Info "Installing backend dependencies..."
        & $VenvPip install -q -r (Join-Path $BackendDir "requirements.txt")
    }

    if (-not (Test-Path $EnvFile)) {
        Write-Info "Copying backend\.env.example -> backend\.env"
        Copy-Item $EnvExample $EnvFile
    }
}

function Ensure-Frontend {
    if (-not (Test-Command "npm")) {
        throw "npm not found. Install Node.js 18+ and add it to PATH."
    }

    $nodeModules = Join-Path $FrontendDir "node_modules"
    if (-not $SkipInstall -and -not (Test-Path $nodeModules)) {
        Write-Info "Installing frontend dependencies (npm install)..."
        Push-Location $FrontendDir
        try {
            npm install
        }
        finally {
            Pop-Location
        }
    }
}

function Start-BackendWindow {
    $backendScript = @"
`$Host.UI.RawUI.WindowTitle = 'MSR Map - Backend :8000'
Set-Location '$BackendDir'
& '$VenvPython' -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
"@

    Start-Process powershell -ArgumentList @(
        "-NoExit",
        "-ExecutionPolicy", "Bypass",
        "-Command", $backendScript
    ) | Out-Null

    Write-Ok "Backend: http://localhost:8000  (docs: http://localhost:8000/docs)"
}

function Start-FrontendWindow {
    $frontendScript = @"
`$Host.UI.RawUI.WindowTitle = 'MSR Map - Frontend :5173'
Set-Location '$FrontendDir'
npm run dev
"@

    Start-Process powershell -ArgumentList @(
        "-NoExit",
        "-ExecutionPolicy", "Bypass",
        "-Command", $frontendScript
    ) | Out-Null

    Write-Ok "Frontend: http://localhost:5173/#/login"
}

# --- main ---

if ($Stop) {
    Write-Info "Stopping dev servers..."
    Stop-Port 8000
    Stop-Port 5173
    Write-Ok "Done."
    exit 0
}

$startBackend = -not $FrontendOnly
$startFrontend = -not $BackendOnly

Write-Info "Project root: $Root"

if ($startBackend) { Ensure-Backend }
if ($startFrontend) { Ensure-Frontend }

if ($startBackend) { Start-BackendWindow }
if ($startFrontend) { Start-FrontendWindow }

if ($startBackend -and $startFrontend -and -not $NoBrowser) {
    Start-Sleep -Seconds 3
    Start-Process "http://localhost:5173/#/login"
}

Write-Host ""
Write-Ok "Started. Log windows opened separately."
Write-Host "  Stop:       .\start-dev.ps1 -Stop" -ForegroundColor DarkGray
Write-Host "  Test login: admin / admin" -ForegroundColor DarkGray
