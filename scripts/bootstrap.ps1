# One-shot setup: install uv, sync deps, launch GUI
# Run: START.bat  or  powershell -File scripts\bootstrap.ps1

$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot
$PythonDir = Join-Path $RepoRoot "python"

function Write-Step([string]$Message) {
    Write-Host ""
    Write-Host "==> $Message" -ForegroundColor Cyan
}

function Refresh-UserPath {
    $userPath = [Environment]::GetEnvironmentVariable("Path", "User")
    $machinePath = [Environment]::GetEnvironmentVariable("Path", "Machine")
    if ($userPath) {
        $env:Path = "$userPath;$machinePath"
    }
}

function Find-UvExe {
    $cmd = Get-Command uv -ErrorAction SilentlyContinue
    if ($cmd) {
        return $cmd.Source
    }
    $candidates = @(
        (Join-Path $env:USERPROFILE ".local\bin\uv.exe"),
        (Join-Path $env:USERPROFILE ".cargo\bin\uv.exe")
    )
    foreach ($path in $candidates) {
        if (Test-Path $path) {
            return $path
        }
    }
    return $null
}

function Ensure-Uv {
    $existing = Find-UvExe
    if ($existing) {
        Write-Step "uv found: $existing"
        return $existing
    }

    Write-Step "uv not found - installing (astral.sh)..."
    Write-Host "Internet access required." -ForegroundColor Yellow

    $installScript = Join-Path $env:TEMP "uv-install.ps1"
    Invoke-WebRequest -Uri "https://astral.sh/uv/install.ps1" -OutFile $installScript -UseBasicParsing
    & powershell -NoProfile -ExecutionPolicy Bypass -File $installScript

    Refresh-UserPath
    $uv = Find-UvExe
    if (-not $uv) {
        throw "uv install failed. See https://docs.astral.sh/uv/getting-started/installation/"
    }
    Write-Host "uv installed: $uv" -ForegroundColor Green
    return $uv
}

function Invoke-Uv {
    param(
        [string]$UvExe,
        [string[]]$UvArgs
    )
    & $UvExe @UvArgs
    $code = $LASTEXITCODE
    if ($code -ne 0) {
        $cmdLine = $UvArgs -join " "
        throw "uv failed with exit code ${code} (uv $cmdLine)"
    }
}

try {
    Write-Host "========================================" -ForegroundColor White
    Write-Host "  CH1-CH8 control - Arduino + ULN2803A" -ForegroundColor White
    Write-Host "========================================" -ForegroundColor White

    $uvExe = Ensure-Uv
    Set-Location $PythonDir

    Write-Step "Creating venv and installing packages (uv sync)..."
    $pyVer = (Get-Content -Path ".python-version" -Raw).Trim()
    Write-Host "First run may download Python $pyVer" -ForegroundColor Gray
    Invoke-Uv -UvExe $uvExe -UvArgs @("sync", "--group", "modern")

    Write-Step "Starting GUI..."
    Write-Host "Flash Arduino first: firmware/multi_channel_driver/" -ForegroundColor Yellow

    try {
        Invoke-Uv -UvExe $uvExe -UvArgs @("run", "python", "gui_modern.py")
    }
    catch {
        Write-Host "Modern GUI failed, trying light GUI (tkinter)..." -ForegroundColor Yellow
        Invoke-Uv -UvExe $uvExe -UvArgs @("run", "python", "gui_light.py")
    }
}
catch {
    Write-Host ""
    Write-Host "ERROR: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}
