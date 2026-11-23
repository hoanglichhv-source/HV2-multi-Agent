"""
Runner phụ trợ cho Web Dashboard (dashboard.py).
Chạy 12 AI Agents theo chỉ thị giao việc, stream log UTF-8 trực tiếp ra stdout
và lưu bản kế hoạch cuối cùng vào file JSON/Markdown chỉ định.
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

from crew import build_hv2_crew


def main() -> None:
    load_dotenv()
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(description="Chạy 12 AI Agents HV2 từ Web Dashboard")
    parser.add_argument("--directive", type=str, default="", help="Chỉ thị giao việc cho CEO HV2")
    parser.add_argument("--result-file", type=str, required=True, help="Đường dẫn lưu kết quả cuối")
    args = parser.parse_args()

    ceo_model = os.getenv("CEO_MODEL", "gemini/gemini-3.1-flash-lite")
    worker_model = os.getenv("WORKER_MODEL", "gemini/gemini-3.1-flash-lite")
    max_rpm = os.getenv("CREW_MAX_RPM", "15")

    print("=" * 70, flush=True)
    print(f"[HV2] Khởi động 12 AI Agents | CEO: {ceo_model} | Workers: {worker_model} | max_rpm={max_rpm}", flush=True)
    if args.directive.strip():
        print(f"[HV2] Chỉ thị giao việc: {args.directive.strip()}", flush=True)
    print("=" * 70, flush=True)

    hv2_crew = build_hv2_crew(
        ceo_directive=args.directive,
        enable_terminal_human_input=False,
    )
    result = hv2_crew.kickoff(
        inputs={
            "run_date": datetime.now().strftime("%Y-%m-%d %H:%M"),
        }
    )

    out_path = Path(args.result_file)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(str(result), encoding="utf-8")
    print("\n[HV2] HOÀN TẤT TỔNG HỢP KẾ HOẠCH - ĐANG TRÌNH BAN LÃNH ĐẠO PHÊ DUYỆT!", flush=True)


if __name__ == "__main__":
    main()
