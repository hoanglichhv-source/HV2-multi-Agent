# Hướng dẫn chạy độc lập Hệ thống 12 AI Agents Nhà máy HV2 (Ngoài Antigravity)

Để chạy hoàn toàn độc lập trên máy tính Windows của bạn (không cần mở Antigravity), chỉ cần làm đúng **1 lần duy nhất** theo 3 bước dưới đây (mất khoảng 2 phút):

---

## Bước 1: Lấy file `credentials.json` (Google Service Account)
1. Truy cập **Google Cloud Console**: https://console.cloud.google.com/
2. Chọn (hoặc tạo mới) 1 Project (ví dụ: `HV2-Factory-AI`).
3. Vào **APIs & Services → Library**, tìm và bấm **Enable** 2 API sau:
   - **Google Sheets API**
   - **Google Drive API**
4. Vào **IAM & Admin → Service Accounts → Create Service Account**:
   - Đặt tên (ví dụ: `hv2-bot`), bấm **Create and Continue → Done**.
5. Bấm vào Service Account vừa tạo → sang tab **Keys → Add Key → Create new key → JSON** → bấm **Create**.
   - Trình duyệt sẽ tải về 1 file `.json`.

---

## Bước 2: Nạp `credentials.json` và Share quyền Google Sheet
Bạn có 2 cách nạp file (chọn 1 trong 2):
- **Cách 1 (Dễ nhất)**: Kéo-thả trực tiếp file `.json` vừa tải vào mục **🔑 Chế độ chạy độc lập** ở thanh bên trái trên Web Dashboard (`http://localhost:8501`). Dashboard sẽ tự lưu thành `credentials.json` và hiện sẵn dòng `client_email` cho bạn copy.
- **Cách 2 (Thủ công)**: Đổi tên file vừa tải thành `credentials.json` và copy vào thư mục:
  `h:\My Drive\hv2_multi_agent\credentials.json`

Sau đó, mở Google Sheet của bạn:
https://docs.google.com/spreadsheets/d/1w1xHdvFITO3NJm_O1bjX-ReXRJsE9iZZK5HydyLKgoc/edit
→ Bấm nút **Share (Chia sẻ)** → dán `client_email` (dạng `hv2-bot@....iam.gserviceaccount.com`) → chọn quyền **Editor (Người chỉnh sửa)** → bấm **Send**.

---

## Bước 3: Chạy độc lập 1-click trên Windows
Từ nay về sau, bạn **không cần mở Antigravity hay gõ lệnh PowerShell nữa**:
- **Mở giao diện Web Dashboard**: Nháy đúp vào file **`CHAY_DASHBOARD_HV2.bat`** trong thư mục `h:\My Drive\hv2_multi_agent\` → trình duyệt tự mở tại `http://localhost:8501`.
- **Chạy chế độ dòng lệnh (Terminal)**: Nháy đúp vào file **`CHAY_TERMINAL_HV2.bat`**.
- **Kiểm tra kết nối độc lập**: Trên thanh bên trái Web Dashboard sẽ hiện dấu xanh **`✅ Độc lập 100% (gspread + credentials.json)`** và bạn có thể bấm nút **🧪 Kiểm tra kết nối gspread độc lập** để xác nhận ngay.
