# QTKĐ RAG trên Windows, không cần Docker

> Cần hướng dẫn từng bước? Xem [HUONG-DAN-CAI-DAT.md](HUONG-DAN-CAI-DAT.md) hoặc bản Word [HUONG-DAN-CAI-DAT.docx](HUONG-DAN-CAI-DAT.docx).
> Tài liệu dưới đây là tham chiếu kỹ thuật đầy đủ.

Bộ cài này chạy toàn bộ hệ thống bằng tiến trình Windows native.
Không cần Docker Desktop, không cần WSL.
Mặc định cài trong `%LOCALAPPDATA%`, riêng bước cài Ruby có thể hiện UAC tùy bản RubyInstaller.

Một cổng duy nhất: `http://127.0.0.1:8080`.
API FastAPI phục vụ luôn bản build React, không còn nginx.

## 1. Yêu cầu

Tất cả yêu cầu áp dụng cho cùng một máy Windows, nơi vừa dựng gói vừa cài đặt.

| Thành phần | Ghi chú |
|---|---|
| Windows 10/11 64-bit | Chưa chạy end-to-end trên Windows thật; xem mục 12 |
| GPU NVIDIA + driver mới | Target RTX 5060 8GB; torch cu128 hỗ trợ sm_120 |
| RAM | Tối thiểu 16GB |
| Ổ đĩa trống | Khoảng 45GB: gói cài, bản đã cài, torch, wheel và model |
| Internet | Tải model (~9-10GB), wheel và Ruby/gem trong lần dựng đầu |
| Python 3.11+ | Có pip và có trong PATH; dùng để chạy build_bundle.py |
| Node.js 20+ | Chỉ cần khi build lại frontend; không có thì dùng `--skip-frontend` |
| Visual C++ 2015-2022 Redistributable | Thường có sẵn; torch cần `msvcp140.dll`. Thiếu thì cài từ https://aka.ms/vs/17/release/vc_redist.x64.exe |

Không có GPU NVIDIA vẫn chạy được, nhưng chat và rerank sẽ rất chậm vì dùng CPU.
Nên dùng đường dẫn ngắn, không dấu, ví dụ `D:\RAG-TC-DL` cho repo và `D:\QTKD-RAG\bundle` cho gói cài.

## 2. Cấu trúc sau khi cài

```
%LOCALAPPDATA%\QTKD-RAG\
  app\                  mã nguồn, frontend/dist, .env
  runtime\python\       CPython 3.12 portable + thư viện
  tools\qdrant\         qdrant.exe
  tools\postgres\       Postgres portable
  tools\ollama\         ollama.exe
  tools\ruby\           Ruby portable + gem (nếu đã cài)
  wheels\               wheel cài offline
  data\                 DỮ LIỆU NGƯỜI DÙNG, giữ qua nâng cấp
    TC_DL\              tài liệu gốc
    build\              Markdown + assets + extraction_report.json
    postgres\           CSDL
    qdrant\             vector store
    registry\           sổ công thức SQLite
    models\hf\          cache HuggingFace
    models\ollama\      model LLM
    logs\               log từng dịch vụ
  CaiDat.bat            cài lại / nâng cấp
  QTKD-RAG.bat          chạy ứng dụng
```

Chỉ `data\` là dữ liệu cần sao lưu.
Xóa `app\`, `runtime\`, `tools\` rồi cài lại không mất tài liệu, tài khoản hay chỉ mục.

## 3. Dựng gói cài

Mở PowerShell tại thư mục repo trên máy Windows.
Dựng gói vào một thư mục làm việc, rồi cài ngay từ thư mục đó.

Chọn một trong các lệnh sau:

```powershell
cd D:\RAG-TC-DL

# Có Node.js: build lại frontend
python windows\build_bundle.py --out D:\QTKD-RAG\bundle --zip

# Không có Node.js: dùng frontend/dist có sẵn
python windows\build_bundle.py --out D:\QTKD-RAG\bundle --zip --skip-frontend

