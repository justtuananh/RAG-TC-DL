# Kế hoạch sửa lỗi lớp tri thức K01..K15

Ngày: 2026-09-25.
Nhánh: `feature/knowledge-management-sprints-3-9`.
Người thực thi: `opencode-go/deepseek-v4.1-flash` qua `opencode run`.
Người review và nghiệm thu: Claude (Opus).

## Bối cảnh

Bộ test `tests/unit/knowledge_corpus/` (612 passed, 24 xfailed) chạy trên corpus tổng hợp `tests/data/knowledge_corpus/`.
24 xfail là các hành vi sai của code hiện tại, mô tả ở bảng mục 6 của `docs/superpowers/research/2026-09-25-knowledge-input-contract.md`, mã K01..K15 (K14 ngoài phạm vi).
Mục tiêu: sửa code sản phẩm để các test đó chuyển sang passed mà không làm lùi bất kỳ hành vi nào trên corpus thật `TC_DL/`.

## Luật chung (áp dụng mọi đợt)

1. TDD: với mỗi mã K, trước tiên gỡ xfail của test tương ứng và thêm test đơn vị nhỏ trong `tests/unit/backend/` (hoặc file test sẵn có của module), chạy thấy đỏ, rồi mới sửa code.
2. Không sửa gold hay manifest để hợp với code.
   Ngoại lệ duy nhất đã duyệt trước: mục "Thay đổi corpus được phép" bên dưới.
3. Không sửa test cũ trừ khi test đó đang khẳng định chính hành vi lỗi; khi đó liệt kê từng test đã sửa, dòng nào, vì sao, trong báo cáo.
4. Không đổi quy ước số kiểu Việt: dấu chấm vẫn là nhóm nghìn (`1.000` là một nghìn), dấu phẩy là thập phân.
5. Khi một mã K đã sửa:
   - gỡ đánh dấu xfail của mã đó trong `tests/unit/knowledge_corpus/` (bảng ánh xạ và decorator);
   - thêm `"fixed": "2026-09-25"` vào mục `known_behaviors` tương ứng trong `manifest.jsonl` (đây là thay đổi manifest được phép, không đổi `current`/`expected`);
   - sửa `xfail_for` trong `tests/unit/knowledge_corpus/conftest.py` để ném lỗi nếu được gọi với mã đã có `fixed`, nhằm chặn xfail cũ sót lại.
6. Không thêm phụ thuộc mới.
   Hàm dưới khoảng 50 dòng, file dưới 800 dòng, comment/docstring tiếng Việt theo phong cách module.
7. Không commit git.
8. Không dùng ký tự em dash trong mọi file viết ra.

## Cổng hồi quy corpus thật (chạy sau mỗi đợt)

Baseline đã chụp trước khi sửa: `logs/kfix/baseline/` bằng `PYTHONPATH=. .venv-dev/bin/python logs/kfix/snapshot_real.py logs/kfix/baseline`.
Sau mỗi đợt chạy lại vào `logs/kfix/after_<đợt>/` và `diff -r logs/kfix/baseline logs/kfix/after_<đợt>`.
Mọi khác biệt phải được giải thích trong báo cáo và quy về một mã K của đợt đó.
Khác biệt không giải thích được là trượt.

Lệnh cổng bắt buộc sau mỗi đợt:

```
.venv-dev/bin/python -m pytest tests/unit/knowledge_corpus -q -rxX
make check          # lint fidelity extract-eval extract-section6-eval intent-eval test-unit
```

`make check` phải xanh; `extract-eval` trên corpus thật không được giảm precision/recall so với trước.

## Thay đổi corpus được phép

