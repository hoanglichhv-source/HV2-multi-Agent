"""
Điểm khởi chạy chính của Hệ thống Multi-Agent Nhà máy HV2.
Cách dùng:
    python main.py
"""

from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

from config.hv2_constraints import FACTORY_NAME, get_constraints_summary
from crew import build_hv2_crew


def main() -> None:
    load_dotenv()

    print("=" * 72)
    print(f"KHỞI ĐỘNG HỆ THỐNG 12 AI AGENTS - {FACTORY_NAME}")
    print("=" * 72)
    print(get_constraints_summary())
    print("-" * 72)
    ceo_model = os.getenv("CEO_MODEL", "gemini/gemini-2.5-pro")
    worker_model = os.getenv("WORKER_MODEL", "gemini/gemini-2.5-flash")
    max_rpm = os.getenv("CREW_MAX_RPM", "15")
    print(f"Đang khởi tạo CEO HV2 ({ceo_model}) và 11 Nhân sự số ({worker_model})...")
    print(f"Chế độ: Process.hierarchical | max_rpm={max_rpm} | human_input=True (Chờ duyệt)")
    print("-" * 72)

    hv2_crew = build_hv2_crew()
    result = hv2_crew.kickoff(
        inputs={
            "run_date": datetime.now().strftime("%Y-%m-%d %H:%M"),
        }
    )

    # Lưu bản kế hoạch cuối cùng sau khi được duyệt ra thư mục output/
    output_dir = Path(__file__).resolve().parent / "output"
    output_dir.mkdir(exist_ok=True)
    report_path = output_dir / f"HV2_Plan_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
    report_path.write_text(str(result), encoding="utf-8")

    print("\n" + "=" * 72)
    print("KẾT QUẢ KẾ HOẠCH SẢN XUẤT NHÀ MÁY HV2 (ĐÃ PHÊ DUYỆT)")
    print("=" * 72)
    print(result)
    print("-" * 72)
    print(f"Đã lưu báo cáo kế hoạch tại: {report_path}")


if __name__ == "__main__":
    main()
