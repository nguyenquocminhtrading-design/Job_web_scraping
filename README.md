# VN Labor Market Intelligence System

Hệ thống thu thập, phân tích và báo cáo dữ liệu thị trường lao động tự động. 
Phiên bản hiện tại tập trung vào ngành **Tài chính - Kế toán - Đầu tư** tại Việt Nam.

---

## 🌊 WORKFLOW & DATA FLOW (Quy trình luân chuyển dữ liệu)

Hệ thống được thiết kế theo kiến trúc 5-Layers, xử lý dữ liệu từ dạng thô (raw HTML) thành các insights có giá trị (Dashboard/API).

### Layer 1: Input Engine (Đầu vào & Lên lịch)
- **Nhiệm vụ**: Định nghĩa các từ khóa cần tìm (ví dụ: "Kế toán tổng hợp", "FP&A") trong file `config/keywords.yaml`.
- **Hoạt động**: `scheduler.py` sẽ định kỳ (ví dụ: mỗi 2h sáng Thứ 2) kích hoạt toàn bộ hệ thống bắt đầu đi cào dữ liệu dựa trên tập từ khóa này.

### Layer 2: Scraping Engine (Thu thập dữ liệu)
- **Nhiệm vụ**: Vào các trang tuyển dụng (VietnamWorks, TopCV, CareerViet) để lấy mô tả công việc (JD).
- **Hoạt động**: Các scraper sử dụng `Playwright` để mở trình duyệt ẩn (headless browser). Nó tự động xoay vòng User-Agent và tạo độ trễ ngẫu nhiên (2-5s) giữa các lần click để tránh bị block. Dữ liệu lấy về (Tên job, mức lương thô, kinh nghiệm, mô tả) được lưu thành object `JobPosting`.

### Layer 3: NLP & Parsing (Xử lý ngôn ngữ tự nhiên)
- **Nhiệm vụ**: Biến text lộn xộn thành dữ liệu có cấu trúc.
- **Hoạt động**:
  1. **Deduplication**: Xóa các tin tuyển dụng bị đăng trùng lặp dựa trên MD5 Hash (Tên công việc + Công ty).
  2. **Text Normalization**: Viết thường, xóa dấu tiếng Việt để dễ so khớp.
  3. **Skill & Cert Extraction**: Quét nội dung JD, đối chiếu với danh mục từ khóa (`skills_taxonomy.json`) để rút trích ra ứng viên cần biết phần mềm gì (Excel, SAP) hay chứng chỉ gì (CPA, ACCA).
  4. **Salary Parsing**: Dịch các chuỗi như "15-25 triệu" hay "$1000" thành dải lương chuẩn (VND).
  5. **Benefits Classification**: Tìm các từ khóa "lương tháng 13", "teambuilding", "hybrid" để xếp vào 8 nhóm phúc lợi chuẩn.

### Layer 4: Analytics Core (Lõi Phân tích)
- **Nhiệm vụ**: Từ kho dữ liệu chuẩn hóa, tính toán ra các chỉ số thị trường.
- **Hoạt động**:
  - **MVJD (Minimum Viable JD)**: Thống kê xem kỹ năng nào xuất hiện trên 60% tin tuyển dụng -> Bắt buộc phải có.
  - **Benefits Compare**: Tính tỷ lệ % doanh nghiệp FDI vs Nội địa có cấp laptop hay có thưởng tháng 13.
  - **Trend Analysis**: Đếm số lần 1 kỹ năng (vd: Python) được nhắc đến theo từng tháng để xem xu hướng tăng hay giảm.
  - **Gap Analysis**: So sánh kỹ năng hiện tại của ứng viên với chuẩn MVJD để chỉ ra điểm thiếu sót.

### Layer 5: Output Delivery (Hiển thị & Cảnh báo)
- **Nhiệm vụ**: Trình bày dữ liệu cho người dùng cuối.
- **Hoạt động**:
  - **FastAPI**: Cung cấp các REST endpoint (`/jd-minimum`, `/benefits-compare`) để các hệ thống khác có thể query dữ liệu.
  - **Streamlit Dashboard**: Giao diện UI trực quan, biểu đồ để xem báo cáo.
  - **Telegram Alert**: Gửi tin nhắn ngay lập tức qua Telegram nếu phát hiện một JD mới cực kỳ phù hợp với nhu cầu.

---

## 🚀 HƯỚNG DẪN CÀI ĐẶT (Môi trường Local Windows)

Do một số thư viện C++ (pandas, numpy) có thể lỗi khi build trên Windows cũ, hãy dùng môi trường ảo chuẩn.

### 1. Tạo môi trường ảo và cài đặt thư viện
```powershell
# Mở PowerShell tại thư mục dự án
python -m venv venv
.\venv\Scripts\activate

# Cập nhật pip
python -m pip install --upgrade pip

# Cài đặt các thư viện cơ bản
pip install -r requirements.txt

# Cài đặt engine trình duyệt cho Playwright
playwright install chromium
```

> **Lưu ý**: Nếu quá trình `pip install` báo lỗi `metadata-generation-failed` liên quan đến `pandas` hoặc `numpy`, hãy cài đặt thủ công các bản pre-compiled wheel:
> `pip install pandas==2.2.2 numpy==1.26.4 --only-binary :all:`

### 2. Cấu hình Biến Môi Trường (.env)
Đổi tên file `.env.example` thành `.env` và điền thông tin:
```env
MONGODB_URI=mongodb://localhost:27017/
TELEGRAM_BOT_TOKEN=token_cua_bot
TELEGRAM_CHANNEL_ID=id_cua_channel
```

### 3. Chạy các dịch vụ (Mở 2 Terminal riêng biệt)

**Terminal 1 - Chạy Backend API (FastAPI):**
```powershell
.\venv\Scripts\activate
uvicorn layer5_output.api.main:app --reload --port 8000
```
*(Truy cập: http://localhost:8000/docs để xem API Swagger UI)*

**Terminal 2 - Chạy Giao diện Báo cáo (Streamlit Dashboard):**
```powershell
.\venv\Scripts\activate
streamlit run layer5_output/dashboard/app.py
```
*(Giao diện sẽ tự bật lên tại: http://localhost:8501)*