- K13: fixture B06 hiện dùng style `TieuDeMuc1` có tên "Tieu de muc 1 (ban dia hoa)" dựa trên `Normal`, không mang tín hiệu heading nào, nên không bản sửa hợp lý nào nhận ra được.
  Word bản địa hoá thật giữ tên style dựng sẵn bằng tiếng Anh (`w:name="heading 1"`) nhưng styleId có thể khác, hoặc dùng style tuỳ biến `basedOn` một style heading.
  Sửa builder `scripts/knowledge_corpus/` để B06 có hai heading bản địa hoá thực tế: một style id `TieuDeMuc1` với `w:name="heading 1"`, một style id `MucCon2` với `basedOn="TieuDeMuc1"` và tên tuỳ ý.
  Gold B06 giữ nguyên; `make knowledge-corpus` vẫn phải tất định; cập nhật `current` của K13 trong manifest cho khớp fixture mới (đo bằng code trước khi sửa).
- K08: đổi test T9 theo quyết định nghiệp vụ mới (mục K08).

## Đợt 1: luật trích xuất và chuyển docx (`knowledge/`, `ingestion/extract_docx.py`)

### K15 - dấu chấm câu sau đơn vị (`knowledge/rules/phamvi.py`)

Lớp ký tự đơn vị `[\w%°/²³.]*` nuốt dấu chấm câu: "từ 0 bar đến 1 400 bar." cho đơn vị "bar.".
Sửa: dấu `.` ở cuối token đơn vị, khi theo sau là khoảng trắng hoặc hết dòng, không thuộc đơn vị và không thuộc `value_text`.
Test: `test_rules_corpus.py[B09-working_range]`.

### K10 - chu kỳ không có "là" (`knowledge/rules/chuky.py`)

Nhận thêm dạng "Chu kỳ kiểm định ...: N tháng|năm" (dấu hai chấm thay cho "là").
Vẫn chỉ nhận trong mục "xử lý chung".
Test: `[B04-calibration_interval]`.

### K02 - tách giá trị điều kiện ở dấu phẩy thập phân (`knowledge/rules/dieukien.py`)

Chỉ tách `value_text` / `condition_text` tại dấu phẩy không nằm giữa hai chữ số.
"(20,5 ± 2) °C" giữ nguyên; "(20 ± 5) °C, không thay đổi quá 1 °C" vẫn tách như cũ.
Test: `[B05-env_condition]`.

### K11 - mã "QTKD" không dấu Đ (`knowledge/procedure.py`)

Regex dòng mã nhận cả `QTKĐ` và `QTKD` (hoa/thường).
Không đổi `ingestion/classify.py`.
Test: `test_procedure_header_corpus.py[B01]`.

### K12 - Phụ lục A bị cắt bởi đoạn kiểu heading (`knowledge/rules/phuluc_a.py`, có thể `sections.py`)

Thân mục Phụ lục A kéo dài từ heading "Phụ lục A" tới heading kế tiếp có tiêu đề bắt đầu bằng "Phụ lục" (B, C, ...) hoặc hết tài liệu; các heading con bên trong ("(Quy định)", "Mẫu biên bản...", "BIÊN BẢN KIỂM ĐỊNH...") không kết thúc mục.
Chỉ áp dụng cho luật phuluc_a; các luật khác giữ ngữ nghĩa `find_section` hiện có.
Test: `test_appendix_extraction_b02_heading_style_paragraph`.
Cổng corpus thật: 1.071, 1.159, 1.160, 1.190 (hiện 0 trường) phải có trường Phụ lục A; liệt kê số trường header và cột bảng của từng tài liệu trong báo cáo để Claude đối chiếu với bản gốc.
1.061, 1.062, 1.063 không được đổi (16, 16, 15 trường).

### K13 - style heading bản địa hoá (`ingestion/extract_docx.py`)

`_heading_level` phân giải styleId qua `word/styles.xml`.
Là heading cấp N khi một trong các điều sau đúng, theo thứ tự:
1. styleId khớp `heading\d` (như hiện nay);
2. `w:name` của style khớp `heading \d` (không phân biệt hoa thường);
3. chuỗi `basedOn` (tối đa 5 bước) tới một style thoả 1 hoặc 2, lấy cấp của style đó.

