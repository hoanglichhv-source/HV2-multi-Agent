"""
Script chạy tự động theo lịch (Cron / GitHub Actions / Cloud Run Jobs)
khi máy tính của bạn đã tắt:
1. Khởi chạy 12 AI Agents HV2 đọc Google Sheet & lập kế hoạch sản xuất.
2. Tự động thử lại tối đa 3 lần (nghỉ 30 giây/lần) nếu Google Gemini API tạm quá tải (503/429).
3. Gửi toàn bộ bản kế hoạch tổng hợp của CEO HV2 (hoặc cảnh báo lỗi nếu quá tải kéo dài)
   vào nhóm/cá nhân Telegram qua Bot API.
"""

from __future__ import annotations

import os
import time
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

from crew import build_hv2_crew
from telegram_bot import send_telegram_message

MAX_RETRIES = 3
RETRY_DELAY_SECONDS = 30


def main() -> None:
    load_dotenv()

    chat_id = (
        os.getenv("TELEGRAM_CHAT_ID", "").strip()
        or os.getenv("TELEGRAM_ALLOWED_CHAT_ID", "").strip()
    )
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    target_chat = chat_id.split(",")[0].strip() if chat_id else ""

    directive = os.getenv(
        "HV2_SCHEDULED_DIRECTIVE",
        "Lập kế hoạch sản xuất định kỳ cho tất cả đơn hàng mới trên HV2_Orders, "
        "tuân thủ tuyệt đối quy tắc khổ tối đa 720mm (bắt buộc qua MX-01 nếu >720mm) "
        "và đồng bộ lên HV2_Production_Schedule & HV2_QC_Reports.",
    )

    run_started = datetime.now().strftime("%d/%m/%Y %H:%M")
    print(f"[HV2 Cron] Bắt đầu phiên lập kế hoạch tự động lúc {run_started}", flush=True)

    plan_text = ""
    last_error: Exception | None = None

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            print(f"[HV2 Cron] Lần chạy {attempt}/{MAX_RETRIES}...", flush=True)
            hv2_crew = build_hv2_crew(
                ceo_directive=directive,
                enable_terminal_human_input=False,
            )
            result = hv2_crew.kickoff(
                inputs={"run_date": datetime.now().strftime("%Y-%m-%d %H:%M")}
            )
            plan_text = str(result)
            last_error = None
            break
        except Exception as exc:
            last_error = exc
            err_msg = str(exc)
            print(f"[HV2 Cron] Lần {attempt} gặp lỗi: {err_msg[:300]}", flush=True)
            if attempt < MAX_RETRIES:
                print(
                    f"[HV2 Cron] Đợi {RETRY_DELAY_SECONDS} giây rồi tự động thử lại...",
                    flush=True,
                )
                time.sleep(RETRY_DELAY_SECONDS)

    if last_error is not None:
        if target_chat and bot_token:
            alert = (
                f"⚠️ CẢNH BÁO NHÀ MÁY HV2 ({run_started})\n"
                f"Phiên lập kế hoạch tự động đã thử lại {MAX_RETRIES} lần nhưng máy chủ Google Gemini API "
                f"đang tạm quá tải (503/429).\n\n"
                f"Chi tiết ngắn: {str(last_error)[:280]}\n\n"
                f"👉 Bạn có thể bấm 'Re-run' trên GitHub Actions hoặc mở Web Dashboard bấm chạy lại sau ít phút."
            )
            try:
                send_telegram_message(target_chat, alert)
            except Exception as tg_exc:
                print(f"[HV2 Cron] Không gửi được cảnh báo Telegram: {tg_exc}", flush=True)
        raise last_error

    output_dir = Path(__file__).resolve().parent / "output"
    output_dir.mkdir(exist_ok=True)
    out_file = output_dir / f"HV2_Scheduled_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
    out_file.write_text(plan_text, encoding="utf-8")
    print(f"[HV2 Cron] Đã lưu báo cáo tại: {out_file}", flush=True)

    if target_chat and bot_token:
        header = (
            f"🏭 BÁO CÁO KẾ HOẠCH TỰ ĐỘNG NHÀ MÁY HV2 ({run_started})\n"
            f"========================================\n\n"
        )
        send_telegram_message(target_chat, header + plan_text)
        print(f"[HV2 Cron] Đã gửi bản kế hoạch tới Telegram Chat ID: {target_chat}", flush=True)
    else:
        print("[HV2 Cron] Chưa cấu hình TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID -> chỉ lưu file cục bộ.", flush=True)


if __name__ == "__main__":
    main()
