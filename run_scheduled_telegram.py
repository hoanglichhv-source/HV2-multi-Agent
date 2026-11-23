"""
Script chạy tự động theo lịch (Cron / GitHub Actions / Cloud Run Jobs)
khi máy tính của bạn đã tắt:
1. Khởi chạy 12 AI Agents HV2 đọc Google Sheet & lập kế hoạch sản xuất.
2. Gửi toàn bộ bản kế hoạch tổng hợp của CEO HV2 vào nhóm/cá nhân Telegram qua Bot API.
"""

from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

from crew import build_hv2_crew
from telegram_bot import send_telegram_message


def main() -> None:
    load_dotenv()

    chat_id = os.getenv("TELEGRAM_CHAT_ID", "").strip() or os.getenv("TELEGRAM_ALLOWED_CHAT_ID", "").strip()
    directive = os.getenv(
        "HV2_SCHEDULED_DIRECTIVE",
        "Lập kế hoạch sản xuất định kỳ cho tất cả đơn hàng mới trên HV2_Orders, "
        "tuân thủ tuyệt đối quy tắc khổ tối đa 720mm (bắt buộc qua MX-01 nếu >720mm) "
        "và đồng bộ lên HV2_Production_Schedule & HV2_QC_Reports.",
    )

    print(f"[HV2 Cron] Bắt đầu phiên lập kế hoạch tự động lúc {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    hv2_crew = build_hv2_crew(
        ceo_directive=directive,
        enable_terminal_human_input=False,
    )
    result = hv2_crew.kickoff(
        inputs={"run_date": datetime.now().strftime("%Y-%m-%d %H:%M")}
    )
    plan_text = str(result)

    output_dir = Path(__file__).resolve().parent / "output"
    output_dir.mkdir(exist_ok=True)
    out_file = output_dir / f"HV2_Scheduled_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
    out_file.write_text(plan_text, encoding="utf-8")
    print(f"[HV2 Cron] Đã lưu báo cáo tại: {out_file}")

    if chat_id and os.getenv("TELEGRAM_BOT_TOKEN", "").strip():
        target_chat = chat_id.split(",")[0].strip()
        header = (
            f"🏭 BÁO CÁO KẾ HOẠCH TỰ ĐỘNG NHÀ MÁY HV2 ({datetime.now().strftime('%d/%m/%Y %H:%M')})\n"
            f"========================================\n\n"
        )
        send_telegram_message(target_chat, header + plan_text)
        print(f"[HV2 Cron] Đã gửi bản kế hoạch tới Telegram Chat ID: {target_chat}")
    else:
        print("[HV2 Cron] Chưa cấu hình TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID -> chỉ lưu file cục bộ.")


if __name__ == "__main__":
    main()
