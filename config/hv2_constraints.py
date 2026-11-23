"""
Ràng buộc năng lực thiết bị thực tế của Nhà máy HV2 (Hardcoded Constraints).
Mọi agent và công cụ trong hệ thống đều tham chiếu trực tiếp từ module này.
"""

from __future__ import annotations

from typing import Any, Dict, List

FACTORY_NAME = "Nhà máy HV2 (Cán nguội - Ủ mềm - Xẻ băng - Mài bề mặt Inox)"

# Giới hạn khổ cuộn tối đa bắt buộc cho 3 máy cán nguội
MAX_ROLLING_WIDTH_MM: int = 720

# Nút thắt cổ chai (Bottleneck) duy nhất của xưởng
BOTTLENECK_MACHINE_ID: str = "MX-01"

# Giới hạn tốc độ gọi Gemini API
DEFAULT_MAX_RPM: int = 15

# Tên 5 tab chuẩn trên Google Sheets
SHEET_TABS: Dict[str, str] = {
    "orders": "HV2_Orders",
    "inventory": "HV2_Inventory",
    "schedule": "HV2_Production_Schedule",
    "maintenance": "HV2_Maintenance",
    "qc_reports": "HV2_QC_Reports",
}

# Danh sách cứng đủ 11 thiết bị thực tế tại Nhà máy HV2
HV2_MACHINES: List[Dict[str, Any]] = [
    # 3 Máy cán nguội (khổ tối đa bắt buộc 720mm)
    {
        "machine_id": "MC-01",
        "name": "Máy cán nguội số 1",
        "group": "Cán nguội",
        "max_width_mm": MAX_ROLLING_WIDTH_MM,
        "is_bottleneck": False,
        "notes": "Khổ cuộn đầu vào tối đa 720mm. Tuyệt đối không đưa cuộn > 720mm vào máy.",
    },
    {
        "machine_id": "MC-02",
        "name": "Máy cán nguội số 2",
        "group": "Cán nguội",
        "max_width_mm": MAX_ROLLING_WIDTH_MM,
        "is_bottleneck": False,
        "notes": "Khổ cuộn đầu vào tối đa 720mm. Tuyệt đối không đưa cuộn > 720mm vào máy.",
    },
    {
        "machine_id": "MC-03",
        "name": "Máy cán nguội số 3",
        "group": "Cán nguội",
        "max_width_mm": MAX_ROLLING_WIDTH_MM,
        "is_bottleneck": False,
        "notes": "Khổ cuộn đầu vào tối đa 720mm. Tuyệt đối không đưa cuộn > 720mm vào máy.",
    },
    # 4 Lò ủ mềm
    {
        "machine_id": "LU-01",
        "name": "Lò ủ mềm số 1",
        "group": "Ủ mềm",
        "max_width_mm": None,
        "is_bottleneck": False,
        "notes": "Ủ mềm khử ứng suất sau cán nguội, kiểm soát khí bảo vệ & nhiệt độ.",
    },
    {
        "machine_id": "LU-02",
        "name": "Lò ủ mềm số 2",
        "group": "Ủ mềm",
        "max_width_mm": None,
        "is_bottleneck": False,
        "notes": "Ủ mềm khử ứng suất sau cán nguội, kiểm soát khí bảo vệ & nhiệt độ.",
    },
    {
        "machine_id": "LU-03",
        "name": "Lò ủ mềm số 3",
        "group": "Ủ mềm",
        "max_width_mm": None,
        "is_bottleneck": False,
        "notes": "Ủ mềm khử ứng suất sau cán nguội, kiểm soát khí bảo vệ & nhiệt độ.",
    },
    {
        "machine_id": "LU-04",
        "name": "Lò ủ mềm số 4",
        "group": "Ủ mềm",
        "max_width_mm": None,
        "is_bottleneck": False,
        "notes": "Ủ mềm khử ứng suất sau cán nguội, kiểm soát khí bảo vệ & nhiệt độ.",
    },
    # 1 Máy xẻ băng (BOTTLENECK)
    {
        "machine_id": "MX-01",
        "name": "Máy xẻ băng số 1 (BOTTLENECK)",
        "group": "Xẻ băng",
        "max_width_mm": 1500,
        "is_bottleneck": True,
        "notes": (
            "NÚT THẮT CỔ CHAI (BOTTLENECK) DUY NHẤT CỦA XƯỞNG. "
            "Bắt buộc xẻ chia khổ cho mọi cuộn phôi có khổ > 720mm trước khi đưa vào MC-01/MC-02/MC-03, "
            "đồng thời đảm nhận xẻ thành phẩm cuối chuyền."
        ),
    },
    # 3 Máy mài bề mặt
    {
        "machine_id": "MM-01",
        "name": "Máy mài bề mặt số 1",
        "group": "Mài bề mặt",
        "max_width_mm": MAX_ROLLING_WIDTH_MM,
        "is_bottleneck": False,
        "notes": "Mài bề mặt inox (No.4 / HL / 2B polish).",
    },
    {
        "machine_id": "MM-02",
        "name": "Máy mài bề mặt số 2",
        "group": "Mài bề mặt",
        "max_width_mm": MAX_ROLLING_WIDTH_MM,
        "is_bottleneck": False,
        "notes": "Mài bề mặt inox (No.4 / HL / 2B polish).",
    },
    {
        "machine_id": "MM-03",
        "name": "Máy mài bề mặt số 3",
        "group": "Mài bề mặt",
        "max_width_mm": MAX_ROLLING_WIDTH_MM,
        "is_bottleneck": False,
        "notes": "Mài bề mặt inox (No.4 / HL / 2B polish).",
    },
]

