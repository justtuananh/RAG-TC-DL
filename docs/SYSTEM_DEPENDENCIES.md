# Môi trường, thư viện và đóng gói

## Runtime chính

Python3.12, React18, Node24, Vite7 và Tailwind3. Docker API dùng cùng `requirements-app.lock` với local/CI; Docker FE dùng `package-lock.json` và `npm ci`. Dải phiên bản có chủ đích ở `requirements-app.txt`; lock giữ cả phụ thuộc bắc cầu. Gradio được giữ major5 cho UI cũ, Chatbot khai báo `type="messages"` rõ ràng.

```bash
python3.12 -m venv .venv-dev
.venv-dev/bin/python -m pip install -r requirements-app.lock -r requirements-dev.txt
.venv-dev/bin/python -m pip check
cd frontend && npm ci
```

SQLite, Decimal và AST dùng thư viện chuẩn, không thêm database server hay bộ thực thi mã tùy ý. Không cài bộ LLM/SymPy của `formula_lab/requirements.lock` vào API chính chỉ để chạy registry.

## Khi nâng thư viện

1. Đổi dải phiên bản có chủ đích trong requirements hoặc package.json; đọc thay đổi tương thích của thư viện.
2. `make lock-runtime PY=.venv-dev/bin/python` cho Python; `npm install` rồi `npm ci` ở frontend để cập nhật/kiểm lock.
3. Cài lại runtime từ lock, `pip check`, `make check`, `make test-formula`, `make check-frontend`.
4. Trên máy có Docker: `make docker-check`; thử dữ liệu giả, kiểm API/FE và persistence qua lần tạo lại container. CI có job build API/FE, không dựng GPU/model.
5. Mọi thay đổi runtime sau một lượt holdout phải ghi nhận là phiên bản khác. Kiểm hồi quy không thay thế lượt giữ riêng mới có đáp án khóa trước.

Python lock được resolve trên Linux/Python3.12; không tuyên bố đã kiểm đủ mọi nền tảng. Base image Docker được ghim theo major, chưa ghim image digest. Ruby gem và inference image vẫn cần quản lý phiên bản riêng; cập nhật này không nâng Torch/model hoặc chứng minh tương thích GPU.

## Lý do bỏ các cấu hình cũ

- Registry dùng `ConfigDict`/`model_config` và strict fields của Pydantic2; khai báo rõ major thay vì phụ thuộc gián tiếp. [Pydantic migration](https://docs.pydantic.dev/latest/migration/).
- Mã truy hồi dùng `query_points`, không còn `.search()`. File dev không ép client1.10.1 theo nhận định `.search()` cũ; runtime vẫn giới hạn client major1. Query API có từ Qdrant1.10. [Qdrant API1.10](https://api.qdrant.tech/v-1-10-x/api-reference/search/query-points).
- Vitest4 yêu cầu Vite6 trở lên; root Vite5 và Vite khác lồng trong Vitest làm hai môi trường build/test không thống nhất. Bản cập nhật dùng Vite7 chung, giữ React18. [Vitest migration](https://vitest.dev/guide/migration.html).

## Dữ liệu cần sao lưu

Sao lưu cùng lúc `TC_DL/`, `build/spike_a/` và thư mục registry trên host (`FORMULA_REGISTRY_DIR`, mặc định `.formula-registry/`). Dừng API trước khi sao chép nguồn và SQLite để tránh lấy hai thời điểm khác nhau; khởi động lại sau sao lưu. Không dùng bản DB test tạm thay DB thật.

`FORMULA_REGISTRY_DB` trong container luôn trỏ `/app/.formula-registry/registry.sqlite3`; biến `.env` cho host là `FORMULA_REGISTRY_DIR`. Đổi host directory phải di chuyển DB hiện có có chủ đích, nếu không sẽ mở registry trống. Đường dẫn nguồn nằm trong repo lưu tương đối, nguồn ngoài repo cần giữ đường dẫn hoặc tạo lại nháp từ nguồn mới.

`/api/health` chỉ xác nhận tiến trình API sống, không xác nhận model/Qdrant sẵn sàng hoặc công thức đúng nghiệp vụ. Phê duyệt/tính dùng SQLite không cần model; chat RAG cần đầy đủ service.