Không dùng `outlineLvl` ở cấp đoạn văn (giữ nguyên chốt chặn lỗi 1.071 trong docstring).
Loại trừ style TOC: styleId hoặc tên bắt đầu bằng `toc` (corpus thật có `TOCHeading` dựa trên `Heading1`, phải không thành heading).
Làm sau khi đã sửa fixture B06 (mục "Thay đổi corpus được phép").
Test: `test_section6_b06_localized_heading_not_found` (đổi tên cho đúng ý nghĩa sau khi sửa) và test đơn vị mới trong `tests/unit/ingestion/test_extract_docx.py`.
Cổng corpus thật: `docx_md/` của 7 file thật không đổi.

### K01 phần số (`knowledge/vnnum.py`)

Nhóm đầu bằng `0` không thể là nhóm nghìn: "0.500", "0.125" là số thập phân (0,5; 0,125).
"1.000", "12.500" giữ nghĩa nhóm nghìn.
Test đơn vị mới trong `tests/unit/backend/test_vnnum.py`; phần xlsx của K01 ở đợt 2.

## Đợt 2: đọc hồ sơ (`records/`)

### K01 phần xlsx (`records/xlsx_reader.py`)

Ô số trong xlsx (không có thuộc tính `t` hoặc `t="n"`) là số máy, luôn dùng dấu chấm thập phân.
Chuyển thành chuỗi kiểu Việt không nhóm nghìn (ví dụ `10.125` thành `10,125`) trước khi đưa xuống tầng parse, để `vnnum` hiểu đúng.
Ô chuỗi (`s`, `inlineStr`) giữ nguyên.
Test: `test_record_points_match_gold[E06]`.

### K05 - ngày ISO và ô ngày Excel (`records/store.py`, `records/xlsx_reader.py`)

`parse_date` nhận `YYYY-MM-DD` (nhóm đầu 4 chữ số là năm) trước các mẫu khác.
`xlsx_reader` đọc `xl/styles.xml`; ô số có định dạng ngày (numFmtId dựng sẵn 14..22 hoặc numFmt tuỳ biến chứa d, m, y và không phải chỉ giờ) được chuyển từ số serial (gốc 1899-12-30) sang `DD/MM/YYYY`.
Test: `[D04-date]`, `[E07-date]`.

### K03 - nhãn có dấu hai chấm trong ô bảng (`records/docx_reader.py`, xlsx cho nhất quán)

Chuẩn hoá ô nhãn trước khi khớp: bỏ dấu `:` và khoảng trắng cuối.
Test: 10 trường `[D02-*]`.

### K04 - kết luận mẫu mơ hồ (`records/store.py`)

`_parse_verdict` trả `None` khi văn bản chứa đồng thời một "đạt" không đứng sau "không" và một "không đạt" (ví dụ "Đạt (không đạt) yêu cầu", "Đạt/Không đạt").
"Đạt yêu cầu" cho `dat`, "Không đạt yêu cầu" cho `khong_dat` như cũ.
Test: `[D03-verdict]`.

### K06 - trường Phụ lục A không có dấu hai chấm (`knowledge/rules/phuluc_a.py` + nguồn nhãn dùng chung)

Dòng trong Phụ lục A bắt đầu bằng một nhãn hồ sơ đã biết (danh sách alias hiện ở `records/store.py:46-68`) mà không có `:` vẫn là trường header, giá trị là phần còn lại đã bỏ chữ mẫu ("tháng", "năm", dấu chấm lửng) hoặc rỗng.
Chuyển danh sách alias sang một module trong `knowledge/` (ví dụ `knowledge/record_labels.py`) để `knowledge` không import `records`; `records/store.py` import lại từ đó.
Test: `test_appendix_date_field_missing_colon_not_recognized` (đổi tên cho đúng ý nghĩa sau khi sửa).
Cổng corpus thật: 1.061 phải có trường "Ngày kiểm định".

### K07 - ô gộp trong bảng (`ingestion/extract_docx.py`, `records/docx_reader.py`)

