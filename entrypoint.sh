#!/usr/bin/env bash
set -e

MODE="${SERVICE_MODE:-both}"
APP_PORT="${PORT:-8501}"

echo "[HV2 Cloud] Starting in SERVICE_MODE=${MODE} on PORT=${APP_PORT}..."

if [ "$MODE" = "telegram" ]; then
    exec python telegram_bot.py
elif [ "$MODE" = "dashboard" ]; then
    exec streamlit run dashboard.py --server.address 0.0.0.0 --server.port "$APP_PORT" --server.headless true --browser.gatherUsageStats false
else
    # Chạy song song Telegram Bot (nền) + Web Dashboard (chính) trong cùng 1 container
    if [ -n "${TELEGRAM_BOT_TOKEN:-}" ]; then
        echo "[HV2 Cloud] Launching Telegram Bot 24/7 in background..."
        python telegram_bot.py &
    else
        echo "[HV2 Cloud] TELEGRAM_BOT_TOKEN chưa cấu hình -> chỉ chạy Web Dashboard."
    fi
    exec streamlit run dashboard.py --server.address 0.0.0.0 --server.port "$APP_PORT" --server.headless true --browser.gatherUsageStats false
fi
