# Hướng dẫn cài đặt QTKĐ RAG trên Windows

Bản Word: [HUONG-DAN-CAI-DAT.docx](HUONG-DAN-CAI-DAT.docx).

Tài liệu này hướng dẫn cài đặt trọn gói trên **một máy Windows**: dựng gói cài và cài đặt ngay trên máy đó.
Không cần Docker, không cần WSL, không cần tách máy build và máy đích.
Toàn bộ giao diện và API chạy trên một cổng duy nhất: `http://127.0.0.1:8080`.

## 0. Checklist nhanh

| Bước | Việc cần làm |
|---|---|
| 1 | Cài Python 3.11 trở lên, thêm vào PATH |
| 2 | Mở PowerShell tại thư mục repo |
| 3 | Chạy `python windows\build_bundle.py --out D:\QTKD-RAG\bundle --zip` |
| 4 | Chạy `D:\QTKD-RAG\bundle\CaiDat.bat` |
| 5 | Nhập tài khoản quản trị, chờ tải model và index |
| 6 | Mở shortcut `QTKD RAG`, đăng nhập, hỏi thử |

## 1. Yêu cầu

Tất cả yêu cầu dưới đây áp dụng cho cùng một máy Windows.

| Thành phần | Yêu cầu |
|---|---|
| Windows | Windows 10 hoặc 11, 64-bit |
| GPU | NVIDIA, driver mới hỗ trợ CUDA 12.8 (mục tiêu RTX 5060 8GB) |
| RAM | Tối thiểu 16GB |
| Ổ đĩa trống | Ít nhất 45GB, chia cho gói cài, bản đã cài và model |
| Visual C++ | Microsoft Visual C++ 2015-2022 Redistributable (x64), thường có sẵn |
| Internet | Cần khi dựng gói và tải model; có thể dựng gói kèm model để cài offline |
| Python | 3.11 trở lên, có pip và có trong PATH |
| Node.js | 20 trở lên nếu muốn build lại frontend; không có thì dùng `--skip-frontend` |
| Quyền | Không cần admin cho QTKĐ RAG; bước cài Ruby có thể hiện UAC tùy bản RubyInstaller |

Nên dùng đường dẫn ngắn, không dấu, ví dụ `D:\RAG-TC-DL` cho repo và `D:\QTKD-RAG\bundle` cho gói cài.
Đường dẫn có dấu tiếng Việt hoặc khoảng trắng vẫn chạy được nhưng dễ gặp lỗi ở PostgreSQL và Ruby hơn.

Máy không có GPU NVIDIA vẫn chạy được nhưng rất chậm vì model dùng CPU.
Thiếu `msvcp140.dll` thì cài VC++ Redistributable từ `https://aka.ms/vs/17/release/vc_redist.x64.exe`.

## 2. Chuẩn bị máy Windows

### 2.1. Cài Python

Tải Python 3.11 hoặc 3.12 từ `https://www.python.org/downloads/windows/`.
Khi cài, chọn **Add python.exe to PATH**.

Kiểm tra trong PowerShell:

```powershell
python --version
pip --version
```

Nếu `python` mở Microsoft Store hoặc báo không tìm thấy, cài lại Python từ python.org và mở PowerShell mới.

### 2.2. Cài Node.js nếu muốn build frontend

Tải Node.js LTS từ `https://nodejs.org/`.
Kiểm tra:

```powershell
node --version
npm --version
```

Không có Node.js vẫn được.
Repo đã có `frontend/dist`; khi dựng gói thêm `--skip-frontend` để dùng bản có sẵn.

### 2.3. Lấy mã nguồn

Chép thư mục repo sang máy, hoặc clone:

```powershell
git clone <địa-chỉ-repo> D:\RAG-TC-DL
cd D:\RAG-TC-DL
```

Kiểm tra file `windows\build_bundle.py` có tồn tại.

### 2.4. Tạo thư mục làm việc

```powershell
mkdir D:\QTKD-RAG
```

Thư mục này chứa gói cài tạm.
Sau khi cài xong và kiểm tra ổn, có thể xoá gói cài để lấy lại dung lượng, hoặc giữ lại để cài lại nhanh.

