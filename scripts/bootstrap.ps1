# Однократный запуск на новом ПК: uv → зависимости → GUI
# Запуск: двойной щелчок START.bat или: powershell -File scripts\bootstrap.ps1

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

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
        Write-Step "uv найден: $existing"
        return $existing
    }

    Write-Step "uv не найден — установка (официальный скрипт Astral)..."
    Write-Host "Может потребоваться доступ в интернет." -ForegroundColor Yellow

    $installScript = Join-Path $env:TEMP "uv-install.ps1"
    Invoke-WebRequest -Uri "https://astral.sh/uv/install.ps1" -OutFile $installScript -UseBasicParsing
    & powershell -NoProfile -ExecutionPolicy Bypass -File $installScript

    Refresh-UserPath
    $uv = Find-UvExe
    if (-not $uv) {
        throw "uv не установился. Установите вручную: https://docs.astral.sh/uv/getting-started/installation/"
    }
    Write-Host "uv установлен: $uv" -ForegroundColor Green
    return $uv
}

function Invoke-Uv {
    param([string]$UvExe, [string[]]$Args)
    & $UvExe @Args
    if ($LASTEXITCODE -ne 0) {
        throw "uv завершился с кодом $LASTEXITCODE: uv $($Args -join ' ')"
    }
}

try {
    Write-Host "========================================" -ForegroundColor White
    Write-Host "  Пульт CH1-CH8 · Arduino + ULN2803A" -ForegroundColor White
    Write-Host "========================================" -ForegroundColor White

    $uvExe = Ensure-Uv
    Set-Location $PythonDir

    Write-Step "Создание окружения и установка зависимостей (uv sync)..."
    Write-Host "При первом запуске uv может скачать Python $(Get-Content .python-version -Raw)." -ForegroundColor Gray
    Invoke-Uv $uvExe @("sync", "--group", "modern")

    Write-Step "Запуск интерфейса..."
    Write-Host "Перед работой: прошейте Arduino (firmware/multi_channel_driver/) и подключите USB." -ForegroundColor Yellow

    try {
        Invoke-Uv $uvExe @("run", "python", "gui_modern.py")
    } catch {
        Write-Host "Современный GUI недоступен, запуск лёгкого (tkinter)..." -ForegroundColor Yellow
        Invoke-Uv $uvExe @("run", "python", "gui_light.py")
    }
}
catch {
    Write-Host ""
    Write-Host "ОШИБКА: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}
