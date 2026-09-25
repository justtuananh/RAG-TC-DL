# Kế hoạch test: bộ test lớp tri thức trên corpus tổng hợp

Ngày: 2026-09-25.
Tiếp nối `docs/superpowers/plans/2026-09-25-knowledge-test-corpus.md` (pha 3).
Người thực thi: subagent Claude Haiku; Claude (Opus) review và bắt làm lại tới khi đạt.

## Đầu vào

- Corpus: `tests/data/knowledge_corpus/` (`files/`, `manifest.jsonl`, `gold/extract_golden.jsonl`, `gold/extract_golden_section6.jsonl`, `gold/records_golden.jsonl`).
- Hợp đồng định dạng và mã hành vi K01..K15: `docs/superpowers/research/2026-09-25-knowledge-input-contract.md`.
- Mẫu test hiện có để bắt chước (fixture SQLite, seed đơn vị, duyệt extraction): `tests/unit/backend/conftest.py`, `test_extraction_db.py`, `test_llm_extract_db.py`, `test_records_readers.py`, `test_records_store.py`, `test_records_matching.py`, `test_review_queue.py`, `test_document_classify.py`.

## Nguyên tắc

1. Mọi test so với giá trị gold hoặc manifest cụ thể; không có test chỉ kiểm "không crash".
2. Test ghi hành vi **đúng theo spec** (tức theo gold).
3. Khi code hiện tại sai ở một mã K, test đó mang `pytest.mark.xfail(strict=True, reason="Kxx: <current> -> <expected>")`, với lý do lấy từ `manifest.known_behaviors`.
   Như vậy test tự đỏ (XPASS strict) khi lỗi được sửa, nhắc gỡ xfail.
4. Không sửa code sản phẩm, không sửa test cũ, không sửa corpus.
   Nếu corpus/gold sai, báo lại cho điều phối viên thay vì tự sửa.
5. Không tái cài đặt logic chấm điểm: dùng lại `eval.extract_eval` (khoá khớp) và `eval.extract_section6_eval` (`build_scripted_payload`, `ScriptedClient`).
6. Không mạng, không Docker, không Ollama; SQLite in-memory; tất định.
7. Tổng thời gian suite mới dưới 60 giây; chuyển docx sang Markdown một lần mỗi session (fixture `scope="session"` với `tmp_path_factory`).

## Bố cục

```
tests/unit/knowledge_corpus/
  __init__.py
  conftest.py                  # đường dẫn corpus, nạp manifest/gold, helper known(code) -> marks xfail, fixture md theo session, fixture DB
  test_corpus_integrity.py
  test_classify_corpus.py
  test_ingest_gate_corpus.py
  test_procedure_header_corpus.py
  test_rules_corpus.py
  test_section6_corpus.py
  test_records_corpus.py
  test_device_matching_corpus.py
  test_supersede_corpus.py
```

## Các test cần viết

### T1. `test_corpus_integrity.py`

- Tập tên file trong `files/` bằng đúng tập `file` trong manifest.
- Số file theo nhóm: A=12, B≥8, C=3, D=14, E=8, F=3, G=2 (lấy từ manifest, kiểm tổng 48..55).
- Mọi `.docx`/`.xlsx` là zip hợp lệ có `word/document.xml` hoặc `xl/workbook.xml`; `.pdf` bắt đầu bằng `%PDF`.
- Mọi `doc` trong hai file gold extract khớp stem đã làm sạch của một file nhóm A/B trong manifest; mọi `file` trong `records_golden` có trong manifest nhóm D/E.
- Mọi mã K trong `known_behaviors` có trong bảng mục 6 của contract.
- Mỗi mã K01..K13 và K15 xuất hiện ở ít nhất một file trong manifest (trừ K08 có thể chỉ ở F02).

### T2. `test_classify_corpus.py`

- Tham số hoá theo manifest: `classify_document(file).doc_type == expected_doc_type` (chỉ tên file, như upload thật).

### T3. `test_ingest_gate_corpus.py`

- G01/G02: `ingestion.spike_a.process_one` trả trạng thái `skipped-legacy`; `ingestion_jobs.save_upload` từ chối (`UploadError`).
  Phải cô lập thư mục upload/DB của `ingestion_jobs` bằng `monkeypatch`/`tmp_path` theo cách test hiện có làm.
- F01: sha256 bằng sha256 của A01; nạp A01 rồi F01 qua `save_upload` thì lần hai bị chặn là trùng.
- Mọi file `expected_ingest == "ok"` có đuôi được upload chấp nhận (`.docx`/`.pdf`) thì `save_upload` nhận; `.xlsx` ghi đúng hành vi hiện tại theo contract mục 1 (không nhận ở upload).

