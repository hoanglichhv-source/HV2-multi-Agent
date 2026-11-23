"""
Telegram Bot 24/7 Điều hành 12 AI Agents - Nhà máy HV2.
Cho phép giao việc, xem tình trạng 11 máy / kho phôi >720mm, chạy 12 AI Agents
và phê duyệt kế hoạch của CEO HV2 ngay trên điện thoại (kể cả khi tắt máy tính).

Biến môi trường cần thiết (trong .env hoặc Cloud Secrets):
- TELEGRAM_BOT_TOKEN: Token lấy từ @BotFather
- TELEGRAM_ALLOWED_CHAT_ID (tùy chọn): Chat ID cá nhân hoặc nhóm HV2 được phép ra lệnh
"""

from __future__ import annotations

import json
import os
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx
from dotenv import load_dotenv

from config.hv2_constraints import (
    BOTTLENECK_MACHINE_ID,
    MAX_ROLLING_WIDTH_MM,
    SHEET_TABS,
    requires_pre_slitting,
)
from crew import build_hv2_crew
from tools.hv2_sheets import ReadHV2SheetTool

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = BASE_DIR / "output"
OUTPUT_DIR.mkdir(exist_ok=True)

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
ALLOWED_CHAT_ID = os.getenv("TELEGRAM_ALLOWED_CHAT_ID", "").strip()
API_BASE = f"https://api.telegram.org/bot{BOT_TOKEN}"

_running_lock = threading.Lock()
_latest_plans: Dict[str, str] = {}


def send_telegram_message(chat_id: str | int, text: str) -> None:
    """Gửi tin nhắn Telegram (tự động chia nhỏ nếu vượt quá giới hạn 4096 ký tự)."""
    if not BOT_TOKEN:
        raise ValueError("Thiếu TELEGRAM_BOT_TOKEN trong biến môi trường.")

    chunk_size = 3800
    chunks = [text[i : i + chunk_size] for i in range(0, len(text), chunk_size)] or ["(Trống)"]
    with httpx.Client(timeout=30.0) as client:
        for chunk in chunks:
            client.post(
                f"{API_BASE}/sendMessage",
                json={
                    "chat_id": chat_id,
                    "text": chunk,
                },
            )


def _is_authorized(chat_id: str | int) -> bool:
    if not ALLOWED_CHAT_ID:
        return True
    allowed = [c.strip() for c in ALLOWED_CHAT_ID.split(",") if c.strip()]
    return str(chat_id) in allowed


def _build_status_report() -> str:
    reader = ReadHV2SheetTool()
    orders_raw = reader._run(SHEET_TABS["orders"])
    inv_raw = reader._run(SHEET_TABS["inventory"])
    maint_raw = reader._run(SHEET_TABS["maintenance"])

    def _safe_json(raw: str) -> List[Dict[str, Any]]:
        try:
            data = json.loads(raw)
            return data if isinstance(data, list) else []
        except Exception:
            return []

    orders = _safe_json(orders_raw)
    inv = _safe_json(inv_raw)
    maint = _safe_json(maint_raw)

    wide_coils = []
    for c in inv:
        try:
            w = float(str(c.get("Width_mm", 0)).replace(",", "."))
            if requires_pre_slitting(w):
                wide_coils.append(f"{c.get('Coil_ID')} ({int(w)}mm)")
        except Exception:
            pass

    avail = [m.get("Machine_ID") for m in maint if str(m.get("Operational_Status", "")).lower() == "available"]
    down = [
        f"{m.get('Machine_ID')} ({m.get('Operational_Status')})"
        for m in maint
        if str(m.get("Operational_Status", "")).lower() != "available"
    ]

    lines = [
        "🏭 TRẠNG THÁI NHÀ MÁY HV2 (TRỰC TIẾP TỪ GOOGLE SHEETS)",
        f"• Đơn hàng (HV2_Orders): {len(orders)}",
        f"• Cuộn phôi trong kho (HV2_Inventory): {len(inv)}",
        f"• Cuộn > {MAX_ROLLING_WIDTH_MM}mm BẮT BUỘC qua {BOTTLENECK_MACHINE_ID}: {', '.join(wide_coils) if wide_coils else 'Không có'}",
        f"• Thiết bị sẵn sàng: {len(avail)}/{len(maint) or 11}",
    ]
    if down:
        lines.append(f"• Máy đang dừng/PM: {', '.join(down)}")
    lines.append("\nGõ /plan [chỉ thị] để chạy 12 AI Agents lập kế hoạch ngay!")
    return "\n".join(lines)


