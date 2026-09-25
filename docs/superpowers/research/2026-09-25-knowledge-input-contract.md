# Hợp đồng định dạng đầu vào của lớp tri thức (khảo sát code 2026-09-25)

Tài liệu này mô tả chính xác code hiện tại nhận dạng gì, để sinh tài liệu test đúng mẫu.
Mọi dẫn chiếu là `file:dòng` trong repo.

## 1. Phân loại tài liệu (`ingestion/classify.py:16-28`)

Regex trên tên file (upload chỉ truyền tên file, `ingestion_jobs.py:151`), thử theo thứ tự:

1. `qtkđ|qtkd|quy trình kiểm định|đlvn` → `qtkd`
2. `biên bản kiểm định|giấy chứng nhận kiểm định|hồ sơ kiểm định` → `ho_so_kiem_dinh` (bắt buộc có dấu; "Bien ban kiem dinh" → `khac`)
3. `phiếu đo|phieu do|measurement` → `phieu_do`
4. `danh mục|danh_muc|catalog` → `danh_muc`
5. còn lại → `khac`

Tên chứa cả "QTKD" và "biên bản" → `qtkd`.
Upload nhận `.docx` và `.pdf`; `.doc`/`.xls` bị từ chối (`ingestion_jobs.py:130`), `spike_a.process_one` trả `skipped-legacy`.
Trùng nội dung bị chặn bằng sha256 (`ingestion_jobs.py:138`).

## 2. docx → Markdown (`ingestion/extract_docx.py`)

- Heading chỉ khi style id là `heading1`..`heading9` (`:104-127`); `outlineLvl` bị bỏ qua.
- Heading bị hạ thành văn bản nếu bắt đầu `- `/`– `, kết thúc `.`/`;`, dài > 80 ký tự và có `. `, hoặc bắt đầu `Hình N`/`Bảng N` (`:131-150`).
- Bảng → bảng Markdown; ô gộp (`gridSpan`/`vMerge`) bị bỏ qua, mỗi `w:tc` là một ô, hàng ngắn được đệm.
- Công thức MathType → `$LaTeX$` (không bắt buộc cho tài liệu tổng hợp).

## 3. Luật trích xuất QTKĐ

Khối tiêu đề (`knowledge/procedure.py:15`): dòng mã khớp `QTKĐ\s*1.061\s*[:-]?\s*2021` (bắt buộc chữ `Đ`); tên là các dòng khác rỗng sau dòng mã cho tới dòng bắt đầu `QUY TRÌNH KIỂM ĐỊNH`, `HÀ NỘI` hoặc `HỒ CHÍ MINH`.
Loại phương tiện suy từ tên qua alias trong `knowledge/seed_data.py` (`DEVICE_TYPES`).

Mục (`knowledge/rules/sections.py:18-87`): heading `#`, số tuỳ chọn `^\d+(\.\d+)*[.)]?\s+`; `find_section` lấy heading **đầu tiên** chứa từ khoá; thân mục dừng ở heading kế tiếp **bất kỳ cấp nào**.

| Luật (fact kind) | Từ khoá heading | Mẫu |
|---|---|---|
| phamvi (`working_range`) | `phạm vi` | `từ A [đv] đến B đv`; `(A ÷ B) đv`; `phạm vi (làm việc|đo)|giới hạn đo … đến X đv`; `value_text` gồm cả dấu `.` cuối câu |
| thuatngu (`term`) | `thuật ngữ` | `Tên VI (English): là …` mỗi dòng; phải có "là"; bỏ dòng CHÚ THÍCH |
| bang1 (`inspection_step`) | `các phép kiểm định` | bảng có cột chứa `tên`, cột `theo điều` tuỳ chọn, tiêu đề hai tầng `Ban đầu`/`Định kỳ`/`Sau sửa chữa`; ô tính khi đúng bằng `+` |
| bang2 (`procedure_standard`) | `phương tiện kiểm định` | mọi bảng dưới heading; cột `tt`, `tên`, `phạm vi`, và một trong `cấp chính xác`/`sai số`/`độ chính xác`/`độ không đảm bảo` |
| dieukien (`env_condition`) | `điều kiện kiểm định` | dòng `[- ]Nhiệt độ…:` / `Độ ẩm…:` / `Áp suất khí quyển:` rồi `(A ± B) đv`, `không lớn/vượt hơn X`, `≤`; tách value/condition ở dấu phẩy đầu tiên |
| chuky (`calibration_interval`) | `xử lý chung` | `Chu kỳ kiểm định … là N tháng|năm` |
| phuluc_a (`appendix_field`) | `phụ lục a` | trường `Nhãn:` (nhãn không có chữ số); bảng có caption `Bảng A.1`/`KẾT QUẢ` ngay trên, hoặc cột chứa `sai số`/`độ chênh`/`giá trị`/`lần kiểm tra`/`mở`/`đóng`. Không được có đoạn kiểu heading bên dưới Phụ lục A |

