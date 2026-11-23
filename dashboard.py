"""
Web Dashboard Điều hành 12 AI Agents - Nhà máy HV2 (Streamlit).
Cách chạy:
    .\.venv\Scripts\streamlit.exe run dashboard.py
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

import streamlit as st
from dotenv import load_dotenv

from config.hv2_constraints import (
    BOTTLENECK_MACHINE_ID,
    FACTORY_NAME,
    MAX_ROLLING_WIDTH_MM,
    SHEET_TABS,
    requires_pre_slitting,
)
from tools.hv2_sheets import ReadHV2SheetTool, get_hv2_spreadsheet

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = BASE_DIR / "output"
OUTPUT_DIR.mkdir(exist_ok=True)

ANSI_RE = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")


def strip_ansi(text: str) -> str:
    return ANSI_RE.sub("", text)


@st.cache_data(ttl=30, show_spinner=False)
def load_sheet_tab(tab_name: str) -> tuple[List[Dict[str, Any]], str]:
    """Đọc dữ liệu từ 1 tab Google Sheets thông qua ReadHV2SheetTool."""
    tool = ReadHV2SheetTool()
    raw = tool._run(tab_name=tab_name)
    if raw.startswith("Lỗi") or raw.startswith("Tab "):
        return [], raw
    try:
        data = json.loads(raw)
        if isinstance(data, list):
            return data, ""
        return [], str(raw)
    except Exception as exc:
        return [], f"Không thể phân tích JSON từ {tab_name}: {exc}"


def parse_width(val: Any) -> float:
    try:
        return float(str(val).replace(",", ".").strip())
    except Exception:
        return 0.0


def run_crew_streaming(directive: str, log_placeholder: Any, status_placeholder: Any) -> tuple[bool, str, str]:
    """Chạy run_web_job.py và cập nhật log trực tiếp lên giao diện Streamlit."""
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    result_file = OUTPUT_DIR / f"HV2_Draft_{ts}.md"

    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUNBUFFERED"] = "1"

    cmd = [
        sys.executable,
        str(BASE_DIR / "run_web_job.py"),
        "--directive",
        directive,
        "--result-file",
        str(result_file),
    ]

    proc = subprocess.Popen(
        cmd,
        cwd=str(BASE_DIR),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
    )

    lines: List[str] = []
    active_agent = "CEO Nhà máy HV2"
    assert proc.stdout is not None

    for raw_line in proc.stdout:
        clean = strip_ansi(raw_line.rstrip("\r\n"))
        if not clean:
            continue
        lines.append(clean)

        # Phát hiện nhanh Agent đang hoạt động để hiển thị thanh trạng thái
        if "Agent:" in clean:
            active_agent = clean.split("Agent:", 1)[1].strip(" │")
            status_placeholder.info(f"🤖 Đang xử lý: **{active_agent}**")
        elif "Tool:" in clean:
            tool_name = clean.split("Tool:", 1)[1].strip(" │")
            status_placeholder.info(f"🔧 **{active_agent}** đang gọi công cụ `{tool_name}`...")

        # Hiển thị 60 dòng log mới nhất để giao diện luôn mượt
        log_placeholder.code("\n".join(lines[-60:]), language="text")

    return_code = proc.wait()
    full_log = "\n".join(lines)

    if return_code == 0 and result_file.exists():
        plan_text = result_file.read_text(encoding="utf-8")
        return True, plan_text, full_log
    return False, "", full_log


# ==============================================================================
# CẤU HÌNH GIAO DIỆN CHÍNH
# ==============================================================================
st.set_page_config(
    page_title="HV2 Multi-Agent Control Center",
    page_icon="🏭",
    layout="wide",
)

sheet_id = os.getenv("GOOGLE_SHEET_ID", "").strip()
sheet_url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/edit" if sheet_id else ""

# --- SIDEBAR ---
with st.sidebar:
    st.title("🏭 Nhà máy HV2")
    st.caption("Hệ thống Điều hành 12 AI Agents (CrewAI Hierarchical)")

    if st.button("🔄 Làm mới dữ liệu Google Sheets", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

    if sheet_url:
        st.link_button("📊 Mở Google Sheet HV2", sheet_url, use_container_width=True)

    st.divider()
    st.subheader("🔑 Chế độ chạy độc lập")
    creds_file = BASE_DIR / os.getenv("GOOGLE_CREDENTIALS_PATH", "credentials.json")
    if creds_file.exists():
        st.success("✅ Độc lập 100% (`gspread` + `credentials.json`)")
        try:
            sa_info = json.loads(creds_file.read_text(encoding="utf-8"))
            sa_email = sa_info.get("client_email", "")
            if sa_email:
                st.caption("Email Service Account (cần quyền Editor trên Sheet):")
                st.code(sa_email, language="text")
        except Exception:
            pass
        if st.button("🧪 Kiểm tra kết nối gspread độc lập", use_container_width=True):
            try:
                ss = get_hv2_spreadsheet()
                st.success(f"Kết nối thành công tới Sheet: {ss.title}")
            except Exception as exc:
                st.error(f"Lỗi kết nối gspread: {exc}")
    else:
        st.warning("⚠️ Chưa có `credentials.json` để chạy độc lập ngoài Antigravity.")
        uploaded_sa = st.file_uploader(
            "Tải lên file `credentials.json` (Service Account):",
            type=["json"],
            help="Tải từ Google Cloud Console -> IAM & Admin -> Service Accounts -> Keys -> JSON.",
        )
        if uploaded_sa is not None:
            try:
                raw_bytes = uploaded_sa.getvalue()
                parsed = json.loads(raw_bytes.decode("utf-8"))
                if "client_email" not in parsed or "private_key" not in parsed:
                    st.error("File JSON không phải Google Service Account key hợp lệ (thiếu client_email / private_key).")
                else:
                    creds_file.write_bytes(raw_bytes)
                    st.cache_data.clear()
                    st.success(
                        f"Đã lưu `credentials.json`! Hãy share quyền Editor trên Google Sheet cho `{parsed['client_email']}` rồi tải lại trang."
                    )
                    st.rerun()
            except Exception as exc:
                st.error(f"Không thể đọc file JSON: {exc}")

    st.divider()
    st.subheader("⚙️ Ràng buộc cứng HV2")
    st.markdown(
        f"""
