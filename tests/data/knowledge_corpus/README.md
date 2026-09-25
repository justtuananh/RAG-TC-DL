# Bộ dữ liệu test lớp tri thức (Pha 2)

Bộ ~50 tài liệu tổng hợp + gold cho lớp tri thức (phân loại tài liệu, trích xuất theo luật, trích xuất §6 bằng LLM, đọc biên bản/phiếu đo).
Toàn bộ tài liệu là hư cấu: số hiệu QTKĐ dùng dải 9.001..9.099, không trùng số hiệu thật.
Nội dung kỹ thuật dựa trên `docs/superpowers/research/2026-09-25-mau-tai-lieu-do-luong.md` nhưng được viết lại, không sao chép nguyên văn `TC_DL/`.

Tái tạo: `make knowledge-corpus` (hoặc `.venv-dev/bin/python -m scripts.knowledge_corpus.build`).
Builder chỉ dùng thư viện chuẩn + `lxml`; không cài thêm gì.

## Cấu trúc

```
scripts/knowledge_corpus/     # builder (đọc trong CLAUDE.md phần "Phạm vi được sửa")
tests/data/knowledge_corpus/
  specs/<id>.json              # nội dung từng tài liệu (nguồn của gold)
  files/<tên file>              # file đã render (docx/xlsx/pdf/doc/xls)
  manifest.jsonl                # id, file, nhóm, loại/ingest mong đợi, known_behaviors
  gold/extract_golden.jsonl            # đúng schema eval/extract_golden.jsonl
  gold/extract_golden_section6.jsonl   # đúng schema eval/extract_golden_section6.jsonl
  gold/records_golden.jsonl            # trường + điểm đo mong đợi của nhóm D/E
```

## Thành phần (50 file)

| Nhóm | Số lượng | Mô tả |
|---|---|---|
| A | 12 | QTKĐ docx sạch, 12 loại phương tiện (mục 7 tài liệu nghiên cứu mẫu), số hiệu 9.001..9.012. |
| B | 9 | QTKĐ docx biên, mỗi file nhắm một mã hành vi (K-code); B09 thêm sau review vòng 2 cho K15. |
| C | 3 | QTKĐ pdf (soffice từ 3 file nhóm A: 9.001/9.002/9.003). |
| D | 14 | Biên bản kiểm định docx (≥3 mỗi QTKĐ chính 9.001/9.002/9.003/9.005, +2 file nhắm K06/K07). |
| E | 8 | Phiếu đo xlsx (1 mỗi QTKĐ chính, +4 file nhắm đa-sheet/K01/K05/nhãn gộp ô). |
| F | 3 | Trùng hash, phiên bản 2, tên chứa cả "QTKD" và "biên bản". |
| G | 2 | .doc/.xls hợp lệ (qua soffice) - mong đợi `skipped-legacy`. |

### Gold nhóm A/B: suy TRỰC TIẾP từ spec (redo R1, không còn vòng tròn)

`scripts/knowledge_corpus/devices_a.py` chứa mọi chuỗi trích xuất mong đợi (`range.value_text`, `env` label/value, `terms[].vi/en`, `bang1[].label`, `bang2[].name/range`, `interval_months`, `section6[].limit/floor/quote`) làm NGUỒN DUY NHẤT.
`qtkd_doc.py` chỉ ghép các chuỗi đó vào câu văn (tiền tố + chuỗi, không định dạng lại số).
`gold_a.py` đóng gói lại ĐÚNG những chuỗi đó theo schema `eval/extract_golden.jsonl` - **không import `knowledge.rules` ở bất kỳ đâu trên đường này**.
Nhóm B dùng lại `gold_a.golden_rows_for_doc(stem, dev)` trên `dev` đã được từng ca biên cập nhật đúng nội dung thật được render (ví dụ B05 đổi hẳn `dev["env"]`); việc chạy `knowledge.rules` trong `build_b.py` chỉ để ĐO `known_behaviors` (hiện tại code trả gì), tách bạch khỏi việc sinh gold.
Việc dùng `knowledge.rules.phuluc_a` để dựng `MappingConfig` cho tự kiểm bước 4 vẫn được phép (không nằm trên đường gold được chấm ở bước 2/3); gold của D/E tiếp tục tính trong `content_records.synth_points` và dùng lại y nguyên cho cả nội dung file lẫn `records_golden.jsonl`.

## Kết quả tự kiểm (sau redo R1..R6)

Chạy `.venv-dev/bin/python -m scripts.knowledge_corpus.build` (hai lần) + các lệnh `eval.*` dưới thư mục tạm `logs/opencode/phase2_tmp/` (không commit).