Tiêu đề hai tầng (`knowledge/rules/markdown_tables.py:58-77`): hàng sau hàng phân cách là tiêu đề con khi ô đầu rỗng và nó lấp cột mà hàng trên rỗng.

§6 LLM (`knowledge/llm_extract.py:36,170-203`): gốc là heading đầu tiên chứa `tiến hành`, cộng các heading `N.x` liền sau.
Model trả `{"facts":[{fact_kind: max_permissible_error|formula, limit:{value,unit,quote}, floor?, quote}]}`; quote phải xuất hiện nguyên văn trong mục, quote số phải chứa giá trị.
Diễn đạt điển hình: "bằng ± 3% … nhưng không nhỏ hơn ± 0,15 bar", "độ chênh áp cho phép là 15 %".

Số (`knowledge/vnnum.py`): phẩy thập phân; khoảng trắng/NBSP/NNBSP nhóm nghìn; `÷`, `đến`, `tới` là khoảng; `±` dung sai; `×10-5` luỹ thừa; dấu trừ Unicode và gạch ngang coi là `-`.
Đơn vị (`knowledge/seed_data.py:25-53`): Pa, kPa, MPa, bar, mbar, hPa, psi, kgf/cm2, at, mmHg, mmH2O, K, °C (`oC`, `độ C`), °F, %RH, m…km, kg/g/mg, s/min/h. `%` trần không có trong seed.

## 4. Biên bản (.docx) và phiếu đo (.xlsx)

Chọn QTKĐ (`records/ingest.py:25`): khớp đầu tiên của `\b\d{1,4}\.\d{2,3}\b` phải bằng một `Procedure.number`; đặt "Phương pháp kiểm định: QTKĐ 1.061 : 2021" trước mọi ngày dạng chấm.
Mapping lấy từ các fact `appendix_field` **đã duyệt** của QTKĐ đó (`records/template.py:150`); nhãn đúng bằng nhãn Phụ lục A, cột là tiêu đề bảng đã ghép.

Nhãn nhận dạng (`records/store.py:46-68`, không phân biệt hoa thường): serial `Số hiệu`/`Số serial`/`Serial`/`Số máy`; model `Ký hiệu`/`Model`; hãng `Nơi (hãng) sản xuất`/`Hãng sản xuất`/`Nhà sản xuất`; `Đơn vị sử dụng`; `Số giấy chứng nhận`; `Người kiểm định`; `Người soát lại`; `Phòng đo lường`/`Đơn vị kiểm định`; `Ngày kiểm định`/`Ngày thực hiện`; `Chế độ kiểm định` đúng bằng `Ban đầu`/`Định kỳ`/`Sau sửa chữa`; `Kết luận` chứa `không đạt`/`đạt`; `Nhiệt độ`, `Độ ẩm` lấy số đầu tiên.

docx (`records/docx_reader.py`): chỉ `w:p`/`w:tbl` cấp thân; trường dạng `Nhãn: giá trị` (nhiều trường một dòng được) hoặc bảng nhãn | giá trị ô bên phải.
Bảng đo: tiêu đề trùng ≥ một nửa slug với cột cấu hình; hàng sau có ô đầu rỗng là tiêu đề con.
Vai trò cột (`:287-311`): `Lần kiểm tra`/`TT`/`STT` thứ tự; `Giá trị đo`/`Áp suất`/`Mở` đo; `Giá trị danh nghĩa` danh nghĩa; `Sai số`/`Độ chênh áp` sai số; `Giới hạn`/`Sai số cho phép` giới hạn; `Ghi chú`.
xlsx (`records/xlsx_reader.py`): chỉ sheet đầu; shared/inline strings; nhãn với giá trị ở ô khác rỗng kế bên phải, hoặc `Nhãn: giá trị` trong một ô.
Ngày (`records/store.py:158-175`): `DD/MM/YYYY`, `D-M-YY`, `D.M.YYYY`, `ngày 20 tháng 1 năm 2024`.
Ghép thiết bị (`records/matching.py`): khoá `(device_type_id, serial casefold, gộp khoảng trắng)`; thiếu serial → thiết bị mới `needs_identification=1`.