# Kèm model để cài offline hoàn toàn
python windows\build_bundle.py --out D:\QTKD-RAG\bundle --zip --with-models
```

Script tải và đóng gói:

- CPython 3.12 portable (python-build-standalone)
- Qdrant 1.10.1 bản Windows (khớp docker-compose)
- PostgreSQL 16.4 bản Windows (khớp image `postgres:16-alpine`)
- Ollama bản Windows
- RubyInstaller 3.3 + gem `mathtype_to_mathml` 0.0.7 (cài ngay trong gói)
- Toàn bộ wheel Python cho `win_amd64` / CPython 3.12, gồm torch 2.9.1 `cu128`
- `frontend/dist` (chạy `npm ci && npm run build` nếu có Node)
- `build/spike_a` và `TC_DL` mồi từ repo

Vì chạy trên Windows, Ruby và gem đã nằm trong `tools\ruby`; bước cài không cần tải Ruby từ Internet.
Dùng `--with-models` nếu muốn bước cài không cần mạng.
Gói có model tăng thêm khoảng 9-10GB.

Sau khi cài xong và kiểm tra ổn, có thể xoá thư mục gói để lấy lại dung lượng, hoặc giữ lại để cài lại nhanh.

## 4. Cài đặt

Chạy bộ cài ngay trên máy vừa dựng gói:

1. Mở PowerShell tại thư mục gói (ví dụ `D:\QTKD-RAG\bundle`).
2. Nháy đúp `CaiDat.bat`, hoặc chạy `.\CaiDat.bat`.
3. Làm theo hướng dẫn: nhập tài khoản quản trị và mật khẩu (ít nhất 8 ký tự).

Bộ cài tự làm:

1. Chép chương trình vào `%LOCALAPPDATA%\QTKD-RAG` (không cần admin).
2. Cài Python deps offline từ `wheels\`.
3. Sinh `.env` với mật khẩu/JWT/Qdrant key ngẫu nhiên và cổng trống.
4. Khởi tạo Postgres trong `data\postgres`, tạo CSDL `qtkd`.
5. Dùng Ruby và gem đã có trong gói.
6. Tải hoặc copy model embedding, reranker và LLM.
7. Chạy migration, đăng ký tài liệu, tạo tài khoản, index vào Qdrant.
8. Tạo shortcut Desktop/Start Menu và mục gỡ cài trong Apps & features.

Cài không tương tác:

```powershell
$env:QTKD_ADMIN_PASSWORD="mat-khau-it-nhat-8-ky-tu"
.\CaiDat.bat --admin-user admin
```

Thêm `--offline` nếu gói được dựng bằng `--with-models`.

Không truyền `--admin-password` trên dòng lệnh nếu máy có nhiều người dùng: mật khẩu sẽ hiện trong Process Explorer.

Nếu muốn dùng cho một máy Windows khác, chép cả thư mục `D:\QTKD-RAG\bundle` sang máy đó và chạy `CaiDat.bat`.
Mỗi máy có `data\` và tài khoản riêng.

Bộ cài chỉ index những Markdown đã có trong gói (`build/spike_a`, hiện là bộ mẫu 7 tài liệu).
Các tài liệu còn lại trong `TC_DL` được đăng ký ở trạng thái **pending**.
Mở tab **Tài liệu** và bấm xử lý để trích xuất từng tài liệu; `.docx` cần Ruby, `.doc` cần LibreOffice, `.pdf` cần Marker.

## 5. Chạy và dừng

Nháy đúp shortcut **QTKD RAG**, hoặc:

```bat
QTKD-RAG.bat
```

Lần chạy đầu chậm vì Ollama nạp LLM (~5GB) lên GPU.
Cửa sổ hiện tiến độ từng dịch vụ; trình duyệt tự mở khi API sẵn sàng.

Dừng: nhấn `Ctrl+C` trong cửa sổ QTKĐ RAG.
Đóng cửa sổ bằng dấu X dừng các tiến trình con do QTKĐ RAG khởi động, nhưng PostgreSQL có thể vẫn chạy; lần sau ứng dụng sẽ dùng lại.

Các lệnh khác:

```bat
QTKD-RAG.bat status     REM kiểm tra dịch vụ đang trả lời
QTKD-RAG.bat index      REM index lại data\build vào Qdrant
QTKD-RAG.bat migrate    REM chạy migration CSDL
QTKD-RAG.bat models     REM tải bổ sung model còn thiếu
```

## 6. Cổng

| Dịch vụ | Cổng mặc định |
|---|---|
| API + React | 8080 |
| Embedding | 8010 |
| Reranker | 8011 |
| Qdrant | 6333 (gRPC 6334) |
| Ollama | 11434 |
| PostgreSQL | 55432 (không phải 5432, tránh đụng Postgres khác) |

Tất cả chỉ nghe trên `127.0.0.1`.
Bộ cài tự chọn cổng khác nếu cổng mặc định đang bận (trừ khi nâng cấp bản đã có).

Mặc định mỗi máy chạy một bản riêng, không chia sẻ qua LAN.
Muốn máy khác trong LAN truy cập, đổi `API_HOST=0.0.0.0` trong `app\.env`, mở cổng 8080 trên Windows Firewall, và giữ `AUTH_ENABLED=true`.

## 7. Nâng cấp

Dựng gói mới vào thư mục mới, rồi chạy `CaiDat.bat` của gói mới trên cùng máy.
Bộ cài giữ `.env`, `data\` và tài khoản; chỉ thay `app\`.
Nếu phiên bản manifest đổi, `runtime\`, `tools\`, `wheels\` cũng được thay.

Đóng ứng dụng trước khi nâng cấp, nếu không bộ cài báo cổng 8080 đang bận.

## 8. Sao lưu và gỡ

Sao lưu: dừng ứng dụng, chép `%LOCALAPPDATA%\QTKD-RAG\data`.
Dữ liệu gồm tài liệu gốc, Markdown, Qdrant, Postgres, sổ công thức và model.
Không cần sao lưu `app\`, `runtime\`, `tools\`, `wheels\` vì cài lại được.

Gỡ: Settings → Apps → **QTKD RAG**, hoặc:

```bat
runtime\python\python.exe app\windows\uninstall.py --root "%LOCALAPPDATA%\QTKD-RAG"
```

Mặc định giữ `data\`.
Thêm `--remove-data` để xóa sạch.

## 9. Khác biệt so với bản Docker

| Điểm | Docker | Native Windows |
|---|---|---|
| Frontend | nginx :3000 | FastAPI phục vụ `frontend/dist` :8080 |
| Postgres | container :5432 | tiến trình :55432 |
| Qdrant storage | `./qdrant_storage` | `data\qdrant` |
| Model | volume `ollama_data` | `data\models\ollama` |
| Dữ liệu tài liệu | `./TC_DL`, `./build/spike_a` | `data\TC_DL`, `data\build` |
| Khởi động | `docker compose up` | shortcut / `QTKD-RAG.bat` |
| GPU | NVIDIA Container Toolkit | driver NVIDIA + torch cu128 |

Chuyển dữ liệu từ bản Docker sang bản Windows: chép `TC_DL`, `build/spike_a`, `.formula-registry` và dữ liệu Postgres/Qdrant theo đúng phiên bản.
Cách gọn nhất là cài mới rồi tải lại tài liệu qua giao diện, tránh lệch phiên bản storage.

## 10. Thành phần tùy chọn

- **Ruby + gem**: bắt buộc để bóc công thức MathType từ `.docx` mới tải lên.
  Bộ cài tự cài nếu có mạng. Thiếu Ruby thì tài liệu đã có vẫn chat được, nhưng upload `.docx` có công thức sẽ không trích được LaTeX.
- **LibreOffice**: chỉ cần cho `.doc`/`.xls` cũ.
  Bộ cài tự tìm `soffice.exe` trên PATH hoặc registry. Không có thì upload `.doc` báo lỗi rõ ràng.
- **Marker (PDF)**: cần môi trường riêng theo `requirements-pdf.txt` (torch CPU, 2-3GB).
  Đặt `MARKER_PYTHON` trong `.env` trỏ tới `python.exe` của môi trường đó.
  Không có Marker thì upload `.pdf` báo `MarkerNotConfigured`, không âm thầm trích mất công thức.

## 11. Xử lý sự cố

| Hiện tượng | Cách xử lý |
|---|---|
| `CUDA: KHÔNG` khi cài | Cập nhật driver NVIDIA; kiểm tra `nvidia-smi`; torch cu128 cần driver hỗ trợ CUDA 12.8 |
| Cổng 8080/8010/8011 đang bận | Đóng cửa sổ QTKĐ RAG cũ, hoặc chọn cổng khác trong `app\.env` |
| Postgres không lên | Xem `data\logs\postgres.log`; kiểm tra ổ đĩa còn trống |
| Ollama chạy CPU | Log `data\logs\ollama.log`; đảm bảo không có ứng dụng khác giữ VRAM |
| Upload `.docx` không ra công thức | Kiểm tra `RUBY_BIN` trong `app\.env`, chạy `tools\ruby\bin\ruby.exe -e "require 'mathtype_to_mathml'"` |
| Antivirus chặn | Thêm thư mục cài vào loại trừ; installer chưa ký số nên SmartScreen có thể cảnh báo |
| Ứng dụng chạy nhưng chat lỗi | `QTKD-RAG.bat status`; xem `data\logs\api.log` và log dịch vụ tương ứng |

Log của từng dịch vụ nằm ở `data\logs\<tên>.log`.

## 12. Đã kiểm chứng và chưa kiểm chứng

Đã chạy trên Linux:

- Test đơn vị cho phục vụ SPA một cổng, Ruby/GEM_PATH, Marker không dùng lệnh `env`, `.env` và chọn cổng của bộ cài.
- `ruff check` và `pytest` cho toàn bộ mã mới.
- Dựng thử gói cài với artifact giả: cây `runtime/python`, `tools/qdrant`, `tools/postgres`, `tools/ollama` ra đúng layout, có làm phẳng thư mục lồng và bỏ pgAdmin/StackBuilder.
- `pip download` phân giải đủ bộ requirements (gồm `requirements-app.lock`) cho `win_amd64` / CPython 3.12; wheel `torch-2.9.1+cu128` (2,86GB) tồn tại và bắt đầu tải. Phiên phát triển không tải hết 2,86GB; máy Windows sẽ tải đủ khi chạy `build_bundle.py`.

Chưa chạy trên Windows thật (môi trường phát triển là Linux):

- Cài đặt end-to-end, driver NVIDIA, CUDA, Postgres portable, Qdrant/ollama.exe.
- RubyInstaller + nokogiri precompiled trên Ruby 3.3 UCRT.
- Shortcut, registry, Apps & features, Job Object khi đóng cửa sổ.

Lần chạy thử đầu tiên trên một máy Windows sạch là bắt buộc trước khi phát hành cho nhiều máy.
Ghi lại lỗi trong `data\logs` và cập nhật mục này.
