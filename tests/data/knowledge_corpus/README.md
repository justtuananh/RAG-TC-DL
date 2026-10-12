# Corpus tài liệu tổng hợp

Bộ 51 tài liệu hư cấu (số hiệu QTKĐ dải 9.001..9.099, không trùng số hiệu thật) dùng làm fixture cho các test ingestion trong `tests/unit/ingestion/test_corpus_*.py`.
Nội dung dựa trên `docs/superpowers/research/2026-09-25-mau-tai-lieu-do-luong.md` nhưng được viết lại, không sao chép nguyên văn `TC_DL/`.
Builder sinh bộ này đã gỡ cùng luồng trích xuất tri thức (2026-10-12); các tệp được đóng băng, không sửa tay.

## Cấu trúc

```
tests/data/knowledge_corpus/
  files/<tên file>   # tài liệu đã render (docx/xlsx/pdf/doc/xls)
  manifest.jsonl     # id, file, nhóm, loại tài liệu và kết quả ingest mong đợi, số hiệu QTKĐ
```

## Thành phần

| Nhóm | Số lượng | Mô tả |
|---|---|---|
| A | 12 | QTKĐ docx sạch, số hiệu 9.001..9.012. |
| B | 9 | QTKĐ docx biên (đầu mục, style tiêu đề, bảng lạ). |
| C | 3 | QTKĐ pdf (soffice từ 9.001/9.002/9.003). |
| D | 14 | Biên bản kiểm định docx. |
| E | 8 | Phiếu đo xlsx. |
| F | 3 | Trùng hash, phiên bản 2, tên chứa cả "QTKD" và "biên bản". |
| G | 2 | .doc/.xls hợp lệ, chuyển bằng soffice khi xử lý. |

## Test dùng bộ này

- `test_corpus_integrity.py`: tệp khớp manifest, số tệp theo nhóm, định dạng hợp lệ.
- `test_corpus_classify.py`: phân loại tài liệu từ tên file khớp `expected_doc_type`.
- `test_corpus_ingest_gate.py`: upload nhận .docx/.doc/.pdf, chặn .xlsx/.xls và tệp trùng sha256.
- `test_corpus_procedure_header.py`: đầu mục QTKĐ nhóm A/B/F và phiên bản mới thay dòng `procedure`.