## 3. Dựng gói cài

Mở PowerShell tại thư mục repo:

```powershell
cd D:\RAG-TC-DL
python windows\build_bundle.py --out D:\QTKD-RAG\bundle --zip
```

Nếu máy không có Node.js:

```powershell
python windows\build_bundle.py --out D:\QTKD-RAG\bundle --zip --skip-frontend
```

Muốn cài offline hoàn toàn ở bước sau, thêm `--with-models`:

```powershell
python windows\build_bundle.py --out D:\QTKD-RAG\bundle --zip --with-models
```

Kết quả:

```
D:\QTKD-RAG\bundle\
  app\                  mã nguồn + frontend\dist + TC_DL + build\spike_a
  runtime\python\       CPython 3.12 portable
  tools\qdrant\         qdrant.exe
  tools\postgres\       PostgreSQL portable
  tools\ollama\         ollama.exe
  tools\ruby\           Ruby + gem
  wheels\               wheel Python cho win_amd64 / CPython 3.12
  models\               model (chỉ khi dùng --with-models)
  manifest.json
  CaiDat.bat
  DOC-TRUOC.txt
```

Vì chạy trên Windows, script cài Ruby và gem `mathtype_to_mathml` vào `tools\ruby` ngay trong gói.
Bước cài sau đó không cần tải Ruby từ Internet.

Các tùy chọn:

| Tùy chọn | Khi nào dùng |
|---|---|
| `--skip-frontend` | Không có Node.js; dùng `frontend/dist` có sẵn |
| `--with-models` | Muốn cài offline hoàn toàn; gói tăng khoảng 9-10GB |
| `--zip` | Tạo thêm tệp .zip để lưu trữ hoặc chép sang máy khác |
| `--skip-wheels` | Đã có sẵn `wheels/` đầy đủ, không tải lại |
| `--skip-downloads` | Dùng lại artifact trong `dist\cache` |

Lần dựng đầu tải khoảng 5GB, chủ yếu là wheel torch CUDA 2,86GB, Ollama 1,7GB và PostgreSQL 338MB.
Thời gian tùy mạng, thường 10-30 phút.
Các lần dựng sau dùng lại `dist\cache` nên nhanh hơn.

Nếu dựng gói bị lỗi giữa chừng, chạy lại cùng lệnh.
Nếu thư mục `D:\QTKD-RAG\bundle` đã có dữ liệu, chọn thư mục khác hoặc xoá thư mục đó trước.

## 4. Cài đặt

Chạy bộ cài ngay trên máy vừa dựng gói:

```powershell
cd D:\QTKD-RAG\bundle
.\CaiDat.bat
```

Nếu Windows SmartScreen hoặc antivirus cảnh báo, chọn **More info** rồi **Run anyway**, hoặc thêm thư mục gói vào danh sách loại trừ.

Bộ cài hỏi:

```
Tên đăng nhập quản trị [admin]:
Mật khẩu quản trị (ít nhất 8 ký tự):
Nhập lại mật khẩu:
```

Sau đó bộ cài tự làm:

