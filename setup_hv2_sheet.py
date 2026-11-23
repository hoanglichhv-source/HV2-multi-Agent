"""
Script khởi tạo cấu trúc Google Sheets và dữ liệu mẫu cho Nhà máy HV2.

Chức năng:
1. Đọc GOOGLE_SHEET_ID từ .env và xác thực qua credentials.json.
2. Tạo (hoặc làm mới) đủ 5 tab:
   - HV2_Orders
   - HV2_Inventory
   - HV2_Production_Schedule
   - HV2_Maintenance
   - HV2_QC_Reports
3. Tự động điền sẵn đủ 11 máy thực tế (MC-01..03, LU-01..04, MX-01, MM-01..03) vào HV2_Maintenance.
4. Nạp sẵn 2 cuộn phôi trong kho HV2_Inventory:
   - 1 cuộn khổ 1219mm (vượt ngưỡng 720mm -> bắt buộc qua MX-01 xẻ chia khổ trước khi cán)
   - 1 cuộn khổ 650mm  (<= 720mm -> vào thẳng máy cán MC-01..03)
5. Nạp sẵn 1 đơn hàng mẫu vào HV2_Orders để test ngay bài toán xẻ thô khổ 720mm.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, List

import gspread

from config.hv2_constraints import HV2_MACHINES, SHEET_TABS
from tools.hv2_sheets import get_hv2_spreadsheet

TAB_HEADERS = {
    SHEET_TABS["orders"]: [
        "Order_ID",
        "Customer",
        "Steel_Grade",
        "Input_Thickness_mm",
        "Target_Thickness_mm",
        "Target_Width_mm",
        "Surface_Finish",
        "Quantity_Tons",
        "Due_Date",
        "Priority",
        "Status",
        "Notes",
    ],
    SHEET_TABS["inventory"]: [
        "Coil_ID",
        "Steel_Grade",
        "Thickness_mm",
        "Width_mm",
        "Weight_Tons",
        "Surface",
        "Location",
        "Status",
        "Pre_Slit_Required",
        "Notes",
    ],
    SHEET_TABS["schedule"]: [
        "Schedule_ID",
        "Order_ID",
        "Coil_ID",
        "Stage",
        "Machine_ID",
        "Input_Width_mm",
        "Output_Width_mm",
        "Start_Time",
        "End_Time",
        "Status",
        "Notes",
    ],
    SHEET_TABS["maintenance"]: [
        "Machine_ID",
        "Machine_Name",
        "Group",
        "Max_Width_mm",
        "Is_Bottleneck",
        "Operational_Status",
        "Next_PM_Date",
        "Tooling_Status",
        "Notes",
    ],
    SHEET_TABS["qc_reports"]: [
        "Report_ID",
        "Timestamp",
        "Order_ID",
        "Coil_ID",
        "QC_Type",
        "Stage_or_Machine",
        "Inspection_Criteria",
        "Result",
        "Action_Notes",
    ],
}


def get_or_create_worksheet(
    spreadsheet: gspread.Spreadsheet, title: str, rows: int = 100, cols: int = 15
) -> gspread.Worksheet:
    """Lấy worksheet nếu đã tồn tại, ngược lại tạo mới."""
    try:
        ws = spreadsheet.worksheet(title)
        print(f"  [OK] Đã tìm thấy tab '{title}' -> đang làm mới tiêu đề & dữ liệu mẫu...")
        ws.clear()
        return ws
    except gspread.WorksheetNotFound:
        print(f"  [+] Đang tạo mới tab '{title}'...")
        return spreadsheet.add_worksheet(title=title, rows=rows, cols=cols)


def build_maintenance_rows() -> List[List[Any]]:
    """Tạo dữ liệu khởi tạo cho đủ 11 máy thực tế của Nhà máy HV2."""
    today = datetime.now()
    rows: List[List[Any]] = []
    for idx, machine in enumerate(HV2_MACHINES, start=1):
        pm_date = (today + timedelta(days=5 + idx)).strftime("%Y-%m-%d")
        if machine["machine_id"] == "MX-01":
            tooling_status = "Bộ dao xẻ thô & xẻ tinh sẵn sàng (cần theo dõi mòn dao)"
        elif machine["group"] == "Cán nguội":
            tooling_status = "Trục cán đạt chuẩn độ bóng, còn >80% chu kỳ mài"
        elif machine["group"] == "Ủ mềm":
            tooling_status = "Khí bảo vệ & điện trở lò ổn định"
        else:
            tooling_status = "Băng nhám No.4/HL đầy đủ"

        rows.append(
            [
                machine["machine_id"],
                machine["name"],
                machine["group"],
                machine["max_width_mm"] if machine["max_width_mm"] is not None else "N/A",
                "YES (BOTTLENECK)" if machine["is_bottleneck"] else "NO",
                "Available",
                pm_date,
                tooling_status,
                machine["notes"],
            ]
        )
    return rows


def build_sample_inventory_rows() -> List[List[Any]]:
    """
    Nạp sẵn 2 cuộn phôi mẫu trong kho:
    - 1 cuộn khổ 1219mm (> 720mm -> BẮT BUỘC xẻ chia khổ qua MX-01 trước khi cán)
    - 1 cuộn khổ 650mm  (<= 720mm -> vào thẳng 3 máy cán MC-01..03)
    """
    return [
        [
            "COIL-HV2-1219",
            "SUS304",
            2.0,
            1219,
            9.5,
            "No.1",
            "Kho-Phôi-A1",
            "Available",
            "YES (>720mm -> Bắt buộc qua MX-01)",
            "Cuộn phôi khổ lớn 1219mm, BẮT BUỘC xẻ chia khổ <=720mm trên MX-01 trước khi đưa vào MC-01..03",
        ],
        [
            "COIL-HV2-0650",
            "SUS304",
            2.0,
            650,
            3.5,
            "No.1",
            "Kho-Phôi-A2",
            "Available",
            "NO (<=720mm -> Cán thẳng)",
            "Cuộn phôi khổ 650mm (<=720mm), đủ điều kiện đưa thẳng vào máy cán MC-01..03 không cần xẻ thô",
        ],
    ]


def build_sample_order_rows() -> List[List[Any]]:
    """
    Nạp sẵn 1 đơn hàng mẫu yêu cầu 8.0 tấn SUS304 cán nguội 0.8mm, khổ 600mm, mài No.4.
    Do cuộn 650mm chỉ có 3.5 tấn nên hệ thống BẮT BUỘC phải sử dụng cuộn 1219mm (9.5 tấn)
    và tự động kích hoạt quy trình xẻ thô chia khổ <=720mm trên nút thắt cổ chai MX-01.
    """
    due_date = (datetime.now() + timedelta(days=3)).strftime("%Y-%m-%d")
    return [
        [
            "ORD-HV2-001",
            "Công ty Cơ khí Inox Miền Bắc (Mẫu Test 720mm)",
            "SUS304",
            2.0,
            0.8,
            600,
            "No.4",
            8.0,
            due_date,
            "High",
            "New",
            (
                "Đơn hàng mẫu kiểm tra tự động bài toán khổ 720mm: cần 8.0 tấn SUS304 dày 0.8mm, "
                "khổ thành phẩm 600mm, ủ mềm và mài bề mặt No.4. Kho có cuộn 1219mm (9.5T) và 650mm (3.5T)."
            ),
        ]
    ]


def setup_hv2_google_sheet() -> None:
    print("=" * 65)
    print("KHỞI TẠO GOOGLE SHEETS CHO HỆ THỐNG MULTI-AGENT NHÀ MÁY HV2")
    print("=" * 65)

    spreadsheet = get_hv2_spreadsheet()
    print(f"Đã kết nối thành công Google Sheet: {spreadsheet.title}")

    # 1. Tạo & định dạng 5 tab chuẩn
    worksheets = {}
    for key, tab_name in SHEET_TABS.items():
        ws = get_or_create_worksheet(spreadsheet, tab_name)
        headers = TAB_HEADERS[tab_name]
        ws.update("A1", [headers], value_input_option="USER_ENTERED")
        ws.format("A1:L1", {"textFormat": {"bold": True}})
        worksheets[key] = ws

    # 2. Điền sẵn 11 thiết bị vào HV2_Maintenance
    maintenance_rows = build_maintenance_rows()
    worksheets["maintenance"].append_rows(
        maintenance_rows, value_input_option="USER_ENTERED"
    )
    print(
        f"  [OK] Đã nạp đủ {len(maintenance_rows)} máy (MC-01..03, LU-01..04, MX-01, MM-01..03) vào HV2_Maintenance."
    )

    # 3. Điền sẵn 2 cuộn phôi (1219mm & 650mm) vào HV2_Inventory
    inventory_rows = build_sample_inventory_rows()
    worksheets["inventory"].append_rows(
        inventory_rows, value_input_option="USER_ENTERED"
    )
    print("  [OK] Đã nạp 2 cuộn phôi mẫu (1219mm và 650mm) vào HV2_Inventory.")

    # 4. Điền sẵn 1 đơn hàng mẫu vào HV2_Orders
    order_rows = build_sample_order_rows()
    worksheets["orders"].append_rows(order_rows, value_input_option="USER_ENTERED")
    print("  [OK] Đã nạp 1 đơn hàng mẫu (ORD-HV2-001) vào HV2_Orders.")

    print("-" * 65)
    print("HOÀN TẤT! Bạn có thể chạy 'python main.py' để kiểm tra 12 AI Agents ngay.")
    print("=" * 65)


if __name__ == "__main__":
    setup_hv2_google_sheet()
