# STTWordH2M - Word Add-in Nhận Dạng Giọng Nói Tiếng Việt (Offline)

Ứng dụng và Plugin Microsoft Word cho phép gõ văn bản bằng giọng nói tiếng Việt, chạy offline 100% sử dụng mô hình Sherpa-ONNX AI local.

---

## 🌟 Tính Năng Nổi Bật

- **Chạy Offline 100%**: Đã tích hợp sẵn bộ thư viện `office-js` offline và mô hình AI local, không cần mạng Internet.
- **Tự Động Đóng Gói 1-Click**: Đóng gói thành file cài đặt `STTWordH2M_Setup.exe` duy nhất cho người dùng cuối.
- **Tự Động Cấu Hình Windows**: Tự động cấp chứng chỉ SSL Localhost, tự động tạo Shared Catalog và đăng ký Registry cho Word khi cài đặt.
- **Quản Lý Qua Khay Hệ Thống (System Tray)**: Chạy ngầm mượt mà, hỗ trợ copy đường dẫn Catalog URL nhanh chóng.

---

## ⚙️ Thông Số Cổng (Ports)

- **HTTPS Web Server (Add-in UI)**: `https://localhost:3009`
- **WebSocket STT Server (AI Engine)**: `ws://localhost:8009/ws/speech`
- **Shared Catalog URL**: `\\localhost\STTWordH2M`

---

## 🛠️ Hướng Dẫn Phát Triển & Kiểm Thử (Developer)

### 1. Yêu cầu môi trường
- Python 3.10+
- Thư viện Python: `pip install pyinstaller pystray Pillow cryptography uvicorn fastapi websockets sherpa_onnx numpy`

### 2. Chạy kiểm thử trực tiếp
Mở Terminal trong thư mục `WordAddin`:
```bat
python launcher.py
```
*Lưu ý: Ứng dụng sẽ chạy ngầm bên dưới khay hệ thống (System Tray) với icon hình tròn xanh.*

### 3. Quy trình Đóng gói phần mềm (Build Release)

1. **Bước 1 (Build EXE)**:
   Mở Terminal tại thư mục `WordAddin` và chạy:
   ```bat
   build.bat
   ```
   *Kết quả: Thư mục `dist\STTWordH2M` được tạo thành công.*

2. **Bước 2 (Tạo File Cài Đặt)**:
   - Cài phần mềm [Inno Setup 6](https://jrsoftware.org/isdl.php).
   - Nhấp chuột phải vào file **`installer.iss`** → Chọn **Compile**.
   *Kết quả: File cài đặt duy nhất `Output\STTWordH2M_Setup.exe` được tạo ra.*

---

## 📦 Hướng Dẫn Cho Người Dùng Cuối (Client)

1. **Cài đặt**: Chạy file `STTWordH2M_Setup.exe` (bấm Next → Install).
2. **Khởi động**: Ứng dụng tự động chạy ngầm dưới góc phải màn hình.
3. **Sử dụng trong Word**:
   - Mở Microsoft Word.
   - Chọn menu **Insert** → **My Add-ins** → Chọn tab **Shared Folder**.
   - Chọn **"STT Word H2M"** → Nhấn **Add**.
   - Bấm nút **Bắt đầu nói** trên Task Pane để bắt đầu nhập liệu bằng giọng nói.

---

## 📁 Cấu Trúc Dự Án

```
WordAddin/
├── launcher.py         # App chính (System Tray + HTTPS Server + STT Server)
├── stt_word.spec       # Cấu hình đóng gói PyInstaller
├── installer.iss       # Cấu hình Inno Setup (Tạo file Setup.exe)
├── build.bat           # Script build 1-click
├── manifest.xml        # File khai báo Add-in cho Microsoft Word
├── taskpane.html       # Giao diện Task Pane
├── taskpane.css        # Style Fluent UI
├── taskpane.js         # Logic thu âm PCM16 + WebSocket + Word Insert
├── commands.html       # Helper cho thanh Ribbon
├── office-js/          # Thư viện Office.js Offline
├── SpeechFunc/         # Thư mục chứa mã nguồn STT Server & Mô hình AI Sherpa-ONNX
└── README_WordAddin.md # Tài liệu hướng dẫn này
```
