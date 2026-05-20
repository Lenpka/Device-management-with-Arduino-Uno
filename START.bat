@echo off
chcp 65001 >nul
title CH1-CH8 - setup and launch
cd /d "%~dp0"

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\bootstrap.ps1"
set ERR=%ERRORLEVEL%

if %ERR% neq 0 (
    echo.
    echo Press any key to exit...
    pause >nul
    exit /b %ERR%
)

exit /b 0