### T4. `test_procedure_header_corpus.py`

- Với mọi file nhóm A, B, F (docx): `parse_procedure_header(markdown)` cho `number == procedure_number` trong manifest và tiêu đề không rỗng.
- B01 (K11) mang xfail strict.

### T5. `test_rules_corpus.py`

- Nhóm A, tham số hoá theo từng tài liệu: tập khoá dự đoán từ `knowledge.rules.extract_all` (hoặc `knowledge.extract.run_rules`) bằng đúng tập khoá gold của tài liệu đó, theo từng fact kind, dùng hàm khoá của `eval.extract_eval`.
- Nhóm A, gộp: precision ≥ 0,95 và recall ≥ 0,80 cho từng fact kind (cổng spec).
- Nhóm B, tham số hoá theo (tài liệu, fact kind): so với gold; cặp nào chạm mã K của tài liệu đó thì mang xfail strict; các cặp còn lại phải đạt, để chứng minh lỗi chỉ cục bộ.
- Riêng B07 (Bảng 2 tách "kết thúc"): số chuẩn đo lường bằng tổng hai bảng; B08 (số kiểu Việt): `value_text` và giá trị số đúng như gold.

### T6. `test_section6_corpus.py`

- Với mỗi tài liệu nhóm A có gold §6: `find_section6` tìm được mục; `extract_section6` với `ScriptedClient(build_scripted_payload(items, inject_hallucinations=True))` cho tập fact đã xác minh khớp gold theo quote chuẩn hoá; mọi fact bịa bị loại; `numeric_hallucinations == 0`.
- Tài liệu có hai mức sai số (9.004, 9.006, 9.008, 9.010) cho đúng hai fact.

### T7. `test_records_corpus.py`

- Pipeline thật trên SQLite: tạo `Document` cho QTKĐ nguồn, `extract_appendix_and_store`, duyệt các extraction `appendix_field`, `derive_mapping_config`, rồi `read_docx`/`read_xlsx` và `store_record_draft`.
- So `CalibrationRecord` và `MeasurementPoint` với `records_golden`: serial, model, hãng, đơn vị sử dụng, ngày (ISO), chế độ, kết luận, nhiệt độ, độ ẩm, và từng điểm đo (thứ tự, danh nghĩa, đo, sai số, giới hạn).
- File mang mã K trong manifest thì các trường bị ảnh hưởng mang xfail strict; trường không bị ảnh hưởng phải đạt.
- K09: một test riêng khẳng định điểm đo có `unit_id` đúng đơn vị của QTKĐ, mang xfail strict.
- E05: chỉ dữ liệu sheet đầu được đọc (giá trị từ sheet 2 không xuất hiện).

### T8. `test_device_matching_corpus.py`

- Nạp toàn bộ D/E vào cùng một DB.
- D04 (`sn-2026-201`) và D05 (`SN-2026-201`) cùng QTKĐ thì cùng một `Device`.
- Hồ sơ thiếu số hiệu (D03, D09) mỗi cái tạo thiết bị mới với `needs_identification` bật.
- Số thiết bị cuối cùng bằng số cặp (loại thiết bị, serial chuẩn hoá) khác nhau tính từ `records_golden`, cộng số hồ sơ thiếu serial.

### T9. `test_supersede_corpus.py`

- Trích lại cùng tài liệu A01 bằng luật: extraction luật cũ thành superseded, extraction mới pending; phần K08 (supersede cả extraction LLM/Phụ lục A) mang xfail strict khẳng định chúng không bị supersede.
- Nạp F02 sau A01: `Procedure 9.001` trỏ tới document của F02; fact đã duyệt của A01 bị superseded mang xfail strict (K08).

## Tiêu chí nghiệm thu (Claude review)

1. `.venv-dev/bin/python -m pytest tests/unit/knowledge_corpus -q` xanh (chỉ có passed và xfailed; không skipped, không xpassed, không error).
2. `make test-unit` xanh toàn bộ, chạy 3 lần liên tiếp đều xanh.
3. `make lint` sạch.
4. Suite mới dưới 60 giây (`--durations=10` để xem).
5. Mỗi `xfail` có `strict=True` và lý do chứa mã K lấy từ manifest; không có xfail nào không gắn mã K.
6. Kiểm đột biến bằng tay: sửa tạm một giá trị trong gold (ví dụ chu kỳ 12 thành 13 tháng) thì ít nhất một test đỏ; hoàn tác sau khi kiểm.
7. Hàm dưới khoảng 50 dòng, file dưới 800 dòng, không `print`, theo phong cách test hiện có (docstring tiếng Việt).
