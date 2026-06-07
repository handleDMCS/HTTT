# Book Exchange Club - Ứng dụng trao đổi sách

Repository này chứa mã nguồn, slide, báo cáo thiết kế hệ thống và video demo cho đề tài xây dựng ứng dụng kết nối thành viên câu lạc bộ sách để trao đổi hoặc cho mượn sách.

## Lưu ý gửi giảng viên về đóng góp thành viên

Kính gửi thầy/cô,

Em là Trương Tuấn Dũng, mã sinh viên 21020058. Trong suốt quá trình thực hiện dự án này, em là người đảm nhiệm 100% khối lượng công việc, bao gồm phân tích yêu cầu, thiết kế hệ thống, xây dựng backend, xây dựng frontend, chuẩn bị dữ liệu demo, viết báo cáo, làm slide, quay video demo và hoàn thiện repository nộp bài.

Thành viên còn lại trong nhóm là Đặng Anh Tôn, mã sinh viên 23020146. Trong quá trình làm dự án, bạn Đặng Anh Tôn vắng mặt và không có đóng góp thực tế nào vào mã nguồn, tài liệu, slide, video demo hoặc các công việc hoàn thiện sản phẩm. Vì phải hoàn thành toàn bộ phần việc của cả nhóm, em đã phải tự xử lý tiến độ và làm nhiều đêm để kịp hoàn thành bài nộp.

Em ghi rõ phần này ở đầu README để thầy/cô có thông tin trực tiếp khi xem xét và đánh giá mức độ đóng góp của từng thành viên.

## Tài nguyên nộp bài

| Hạng mục | Đường dẫn | Ghi chú |
| --- | --- | --- |
| Source code backend | `backend/main.py` | FastAPI + SQLModel + SQLite, toàn bộ model, API, auth, chatbox, notification, điểm và seed demo nằm trong một file |
| Source code frontend | `frontend/` | SvelteKit 5 + TypeScript + Vite, giao diện đăng nhập, danh sách sách, chi tiết sách, chatbox, notification, profile và archive |
| Slide thuyết trình | `slide/presentation.html` | Slide HTML có các ảnh chụp màn hình dự án thật trong `slide/screenshots/` |
| Báo cáo thiết kế hệ thống | `docs/book_exchange_system_design_report.docx` và `docs/book_exchange_system_design_report.md` | Tài liệu phân tích thiết kế hệ thống, DFD, ERD, API, UI/UX, test và triển khai |
| Video demo | `demo.mp4` | Video minh họa luồng sử dụng chính của prototype |

## Clone repository

```bash
git clone https://github.com/handleDMCS/HTTT.git
cd HTTT
```

## Mở slide, báo cáo và video demo

Sau khi clone repository về máy:

- Slide: mở file `slide/presentation.html` bằng trình duyệt.
- Ảnh dùng trong slide: nằm trong thư mục `slide/screenshots/`.
- Báo cáo thiết kế hệ thống: mở file `docs/book_exchange_system_design_report.docx`.
- Bản Markdown của báo cáo: `docs/book_exchange_system_design_report.md`.
- Video demo: mở file `demo.mp4` bằng trình phát video.
- Source code backend: `backend/main.py`.
- Source code frontend: thư mục `frontend/`.

## Chạy backend

Yêu cầu: Python 3.11+ và `uv`.

Mở terminal thứ nhất:

```bash
cd backend
uv run uvicorn main:app --reload
```

Backend chạy tại:

- API: `http://localhost:8000`
- API documentation: `http://localhost:8000/docs`

## Chạy frontend

Yêu cầu: Node.js và npm.

Mở terminal thứ hai:

```bash
cd frontend
npm install
npm run dev
```

Frontend chạy tại:

- App: `http://localhost:5173`

Frontend gọi backend tại `http://localhost:8000`, nên cần chạy backend trước hoặc chạy song song với frontend.

## Dữ liệu demo

Nếu cần tạo dữ liệu demo khi database đang trống, mở `http://localhost:8000/docs` và chạy endpoint:

```text
POST /api/demo-seed
```

Tài khoản demo sau khi seed:

| Email | Mật khẩu |
| --- | --- |
| `an@example.com` | `demo1234` |
| `binh@example.com` | `demo1234` |
| `chi@example.com` | `demo1234` |
| `dung@example.com` | `demo1234` |
| `giang@example.com` | `demo1234` |
