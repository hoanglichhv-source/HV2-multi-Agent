# Hệ thống Multi-Agent Nhà máy HV2 (CrewAI + Gemini API + Google Sheets)

Dự án điều phối sản xuất thông minh bằng **12 AI Agents** (mô hình 2 tầng `Process.hierarchical`) dành riêng cho **Nhà máy HV2** (cán nguội, ủ mềm, xẻ băng, mài bề mặt inox), tích hợp **Google Gemini API** (`max_rpm=15`) và **Google Sheets (`gspread`)**.

---

## 1. Ràng buộc năng lực thiết bị thực tế HV2 (Hardcoded)

Được hardcode đồng bộ tại `config/hv2_constraints.py`, `config/agents.yaml`, `config/tasks.yaml` và bộ chặn tự động trong `tools/hv2_sheets.py`:

| Nhóm thiết bị | Mã máy | Số lượng | Ràng buộc bắt buộc |
| :--- | :--- | :---: | :--- |
| **Máy cán nguội** | `MC-01`, `MC-02`, `MC-03` | 3 | **Khổ cuộn tối đa bắt buộc = 720mm**. Cấm tuyệt đối đưa cuộn > 720mm vào máy cán. |
| **Lò ủ mềm** | `LU-01`, `LU-02`, `LU-03`, `LU-04` | 4 | Ủ mềm khử ứng suất sau cán nguội. |
| **Máy xẻ băng** | `MX-01` | 1 | **NÚT THẮT CỔ CHAI (BOTTLENECK)**. Mọi cuộn phôi khổ > 720mm **BẮT BUỘC** phải xếp lịch qua `MX-01` xẻ chia khổ (<= 720mm) trước khi vào `MC-01..03`. |
| **Máy mài bề mặt** | `MM-01`, `MM-02`, `MM-03` | 3 | Hoàn thiện bề mặt inox (No.4, HL, bóng). |
| **Tổng cộng** | | **11 máy** | |

---

## 2. Cấu trúc 12 AI Agents (`Process.hierarchical`)

- **Tầng 1 — Manager Agent (`gemini/gemini-2.5-pro`)**:
  1. **CEO Nhà máy HV2**: Điều phối trực tiếp 11 nhân sự số, phát hiện xung đột lịch trên nút thắt cổ chai `MX-01`, tổng hợp kế hoạch và dừng chờ bạn phê duyệt (`human_input=True`).
- **Tầng 2 — 11 Nhân sự số thực thi (`gemini/gemini-2.5-flash`)**:
  - **Kế hoạch SX & Vật tư (2)**: Nhân sự Kế hoạch & Phôi; Nhân sự Vật tư & Kho.
  - **Sản xuất (5)**: Tổ trưởng Cán (3 máy); Tổ trưởng Ủ (4 lò); Tổ trưởng Xẻ (1 máy `MX-01`); Tổ trưởng Mài (3 máy); Tổ Cơ động (luân chuyển 11 máy & đóng gói).
  - **Kỹ thuật Bảo trì (2)**: Kỹ sư Bảo trì Cơ - Điện (PM 11 thiết bị); Kỹ sư Trục cán & Phụ tùng (mài trục cán & dao xẻ).
  - **Quản lý Chất lượng (2)**: QC Đầu vào & Trong chuyền (IQC/IPQC); QC Thành phẩm & Xử lý lỗi (OQC).

---

## 3. Hướng dẫn cài đặt và chạy nhanh

### Bước 1: Tạo môi trường ảo & cài thư viện
```powershell
cd "h:\My Drive\hv2_multi_agent"
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### Bước 2: Cấu hình `.env` và `credentials.json`
1. Sao chép `.env.example` thành `.env`:
   ```powershell
   Copy-Item .env.example .env
   ```
2. Điền `GEMINI_API_KEY` và `GOOGLE_SHEET_ID` vào file `.env`.
3. Đặt file Google Service Account key tên **`credentials.json`** vào thư mục gốc `hv2_multi_agent/`.
4. Chia sẻ Google Sheet (quyền **Editor**) cho địa chỉ `client_email` nằm trong file `credentials.json`.

### Bước 3: Khởi tạo 5 tab Google Sheets & dữ liệu mẫu test 720mm
```powershell
python setup_hv2_sheet.py
```
Lệnh này sẽ tự động tạo 5 tab (`HV2_Orders`, `HV2_Inventory`, `HV2_Production_Schedule`, `HV2_Maintenance`, `HV2_QC_Reports`), điền đủ **11 thiết bị**, nạp sẵn **2 cuộn phôi** (`1219mm` và `650mm`) và **1 đơn hàng mẫu (`ORD-HV2-001`)**.

### Bước 4: Chạy hệ thống 12 AI Agents
```powershell
python main.py
```
Ở bước cuối cùng, CEO Nhà máy HV2 sẽ trình bày bản kế hoạch hoàn chỉnh (đã xử lý bài toán xẻ thô 720mm trên `MX-01` và đồng bộ lên Google Sheets) rồi **dừng chờ bạn nhập phản hồi / phê duyệt** ngay trên terminal.