1. **Tất định (sha256)**: build hai lần liên tiếp, so sha256 mọi `.docx`/`.xlsx` (45 file, không tính pdf/doc/xls do soffice sinh) - **giống hệt byte, ĐẠT**.
2. **`eval.extract_eval` trên nhóm A** (12 file, golden lọc theo nhóm A):

   | loại | trước (vòng 1, gold = auto extract_all) | sau (vòng 2, gold = spec) | P sau | R sau |
   |---|---|---|---|---|
   | working_range | 12 | 12 | 1.000 | 1.000 |
   | calibration_interval | 12 | 12 | 1.000 | 1.000 |
   | env_condition | 36 | 36 | 1.000 | 1.000 |
   | inspection_step | 36 | 44 | 1.000 | 1.000 |
   | standard | 26 | 39 | 1.000 | 1.000 |
   | term | 14 | 26 | 1.000 | 1.000 |
   | **tổng** | **136** | **169** | **1.000** | **1.000** |

   Số dòng vàng tăng do R4 (đa dạng hoá: 2-4 thuật ngữ/QTKĐ thay vì 1, 3-5 chuẩn Bảng 2 thay vì 2, 3-6 bước Bảng 1 thay vì 3).
   Cổng precision ≥ 0.95, recall ≥ 0.80 → **ĐẠT** cho mọi loại.
   **Lần chạy đầu của gold spec-derived (trước khi sửa `_section_1`) cho `working_range` 0/12 đúng - KHÔNG bị bẻ để khớp**: điều tra cho thấy câu "...đến 1 400 bar." (chấm câu ngay sau đơn vị, không có từ nào theo sau) khiến lớp ký tự đơn vị của `phamvi.py` (`[\w%°/²³.]*`, có chứa `.`) nuốt luôn dấu chấm câu vào đơn vị ("bar."), lệch khỏi gold "...bar". Đây là lỗi TÀI LIỆU (câu văn không tự nhiên, không giống văn phong QTKĐ thật vốn luôn có mệnh đề sau đơn vị) chứ không phải lỗi code trên tài liệu hợp lệ, nên đã **sửa tài liệu** (`_section_1` nay luôn thêm mệnh đề + dấu phẩy sau `value_text`) chứ không sửa gold. Không có K-code mới.
3. **`eval.extract_section6_eval` trên nhóm A**: `max_permissible_error` 14→16 dòng vàng (R4: thêm sai số vùng lưu lượng cao của 9.004, sai số khoảng cách của 9.008), 16/16/16 (P=1.000, R=1.000), `formula` 0 dòng, bịa số = 0. Cổng precision ≥ 0.90 → **ĐẠT**.
4. **Đọc D/E bằng `records.docx_reader`/`records.xlsx_reader`** với `MappingConfig` dựng từ nhãn/cột Phụ lục A thật của từng QTKĐ (`knowledge.rules.phuluc_a.extract`, chỉ dùng ở bước tự kiểm này), so với `records_golden.jsonl` (không đổi so với vòng 1 vì D/E không phụ thuộc trường đã sửa ở nhóm A):
   - 16/22 hồ sơ khớp tuyệt đối (mọi trường + mọi điểm đo).
   - 6/22 hồ sơ có sai khác, đúng như thiết kế để lộ K-code (xem bảng dưới) - tổng 18 điểm sai khác, tất cả đã ghi vào `manifest.jsonl` (`known_behaviors`).
5. **Số file**: `find tests/data/knowledge_corpus/files -type f | wc -l` = **51** (trong khoảng 48..55; `build.py` tự kiểm ở cuối rằng tập tên trong `files/` khớp CHÍNH XÁC tập `file` trong manifest, ở cả hai chế độ có/không `--no-soffice`, và dừng lỗi nếu lệch).

## R2..R5 đã sửa