Cả hai nơi dựng lưới bảng phải tôn trọng `w:gridSpan` (ô chiếm N cột: văn bản ở cột đầu, N-1 ô rỗng theo sau) và `w:vMerge` (ô tiếp nối là ô rỗng).
Như vậy số cột của bảng Markdown (nguồn của MappingConfig qua Phụ lục A) và của lưới mà reader đọc khớp nhau, và tiêu đề hai tầng ghép đúng cột.
Test: `test_record_points_match_gold[D13]` và B03.
Cổng corpus thật: mọi khác biệt ở `docx_md/` phải là bảng có ô gộp; Bảng 1 và Bảng 2 thật vẫn cho cùng dữ kiện (`rules.jsonl` không đổi ở inspection_step và standard); `make extract-eval` không giảm.

### K09 - điểm đo không có đơn vị (`records/`)

Mỗi điểm đo nhận `unit_text`: ưu tiên đơn vị trong ngoặc ở tiêu đề cột giá trị (ví dụ "Giá trị đo (bar)"); nếu không có, dùng đơn vị (`unit_max`, rồi `unit`) của dữ kiện `working_range` đã duyệt của QTKĐ áp dụng.
`store.py` resolve `unit_id` như hiện có qua `_resolve_unit_id`; đơn vị không resolve được thì `unit_id` để `None` và giữ `unit_text`.
Test: `test_record_points_have_unit_id`.

## Đợt 3: thay thế dữ kiện (`knowledge/extract.py`, `review/queue.py`)

### K08a - trích lại bằng luật chỉ thay thế extraction của luật

`extract_and_store` khi `supersede=True` chỉ chuyển sang superseded các extraction có `extractor` bắt đầu bằng `rule:` và không bắt đầu bằng `rule:phuluc_a`.
Extraction `llm:` và `rule:phuluc_a` có vòng đời riêng (`extract_section6_and_store`, `extract_appendix_and_store` đã có `extractor_prefix`).
Test: phần K08 của `test_supersede_corpus.py` cho trích lại A01.

### K08b - phiên bản mới thay bản cũ khi DUYỆT (quyết định của người dùng 2026-09-25)

Nạp phiên bản mới (tài liệu khác, cùng số hiệu QTKĐ) không đụng tới dữ kiện đã duyệt của bản cũ; tra cứu số liệu không có khoảng trống.
Khi một extraction của tài liệu hiện hành của QTKĐ (`procedure.document_id`) được duyệt (`approve`, `edit_and_approve`, `bulk_approve` trong `review/queue.py`), các extraction ĐÃ DUYỆT của cùng QTKĐ nhưng thuộc tài liệu khác, cùng khoá (`fact_kind`, `label`) với dữ kiện vừa duyệt (label `None` khớp `None`; với chuẩn đo lường dùng `name_vi`), chuyển sang superseded, `supersedes_id` của extraction mới trỏ tới extraction cũ, và ghi nhật ký audit như các thao tác duyệt khác.
Dữ kiện bản cũ không có đối ứng ở bản mới vẫn giữ trạng thái đã duyệt.
Viết lại `test_supersede_corpus.py::test_new_version_does_not_supersede_old_approved_facts` theo ngữ nghĩa này, thành ba khẳng định:
1. sau khi nạp F02, mọi dữ kiện đã duyệt của A01 vẫn approved;
2. duyệt một dữ kiện của F02 thì đúng dữ kiện cùng khoá của A01 thành superseded, liên kết `supersedes_id` đúng;
3. các dữ kiện khác của A01 vẫn approved.

Thêm test đơn vị cho `review/queue.py` trong `tests/unit/backend/test_review_queue.py`.
View đã duyệt (P3) phải chỉ trả một bản của mỗi khoá sau khi duyệt.

## Báo cáo sau mỗi đợt (gửi Claude)

