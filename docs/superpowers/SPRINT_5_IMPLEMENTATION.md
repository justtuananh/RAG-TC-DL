# Sprint 5 — Trích xuất bằng LLM cho mục 6

## Đã triển khai

- `knowledge/llm_extract.py`: trích xuất §6 Tiến hành kiểm định bằng LLM, gồm:
  - **Schema pydantic**: `NumericClaim(value, unit, quote)` buộc MỌI trường số đi
    kèm `quote`; `Section6Fact` cho `max_permissible_error` (có `limit` và tùy
    chọn `floor`) và `formula`.
  - **Bộ xác minh**: `locate_quote` khớp nguyên văn, rồi khớp sau khi chuẩn hóa
    dấu cách (gồm NBSP U+00A0 và khoảng trắng hẹp không ngắt U+202F), trả khoảng
    ký tự gốc để giữ P1. `verify_fact` từ chối dòng có quote không tìm thấy hoặc
    quote không chứa đúng con số đã khai.
  - **Chấm điểm tin cậy**: cộng dồn bốn thành phần — khớp nguyên văn (0,45), số
    hợp lệ (0,20), đơn vị nhận diện được (0,15), giá trị nằm trong khoảng hợp lý
    so với phạm vi đo của chính QTKĐ (0,20). Đơn vị lạ hoặc giá trị ngoài phạm vi
    bị trừ đúng phần tương ứng.
  - **Client Ollama** (`OllamaClient`): gọi `/api/chat` native, cấu hình qua
    `SECTION6_*` / `OLLAMA_*`, **thất bại an toàn** — mọi lỗi/kết nối trả `None`,
    `extract_section6` trả kết quả rỗng kèm `error`, không ném ra ngoài.
  - `numeric_hallucinations(result, text)` là thước đo hồi quy "0 bịa số".
- `knowledge/vnnum.py`: thêm `numbers(text)` (danh sách số trong câu) phục vụ
  xác minh quote chứa đúng con số.
- `knowledge/extract.py`: `extract_section6_and_store` ánh xạ dữ kiện §6 ĐÃ XÁC
  MINH sang `extraction` + `procedure_fact` ở trạng thái `pending`. Dòng sai số
  có thể sinh hai `procedure_fact` cùng một extraction (giới hạn + giá trị sàn,
  spec §5.4). Supersede tách riêng theo tiền tố `llm:` nên không vô hiệu hóa dòng
  luật trong cùng lần nạp.
- `ingestion_jobs._run_extraction`: sau bộ luật, nếu `SECTION6_LLM_ENABLED` bật
  thì chạy §6 trong SAVEPOINT và thất bại an toàn; mặc định tắt để ingestion
  không phụ thuộc Ollama.
- `scripts/extract_section6.py`: đường batch ngoài giờ (mặc định dry-run,
  `--apply` để ghi pending); `make extract-section6`.
- `eval/extract_section6_eval.py` + `eval/extract_golden_section6.jsonl`: cổng
  eval §6 (mặc định client kịch bản có chèn dòng bịa để chứng minh hàng rào;
  `--live` để đo model thật).
- `make extract-section6-eval` được thêm vào `make check`.

## Bất biến

- **P1**: mọi dòng đều có `document_id`, `section_path`, `quote` nguyên văn và
  `char_start`/`char_end` khi khớp chính xác.
- **P2**: module chỉ đọc nguyên văn; quy đổi SI chỉ chạy khi đơn vị chắc chắn,
  không bao giờ tính lại số liệu nguồn.
- **P3**: mọi extraction §6 đều `pending`; bề mặt tra cứu chỉ đọc view đã duyệt.

## Cổng kiểm chứng

- `tests/unit/backend/test_llm_extract.py`: schema bắt buộc quote, quote nguyên
  văn/chuẩn hóa dấu cách, từ chối quote bịa, chấm điểm theo đơn vị/khoảng, client
  Ollama mock + thất bại an toàn, 0 bịa số lọt.
- `tests/unit/backend/test_llm_extract_db.py`: ghi `pending`, P3 view che tới khi
  duyệt, supersede tách khỏi dòng luật, nối `ingestion_jobs` khi bật/tắt cờ.
- `tests/unit/backend/test_extract_section6_eval.py`: cổng precision ≥ 0,90 và
  0 bịa số.

## Lệnh vận hành

```bash
make check                    # gồm extract-section6-eval
SECTION6_LLM_ENABLED=true ... # bật §6 khi ingestion
make extract-section6         # batch §6 cho QTKĐ đang có (dry-run: bỏ --apply)
```
