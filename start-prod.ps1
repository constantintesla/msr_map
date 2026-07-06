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

.EXAMPLE
  .\start-prod.ps1 -Local
#>
param(
    [switch]$Stop,
    [switch]$Rebuild,
    [switch]$NoBuild,
    [switch]$Local
)

$ErrorActionPreference = "Stop"
$Root = $PSScriptRoot
$EnvFile = Join-Path $Root ".env"
$EnvExample = Join-Path $Root ".env.example"
$ComposeFile = Join-Path $Root "docker-compose.yml"
$ComposeLocalFile = Join-Path $Root "docker-compose.local.yml"
$ComposeSslExternalFile = Join-Path $Root "docker-compose.ssl-external.yml"
$LegacyCertVolume = "msrv_b9_kadastr_certbot_conf"
$CertDomain = "preshevkadastr.ru"

function Test-DockerVolume {
    param([string]$Name)
    docker volume inspect $Name 2>$null | Out-Null
    return $LASTEXITCODE -eq 0
}

function Test-LegacySslCerts {
    if (-not (Test-DockerVolume $LegacyCertVolume)) {
        return $false
    }
    $out = docker run --rm -v "${LegacyCertVolume}:/certs:ro" alpine:3.20 `
        test -f "/certs/live/$CertDomain/fullchain.pem" 2>$null
    return $LASTEXITCODE -eq 0
}

function Test-ProjectSslCerts {
    $out = docker run --rm -v msr_map_certbot_certs:/certs:ro alpine:3.20 `
        test -f "/certs/live/$CertDomain/fullchain.pem" 2>$null
    return $LASTEXITCODE -eq 0
}

function Get-ComposeFiles {
    param([bool]$UseLocal)
    $files = @($ComposeFile)
    if ($UseLocal) {
        $files += $ComposeLocalFile
    } elseif (Test-LegacySslCerts) {
        $files += $ComposeSslExternalFile
    }
    return $files
}

function Get-ComposeServices {
    param([bool]$UseLocal)
    if ($UseLocal) {
        return @("postgres", "backend", "frontend", "nginx")
    }
    return @()
}

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
            $params = @{
                Uri             = $Url
                UseBasicParsing = $true
                TimeoutSec      = 5
            }
            if ($Url -like "https://*") {
                $params.SkipCertificateCheck = $true
            }
            $resp = Invoke-WebRequest @params
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
    $stopFiles = Get-ComposeFiles -UseLocal:$Local
    if (-not $Local -and (Test-LegacySslCerts)) {
        $stopFiles = @($ComposeFile, $ComposeSslExternalFile)
    }
    $stopArgs = @("compose") + ($stopFiles | ForEach-Object { "-f"; $_ }) + @("down")
    & docker @stopArgs
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

$useLocal = $Local
if (-not $useLocal -and -not (Test-LegacySslCerts) -and -not (Test-ProjectSslCerts)) {
    $useLocal = $true
    Write-Warn "SSL certificates not found - starting in local HTTP mode (http://localhost)"
    Write-Warn "For HTTPS on server: issue certs (see README) or use legacy volume msrv_b9_kadastr_certbot_conf"
} elseif (-not $useLocal -and (Test-LegacySslCerts)) {
    Write-Info "Using legacy SSL volume: $LegacyCertVolume"
}

$composeFiles = Get-ComposeFiles -UseLocal:$useLocal
$composeArgs = @("compose") + ($composeFiles | ForEach-Object { "-f"; $_ }) + @("up", "-d")
$services = Get-ComposeServices -UseLocal:$useLocal
if ($services.Count -gt 0) {
    $composeArgs += $services
}
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
    $imgArgs = @("compose") + ($composeFiles | ForEach-Object { "-f"; $_ }) + @("images", "-q", $svc)
    $img = & docker @imgArgs 2>$null
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
$healthUrl = if ($useLocal) { "http://localhost/health" } else { "https://localhost/health" }
if (Wait-Healthy $healthUrl) {
    if ($useLocal) {
        Write-Ok "Stack is up: http://localhost"
    } else {
        Write-Ok "Production is up: https://preshevkadastr.ru"
    }
} else {
    Write-Warn "Stack started, but /health did not respond in time. Check: docker compose logs -f nginx backend"
}
