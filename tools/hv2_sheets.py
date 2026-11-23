"""
Công cụ Google Sheets (gspread) tích hợp CrewAI cho Nhà máy HV2.
Đọc GOOGLE_SHEET_ID từ .env và xác thực qua credentials.json (Service Account).
Tích hợp sẵn bộ kiểm tra ràng buộc cứng: khổ cuộn > 720mm cấm đưa thẳng vào MC-01..03.
"""

from __future__ import annotations

import base64
import json
import os
import shutil
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any, List, Optional, Type

import gspread
import httpx
from crewai.tools import BaseTool
from dotenv import load_dotenv
from google.auth.transport import Request as GoogleAuthRequest
from google.auth.transport import Response as GoogleAuthResponse
from google.oauth2.service_account import Credentials
from pydantic import BaseModel, Field

from config.hv2_constraints import (
    ALL_MACHINE_IDS,
    BOTTLENECK_MACHINE_ID,
    MAX_ROLLING_WIDTH_MM,
    ROLLING_MACHINES,
    SHEET_TABS,
    requires_pre_slitting,
)

load_dotenv()

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]


def _get_sheet_id() -> str:
    sheet_id = os.getenv("GOOGLE_SHEET_ID", "").strip()
    if not sheet_id or sheet_id == "your_google_sheet_id_here":
        raise ValueError(
            "Thiếu GOOGLE_SHEET_ID trong file .env. "
            "Hãy điền ID Google Sheet của bạn vào .env trước khi chạy."
        )
    return sheet_id


def _load_service_account_credentials() -> Optional[Credentials]:
    """
    Hỗ trợ 3 nguồn xác thực chuẩn cho cả Local & Cloud 24/7:
    1. File credentials.json trên ổ đĩa (Local / VPS / Docker volume).
    2. Biến môi trường GOOGLE_CREDENTIALS_JSON (chuỗi JSON hoặc Base64 — Cloud Run / Render / GitHub Actions).
    3. Streamlit Secrets (st.secrets["gcp_service_account"] — Streamlit Community Cloud).
    """
    creds_path = Path(os.getenv("GOOGLE_CREDENTIALS_PATH", "credentials.json"))
    if not creds_path.is_absolute():
        project_root = Path(__file__).resolve().parent.parent
        creds_path = project_root / creds_path
    if creds_path.exists():
        return Credentials.from_service_account_file(str(creds_path), scopes=SCOPES)

    raw_env = os.getenv("GOOGLE_CREDENTIALS_JSON", "").strip()
    if raw_env:
        try:
            info = json.loads(raw_env)
        except json.JSONDecodeError:
            decoded = base64.b64decode(raw_env).decode("utf-8")
            info = json.loads(decoded)
        return Credentials.from_service_account_info(info, scopes=SCOPES)

    try:
        import streamlit as st

        if "gcp_service_account" in st.secrets:
            info = dict(st.secrets["gcp_service_account"])
            return Credentials.from_service_account_info(info, scopes=SCOPES)
    except Exception:
        pass

    return None


def _has_service_account_file() -> bool:
    return _load_service_account_credentials() is not None