def _run_crew_for_chat(chat_id: str | int, directive: str) -> None:
    if not _running_lock.acquire(blocking=False):
        send_telegram_message(
            chat_id,
            "⏳ Hệ thống 12 AI Agents đang xử lý một phiên lập kế hoạch khác. Vui lòng đợi vài phút rồi thử lại.",
        )
        return

    try:
        send_telegram_message(
            chat_id,
            "🚀 Đã nhận lệnh! CEO Nhà máy HV2 đang điều phối 11 nhân sự số đọc Google Sheet, "
            "kiểm tra quy tắc 720mm / nút thắt cổ chai MX-01 và lập kế hoạch (tốc độ max_rpm=15)...",
        )
        hv2_crew = build_hv2_crew(
            ceo_directive=directive,
            enable_terminal_human_input=False,
        )
        result = hv2_crew.kickoff(
            inputs={"run_date": datetime.now().strftime("%Y-%m-%d %H:%M")}
        )
        plan_text = str(result)
        _latest_plans[str(chat_id)] = plan_text

        draft_path = OUTPUT_DIR / f"HV2_Telegram_Draft_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
        draft_path.write_text(plan_text, encoding="utf-8")

        send_telegram_message(
            chat_id,
            f"📋 KẾ HOẠCH SẢN XUẤT NHÀ MÁY HV2 — CEO TRÌNH DUYỆT:\n\n{plan_text}\n\n"
            "----------------------------------------\n"
            "✅ Gõ /approve để PHÊ DUYỆT & lưu bản chính thức\n"
            "🔄 Hoặc gõ /revise <yêu cầu chỉnh sửa> để CEO lập lại.",
        )
    except Exception as exc:
        send_telegram_message(chat_id, f"❌ Lỗi khi chạy 12 AI Agents: {exc}")
    finally:
        _running_lock.release()


def handle_message(chat_id: str | int, text: str) -> None:
    if not _is_authorized(chat_id):
        send_telegram_message(
            chat_id,
            f"⛔ Chat ID `{chat_id}` chưa được cấp quyền điều khiển Nhà máy HV2.",
        )
        return

    cmd = text.strip()
    lower = cmd.lower()

    if lower in ("/start", "/help"):
        send_telegram_message(
            chat_id,
            "🏭 TRỢ LÝ ĐIỀU HÀNH 12 AI AGENTS — NHÀ MÁY HV2 (24/7)\n\n"
            "Các lệnh sử dụng:\n"
            "• /status — Xem nhanh đơn hàng, cuộn >720mm và trạng thái 11 máy\n"
            "• /plan [chỉ thị] — Giao việc cho CEO HV2 & 11 nhân sự lập kế hoạch\n"
            "• /approve — Phê duyệt kế hoạch CEO vừa trình\n"
            "• /revise <góp ý> — Yêu cầu CEO điều chỉnh lại kế hoạch\n"
            "• /id — Xem Chat ID hiện tại để cấu hình bảo mật\n\n"
            "💡 Bạn cũng có thể nhắn trực tiếp yêu cầu (VD: 'Ưu tiên đơn ORD-HV2-001, giữ MC-03 dự phòng').",
        )
    elif lower == "/id":
        send_telegram_message(chat_id, f"Chat ID của bạn là: {chat_id}")
    elif lower == "/status":
        send_telegram_message(chat_id, _build_status_report())
    elif lower == "/approve":
        plan = _latest_plans.get(str(chat_id))
        if not plan:
            send_telegram_message(chat_id, "⚠️ Chưa có bản kế hoạch nào đang chờ duyệt. Gõ /plan để chạy trước.")
            return
        approved_path = OUTPUT_DIR / f"HV2_Approved_TG_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
        approved_path.write_text(plan, encoding="utf-8")
        send_telegram_message(
            chat_id,
            f"✅ ĐÃ PHÊ DUYỆT KẾ HOẠCH NHÀ MÁY HV2!\nĐã lưu bản chính thức: {approved_path.name}",
        )
    elif lower.startswith("/revise"):
        feedback = cmd[len("/revise") :].strip()
        if not feedback:
            send_telegram_message(chat_id, "Vui lòng nhập nội dung góp ý sau /revise. VD: /revise Đổi cuộn 650mm sang MC-03")
            return
        threading.Thread(
            target=_run_crew_for_chat,
            args=(chat_id, f"YÊU CẦU ĐIỀU CHỈNH TỪ BAN LÃNH ĐẠO: {feedback}"),
            daemon=True,
        ).start()
    elif lower.startswith("/plan"):
        directive = cmd[len("/plan") :].strip()
        threading.Thread(
            target=_run_crew_for_chat,
            args=(chat_id, directive),
            daemon=True,
        ).start()
    else:
        # Nhắn tự do -> hiểu như chỉ thị giao việc trực tiếp cho CEO HV2
        threading.Thread(
            target=_run_crew_for_chat,
            args=(chat_id, cmd),
            daemon=True,
        ).start()


def poll_forever() -> None:
    if not BOT_TOKEN:
        raise ValueError(
            "Thiếu TELEGRAM_BOT_TOKEN trong .env hoặc Cloud Secrets. "
            "Hãy tạo bot qua @BotFather và điền token vào .env."
        )

    print("🤖 HV2 Telegram Bot 24/7 đang chạy (long-polling)...", flush=True)
    offset: Optional[int] = None

    with httpx.Client(timeout=40.0) as client:
        while True:
            try:
                params: Dict[str, Any] = {"timeout": 30}
                if offset is not None:
                    params["offset"] = offset
                resp = client.get(f"{API_BASE}/getUpdates", params=params)
                data = resp.json()
                for update in data.get("result", []):
                    offset = update["update_id"] + 1
                    msg = update.get("message") or update.get("edited_message")
                    if not msg:
                        continue
                    chat_id = msg["chat"]["id"]
                    text = msg.get("text", "")
                    if text:
                        handle_message(chat_id, text)
            except Exception as exc:
                print(f"[Telegram Polling Error] {exc}", flush=True)
                time.sleep(5)


if __name__ == "__main__":
    poll_forever()