1. Chép chương trình vào `%LOCALAPPDATA%\QTKD-RAG`.
2. Cài Python deps từ `wheels\`, không cần mạng.
3. Sinh `.env` với mật khẩu, JWT, Qdrant key ngẫu nhiên và cổng trống.
4. Khởi tạo PostgreSQL trong `data\postgres`, tạo CSDL `qtkd`.
5. Dùng Ruby và gem đã có trong gói.
6. Tải model embedding, reranker và LLM, tổng khoảng 9-10GB, hoặc dùng model có sẵn nếu dựng gói bằng `--with-models`.
7. Chạy migration, đăng ký tài liệu, tạo tài khoản quản trị và index.
8. Tạo shortcut Desktop/Start Menu và mục gỡ cài trong Settings > Apps.

Cuối cùng bộ cài hỏi có mở ứng dụng ngay không.
Chọn `Y` để mở, hoặc mở shortcut **QTKD RAG** sau.

### 4.1. Cài không tương tác

```powershell
$env:QTKD_ADMIN_PASSWORD="mat-khau-it-nhat-8-ky-tu"
.\CaiDat.bat --admin-user admin --start
```

Không truyền mật khẩu trực tiếp bằng `--admin-password` trên máy nhiều người dùng, vì mật khẩu sẽ hiện trong danh sách tiến trình.

### 4.2. Cài offline hoàn toàn

Điều kiện: gói được dựng bằng `--with-models`.
Vì bước dựng đã chạy trên Windows, Ruby và gem cũng đã nằm trong gói.

```powershell
.\CaiDat.bat --offline
```

Nếu gói thiếu model hoặc gem, bộ cài dừng với thông báo rõ thay vì tải ngầm.

### 4.3. Cài nhanh để kiểm tra máy

```powershell
.\CaiDat.bat --skip-models --skip-ruby
```

Bộ cài bỏ qua model và index, chỉ kiểm tra chép file, pip, PostgreSQL và migration.
Dùng để chẩn đoán trước khi chạy cài đầy đủ.

## 5. Kiểm tra sau cài

1. Mở shortcut **QTKD RAG** trên Desktop hoặc Start Menu.
2. Cửa sổ đen hiện tiến trình từng dịch vụ:

```
Khởi động QTKĐ RAG...
  [postgres] ...
  [qdrant] ...
  [ollama] ...
  [reranker] ...
  [embedding] ...
  [api] ...
Sẵn sàng: http://127.0.0.1:8080
```

Lần đầu chậm vì Ollama nạp LLM khoảng 5GB lên GPU.
Trình duyệt tự mở khi API sẵn sàng.

3. Đăng nhập bằng tài khoản đã tạo ở bước cài.
4. Hỏi thử: `Sai số cho phép khi kiểm tra van an toàn là bao nhiêu?`
5. Kiểm tra tab **Tài liệu**: các tài liệu đã index có trạng thái sẵn sàng.

Kiểm tra nhanh bằng dòng lệnh:

```powershell
& "$env:LOCALAPPDATA\QTKD-RAG\QTKD-RAG.bat" status
```

Kết quả mong đợi:

| Dịch vụ | Địa chỉ kiểm tra |
|---|---|
| API | `http://127.0.0.1:8080/api/health` |
| embedding | `http://127.0.0.1:8010/health` |
| reranker | `http://127.0.0.1:8011/health` |
| qdrant | `http://127.0.0.1:6333/healthz` |
| ollama | `http://127.0.0.1:11434/api/tags` |

## 6. Sử dụng hằng ngày

Các lệnh dưới đây dùng đường dẫn đầy đủ, chạy được từ PowerShell ở bất kỳ thư mục nào.

| Việc | Cách làm |
|---|---|
| Chạy | Nháy đúp shortcut **QTKD RAG**, hoặc `& "$env:LOCALAPPDATA\QTKD-RAG\QTKD-RAG.bat"` |
| Dừng | Nhấn `Ctrl+C` trong cửa sổ QTKĐ RAG |
| Kiểm tra dịch vụ | `& "$env:LOCALAPPDATA\QTKD-RAG\QTKD-RAG.bat" status` |
| Index lại tài liệu | `& "$env:LOCALAPPDATA\QTKD-RAG\QTKD-RAG.bat" index` |
| Chạy migration | `& "$env:LOCALAPPDATA\QTKD-RAG\QTKD-RAG.bat" migrate` |
| Tải bổ sung model | `& "$env:LOCALAPPDATA\QTKD-RAG\QTKD-RAG.bat" models` |

Nên dừng bằng `Ctrl+C` để PostgreSQL đóng sạch.
Đóng cửa sổ bằng dấu X sẽ dừng các tiến trình con do QTKĐ RAG khởi động, nhưng PostgreSQL có thể vẫn chạy; lần sau ứng dụng sẽ dùng lại.

## 7. Cấu hình sau khi cài