## 5. Gold hiện có (tái dùng định dạng)

- `eval/extract_golden.jsonl`: `{"doc", "kind": "fact|standard|term", "fact_kind", "label", "value_text", "term_vi", "term_en", "name_vi", "range_text"}`; khoá khớp (`eval/extract_eval.py:39-60`): term → `term_vi`; standard → `name_vi|range_text`; step → `label`; env → `label|value_text`; khác → `value_text`.
- `eval/extract_golden_section6.jsonl`: `{doc, fact_kind, label, rel_op, value_text, condition_text, limit{value,unit,quote}, floor, formula, quote}`, khớp theo `quote` đã chuẩn hoá.
- Chạy: `python -m ingestion.spike_a <src> <out>` rồi `python -m eval.extract_eval --md-dir <out> --golden <file>`. Stem file bị làm sạch: ký tự ngoài chữ-số và `-._` thành `_`.

## 6. Hành vi sai hoặc dễ vỡ đã xác nhận (test phải nhắm tới)

| Mã | Hành vi hiện tại | Đúng theo spec |
|---|---|---|
| K01 | `parse_number("0.500")` → 500 (coi `.` là nhóm nghìn); ô xlsx số 10.125 → 10125 | 0,5 và 10,125 |
| K02 | `dieukien` tách ở phẩy đầu: `(20,5 ± 2) °C` → value `(20` | value `(20,5 ± 2) °C` |
| K03 | Ô bảng docx `Số hiệu:` (có dấu hai chấm) lưu khoá kèm `:` nên không nhận serial/ngày | nhận như không có `:` |
| K04 | `Kết luận: Đạt (không đạt) yêu cầu` (chữ mẫu) → `khong_dat` | không kết luận được / cần xác định |
| K05 | Ngày ISO `2024-01-15` → 24/01/2015; ô ngày Excel (số serial) không đọc được | 15/01/2024 |
| K06 | Dòng Phụ lục A `Ngày kiểm định tháng năm` không có `:` → không map ngày, không tính hạn | map được trường ngày |
| K07 | Bảng gộp ô bị bỏ qua: cột `Lần kiểm tra|Áp suất|Sai số|Ghi chú` nhưng dữ liệu Mở/Đóng/Độ chênh → sai vai trò | đúng vai trò cột |
| K08 | Phiên bản mới là document mới; fact đã duyệt của bản cũ không bị supersede; trích lại bằng luật supersede cả fact LLM/Phụ lục A | supersede đúng phạm vi |
| K09 | Reader không đặt `unit_text` → mọi điểm đo `unit_id` NULL | có đơn vị |
| K10 | `Chu kỳ kiểm định: 6 tháng` (không "là") không trích | trích 6 tháng |
| K11 | Mã `QTKD` không có `Đ` → procedure NULL | nhận mã |
| K12 | Phụ lục A có đoạn kiểu heading ("(Quy định)", "Mẫu biên bản…") → 0 appendix_field (thực tế ở 1.071, 1.159, 1.160, 1.190) | trích đủ trường |
| K13 | Style heading bản địa hoá (không phải `heading1..9`) không thành heading (suy luận, chưa thử) | nhận heading |
| K14 | Heading con trong mục cắt thân mục (bảng sau heading con bị mất khỏi luật của mục cha) | cần xác định |
| K15 | `phamvi`: câu kết thúc ngay sau đơn vị bằng dấu chấm câu, không có mệnh đề theo sau (ví dụ "...từ 0 bar đến 1 400 bar.") - lớp ký tự đơn vị (`[\w%°/²³.]*`, có chứa `.`) nuốt luôn dấu chấm câu vào đơn vị: `value_text` dính chấm câu, `unit`/`unit_max` = `"bar."` (không khớp `Unit.code`, không quy đổi SI được) | `value_text` không có chấm câu cuối; đơn vị resolve được thành `"bar"` |