- Danh sách mã K đã sửa, file và hàm đã đổi.
- Dòng tổng kết pytest của `tests/unit/knowledge_corpus` (passed/xfailed) và danh sách xfail còn lại.
- Kết quả `make check`.
- Diff corpus thật: khác biệt nào, thuộc mã K nào.
- Test cũ đã sửa (nếu có) và lý do.

## Nghiệm thu cuối (Claude)

1. `tests/unit/knowledge_corpus`: 0 xfail cho K01..K13, K15; 0 xpass, 0 skip, 0 fail.
2. `make check` xanh, chạy `make test-unit` 3 lần đều xanh.
3. Diff corpus thật chỉ gồm thay đổi đã giải thích; `make extract-eval` không giảm; 1.071, 1.159, 1.160, 1.190 có trường Phụ lục A và Claude đối chiếu mẫu với file gốc.
4. Claude tự chạy thêm kiểm đột biến: hoàn tác từng bản sửa thì test tương ứng phải đỏ.
5. Review code: đúng phạm vi, không thêm hardcode, không nuốt lỗi im lặng.

## Nhật ký review

- 2026-09-25: đợt 1 vòng 1: K15, K10, K02, K11, K13, K01(vnnum) đạt; K12 trượt vì "Phụ lục B" dạng đoạn văn thường ở 1.071 không phải điểm dừng, Phụ lục A nuốt cả Phụ lục B (44 trường, header lặp, bảng B.1..B.4).
- 2026-09-25: đợt 1 vòng 2: K12 đạt trên corpus thật (1.071: 18+4, 1.159: 19+5, 1.160: 15+3, 1.190: 15+4; 1.061/1.062/1.063 không đổi); còn lỗi biên "Phụ lục này ..." cắt mục, chuyển vào mục 0 của đợt 2.
- 2026-09-25: đợt 2 bị ngắt nhiều lần bởi `Provider request failed with HTTP 400` của opencode-go; dùng script tự nối lại phiên (`logs/opencode/run_with_resume.sh`).
- 2026-09-25: đợt 2 ĐẠT sau khi Claude tự chạy cổng: `make test-unit` 1312 passed, 1 xfailed (K08); fidelity 351/351; extract-eval, section6, intent đạt. K07 chỉ đổi dòng bảng ở `docx_md` của 7 file thật; Bảng 1/Bảng 2 không đổi; cột bảng Phụ lục A đúng hơn (1.061: `Áp suất Mở | Đóng | Độ chênh áp`). Thay đổi fixture B03 (thêm `gridSpan=3`) ngoài phạm vi được phép nhưng đúng với XML thật của 1.061 (đã kiểm), chấp nhận.
- 2026-09-25: phát hiện lỗi builder: `known_behaviors` được đo bằng code sống lúc build nên rebuild sau khi sửa đã ghi đè `current` và xoá cờ `fixed`; chuyển sang nguồn tĩnh `known_behaviors.json` trong đợt 3. Còn: lint format một file test, K06 cho giá trị mẫu "202" thay vì rỗng.
- 2026-09-25: đợt 3 (lint, K06 giá trị mẫu, nguồn tĩnh `known_behaviors.json`, K08a, K08b) ĐẠT. Claude tự nghiệm thu:
  - `tests/unit/knowledge_corpus`: 0 xfail, 0 xpass; `make check` xanh; `make test-unit` 3 lần: 1324 passed, 1 skipped (skip có sẵn, thiếu gói `kotaemon`).
  - manifest: `current`/`expected` của 14 hành vi khớp nguyên văn bản trước khi sửa; cả 14 có `fixed`; gold không đổi nội dung.
  - corpus thật so với cuối đợt 2: chỉ đổi `value_text` của "Ngày kiểm định" ở 1.061/1.062/1.063 ("202" thành rỗng).
  - kiểm đột biến: hoàn tác từng file sửa (13 file) đều làm test đỏ; đột biến có chủ đích trong `extract_docx.py` (bỏ đệm gridSpan, bỏ nhận diện theo `w:name`) đều bị bắt.