| File | Nội dung |
|---|---|
| `%LOCALAPPDATA%\QTKD-RAG\app\.env` | Cổng, mật khẩu, JWT, Qdrant key, URL dịch vụ |
| `%LOCALAPPDATA%\QTKD-RAG\app\config\settings.yaml` | Tham số truy hồi, LLM, ingestion, API |
| `%LOCALAPPDATA%\QTKD-RAG\data\` | Dữ liệu người dùng |

Các cổng mặc định:

| Dịch vụ | Cổng |
|---|---|
| API + React | 8080 |
| Embedding | 8010 |
| Reranker | 8011 |
| Qdrant HTTP / gRPC | 6333 / 6334 |
| Ollama | 11434 |
| PostgreSQL | 55432 |

Bộ cài tự chọn cổng khác nếu cổng mặc định đang bận.
Mặc định mọi dịch vụ chỉ nghe `127.0.0.1`.

Muốn máy khác trong LAN truy cập, đổi trong `app\.env`:

```
API_HOST=0.0.0.0
```

Sau đó mở cổng 8080 trên Windows Firewall và giữ `AUTH_ENABLED=true`.
Chỉ nên làm việc này trong mạng nội bộ tin cậy.

## 8. Nâng cấp

1. Đóng ứng dụng bằng `Ctrl+C`.
2. Cập nhật mã nguồn trong `D:\RAG-TC-DL`.
3. Dựng gói mới vào thư mục mới, ví dụ `D:\QTKD-RAG\bundle-2`.
4. Chạy `CaiDat.bat` của gói mới.

Bộ cài giữ nguyên `.env`, `data\`, tài khoản và tài liệu.
Chỉ thay `app\`; nếu phiên bản thành phần đổi (`tools_key` trong `manifest.json`), `runtime\`, `tools\`, `wheels\` cũng được thay.

Nếu cổng 8080 đang bận, bộ cài báo ứng dụng cũ chưa đóng.
Sau khi nâng cấp thành công, có thể xoá gói cũ.

## 9. Sao lưu và khôi phục

Sao lưu:

1. Dừng ứng dụng bằng `Ctrl+C`.
2. Chép `%LOCALAPPDATA%\QTKD-RAG\data`.
3. Chép `%LOCALAPPDATA%\QTKD-RAG\app\.env` để giữ mật khẩu, JWT và Qdrant key.

Dữ liệu gồm tài liệu gốc, Markdown, PostgreSQL, Qdrant, sổ công thức SQLite và model.
Không cần sao lưu `runtime\`, `tools\`, `wheels\`, `app\` vì cài lại được.

Khôi phục:

1. Cài bản tương ứng.
2. Dừng ứng dụng.
3. Chép `data` và `.env` trở lại.
4. Chạy kiểm tra trạng thái rồi mở ứng dụng.

Không chép `data\postgres` hoặc `data\qdrant` khi hai bản dùng phiên bản PostgreSQL/Qdrant khác nhau.
Nếu nâng phiên bản các thành phần, nên xử lý lại tài liệu trong tab **Tài liệu** rồi index lại.

## 10. Gỡ cài

Mở **Settings > Apps > Installed apps**, tìm **QTKD RAG**, chọn **Uninstall**.
Hoặc chạy trong PowerShell:

```powershell
$root = "$env:LOCALAPPDATA\QTKD-RAG"
& "$root\runtime\python\python.exe" "$root\app\windows\uninstall.py" --root $root
```

Mặc định giữ `data\`.
Thêm `--remove-data` để xoá cả tài liệu, chỉ mục và CSDL.

## 11. Xử lý sự cố

| Hiện tượng | Nguyên nhân và cách xử lý |
|---|---|
| `python` mở Microsoft Store | Chưa cài Python thật. Cài từ python.org, chọn Add to PATH, mở PowerShell mới |
| `npm` không tìm thấy | Không có Node.js. Dựng gói với `--skip-frontend` |
| Dựng gói lỗi khi tải wheel | Mạng/proxy chặn PyTorch. Kiểm tra mạng, chạy lại; xoá `dist\cache` nếu tệp hỏng |
| `--out` báo đã có dữ liệu | Thư mục gói không rỗng. Chọn thư mục mới hoặc xoá thư mục cũ |
| Hết dung lượng khi dựng gói | Cần khoảng 15GB cho gói và cache; dọn ổ hoặc đổi `--out` sang ổ khác |
| Hết dung lượng khi cài | Bản cài và model cần khoảng 30GB; kiểm tra ổ chứa `%LOCALAPPDATA%` |
| Cổng 8080/8010/8011 đang bận | Ứng dụng cũ chưa đóng. Nhấn Ctrl+C ở cửa sổ cũ rồi chạy lại |
| `torch` báo CUDA: KHÔNG | Driver NVIDIA cũ hoặc không có GPU. Cập nhật driver; kiểm tra `nvidia-smi` |
| `ImportError: DLL load failed`, thiếu `msvcp140.dll` | Thiếu VC++ Redistributable. Cài `https://aka.ms/vs/17/release/vc_redist.x64.exe` |
| Ollama chạy CPU | VRAM bị giữ bởi ứng dụng khác. Đóng bớt ứng dụng, khởi động lại |
| PostgreSQL không lên | Xem `data\logs\postgres.log`; kiểm tra ổ đĩa còn trống; không chạy hai bản cùng `data` |
| Upload `.docx` không ra công thức | Kiểm tra `RUBY_BIN` trong `app\.env`; chạy `tools\ruby\bin\ruby.exe -e "require 'mathtype_to_mathml'"` |
| Upload `.doc` báo thiếu LibreOffice | Cài LibreOffice rồi chạy lại; bộ cài tự tìm `soffice.exe` trên PATH hoặc registry |
| Upload `.pdf` báo `MarkerNotConfigured` | Cài môi trường Marker theo `requirements-pdf.txt`, đặt `MARKER_PYTHON` trong `.env` |
| SmartScreen/antivirus chặn | Chọn More info > Run anyway; thêm thư mục cài vào loại trừ; tốt nhất là ký số gói phát hành |
| Ứng dụng chạy nhưng chat lỗi | Kiểm tra trạng thái dịch vụ; xem `data\logs\api.log` và log dịch vụ tương ứng |
| Tài liệu hiện pending | Bấm xử lý trong tab Tài liệu; `.docx` cần Ruby, `.doc` cần LibreOffice, `.pdf` cần Marker |

