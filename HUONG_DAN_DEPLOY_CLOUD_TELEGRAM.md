# Hướng dẫn Deploy Cloud 24/7 & Telegram Bot — Nhà máy HV2

Bộ dự án `hv2_multi_agent` đã được đóng gói sẵn để chạy **24/7 kể cả khi tắt máy tính**, hỗ trợ cả **Web Dashboard trên điện thoại** lẫn **Telegram Bot điều hành & báo cáo định kỳ**.

---

## Bước 1: Tạo Telegram Bot (2 phút)
1. Mở Telegram, tìm **`@BotFather`** → nhắn `/newbot`.
2. Đặt tên (VD: `HV2 Factory CEO Bot`) và username kết thúc bằng `bot` (VD: `hv2_factory_ceo_bot`).
3. Copy **Bot Token** (`TELEGRAM_BOT_TOKEN`).
4. Lấy **Chat ID** (`TELEGRAM_CHAT_ID`):
   - Thêm bot vào nhóm Telegram của nhà máy (hoặc nhắn riêng cho bot) → chạy thử `CHAY_TELEGRAM_BOT_HV2.bat` rồi nhắn `/id` để bot trả về đúng Chat ID.

---

## Bước 2: Đẩy mã nguồn lên GitHub (An toàn — không lộ khóa)
File `.gitignore` đã **chặn sẵn** `.env` và `credentials.json` nên không bao giờ bị đẩy lên GitHub.
```powershell
cd "h:\My Drive\hv2_multi_agent"
git init
git add .
git commit -m "HV2 Multi-Agent 24/7 Cloud + Telegram package"
# Tạo 1 repo Private trên GitHub rồi push lên:
git remote add origin https://github.com/<tai-khoan-cua-ban>/hv2-multi-agent.git
git branch -M main
git push -u origin main
```

---

## Bước 3: Chọn 1 trong 3 cách chạy Cloud 24/7

### Cách A — MIỄN PHÍ 100%: Streamlit Cloud (Web Dashboard) + GitHub Actions (Lập lịch gửi Telegram)
1. **Web Dashboard 24/7 trên Streamlit Community Cloud** (https://share.streamlit.io):
   - Kết nối repo GitHub `hv2-multi-agent`, chọn file chính `dashboard.py`.
   - Vào **App Settings → Secrets**, dán các biến:
     ```toml
     GEMINI_API_KEY = "..."
     GOOGLE_SHEET_ID = "1w1xHdvFITO3NJm_O1bjX-ReXRJsE9iZZK5HydyLKgoc"
     CEO_MODEL = "gemini/gemini-3.1-flash-lite"
     WORKER_MODEL = "gemini/gemini-3.1-flash-lite"
     CREW_MAX_RPM = "15"

     [gcp_service_account]
     # Dán các trường trong credentials.json vào đây
     ```
2. **Tự động chạy 07:00 sáng & 13:00 chiều (giờ VN) gửi Telegram trên GitHub Actions**:
   - Vào repo GitHub → **Settings → Secrets and variables → Actions → New repository secret**, thêm 5 secret:
     - `GEMINI_API_KEY`
     - `GOOGLE_SHEET_ID`
     - `GOOGLE_CREDENTIALS_JSON` *(dán toàn bộ nội dung file `credentials.json`)*
     - `TELEGRAM_BOT_TOKEN`
     - `TELEGRAM_CHAT_ID`
   - Workflow `.github/workflows/hv2_scheduled_plan.yml` sẽ tự động chạy đúng giờ hằng ngày (và có nút **Run workflow** để bấm chạy tay ngay trên điện thoại).

---

### Cách B — 1-Click Cloud chạy SONG SONG cả Web Dashboard + Telegram Bot tương tác 24/7 (Render.com)
1. Truy cập https://dashboard.render.com → **New → Blueprint** → chọn repo GitHub `hv2-multi-agent`.
2. Render tự đọc file **`render.yaml`** và **`Dockerfile`**.
3. Điền các biến bí mật (`GEMINI_API_KEY`, `GOOGLE_SHEET_ID`, `GOOGLE_CREDENTIALS_JSON`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, `TELEGRAM_ALLOWED_CHAT_ID`) → bấm **Apply**.
4. Hoàn tất: vừa có link Web Dashboard 24/7, vừa nhắn `/plan`, `/status`, `/approve`, `/revise` trực tiếp với Bot Telegram bất cứ lúc nào!

---

### Cách C — Chạy trên VPS riêng bằng Docker (1 lệnh)
Copy thư mục dự án (kèm `.env` và `credentials.json`) lên VPS rồi chạy:
```bash
docker compose up -d --build
```
Container `hv2_multi_agent_24x7` tự động chạy song song cả Web Dashboard (`port 8501`) lẫn Telegram Bot và tự khởi động lại khi VPS reboot (`restart: unless-stopped`).