- **3 Máy cán nguội** (`MC-01..03`): Khổ tối đa bắt buộc **`{MAX_ROLLING_WIDTH_MM}mm`**
- **4 Lò ủ mềm** (`LU-01..04`)
- **1 Máy xẻ băng** (`{BOTTLENECK_MACHINE_ID}`): **⚠️ NÚT THẮT CỔ CHAI (BOTTLENECK)** — mọi cuộn `> {MAX_ROLLING_WIDTH_MM}mm` bắt buộc xẻ chia khổ trước khi cán
- **3 Máy mài bề mặt** (`MM-01..03`)
- **Rate limit**: `max_rpm={os.getenv('CREW_MAX_RPM', '15')}`
        """
    )

    st.divider()
    st.subheader("👥 Cơ cấu 12 AI Agents")
    st.markdown(
        f"""
**Tầng 1 — Manager (`{os.getenv('CEO_MODEL', 'gemini-3.1-flash-lite')}`):**
1. CEO Nhà máy HV2 *(Điều phối & Trình duyệt)*

**Tầng 2 — 11 Nhân sự số (`{os.getenv('WORKER_MODEL', 'gemini-3.1-flash-lite')}`):**
- **Kế hoạch & Vật tư (2)**: Kế hoạch & Phôi; Vật tư & Kho
- **Sản xuất (5)**: Tổ Cán (3 máy); Tổ Ủ (4 lò); Tổ Xẻ (MX-01); Tổ Mài (3 máy); Tổ Cơ động
- **Bảo trì (2)**: Bảo trì Cơ-Điện (11 máy); Trục cán & Phụ tùng
- **Chất lượng (2)**: IQC/IPQC; OQC
        """
    )

# --- HEADER & KPI ---
st.title("🏭 Trung tâm Điều hành 12 AI Agents — Nhà máy HV2")
st.caption(f"{FACTORY_NAME} | Kết nối trực tiếp Google Sheets & Google Gemini API")

orders_data, orders_err = load_sheet_tab(SHEET_TABS["orders"])
inv_data, inv_err = load_sheet_tab(SHEET_TABS["inventory"])
sched_data, sched_err = load_sheet_tab(SHEET_TABS["schedule"])
maint_data, maint_err = load_sheet_tab(SHEET_TABS["maintenance"])
qc_data, qc_err = load_sheet_tab(SHEET_TABS["qc_reports"])

wide_coils = [c for c in inv_data if requires_pre_slitting(parse_width(c.get("Width_mm", 0)))]
avail_machines = [
    m for m in maint_data if str(m.get("Operational_Status", "")).strip().lower() == "available"
]

c1, c2, c3, c4 = st.columns(4)
c1.metric("📦 Đơn hàng (HV2_Orders)", len(orders_data))
c2.metric(
    "🌀 Cuộn phôi trong kho",
    len(inv_data),
    delta=f"{len(wide_coils)} cuộn >720mm cần qua MX-01" if wide_coils else "Tất cả <=720mm",
    delta_color="inverse" if wide_coils else "normal",
)
c3.metric("🛠️ Thiết bị sẵn sàng", f"{len(avail_machines)} / {len(maint_data) or 11}")
c4.metric("📅 Lệnh SX đã xếp", len(sched_data))

# --- MAIN TABS ---
tab_run, tab_sheets, tab_history = st.tabs(
    [
        "🚀 Giao việc & Theo dõi 12 AI Agents",
        "📊 Dữ liệu 5 Tab Google Sheets",
        "📁 Lịch sử Kế hoạch đã duyệt",
    ]
)

# ==============================================================================
# TAB 1: GIAO VIỆC & THEO DÕI TRỰC TIẾP
# ==============================================================================
with tab_run:
    st.subheader("1️⃣ Nhập chỉ thị giao việc cho CEO Nhà máy HV2")
    st.caption(
        "Hệ thống sẽ tự động đọc toàn bộ đơn hàng mới ở tab HV2_Orders, phôi ở HV2_Inventory và tình trạng 11 máy ở HV2_Maintenance. "
        "Bạn có thể ghi thêm yêu cầu ưu tiên bên dưới (hoặc để mặc định)."
    )

    if "directive_input" not in st.session_state:
        st.session_state.directive_input = (
            "Lập kế hoạch sản xuất cho tất cả đơn hàng mới trên HV2_Orders. "
            "Kiểm tra nghiêm ngặt quy tắc khổ tối đa 720mm cho MC-01..03, ưu tiên giải tỏa nút thắt cổ chai MX-01 "
            "và đồng bộ lịch dự kiến lên HV2_Production_Schedule cùng phiếu kiểm tra lên HV2_QC_Reports."
        )

    directive = st.text_area(
        "Chỉ thị từ Ban Lãnh đạo:",
        key="directive_input",
        height=100,
    )

    col_btn1, col_btn2 = st.columns([1, 3])
    with col_btn1:
        start_clicked = st.button("🚀 Khởi chạy 12 AI Agents", type="primary", use_container_width=True)

    if start_clicked:
        status_box = st.empty()
        status_box.info("⏳ Đang khởi động CEO Nhà máy HV2 và 11 Nhân sự số...")
        st.markdown("#### 📡 Nhật ký hoạt động trực tiếp (Live Agent Stream)")
        log_box = st.empty()

        ok, plan_text, full_log = run_crew_streaming(directive, log_box, status_box)
        st.session_state.last_log = full_log
        if ok:
            status_box.success("✅ CEO Nhà máy HV2 đã hoàn tất tổng hợp kế hoạch và đang chờ bạn phê duyệt!")
            st.session_state.latest_plan = plan_text
            st.cache_data.clear()
        else:
            status_box.error(
                "❌ Phiên chạy gặp gián đoạn (có thể do Gemini API tạm quá tải 503). "
                "Hãy xem log chi tiết bên trên và bấm chạy lại."
            )

    # Hiển thị bản kế hoạch chờ phê duyệt (Human-in-the-Loop)
    if st.session_state.get("latest_plan"):
        st.divider()
        st.subheader("2️⃣ Bản Kế hoạch Tổng thể — CEO Nhà máy HV2 Trình duyệt")
        st.markdown(st.session_state.latest_plan)

        st.divider()
        st.subheader("3️⃣ Phê duyệt của Ban Lãnh đạo (Human-in-the-Loop)")
        feedback = st.text_input(
            "Góp ý điều chỉnh (nếu muốn CEO sửa lại kế hoạch):",
            placeholder="Ví dụ: Đổi cuộn 650mm sang máy MC-03, giữ MC-01 dự phòng...",
        )

        ap_col1, ap_col2 = st.columns(2)
        with ap_col1:
            if st.button("✅ Phê duyệt & Lưu bản chính thức", type="primary", use_container_width=True):
                final_path = OUTPUT_DIR / f"HV2_Approved_Plan_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
                final_path.write_text(st.session_state.latest_plan, encoding="utf-8")
                st.success(f"🎉 Đã phê duyệt và lưu báo cáo chính thức tại: `{final_path.name}`")
        with ap_col2:
            if st.button("🔄 Yêu cầu CEO điều chỉnh theo góp ý", use_container_width=True):
                if not feedback.strip():
                    st.warning("Vui lòng nhập nội dung góp ý điều chỉnh ở ô phía trên trước.")
                else:
                    st.session_state.directive_input = (
                        f"{directive}\n\nYÊU CẦU ĐIỀU CHỈNH TỪ BAN LÃNH ĐẠO: {feedback.strip()}"
                    )
                    st.info("Đã nạp yêu cầu điều chỉnh vào ô chỉ thị phía trên — bấm '🚀 Khởi chạy 12 AI Agents' để CEO lập lại!")

# ==============================================================================
# TAB 2: XEM TRỰC TIẾP 5 TAB GOOGLE SHEETS
# ==============================================================================
with tab_sheets:
    st.subheader("📊 Dữ liệu trực tiếp từ Google Sheet Nhà máy HV2")
    sub1, sub2, sub3, sub4, sub5 = st.tabs(
        [
            f"HV2_Orders ({len(orders_data)})",
            f"HV2_Inventory ({len(inv_data)})",
            f"HV2_Production_Schedule ({len(sched_data)})",
            f"HV2_Maintenance ({len(maint_data)})",
            f"HV2_QC_Reports ({len(qc_data)})",
        ]
    )

    with sub1:
        if orders_data:
            st.dataframe(orders_data, use_container_width=True)
        else:
            st.info(orders_err or "Chưa có dữ liệu đơn hàng.")

    with sub2:
        if wide_coils:
            st.warning(
                f"⚠️ Phát hiện **{len(wide_coils)} cuộn phôi có khổ > {MAX_ROLLING_WIDTH_MM}mm** — "
                f"Hệ thống BẮT BUỘC xếp lịch xẻ chia khổ qua nút thắt cổ chai **{BOTTLENECK_MACHINE_ID}** trước khi đưa vào `MC-01..03`."
            )
        if inv_data:
            st.dataframe(inv_data, use_container_width=True)
        else:
            st.info(inv_err or "Chưa có dữ liệu tồn kho.")

    with sub3:
        if sched_data:
            st.dataframe(sched_data, use_container_width=True)
        else:
            st.info(sched_err or "Chưa có lịch sản xuất nào.")

    with sub4:
        if maint_data:
            st.dataframe(maint_data, use_container_width=True)
        else:
            st.info(maint_err or "Chưa có dữ liệu thiết bị.")

    with sub5:
        if qc_data:
            st.dataframe(qc_data, use_container_width=True)
        else:
            st.info(qc_err or "Chưa có báo cáo QC.")

# ==============================================================================
# TAB 3: LỊCH SỬ BÁO CÁO ĐÃ LƯU
# ==============================================================================
with tab_history:
    st.subheader("📁 Các bản kế hoạch đã lưu trong thư mục `output/`")
    files = sorted(OUTPUT_DIR.glob("*.md"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not files:
        st.info("Chưa có file báo cáo nào được lưu. Hãy chạy 12 AI Agents ở tab đầu tiên!")
    else:
        selected = st.selectbox("Chọn báo cáo để xem:", files, format_func=lambda p: p.name)
        if selected:
            content = selected.read_text(encoding="utf-8")
            st.download_button(
                "⬇️ Tải file Markdown",
                data=content,
                file_name=selected.name,
                mime="text/markdown",
            )
            st.markdown(content)
