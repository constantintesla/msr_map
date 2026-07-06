#Requires -Version 5.1
<#
.SYNOPSIS
  Production deploy for MSR Map on preshevkadastr.ru.

.EXAMPLE
  .\start-prod.ps1

.EXAMPLE
  .\start-prod.ps1 -Stop

.EXAMPLE
  .\start-prod.ps1 -NoBuild

.EXAMPLE
  .\start-prod.ps1 -Rebuild
#>
param(
    [switch]$Stop,
    [switch]$Rebuild,
    [switch]$NoBuild
)

$ErrorActionPreference = "Stop"
$Root = $PSScriptRoot
$EnvFile = Join-Path $Root ".env"
$EnvExample = Join-Path $Root ".env.example"
$ComposeFile = Join-Path $Root "docker-compose.yml"

function Test-DockerRegistry {
    param([int]$TimeoutSec = 8)
    try {
        $req = [System.Net.HttpWebRequest]::Create("https://auth.docker.io/token")
        $req.Method = "GET"
        $req.Timeout = $TimeoutSec * 1000
        $req.ReadWriteTimeout = $TimeoutSec * 1000
        $resp = $req.GetResponse()
        $resp.Close()
        return $true
    } catch {
        return $false
    }
}

function Write-DockerHubHelp {
    Write-Warn @"
Docker Hub is unreachable (registry pull failed). Common fixes on Windows:
  1. Start without rebuild:  .\start-prod.ps1 -NoBuild
  2. Docker Desktop -> Settings -> Docker Engine -> add DNS and restart:
       `"dns`": [`"8.8.8.8`", `"1.1.1.1`"]
  3. Disable broken IPv6 route to registry (VPN/firewall) or retry on another network
  4. When online: docker pull python:3.12-slim node:20-alpine
"@
}

function Write-Info([string]$Message) {
    Write-Host "[msr_map prod] $Message" -ForegroundColor Cyan
}

function Write-Ok([string]$Message) {
    Write-Host "[msr_map prod] $Message" -ForegroundColor Green
}

function Write-Warn([string]$Message) {
    Write-Host "[msr_map prod] $Message" -ForegroundColor Yellow
}

function Ensure-EnvFile {
    if (Test-Path $EnvFile) {
        return
    }
    if (-not (Test-Path $EnvExample)) {
        throw "Missing $EnvExample"
    }
    Copy-Item $EnvExample $EnvFile
    $secret = [Convert]::ToBase64String((1..48 | ForEach-Object { Get-Random -Maximum 256 }))
    (Get-Content $EnvFile -Raw) -replace 'SECRET_KEY=.*', "SECRET_KEY=$secret" |
        Set-Content $EnvFile -NoNewline
    Write-Ok "Created .env with generated SECRET_KEY"
}

function Stop-LegacyNginx {
    $legacy = docker ps --format "{{.Names}}" | Where-Object { $_ -eq "msrv_b9_kadastr_nginx" }
    if ($legacy) {
        Write-Warn "Stopping legacy nginx (msrv_b9_kadastr) to free ports 80/443"
        docker stop msrv_b9_kadastr_nginx | Out-Null
    }
    $legacyCertbot = docker ps --format "{{.Names}}" | Where-Object { $_ -eq "msrv_b9_kadastr-certbot-1" }
    if ($legacyCertbot) {
        Write-Warn "Stopping legacy certbot (msrv_b9_kadastr)"
        docker stop msrv_b9_kadastr-certbot-1 | Out-Null
    }
}

function Wait-Healthy {
    param([string]$Url, [int]$Retries = 30)
    for ($i = 1; $i -le $Retries; $i++) {
        try {
            $resp = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 5
            if ($resp.StatusCode -eq 200) {
                return $true
            }
        } catch {
            Start-Sleep -Seconds 2
        }
    }
    return $false
}

if ($Stop) {
    Write-Info "Stopping MSR Map production stack"
    docker compose -f $ComposeFile down
    Write-Ok "Stopped"
    exit 0
}

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    throw "Docker is not installed or not in PATH"
}

Ensure-EnvFile
Stop-LegacyNginx

if ($Rebuild -and $NoBuild) {
    throw "Use either -Rebuild or -NoBuild, not both"
}

$composeArgs = @("compose", "-f", $ComposeFile, "up", "-d")
if ($Rebuild) {
    if (-not (Test-DockerRegistry)) {
        Write-DockerHubHelp
        throw "Cannot reach Docker Hub - rebuild aborted. Use .\start-prod.ps1 -NoBuild if images already exist locally."
    }
    $composeArgs += "--build"
} elseif (-not $NoBuild) {
  # Default: build only if service images are missing (no forced pull of base images).
  $missing = @()
  foreach ($svc in @("backend", "frontend")) {
    $img = docker compose -f $ComposeFile images -q $svc 2>$null
    if (-not $img) { $missing += $svc }
  }
  if ($missing.Count -gt 0) {
    Write-Info "Missing images for: $($missing -join ', ') - building once (pull: false in compose)"
    if (-not (Test-DockerRegistry)) {
      Write-DockerHubHelp
      throw "Cannot reach Docker Hub and local images for $($missing -join ', ') are missing."
    }
    $composeArgs += "--build"
  } else {
    Write-Info "Using existing local images (pass -Rebuild to force rebuild)"
  }
}

Write-Info "Starting MSR Map production stack"
Push-Location $Root
try {
    & docker @composeArgs
    if ($LASTEXITCODE -ne 0) {
        Write-DockerHubHelp
        throw "docker compose failed with exit code $LASTEXITCODE"
    }
} finally {
    Pop-Location
}

Write-Info "Waiting for backend /health"
if (Wait-Healthy "http://localhost/health") {
    Write-Ok "Production is up: https://preshevkadastr.ru"
} else {
    Write-Warn "Stack started, but /health did not respond in time. Check: docker compose -f docker-compose.yml logs -f"
}
