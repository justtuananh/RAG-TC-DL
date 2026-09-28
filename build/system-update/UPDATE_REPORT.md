# Cập nhật hệ thống sau luồng phê duyệt và audit bias

## Đã thay đổi

- README gốc và FE được viết lại theo API thật, cách dùng công thức, giới hạn, lưu trữ và luồng Docker/local; bỏ mô tả mock-only và tuyên bố chỉ tra cứu áp dụng cho toàn bộ ứng dụng.
- Bổ sung `requirements-app.lock` cho Python3.12, dùng chung Docker/local/CI. Khai báo Pydantic2 rõ ràng, bỏ pin dev dựa trên `.search()` cũ; giữ Gradio major5 và chuẩn hóa messages protocol.
- FE chuyển Node24, Vite7.3.6/pluginReact5.2.0/Vitest4.1.11, cùng một Vite; npm lock được cập nhật và `npm ci` cài lại thành công. Dev/preview dùng chung proxy theo API_PORT.
- Docker API có registry, engine và dữ liệu template; mặc định chạy API8080, bind-mount SQLite qua FORMULA_REGISTRY_DIR, healthcheck API. Docker FE typecheck trước build; thêm ignore để không đưa node_modules/venv/DB và env vào build context.
- CI có unit/lint/fidelity Python, FE tests/build, và job build hai image + kiểm import/route trong API image. Không tải model/GPU cho job kiểm đóng gói.
- run.sh ưu tiên venv dự án có đủ API runtime; Makefile thêm lệnh công thức, lock runtime, kiểm FE và Docker. Hướng dẫn lưu trữ/sao lưu trong docs/SYSTEM_DEPENDENCIES.md.

## Kiểm tra đã chạy

| Kiểm tra | Kết quả |
|---|---|
| Cài runtime lock và pip check | Qua |
| Python unit suite | 204 đạt, 1 bỏ qua adapter kotaemon thiếu gói tùy chọn |
| Lint/format + fidelity artifact | Qua; fidelity đọc artifact lịch sử, không đo lại khả năng trích xuất hiện tại |
| Gradio UI construction | Qua với type=messages |
| FE | 47/47, typecheck/lint/build qua; npm ci qua |
| npm audit | 0 lỗ hổng được báo tại thời điểm kiểm; không phải chứng nhận an toàn |
| Proxy dev/preview | GET/POST và SPA qua ở cổng tạm |
| API + React mới | Qua trên nguồn thật, chỉ đọc; 7DOCX/334pending giữ nguyên |
| Compose/CI YAML, registry mount | Qua kiểm cấu trúc |
| Bố cục COPY Docker trong thư mục cô lập | Import API/registry/template qua |
| Docker image build/runtime | **Chưa chạy**, máy không có Docker CLI/daemon; CI job đã thêm nhưng chưa chạy trên CI |
| Model/GPU và các dịch vụ RAG thật | Không kiểm lại trong lượt này |

Lần chạy unit đầu có3 lỗi test Gradio dùng lịch sử tuple cũ trong khi handler đã dùng message dictionaries. Đã đổi fixture sang giao thức hiện hành, giữ các kỳ vọng về câu trả lời/citation/lỗi. Đồng thời sửa nhánh từ chối tính của UI cũ để thêm assistant message đúng định dạng và thêm test chặn retrieval/LLM. Hai lỗi lint trong test OMML chỉ được sửa định dạng/import, không đổi kỳ vọng. Đây là sửa tương thích/hồi quy sau holdout, không dùng để nâng điểm đánh giá độc lập.

## Kết luận đánh giá được đính chính

[Audit bias](../formula-review/BIAS_AUDIT.md) đã rút cách diễn giải96% như chất lượng/năng lực. Giữ lịch sử cũ để truy vết và đánh dấu ngay đầu báo cáo/tiêu chí/tiến độ. Holdout đã khóa và chạy trước khi đổi các file triển khai của lượt này; kết quả không được ghi đè.

25/32 ca pass thô không dùng làm điểm chất lượng: có2 quan sát thực (độ chính xác slope khi offset lớn, chưa kiểm thứ nguyên biểu thức),3 lỗi thiết kế test và2 ca UI bị chặn bởi harness. **Hai quan sát thực chưa được sửa trong lượt cập nhật đóng gói/thư viện này**, đã ghi thành giới hạn trong hướng dẫn công thức. Không khẳng định bộ runtime mới đạt96% hoặc đã được đánh giá mù lại.

Chi tiết phiên bản, hashes và kết quả: [verification.json](verification.json), [packaging-check.json](packaging-check.json), [runtime-smoke.json](runtime-smoke.json), [make-check.log](make-check.log).
