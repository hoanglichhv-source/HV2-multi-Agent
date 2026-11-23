@echo off
chcp 65001 >nul
title Nha may HV2 - Web Dashboard 12 AI Agents
cd /d "%~dp0"

echo ========================================================================
echo   KHOI DONG WEB DASHBOARD 12 AI AGENTS - NHA MAY HV2 (DOC LAP)
echo ========================================================================

if not exist ".venv\Scripts\python.exe" (
    echo [LOI] Chua co moi truong ao .venv!
    echo Hay mo PowerShell tai thu muc nay va chay:
    echo   python -m venv .venv
    echo   .\.venv\Scripts\pip.exe install -r requirements.txt
    pause
    exit /b 1
)

if not exist ".env" (
    echo [CANH BAO] Chua co file .env! Hay copy .env.example thanh .env va dien GEMINI_API_KEY, GOOGLE_SHEET_ID.
)

if not exist "credentials.json" (
    echo [LUU Y] Chua co file credentials.json trong thu muc du an.
    echo Ban co the tai len truc tiep ngay tren giao dien Web Dashboard sap mo!
)

set PYTHONIOENCODING=utf-8
echo.
echo Dang mo trinh duyet tai http://localhost:8501 ...
echo (Giu cua so den nay mo trong khi su dung Dashboard. Nhan Ctrl+C de tat.)
echo.

".venv\Scripts\streamlit.exe" run dashboard.py --server.port 8501 --browser.gatherUsageStats false
pause
