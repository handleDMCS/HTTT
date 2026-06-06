# Book Exchange Club - Ứng dụng trao đổi sách

Repository này chứa mã nguồn, slide, báo cáo thiết kế hệ thống và video demo cho đề tài xây dựng ứng dụng kết nối thành viên câu lạc bộ sách để trao đổi hoặc cho mượn sách.

## Tài nguyên nộp bài

| Hạng mục | Đường dẫn | Ghi chú |
| --- | --- | --- |
| Source code backend | `backend/main.py` | FastAPI + SQLModel + SQLite, toàn bộ model, API, auth, chatbox, notification, điểm và seed demo nằm trong một file |
| Source code frontend | `frontend/` | SvelteKit 5 + TypeScript + Vite, giao diện đăng nhập, danh sách sách, chi tiết sách, chatbox, notification, profile và archive |
| Slide thuyết trình | `slide/presentation.html` | Slide HTML có các ảnh chụp màn hình dự án thật trong `slide/screenshots/` |
| Báo cáo thiết kế hệ thống | `docs/book_exchange_system_design_report.docx` và `docs/book_exchange_system_design_report.md` | Tài liệu phân tích thiết kế hệ thống, DFD, ERD, API, UI/UX, test và triển khai |
| Video demo | `demo.mp4` | Video minh họa luồng sử dụng chính của prototype |
| Ý tưởng nghiệp vụ | `IDEA.md` | Mô tả yêu cầu ban đầu của bài toán trao đổi sách |

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