def _gsheets_cli_read(tab_name: str) -> List[dict]:
    """Đọc dữ liệu qua gsheets CLI khi chưa có credentials.json."""
    sheet_id = _get_sheet_id()
    gsheets_bin = shutil.which("gsheets")
    if not gsheets_bin:
        raise FileNotFoundError("Không tìm thấy lệnh gsheets trên PATH.")
    proc = subprocess.run(
        [gsheets_bin, "readonly", "read", sheet_id, f"{tab_name}!A1:Z200", "--json"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
    )
    rows = json.loads(proc.stdout) if proc.stdout.strip() else []
    if not rows or len(rows) < 2:
        return []
    headers = rows[0]
    records = []
    for row in rows[1:]:
        padded = list(row) + [""] * max(0, len(headers) - len(row))
        records.append(dict(zip(headers, padded)))
    return records


def _gsheets_cli_append(tab_name: str, row: List[Any]) -> None:
    """Ghi nối tiếp 1 dòng qua gsheets CLI khi chưa có credentials.json."""
    sheet_id = _get_sheet_id()
    gsheets_bin = shutil.which("gsheets")
    if not gsheets_bin:
        raise FileNotFoundError("Không tìm thấy lệnh gsheets trên PATH.")
    escaped = [str(cell).replace("\\", "\\\\").replace(",", "\\,").replace("|", "/") for cell in row]
    payload = ",".join(escaped)
    subprocess.run(
        [gsheets_bin, "mutate", "append", sheet_id, f"{tab_name}!A1", payload],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
    )


class _HttpxAuthResponse(GoogleAuthResponse):
    def __init__(self, resp: httpx.Response) -> None:
        self._resp = resp

    @property
    def status(self) -> int:
        return self._resp.status_code

    @property
    def headers(self) -> Any:
        return self._resp.headers

    @property
    def data(self) -> bytes:
        return self._resp.content


class _HttpxAuthRequest(GoogleAuthRequest):
    def __call__(
        self,
        url: str,
        method: str = "GET",
        body: Any = None,
        headers: Any = None,
        timeout: Optional[float] = None,
        **kwargs: Any,
    ) -> _HttpxAuthResponse:
        resp = httpx.request(
            method,
            url,
            content=body,
            headers=headers,
            timeout=timeout or 30.0,
        )
        return _HttpxAuthResponse(resp)


class _HttpxGspreadResponse:
    """Adapter nhẹ biến httpx.Response thành đối tượng tương thích gspread/requests."""

    def __init__(self, resp: httpx.Response) -> None:
        self._resp = resp
        self.status_code = resp.status_code
        self.headers = resp.headers
        self.content = resp.content
        self.text = resp.text
        self.ok = 200 <= resp.status_code < 400
        self.url = str(resp.url)
        self.reason = resp.reason_phrase

    def json(self) -> Any:
        return self._resp.json()

    def raise_for_status(self) -> None:
        self._resp.raise_for_status()


class _HttpxGspreadSession:
    """Session dùng httpx thay urllib3 để tránh lỗi SSLEOFError trên Windows khi gọi Google API."""

    def __init__(self, credentials: Credentials) -> None:
        self.credentials = credentials
        self._client = httpx.Client(timeout=30.0)
        self._auth_request = _HttpxAuthRequest()

    def request(
        self,
        method: str,
        url: str,
        params: Any = None,
        data: Any = None,
        json: Any = None,
        headers: Any = None,
        timeout: Optional[float] = None,
        **kwargs: Any,
    ) -> _HttpxGspreadResponse:
        if not self.credentials.valid or self.credentials.expired or not self.credentials.token:
            self.credentials.refresh(self._auth_request)
        req_headers = dict(headers or {})
        req_headers["Authorization"] = f"Bearer {self.credentials.token}"
        clean_params = (
            {k: v for k, v in params.items() if v is not None}
            if isinstance(params, dict)
            else params
        )
        resp = self._client.request(
            method=method.upper(),
            url=url,
            params=clean_params,
            content=data if isinstance(data, (bytes, str)) else None,
            data=data if isinstance(data, dict) else None,
            json=json,
            headers=req_headers,
            timeout=timeout or 30.0,
        )
        return _HttpxGspreadResponse(resp)


def get_hv2_spreadsheet() -> gspread.Spreadsheet:
    """Kết nối độc lập tới Google Sheet của Nhà máy HV2 (hỗ trợ cả Local credentials.json và Cloud Secrets)."""
    sheet_id = _get_sheet_id()
    credentials = _load_service_account_credentials()
    if credentials is None:
        raise FileNotFoundError(
            "Không tìm thấy thông tin xác thực Google Service Account "
            "(credentials.json, biến môi trường GOOGLE_CREDENTIALS_JSON, hoặc Streamlit Secrets)."
        )

    session = _HttpxGspreadSession(credentials)
    client = gspread.Client(auth=credentials, session=session)
    return client.open_by_key(sheet_id)


# ==============================================================================
# 1. Tool đọc dữ liệu từ 5 tab HV2 trên Google Sheets
# ==============================================================================


class ReadHV2SheetInput(BaseModel):
    tab_name: str = Field(
        ...,
        description=(
            "Tên tab cần đọc. Phải là một trong 5 tab: "
            "HV2_Orders, HV2_Inventory, HV2_Production_Schedule, "
            "HV2_Maintenance, HV2_QC_Reports."
        ),
    )


class ReadHV2SheetTool(BaseTool):
    name: str = "read_hv2_sheet"
    description: str = (
        "Đọc toàn bộ dữ liệu từ một trong 5 tab Google Sheets của Nhà máy HV2: "
        "HV2_Orders, HV2_Inventory, HV2_Production_Schedule, HV2_Maintenance, HV2_QC_Reports."
    )
    args_schema: Type[BaseModel] = ReadHV2SheetInput

    def _run(self, tab_name: str) -> str:
        valid_tabs = list(SHEET_TABS.values())
        if tab_name not in valid_tabs:
            return (
                f"Lỗi: Tab '{tab_name}' không hợp lệ. "
                f"Chỉ chấp nhận một trong các tab: {', '.join(valid_tabs)}."
            )
        try:
            if _has_service_account_file():
                spreadsheet = get_hv2_spreadsheet()
                worksheet = spreadsheet.worksheet(tab_name)
                records = worksheet.get_all_records()
            elif shutil.which("gsheets"):
                records = _gsheets_cli_read(tab_name)
            else:
                get_hv2_spreadsheet()  # Raise clear FileNotFoundError
                records = []
            if not records:
                return f"Tab {tab_name} hiện đang trống (chưa có dòng dữ liệu nào)."
            return json.dumps(records, ensure_ascii=False, indent=2)
        except Exception as exc:
            return f"Lỗi khi đọc tab {tab_name}: {exc}"


# ==============================================================================
# 2. Tool ghi lịch sản xuất vào tab HV2_Production_Schedule (có kiểm tra 720mm)
# ==============================================================================


class AppendHV2ScheduleInput(BaseModel):
    schedule_id: str = Field(..., description="Mã lệnh sản xuất, ví dụ: SCH-001")
    order_id: str = Field(..., description="Mã đơn hàng, ví dụ: ORD-HV2-001")
    coil_id: str = Field(..., description="Mã cuộn phôi hoặc băng sau xẻ, ví dụ: COIL-HV2-1219")
    stage: str = Field(
        ...,
        description="Công đoạn: Xẻ thô chia khổ / Cán nguội / Ủ mềm / Mài bề mặt / Xẻ thành phẩm / Đóng gói",
    )
    machine_id: str = Field(
        ...,
        description="Mã máy trong 11 máy HV2 (MC-01..03, LU-01..04, MX-01, MM-01..03)",
    )
    input_width_mm: float = Field(..., description="Khổ cuộn đầu vào của công đoạn này (mm)")
    output_width_mm: float = Field(..., description="Khổ cuộn/băng đầu ra của công đoạn này (mm)")
    start_time: str = Field(..., description="Thời gian bắt đầu dự kiến (YYYY-MM-DD HH:MM)")
    end_time: str = Field(..., description="Thời gian kết thúc dự kiến (YYYY-MM-DD HH:MM)")
    status: str = Field(default="Pending Approval", description="Trạng thái lịch (mặc định: Pending Approval)")
    notes: str = Field(default="", description="Ghi chú kỹ thuật / cảnh báo nút thắt cổ chai MX-01")


class AppendHV2ScheduleTool(BaseTool):
    name: str = "append_hv2_schedule"
    description: str = (
        "Thêm một dòng lịch sản xuất vào tab HV2_Production_Schedule. "
        "Tự động chặn lỗi nếu xếp cuộn có input_width_mm > 720mm vào 3 máy cán MC-01, MC-02, MC-03."
    )
    args_schema: Type[BaseModel] = AppendHV2ScheduleInput

    def _run(
        self,
        schedule_id: str,
        order_id: str,
        coil_id: str,
        stage: str,
        machine_id: str,
        input_width_mm: float,
        output_width_mm: float,
        start_time: str,
        end_time: str,
        status: str = "Pending Approval",
        notes: str = "",
    ) -> str:
        machine_code = machine_id.strip().upper()

        # Kiểm tra mã máy thuộc đúng 11 máy HV2 (cho phép 'PACKING' riêng cho công đoạn đóng gói)
        if machine_code not in ALL_MACHINE_IDS and machine_code != "PACKING":
            return (
                f"TỪ CHỐI GHI LỊCH: Mã thiết bị '{machine_code}' không nằm trong danh sách 11 máy HV2 "
                f"({', '.join(ALL_MACHINE_IDS)})."
            )

        # RÀNG BUỘC CỨNG: Cấm tuyệt đối đưa cuộn > 720mm vào 3 máy cán MC-01..03
        if machine_code in ROLLING_MACHINES and requires_pre_slitting(input_width_mm):
            return (
                f"VI PHẠM RÀNG BUỘC CỨNG HV2: Không thể xếp cuộn '{coil_id}' khổ {input_width_mm}mm "
                f"vào máy cán {machine_code} (khổ tối đa bắt buộc = {MAX_ROLLING_WIDTH_MM}mm). "
                f"BẮT BUỘC phải xếp lịch xẻ chia khổ (<= {MAX_ROLLING_WIDTH_MM}mm) trên máy xẻ "
                f"{BOTTLENECK_MACHINE_ID} trước!"
            )

        try:
            row: List[Any] = [
                schedule_id,
                order_id,
                coil_id,
                stage,
                machine_code,
                input_width_mm,
                output_width_mm,
                start_time,
                end_time,
                status,
                notes,
            ]
            if _has_service_account_file():
                spreadsheet = get_hv2_spreadsheet()
                worksheet = spreadsheet.worksheet(SHEET_TABS["schedule"])
                worksheet.append_row(row, value_input_option="USER_ENTERED")
            elif shutil.which("gsheets"):
                _gsheets_cli_append(SHEET_TABS["schedule"], row)
            else:
                get_hv2_spreadsheet()
            return f"Đã ghi lịch {schedule_id} ({stage} - {machine_code}) vào tab HV2_Production_Schedule thành công."
        except Exception as exc:
            return f"Lỗi khi ghi vào HV2_Production_Schedule: {exc}"


# ==============================================================================
# 3. Tool ghi hạng mục kiểm tra chất lượng vào tab HV2_QC_Reports
# ==============================================================================


class AppendHV2QCReportInput(BaseModel):
    report_id: str = Field(..., description="Mã phiếu QC, ví dụ: QC-001")
    order_id: str = Field(..., description="Mã đơn hàng liên quan")
    coil_id: str = Field(..., description="Mã cuộn kiểm tra")
    qc_type: str = Field(..., description="Loại QC: IQC / IPQC / OQC")
    stage_or_machine: str = Field(..., description="Công đoạn hoặc mã máy kiểm tra (VD: MX-01, MC-01)")
    inspection_criteria: str = Field(..., description="Tiêu chí kiểm tra (độ dày, khổ, bavia, độ cứng, độ nhám)")
    result: str = Field(default="Planned", description="Kết quả: Planned / Pass / Fail / Hold")
    action_notes: str = Field(default="", description="Biện pháp phòng ngừa / xử lý lỗi nếu có")


class AppendHV2QCReportTool(BaseTool):
    name: str = "append_hv2_qc_report"
    description: str = (
        "Ghi một dòng kế hoạch hoặc báo cáo kiểm tra chất lượng (IQC/IPQC/OQC) "
        "vào tab HV2_QC_Reports trên Google Sheets."
    )
    args_schema: Type[BaseModel] = AppendHV2QCReportInput

    def _run(
        self,
        report_id: str,
        order_id: str,
        coil_id: str,
        qc_type: str,
        stage_or_machine: str,
        inspection_criteria: str,
        result: str = "Planned",
        action_notes: str = "",
    ) -> str:
        try:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
            row = [
                report_id,
                timestamp,
                order_id,
                coil_id,
                qc_type,
                stage_or_machine,
                inspection_criteria,
                result,
                action_notes,
            ]
            if _has_service_account_file():
                spreadsheet = get_hv2_spreadsheet()
                worksheet = spreadsheet.worksheet(SHEET_TABS["qc_reports"])
                worksheet.append_row(row, value_input_option="USER_ENTERED")
            elif shutil.which("gsheets"):
                _gsheets_cli_append(SHEET_TABS["qc_reports"], row)
            else:
                get_hv2_spreadsheet()
            return f"Đã ghi phiếu {report_id} ({qc_type}) vào tab HV2_QC_Reports thành công."
        except Exception as exc:
            return f"Lỗi khi ghi vào HV2_QC_Reports: {exc}"


# ==============================================================================
# 4. Tool kiểm tra nhanh quy tắc khổ 720mm và gợi ý chia băng trên MX-01
# ==============================================================================


class CheckCoilWidthRuleInput(BaseModel):
    coil_id: str = Field(..., description="Mã cuộn phôi cần kiểm tra")
    coil_width_mm: float = Field(..., description="Khổ hiện tại của cuộn phôi (mm)")
    target_order_width_mm: Optional[float] = Field(
        default=None,
        description="Khổ thành phẩm mong muốn của đơn hàng (mm), tùy chọn",
    )


class CheckCoilWidthRuleTool(BaseTool):
    name: str = "check_coil_width_rule"
    description: str = (
        "Kiểm tra quy tắc khổ tối đa 720mm của 3 máy cán MC-01..03 và tính toán "
        "xem cuộn phôi có BẮT BUỘC phải xẻ chia khổ qua nút thắt cổ chai MX-01 hay không."
    )
    args_schema: Type[BaseModel] = CheckCoilWidthRuleInput

    def _run(
        self,
        coil_id: str,
        coil_width_mm: float,
        target_order_width_mm: Optional[float] = None,
    ) -> str:
        need_slit = requires_pre_slitting(coil_width_mm)
        if not need_slit:
            return json.dumps(
                {
                    "coil_id": coil_id,
                    "coil_width_mm": coil_width_mm,
                    "max_rolling_width_mm": MAX_ROLLING_WIDTH_MM,
                    "requires_pre_slitting_on_MX01": False,
                    "routing_decision": (
                        f"ĐẠT CHUẨN CÁN THẲNG: Khổ {coil_width_mm}mm <= {MAX_ROLLING_WIDTH_MM}mm. "
                        "Có thể cấp trực tiếp vào MC-01, MC-02 hoặc MC-03 mà KHÔNG cần chiếm lịch MX-01."
                    ),
                },
                ensure_ascii=False,
                indent=2,
            )

        # Tính toán phương án chia băng gợi ý <= 720mm (tính thêm ~10-15mm cắt biên)
        edge_trim_mm = 10.0
        usable_width = max(coil_width_mm - edge_trim_mm, 0)
        if target_order_width_mm and 0 < target_order_width_mm <= MAX_ROLLING_WIDTH_MM:
            num_strips = int(usable_width // target_order_width_mm)
            strip_width = target_order_width_mm
            scrap_mm = round(coil_width_mm - (num_strips * strip_width), 2)
        else:
            num_strips = 2
            while usable_width / num_strips > MAX_ROLLING_WIDTH_MM:
                num_strips += 1
            strip_width = round(usable_width / num_strips, 1)
            scrap_mm = round(coil_width_mm - (num_strips * strip_width), 2)

        return json.dumps(
            {
                "coil_id": coil_id,
                "coil_width_mm": coil_width_mm,
                "max_rolling_width_mm": MAX_ROLLING_WIDTH_MM,
                "requires_pre_slitting_on_MX01": True,
                "bottleneck_machine": BOTTLENECK_MACHINE_ID,
                "suggested_split": {
                    "num_strips": num_strips,
                    "each_strip_width_mm": strip_width,
                    "estimated_edge_trim_scrap_mm": scrap_mm,
                },
                "routing_decision": (
                    f"BẮT BUỘC XẺ THÔ QUA {BOTTLENECK_MACHINE_ID}: Khổ {coil_width_mm}mm > {MAX_ROLLING_WIDTH_MM}mm. "
                    f"Phải xếp lịch chia khổ thành {num_strips} băng x {strip_width}mm (hao hụt biên ~{scrap_mm}mm) "
                    f"trên {BOTTLENECK_MACHINE_ID} TRƯỚC KHI đưa vào MC-01/MC-02/MC-03."
                ),
            },
            ensure_ascii=False,
            indent=2,
        )