- **R2** (`là là`): `qtkd_doc._section_terms` không còn tự thêm `"là "` trước `definition` (đã có sẵn trong spec) - xác minh `grep -rn "là là"` trên toàn bộ Markdown đã render = 0 kết quả.
- **R3** (Bảng 2 vô nghĩa): mọi chuẩn trong `devices_a.py["bang2"]` nay có `range` là khoảng đo thật (`"(0 ÷ 200) L"`, …) tách bạch khỏi `accuracy`; 3-5 chuẩn mỗi QTKĐ (đủ "Chuẩn sử dụng" + phụ trợ nhiệt kế/ẩm kế/barômét/đồng hồ bấm giây khi hợp lý).
- **R4** (đa dạng hoá): thêm mục "Tài liệu viện dẫn" (§2); 2-4 thuật ngữ/QTKĐ (một số kèm CHÚ THÍCH); Bảng 1 3-6 bước với ô để trống thay vì "+" khi không áp dụng Định kỳ (gold chỉ dùng `label`, không phụ thuộc mode - đúng `eval/extract_eval.py:golden_key`); điều kiện môi trường luân phiên 4 hồ sơ (`(A±B)`, "không lớn hơn X", "≤ X", `%RH` và `%`, `oC` và `°C`); phạm vi đo luân phiên `từ...đến`/`(...) đv`/`giới hạn đo...đến X`; đánh số mục luân phiên `"1 "`/`"1. "`/`"1) "`; §6.3 nay có đủ các câu MPE nghiên cứu đưa ra cho đồng hồ nước (2 vùng lưu lượng), công tơ điện (2 mức tải), nhiệt kế (2 vùng), máy đo tốc độ (tốc độ + khoảng cách).
- **R5** (bìa): bỏ dòng thừa "QTKĐ QUY TRÌNH KIỂM ĐỊNH"; bìa nay theo đúng thứ tự `build/spike_a/QTKD_1.061_2021_ND_V2.md` (mã QTKĐ, tên in hoa, "QUY TRÌNH KIỂM ĐỊNH", quyết định ban hành, "HÀ NỘI - 2026", tên thường, "Quy trình kiểm định").
- **R6**: build lại toàn bộ (D/E không đổi nội dung vì không phụ thuộc trường nhóm A đã sửa), chạy lại cả 5 tự kiểm + tất định - xem trên.

## Mã hành vi (K-code) và file minh hoạ

Không phát sinh K-code mới (K15+) - mọi sai lệch quan sát được trong vòng redo đều là lỗi tài liệu, đã sửa tài liệu (xem mục "Lần chạy đầu... " ở bước 2).

| Mã | File | Hiện tại (đo thật) | Đúng theo spec |
|---|---|---|---|
| K01 | E06 | `parse_number("100.125")` = 100125.0 | 100,125 |
| K02 | B05 | `env_condition` "Nhiệt độ môi trường" value_text = "(20" | "(20,5 ± 2) °C" |
| K03 | D02 | Toàn bộ trường bảng (nhãn có dấu `:` trong ô) không khớp - mọi field None | Nhận diện được nhãn |
| K04 | D03 | `_parse_verdict("Đạt (không đạt) yêu cầu...")` = "khong_dat" | None (không kết luận được) |
| K05 | D04 (docx, ISO) + E07 (xlsx, số serial) | D04: "2026-04-10" → 2010-04-26; E07: ô ngày đọc ra "46223" | D04: 10/04/2026; E07: 20/07/2026 |
| K06 | D14 | Phụ lục A "Ngày kiểm định tháng năm 2026" không có `:` → không sinh trường ngày (xác minh trực tiếp) | Có trường ngày kiểm định |
| K07 | D13 (bảng gộp ô dựng ở B03) | `point[0].error` đọc ra 120.0 (giá trị cột "Đóng") | 0,05 (giá trị "Độ chênh áp") |
| K08 | *(không có trong B/D/E - xem "Không làm được")* | | |
| K09 | D12 (áp dụng mọi hồ sơ D/E) | `unit_id`/`unit_text` không được reader đặt | Có đơn vị |
| K10 | B04 | 0 dòng `calibration_interval` (thiếu "là") | "6 tháng" |
| K11 | B01 | `parse_procedure_header` → None | number = "9.013" |
| K12 | B02 | 0 dòng `appendix_field` | ≥ 12 dòng |
| K13 | B06 | `find_section6` → None (style `TieuDeMuc1` không nhận diện) | Tìm thấy mục "Tiến hành kiểm định" |
| K14 | *(không làm - tuỳ chọn theo spec)* | | |
| K15 | B09 | `phamvi`: "...từ 0 bar đến 1 400 bar." (chấm câu ngay sau đơn vị, không mệnh đề theo sau) → `value_text` dính chấm câu, `unit_max="bar."` không resolve được (đo thật, xem `manifest.jsonl` id B09) | `value_text` không chấm câu, đơn vị resolve thành `"bar"`; đã ghi vào `docs/superpowers/research/2026-09-25-knowledge-input-contract.md` §6 |

## Không làm được / giới hạn đã biết

- **K08** (supersede khi nạp phiên bản mới) là hành vi tầng DB/`records/ingest.py`, không thể quan sát qua `docx_reader`/`xlsx_reader` hay luật trích xuất thuần - không có file nào trong B/D/E chạm tới nó như spec đề nghị; đã ghi chú tại `F02` (QTKĐ 9.001 phiên bản 2) để Pha 3 kiểm tra khi có DB.
- **K14** (heading con cắt ngang mục cha) là tuỳ chọn theo spec - không dựng file riêng.
- Không có formula fact nào trong `extract_golden_section6.jsonl` (chỉ `max_permissible_error`); cổng eval không yêu cầu recall nên không ảnh hưởng self-check.