ROLLING_MACHINES = ["MC-01", "MC-02", "MC-03"]
ANNEALING_FURNACES = ["LU-01", "LU-02", "LU-03", "LU-04"]
SLITTING_MACHINES = ["MX-01"]
GRINDING_MACHINES = ["MM-01", "MM-02", "MM-03"]
ALL_MACHINE_IDS = (
    ROLLING_MACHINES + ANNEALING_FURNACES + SLITTING_MACHINES + GRINDING_MACHINES
)


def requires_pre_slitting(coil_width_mm: float) -> bool:
    """
    Kiểm tra quy tắc bắt buộc của HV2:
    Nếu cuộn phôi có khổ > 720mm thì BẮT BUỘC phải xẻ chia khổ trên MX-01 trước khi cán.
    """
    return float(coil_width_mm) > MAX_ROLLING_WIDTH_MM


def get_constraints_summary() -> str:
    """Trả về bản tóm tắt ràng buộc thiết bị HV2 để nhúng vào prompt/context."""
    return (
        f"RÀNG BUỘC NĂNG LỰC THIẾT BỊ THỰC TẾ {FACTORY_NAME}:\n"
        f"- 3 Máy cán nguội ({', '.join(ROLLING_MACHINES)}): KHỔ CUỘN TỐI ĐA BẮT BUỘC = {MAX_ROLLING_WIDTH_MM}mm.\n"
        f"- 4 Lò ủ mềm ({', '.join(ANNEALING_FURNACES)}): Ủ mềm khử ứng suất sau cán nguội.\n"
        f"- 1 Máy xẻ băng ({BOTTLENECK_MACHINE_ID}): NÚT THẮT CỔ CHAI (BOTTLENECK) DUY NHẤT CỦA XƯỞNG.\n"
        f"  * QUY TẮC BẮT BUỘC: Mọi cuộn phôi trong kho có khổ > {MAX_ROLLING_WIDTH_MM}mm BẮT BUỘC phải "
        f"xếp lịch qua {BOTTLENECK_MACHINE_ID} để xẻ chia khổ (<= {MAX_ROLLING_WIDTH_MM}mm) TRƯỚC KHI đưa vào "
        f"{', '.join(ROLLING_MACHINES)}.\n"
        f"  * CẢNH BÁO XUNG ĐỘT: {BOTTLENECK_MACHINE_ID} vừa phải xẻ thô đầu vào (> {MAX_ROLLING_WIDTH_MM}mm) "
        f"vừa phải xẻ băng thành phẩm nên cực kỳ dễ xung đột lịch; phải kiểm soát thứ tự ưu tiên chặt chẽ.\n"
        f"- 3 Máy mài bề mặt ({', '.join(GRINDING_MACHINES)}): Hoàn thiện bề mặt inox (No.4, HL, bóng).\n"
        f"- Tổng số thiết bị: {len(ALL_MACHINE_IDS)} máy."
    )
