@echo off
chcp 65001 >nul
title Nha may HV2 - 12 AI Agents (Terminal Mode)
cd /d "%~dp0"

echo ========================================================================
echo   CHAY HE THONG 12 AI AGENTS NHA MAY HV2 (CHUONG TRINH DOC LAP)
echo ========================================================================

if not exist ".venv\Scripts\python.exe" (
    echo [LOI] Chua co moi truong ao .venv!
    pause
    exit /b 1
)

if not exist "credentials.json" (
    echo [LOI] Thieu file credentials.json (Google Service Account) trong thu muc:
    echo       %cd%
    echo Xem file HUONG_DAN_CHAY_DOC_LAP.md de lay file trong 2 phut.
    pause
    exit /b 1
)

set PYTHONIOENCODING=utf-8
".venv\Scripts\python.exe" main.py
echo.
pause