Log của từng dịch vụ nằm trong `%LOCALAPPDATA%\QTKD-RAG\data\logs\`.

## 12. Giới hạn đã biết

- Bộ cài chỉ index những Markdown có sẵn trong gói (hiện là bộ mẫu 7 tài liệu).
  Các tài liệu còn lại được đăng ký ở trạng thái pending và cần xử lý trong tab Tài liệu.
- LibreOffice và Marker là thành phần tùy chọn, không nằm trong gói mặc định.
- Chưa chạy end-to-end trên Windows thật trong môi trường phát triển.
  Lần cài đầu trên một máy Windows sạch cần được kiểm tra kỹ.
- Gói chưa được ký số, nên SmartScreen có thể cảnh báo.
- Chưa có tự động cập nhật; nâng cấp bằng cách dựng gói mới và chạy `CaiDat.bat`.

## 13. Câu lệnh tóm tắt

```powershell
# Dựng gói
cd D:\RAG-TC-DL
python windows\build_bundle.py --out D:\QTKD-RAG\bundle --zip

# Cài đặt
cd D:\QTKD-RAG\bundle
.\CaiDat.bat

# Chạy
& "$env:LOCALAPPDATA\QTKD-RAG\QTKD-RAG.bat"

# Kiểm tra
& "$env:LOCALAPPDATA\QTKD-RAG\QTKD-RAG.bat" status

# Index lại
& "$env:LOCALAPPDATA\QTKD-RAG\QTKD-RAG.bat" index

# Gỡ cài, giữ dữ liệu
$root = "$env:LOCALAPPDATA\QTKD-RAG"
& "$root\runtime\python\python.exe" "$root\app\windows\uninstall.py" --root $root
```

Nếu muốn dùng cho một máy Windows khác, chép thư mục `D:\QTKD-RAG\bundle` sang máy đó và chạy `CaiDat.bat`.
Mỗi máy có `data\` và tài khoản riêng.

Xem thêm tài liệu tham chiếu đầy đủ tại `windows\README.md`.
