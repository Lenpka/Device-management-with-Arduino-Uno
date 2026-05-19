@echo off
chcp 65001 >nul
title Пульт CH1-CH8 — установка и запуск
cd /d "%~dp0"

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\bootstrap.ps1"
set ERR=%ERRORLEVEL%

if %ERR% neq 0 (
    echo.
    echo Нажмите любую клавишу для выхода...
    pause >nul
    exit /b %ERR%
)

exit /b 0
