"""
Hệ thống 12 AI Agents Nhà máy HV2 theo mô hình 2 tầng (Process.hierarchical).
- Tầng 1 (Manager): CEO Nhà máy HV2 (gemini/gemini-2.5-pro)
- Tầng 2 (11 Nhân sự số thực thi): gemini/gemini-2.5-flash
- Giới hạn tốc độ API: max_rpm=15
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict

import yaml
from crewai import Agent, Crew, LLM, Process, Task
from dotenv import load_dotenv

from config.hv2_constraints import (
    DEFAULT_MAX_RPM,
    get_constraints_summary,
)
from tools.hv2_sheets import (
    AppendHV2QCReportTool,
    AppendHV2ScheduleTool,
    CheckCoilWidthRuleTool,
    ReadHV2SheetTool,
)

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent
CONFIG_DIR = BASE_DIR / "config"


def _load_yaml(filename: str) -> Dict[str, Any]:
    path = CONFIG_DIR / filename
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def _build_llms() -> tuple[LLM, LLM]:
    """Khởi tạo 2 model Gemini riêng biệt cho CEO (Pro) và 11 Nhân sự số (Flash)."""
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key or api_key == "your_gemini_api_key_here":
        raise ValueError(
            "Thiếu GEMINI_API_KEY trong file .env. "
            "Hãy điền khóa API Google Gemini trước khi chạy."
        )

    ceo_model = os.getenv("CEO_MODEL", "gemini/gemini-2.5-pro")
    worker_model = os.getenv("WORKER_MODEL", "gemini/gemini-2.5-flash")

    ceo_llm = LLM(
        model=ceo_model,
        api_key=api_key,
        temperature=0.2,
        max_retries=5,
    )
    worker_llm = LLM(
        model=worker_model,
        api_key=api_key,
        temperature=0.2,
        max_retries=5,
    )
    return ceo_llm, worker_llm


def build_hv2_crew(
    ceo_directive: str = "",
    enable_terminal_human_input: bool = True,
) -> Crew:
    """
    Khởi tạo đầy đủ 12 AI Agents (1 CEO + 11 Nhân sự số) và Crew
    vận hành theo Process.hierarchical với max_rpm=15.

    Args:
        ceo_directive: Chỉ thị giao việc bổ sung từ Ban Lãnh đạo (Web Dashboard hoặc CLI).
        enable_terminal_human_input: True khi chạy CLI (dừng chờ Enter ở terminal);
            False khi chạy Web Dashboard (Web UI sẽ hiển thị nút Phê duyệt / Yêu cầu sửa).
    """
    agents_cfg = _load_yaml("agents.yaml")
    tasks_cfg = _load_yaml("tasks.yaml")
    ceo_llm, worker_llm = _build_llms()
    max_rpm = int(os.getenv("CREW_MAX_RPM", str(DEFAULT_MAX_RPM)))

    # Khởi tạo các công cụ Google Sheets & Kiểm tra quy tắc 720mm
    read_sheet_tool = ReadHV2SheetTool()
    append_schedule_tool = AppendHV2ScheduleTool()
    append_qc_tool = AppendHV2QCReportTool()
    check_width_tool = CheckCoilWidthRuleTool()

    constraints_text = get_constraints_summary()

    def make_worker(key: str, tools: list) -> Agent:
        cfg = agents_cfg[key]
        return Agent(
            role=cfg["role"],
            goal=cfg["goal"],
            backstory=f"{cfg['backstory']}\n\n{constraints_text}",
            llm=worker_llm,
            tools=tools,
            allow_delegation=False,
            verbose=True,
            max_rpm=max_rpm,
        )

    # ==========================================================================
    # TẦNG 1: MANAGER AGENT - CEO NHÀ MÁY HV2 (gemini/gemini-2.5-pro)
    # Lưu ý CrewAI Process.hierarchical: manager_agent không gắn tools trực tiếp
    # mà điều phối & ủy quyền việc đọc/ghi Google Sheets cho 11 nhân sự bên dưới.
    # ==========================================================================
    ceo_cfg = agents_cfg["ceo_hv2"]
    ceo_agent = Agent(
        role=ceo_cfg["role"],
        goal=ceo_cfg["goal"],
        backstory=f"{ceo_cfg['backstory']}\n\n{constraints_text}",
        llm=ceo_llm,
        tools=[],
        allow_delegation=True,
        verbose=True,
        max_rpm=max_rpm,
    )

    # ==========================================================================
    # TẦNG 2: 11 NHÂN SỰ SỐ THỰC THI (gemini/gemini-2.5-flash)
    # ==========================================================================

    # 1. Khối Kế hoạch SX & Vật tư (2 agents)
    production_planner = make_worker(
        "production_planner",
        tools=[read_sheet_tool, check_width_tool, append_schedule_tool],
    )
    inventory_controller = make_worker(
        "inventory_controller",
        tools=[read_sheet_tool, check_width_tool],
    )

    # 2. Khối Sản xuất (5 agents)
    rolling_leader = make_worker(
        "rolling_leader",
        tools=[read_sheet_tool, check_width_tool, append_schedule_tool],
    )
    annealing_leader = make_worker(
        "annealing_leader",
        tools=[read_sheet_tool, append_schedule_tool],
    )
    slitting_leader = make_worker(
        "slitting_leader",
        tools=[read_sheet_tool, check_width_tool, append_schedule_tool],
    )
    grinding_leader = make_worker(
        "grinding_leader",
        tools=[read_sheet_tool, append_schedule_tool],
    )
    logistics_packaging_leader = make_worker(
        "logistics_packaging_leader",
        tools=[read_sheet_tool, append_schedule_tool],
    )

    # 3. Khối Kỹ thuật Bảo trì (2 agents)
    maintenance_engineer = make_worker(
        "maintenance_engineer",
        tools=[read_sheet_tool],
    )
    rolls_tooling_engineer = make_worker(
        "rolls_tooling_engineer",
        tools=[read_sheet_tool],
    )

    # 4. Khối Quản lý Chất lượng (2 agents)
    iqc_ipqc_engineer = make_worker(
        "iqc_ipqc_engineer",
        tools=[read_sheet_tool, check_width_tool, append_qc_tool],
    )
    oqc_engineer = make_worker(
        "oqc_engineer",
        tools=[read_sheet_tool, append_qc_tool],
    )

    worker_agents = [
        production_planner,
        inventory_controller,
        rolling_leader,
        annealing_leader,
        slitting_leader,
        grinding_leader,
        logistics_packaging_leader,
        maintenance_engineer,
        rolls_tooling_engineer,
        iqc_ipqc_engineer,
        oqc_engineer,
    ]

    directive_block = (
        f"\n\nCHỈ THỊ GIAO VIỆC TRỰC TIẾP TỪ BAN LÃNH ĐẠO:\n{ceo_directive.strip()}\n"
        if ceo_directive and ceo_directive.strip()
        else ""
    )

    # ==========================================================================
    # DANH SÁCH NHIỆM VỤ (TASKS)
    # ==========================================================================
    task_1_cfg = tasks_cfg["analyze_orders_and_inventory_task"]
    analyze_task = Task(
        description=f"{task_1_cfg['description']}{directive_block}\n\n{constraints_text}",
        expected_output=task_1_cfg["expected_output"],
    )

    task_2_cfg = tasks_cfg["build_department_schedules_task"]
    schedule_task = Task(
        description=f"{task_2_cfg['description']}{directive_block}\n\n{constraints_text}",
        expected_output=task_2_cfg["expected_output"],
        context=[analyze_task],
    )

    # Nhiệm vụ cuối cùng: CEO tổng hợp, đồng bộ lịch/QC qua nhân sự và DỪNG CHỜ DUYỆT (human_input=True)
    task_3_cfg = tasks_cfg["ceo_review_and_approval_task"]
    ceo_approval_task = Task(
        description=(
            f"{task_3_cfg['description']}{directive_block}\n\n"
            "Lưu ý điều phối: CEO giao Nhân sự Kế hoạch & Phôi / các Tổ trưởng ghi lịch vào "
            "tab HV2_Production_Schedule (qua append_hv2_schedule) và giao IQC/IPQC/OQC ghi "
            "phiếu kiểm soát vào tab HV2_QC_Reports (qua append_hv2_qc_report) trước khi trình duyệt.\n\n"
            f"{constraints_text}"
        ),
        expected_output=task_3_cfg["expected_output"],
        context=[analyze_task, schedule_task],
        human_input=enable_terminal_human_input,
    )

    return Crew(
        agents=worker_agents,
        tasks=[analyze_task, schedule_task, ceo_approval_task],
        process=Process.hierarchical,
        manager_agent=ceo_agent,
        max_rpm=max_rpm,
        verbose=True,
    )
