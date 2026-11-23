@echo off
chcp 65001 >nul
title Nha may HV2 - Telegram Bot 24/7
cd /d "%~dp0"
set PYTHONIOENCODING=utf-8
".venv\Scripts\python.exe" telegram_bot.py
pause
