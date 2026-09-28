# Kế hoạch upload và test 20 biên bản áp kế pittông (QTKĐ 1.159:2021)

Ngày: 2026-09-27.
Nhánh: `feature/knowledge-management-sprints-3-9`.
Người thực thi sinh dữ liệu và sửa lỗi: `opencode-go/deepseek-v4.1-flash` qua `opencode run` (script `logs/opencode/run_with_resume.sh`).
Người review, nghiệm thu và chạy test E2E: Claude (Opus).

## 1. Mục tiêu

Người dùng test trực tiếp trên UI ba chức năng với dữ liệu gần thật:

1. Tri thức: dữ kiện QTKĐ 1.159:2021 (phạm vi, chu kỳ, phương tiện chuẩn, sơ đồ Phụ lục A) đi qua hàng đợi duyệt ở tab Tri thức.
2. Dữ liệu: 20 biên bản kiểm định dạng Excel được đọc thành hồ sơ + điểm đo, duyệt, rồi xem ở tab Dữ liệu.
3. Hỏi đáp: chat lai văn bản + số liệu trả lời đúng câu hỏi về thiết bị, lịch sử, kết luận, hạn hiệu lực, kèm trích dẫn.

Mẫu chuẩn: `AP KE PITTONG-P2-BBKD-QTKD 1.159 2021.xlsx` (bản sao cố định ở `scripts/pittong_records/template.xlsx`).

## 2. Hiện trạng đo được (2026-09-27)

- Docker: postgres, qdrant, embedding, reranker, ollama (`qwen2.5:3b`) đang chạy; `api_server.py` và frontend chưa chạy.
- DB ở revision `008_reference_views`: 8 `document` (7 QTKĐ `ready`, 1 `khac`), 0 `procedure`, 0 `extraction`, 0 `calibration_record`, 1 user `admin`.
  Tức là 7 QTKĐ đã được nhúng vào Qdrant nhưng CHƯA có dữ kiện tri thức nào trong sổ cái.
- Chạy thử luật tri thức trên `build/spike_a/QTKD_1.159_2021_ND_FINAL.md` (không ghi DB):
  - đầu mục: số `1.159`, năm 2021, loại thiết bị "Áp kế píttông tiêu chuẩn";
  - 3 `working_range`, 1 `calibration_interval` ("02 năm"), 2 `env_condition`, 11 `inspection_step`, 12 phương tiện chuẩn;
  - Phụ lục A: 19 trường đầu mục (Ký hiệu, Số hiệu, Nước (hãng) sản xuất, Phạm vi đo, Cấp chính xác, Đơn vị sử dụng, Ngày kiểm định...) và 5 bảng A.1 đến A.5.
- Chạy thử bộ đọc Excel trên file mẫu với cấu hình dựng từ Phụ lục A: xem các lỗi B4 đến B6 bên dưới.

## 3. Các điểm chặn phải sửa trước khi upload

| Mã | Điểm chặn | Bằng chứng |
|---|---|---|
| B1 | Upload chỉ nhận `.docx`/`.pdf`. | `ingestion_jobs.py:103` `SUPPORTED_EXTS`, `:129`; `frontend/src/components/docs/DocsTab.tsx` `accept=".docx,.pdf"`. |
| B2 | Không tìm lại được tệp gốc `.xlsx` (`_find_source` chỉ quét `SUPPORTED_EXTS`), nên `records.ingest.ingest_file_stem` báo "Không tìm thấy tệp gốc". Bước "Xử lý" lại chạy trích Markdown + nhúng Qdrant cho mọi loại tài liệu; hồ sơ không được nhúng lẫn vào kho văn bản QTKĐ. | `ingestion_jobs.py:108-122`, `_run_job` `:235`. |
| B3 | Không có nút nào trên UI gọi `POST /api/records/ingest/{file_stem}`; hồ sơ upload xong không tự thành bản ghi. | `api_server.py:681`; khảo sát 2026-09-27. |
| B4 | Bộ đọc Excel chỉ đọc sheet ĐẦU TIÊN. Sheet đầu của mẫu là `Chọn quả` (bảng tra quả cân) nên đọc ra 0 trường, 0 điểm đo. | `records/xlsx_reader.py` `_first_sheet_path`, `_read_grid`. |
| B5 | Sheet `KQ KĐ` đặt bảng 2 (quả cân, cột J:O) song song với khối đầu mục (cột A:H). Bộ đọc coi mỗi dòng là một dải liền: "Đặc trưng kỹ thuật đo lường" nhận giá trị `5`, "Điều kiện kiểm định" nhận `11` (số TT của bảng bên cạnh). Khớp bảng chỉ cần nửa số cột nên sinh 47 "điểm đo" rác từ khối đầu mục; bảng 3 (sheet `KQ KĐ (2)`) không được đọc. | Chạy thử 2026-09-27 trên file mẫu. |
| B6 | Nhãn lệch: "Nhiệt độ môi trường:" so với nhãn Phụ lục A "Nhiệt độ" cho giá trị `môi trường:`; "Nước (hãng) sản xuất" không có trong `HEADER_ALIASES` nên `manufacturer` rỗng; kết luận nằm ở "4. Kết luận: ..." và ô đánh dấu Wingdings (`` đã chọn, `` trống) nên `verdict` rỗng; tên kiểm định viên nằm dưới dòng tiêu đề chữ ký nên `inspector_name` rỗng; "Số:" (số biên bản) không map sang `cert_no`. | `knowledge/record_labels.py`, `records/store.py` `_parse_verdict`. |
| B7 | QTKĐ 1.159 chưa có `procedure` và chưa có dữ kiện nào trong sổ cái; cấu hình đọc hồ sơ chỉ dựng từ `appendix_field` ĐÃ DUYỆT. | Mục 2. |
| B8 | Sequence `device_type_id_seq` tụt sau `max(id)` (migration 003 chèn id tường minh). Lần chèn loại thiết bị mới đầu tiên sẽ lỗi trùng khóa. | Khảo sát: `last_value=1`, `max(id)=7`. |
| B9 | Image Docker `api` không copy `query/`, `records/`, `review/`; phải chạy API trên host bằng `./run-dev.sh`. | `Dockerfile:25-39`. |
| B10 | Bấm "Xử lý" lại một QTKĐ trên máy thiếu gem `pry` làm tỉ lệ chuyển công thức của 1.159 rơi từ 232/232 xuống 22/232, GHI ĐÈ `.md` đã kiểm chứng và nhúng bản hỏng, không báo lỗi. | Tái hiện E2E 2026-09-27; `ingestion_jobs._run_markdown_job`. |
| B11 | Nhúng lại một file chỉ upsert, không xóa chunk cũ: Qdrant chứa lẫn 83 chunk hỏng với chunk tốt của 1.159. | `index.embed_store.index_chunks`. |
| B12 | README thiếu `gem install pry` (Dockerfile có): trên host mọi lần chuyển MathType lỗi `LoadError: cannot load such file -- pry`. | `README.md` mục 3.2, `Dockerfile:18`. |

Ghi chú về kỳ vọng, không phải lỗi:

- Bảng 3 của QTKĐ 1.159 là bảng cân bằng áp suất, không có cột "Sai số" từng điểm, nên intent `error_trend` chỉ có dữ liệu nếu map cột "Sai số tương đối khối lượng" và "Giá trị cho phép" của bảng 2 (quả cân) sang `error`/`limit`.
  Đề xuất ở pha 1: map như vậy, `label` là "Tên, mã số" của quả cân, để xu hướng sai số khối lượng từng quả cân theo thời gian truy vấn được.
- `devices_by_range` lọc theo `working_range` của QTKĐ, không theo phạm vi riêng của từng thiết bị; với một QTKĐ, mọi thiết bị cùng khớp.

## 4. Các pha

### Pha 0: sinh 20 biên bản (đang chạy)

Prompt: `logs/opencode/pittong_gen_prompt.md`.
Đầu ra: `scripts/pittong_records/{spec.json,xlsx_patch.py,build.py}`, `tests/unit/backend/test_pittong_records.py`, 20 file ở `mau_bien_ban/ap_ke_pittong/` + `manifest.json`.

Ma trận đã chốt (12 thiết bị, 20 biên bản, 2 bản "Không đạt", mọi bản theo QTKĐ 1.159:2021):

| Mã | Ký hiệu | Số hiệu | Đơn vị sử dụng | Ngày kiểm định và kết luận |
|---|---|---|---|---|
| D01 | МП-6 | 6112 | Phòng Đo lường Nhiệt-Áp suất, Trung tâm Đo lường | 2023-03-14 Đạt; 2024-03-12 Đạt; 2025-03-18 Đạt |
| D02 | МП-60 | 1045 | Công ty CP Cơ khí Thủy lực Hải An | 2023-06-20 Đạt; 2024-06-25 Không đạt (độ kín); 2024-07-10 Đạt |
| D03 | МП-600 | 2218 | Nhà máy Nhiệt điện Sông Lam | 2022-09-05 Đạt; 2023-09-11 Đạt |
| D04 | МП-2500 | 0391 | Nhà máy Nhiệt điện Sông Lam | 2024-11-19 Đạt |
| D05 | DH-Budenberg 580 | 58-3312 | Công ty TNHH Khí công nghiệp Đông Phương | 2023-02-08 Đạt; 2024-02-06 Đạt |
| D06 | WIKA CPB5800 | 1A0043219 | Công ty TNHH Khí công nghiệp Đông Phương | 2025-05-21 Đạt; 2026-05-19 Không đạt (thời gian quay tự do) |
| D07 | Fluke P3125 | 4471 | Viện Cơ khí Năng lượng Miền Trung | 2024-08-27 Đạt |
| D08 | Budenberg 280 | B280-7702 | Trung tâm Kiểm định Kỹ thuật An toàn Khu vực 4 | 2022-12-15 Đạt; 2023-12-12 Đạt |
| D09 | Xinghua YS-600 | YS600-19087 | Công ty CP Lọc hóa dầu Minh Sơn | 2025-10-07 Đạt |
| D10 | Pressurements T2300 | T23-0512 | Viện Cơ khí Năng lượng Miền Trung | 2026-01-13 Đạt |
| D11 | Fluke PG7601 | 1520 | Phòng Đo lường Nhiệt-Áp suất, Trung tâm Đo lường | 2026-04-22 Đạt |
| D12 | МП-60 | 1046 | Công ty CP Cơ khí Thủy lực Hải An | 2025-08-12 Đạt |

Ma trận phủ: lịch sử nhiều lần (D01, D02), không đạt rồi sửa chữa đạt (D02), không đạt ở lần gần nhất (D06), hai thiết bị cùng ký hiệu có số hiệu chỉ lệch 1 (D02/D12), số hiệu có số 0 đầu (D04), số hiệu chữ-số (D06, D08, D09, D10), 5 đơn vị áp suất khác nhau, trải 2022 đến 2026.

Nghiệm thu pha 0 (Claude):

1. `pytest tests/unit/backend/test_pittong_records.py` xanh, `make check` không có test mới đỏ.
2. Mở từng file bằng LibreOffice (chụp màn hình trang 1 và trang 4 của 3 file mẫu) và so với file gốc: bố cục, merge, font, ô đánh dấu hiển thị đúng.
3. Mọi ô công thức có giá trị cache; M7 và F6 khớp công thức với số mới.
4. `manifest.json` khớp nội dung ô cho cả 20 file (script đối chiếu độc lập của Claude, không dùng code của builder).
5. Không file nào bị đổi ngoài phạm vi (`git status`), file mẫu giữ sha256.

### Pha 1: sửa đường nạp hồ sơ Excel (B1 đến B6, B8)

Người thực thi: DeepSeek V4.1 Flash, theo TDD như kế hoạch K01..K15; Claude review từng đợt.

1. B1, B2: `ingestion_jobs` nhận `.xlsx` cho upload; `_find_source` tìm được `.xlsx`; frontend `accept` thêm `.xlsx`.
   Tài liệu loại `ho_so_kiem_dinh`/`phieu_do` KHÔNG đi đường trích Markdown + nhúng Qdrant.
2. B3: bước "Xử lý" của tài liệu hồ sơ gọi `records.ingest` (tự nhận QTKĐ qua dòng "Phương pháp kiểm định: QTKĐ 1.159 : 2021"), trạng thái job và lỗi nghiệp vụ ("chưa duyệt Phụ lục A của QTKĐ 1.159") hiện trên UI tab Tài liệu.
3. B4: bộ đọc Excel đọc MỌI sheet theo thứ tự, gắn tên sheet vào `section_path`/`quote` để truy nguyên (P1).
4. B5: tách dải bảng theo vùng cột liền mạch (khối A:H và khối J:O là hai vùng riêng); khớp header bảng theo đa số cột của CHÍNH vùng đó; dừng bảng ở dòng trống hoặc tiêu đề bảng kế tiếp; đọc được bảng 2 và bảng 3.
5. B6: thêm alias còn thiếu (`nước (hãng) sản xuất`, `nhiệt độ môi trường`, `độ ẩm môi trường`, `số` cho số biên bản); đọc ô đánh dấu Wingdings và dòng "Kết luận: ..." thành `verdict`; đọc tên dưới "KIỂM ĐỊNH VIÊN"/"NGƯỜI KIỂM SOÁT" thành `inspector_name`/`reviewer_name`.
6. B8: migration mới `setval` cho sequence của `device_type`, `unit`, `quantity`.

Cổng nghiệm thu pha 1: một test tích hợp đọc cả 20 file theo cấu hình dựng từ Phụ lục A thật của 1.159, so với `manifest.json`:

- 100 % khớp: số hiệu, ký hiệu, hãng, đơn vị sử dụng, ngày kiểm định, kết luận, số biên bản, kiểm định viên, người kiểm soát;
- mỗi biên bản đúng 10 điểm bảng 3 và 18 điểm bảng 2, không có điểm đo nào sinh từ khối đầu mục;
- không số nào được tính lại (P2): mọi `*_value` phân tích từ đúng ô nguồn;
- corpus test cũ (`tests/unit/knowledge_corpus/`) và `make check` không lùi.

### Pha 2: nạp tri thức QTKĐ 1.159

Chạy trên host, `.venv-dev`, DB localhost:

```bash
./run-dev.sh                                             # api :8080 + frontend :5173, tự migrate
.venv-dev/bin/python -m scripts.seed_knowledge            # đại lượng, đơn vị, loại thiết bị
.venv-dev/bin/python -m scripts.generate_procedures --apply
.venv-dev/bin/python -m scripts.extract_appendix --apply --file-stem QTKD_1.159_2021_ND_FINAL
```

Rồi trên UI (đăng nhập `admin`):

1. Tab Tài liệu: bấm "Xử lý" lại `QTKD 1.159 2021 ND FINAL` để chạy luật lõi (phạm vi, chu kỳ, phương tiện chuẩn) ở trạng thái chờ duyệt.
2. Tab Tri thức: duyệt dữ kiện của 1.159.
   Bắt buộc duyệt `appendix_field` (19 trường + 5 bảng) và `calibration_interval` "02 năm".
   Đây là bước test chức năng Tri thức: thử sửa một nhãn, từ chối một dữ kiện sai, duyệt hàng loạt.

### Pha 3: upload 20 biên bản qua UI

1. Tab Tài liệu: upload 20 file trong `mau_bien_ban/ap_ke_pittong/` (chọn nhiều file một lần).
   Kỳ vọng: phân loại `ho_so_kiem_dinh`; upload lại một file báo "trùng nội dung".
2. Bấm "Xử lý" từng file (hoặc hàng loạt): mỗi file sinh 1 extraction `record:xlsx.v1` chờ duyệt.
3. Tab Tri thức: lọc extractor `record:xlsx.v1`, mở vài hồ sơ đối chiếu nguyên văn, rồi duyệt hàng loạt.
   Thử từ chối 1 hồ sơ để thấy nó biến khỏi tab Dữ liệu, rồi nạp lại.
4. Tab Dữ liệu: kiểm 20 hồ sơ, 12 thiết bị, không thiết bị nào "cần nhận dạng", lọc theo kết luận và theo năm, xuất Excel kèm cột xuất xứ.

Bảng đối chiếu nhanh (từ ma trận):

- Theo năm: 2022 có 2, 2023 có 5, 2024 có 6, 2025 có 4, 2026 có 3.
- Không đạt: 1045 (2024-06-25), 1A0043219 (2026-05-19).
- Hạn hiệu lực (chu kỳ 02 năm) tính tới 2026-09-27: hết hạn 2218, B280-7702, 58-3312, 4471, 1045; còn hạn 0391 (tới 2026-11-19), 6112, 1046, YS600-19087, T23-0512, 1520; 1A0043219 lần gần nhất không đạt.

### Pha 4: kịch bản hỏi đáp

Mỗi câu ghi lại: nhánh (`text`/`data`/`mixed`), câu trả lời, trích dẫn, đúng/sai so với kỳ vọng.

| # | Câu hỏi | Nhánh kỳ vọng | Kỳ vọng |
|---|---|---|---|
| 1 | Lịch sử kiểm định áp kế số hiệu 6112 | data | 3 lần: 14/03/2023, 12/03/2024, 18/03/2025, đều Đạt |
| 2 | Hồ sơ kiểm định gần nhất của thiết bị 1045 | data | 10/07/2024, Đạt, hết hạn 10/07/2026 |
| 3 | Thiết bị 1046 kiểm định lần cuối khi nào | data | 12/08/2025, không lẫn với 1045 |
| 4 | Các biên bản không đạt năm 2024 | data | chỉ 1045 ngày 25/06/2024 |
| 5 | Có bao nhiêu hồ sơ kiểm định trong năm 2025 | data | 4 |
| 6 | Lần kiểm định gần nhất của 1A0043219 có đạt không | data | Không đạt, 19/05/2026, lý do thời gian quay tự do |
| 7 | Lịch sử thiết bị 0391 | data | 1 lần 19/11/2024 (giữ số 0 đầu) |
| 8 | Chu kỳ kiểm định áp kế píttông là bao lâu | text hoặc data | 02 năm, trích QTKĐ 1.159:2021 |
| 9 | Thông số của QTKĐ 1.159 | data | phạm vi, chu kỳ, điều kiện môi trường đã duyệt |
| 10 | Phương tiện chuẩn dùng cho QTKĐ 1.159 | data | 12 phương tiện |
| 11 | Thời gian quay tự do tối thiểu cho phép là bao nhiêu | text | theo mục 6.2.3 QTKĐ 1.159, có trích dẫn |
| 12 | Lịch sử thiết bị số hiệu 9999 | data rồi rơi về text | không tìm thấy, không bịa số |
| 13 | Xu hướng sai số quả cân của áp kế 6112 | data | 3 mốc theo năm cho từng quả cân (nếu duyệt đề xuất ở mục 3) |
| 14 | Tính giúp diện tích hiệu dụng của 6112 | chặn | từ chối tính toán (lookup-only) |

Mọi con số trong câu trả lời nhánh số liệu phải có tham chiếu xuất xứ (P1) về đúng file và ô nguồn.

### Pha 5: dọn và lặp lại

- Làm lại từ đầu: `make db-backup` trước pha 2, khôi phục bằng `scripts/restore_db.sh`.
- Sinh lại dữ liệu: `.venv-dev/bin/python -m scripts.pittong_records.build`.

## 5. Nhật ký

- 2026-09-27: khảo sát; 20 mẫu Word CT/cầu trục trong `mau_bien_ban/*.docx` hoãn lại (cần mở rộng bộ đọc Word, ngoài phạm vi kế hoạch này).
- 2026-09-27: giao pha 0 cho DeepSeek V4.1 Flash, phiên `pittong-gen-20`, log `logs/opencode/pittong_gen_r*.log`.
- 2026-09-27: pha 1a (DeepSeek: B1, B2, B3, B6, B8), pha 1b (Claude: B4, B5, B6 phần đọc, kèm hai lỗi thật `vnnum` không nhận số mũ `E` hoa của Excel và số máy dạng `999.99784999999997`), pha 1c (DeepSeek: phân loại `.xlsx`/`BBKD`) đã nghiệm thu; toàn bộ unit test xanh.
- 2026-09-27: pha 0 nghiệm thu độc lập 20/20 file khớp manifest (0 lỗi ô, cache công thức, ô đánh dấu); sửa hiển thị ô "Số:" bị cắt (giao DeepSeek).
- 2026-09-27: E2E pha 2 phát hiện B10, B11, B12; đã khôi phục `.md` 1.159 từ git, xóa và nhúng lại 426 chunk sạch của 1.159, cài `pry` trên host, trích lại tri thức 7 QTKĐ từ `.md` đã kiểm chứng (không bấm "Xử lý"); B10/B11/B12 giao DeepSeek (pha 1d).
- 2026-09-27: tạo tài khoản test tạm `e2e_claude` (admin) cho E2E; xóa sau khi xong.
- 2026-09-28: E2E pha 3-4 phát hiện và sửa thêm: số điểm đo trống trong lịch sử thiết bị (R1), phạm vi SI gắn nhầm đơn vị gốc ở chat/tab Dữ liệu/xuất Excel (R3), diễn biến sai số gộp lẫn mốc đo (R5), đơn vị sai số tương đối `%` riêng (migration 010, M1-M3), hoàn thiện hiển thị (chip đơn vị, tên hồ sơ, thứ tự điểm đo, gộp hàm đổi đơn vị vào `query/units.py`).
- 2026-09-28: định tuyến chat lai với model thật `qwen2.5:3b`: trước 0,690 trên tập vàng; sau sửa bộ lọc tín hiệu (có tra số hiệu sổ cái), prompt, `extract_json`: tập vàng 71/71, tập giữ kín của Claude 23/24 = 0,958 (không rò rỉ few-shot).
- 2026-09-28: kết quả 14 câu hỏi đáp: 13 đúng kỳ vọng; còn Q11 (câu không nêu QTKĐ trích 1.071 thay vì 1.159, giới hạn truy hồi). Q10 rỗng đúng P3 vì Bảng 2 của 1.159 còn chờ duyệt.
- 2026-09-28: trạng thái bàn giao: 20 hồ sơ đã duyệt (49 bản cũ `superseded`), 28 dữ kiện 1.159 đã duyệt, 124 dữ kiện tri thức 7 QTKĐ chờ duyệt để người dùng test tab Tri thức; `make check` 1414 passed, frontend 94 passed; tài khoản `e2e_claude` đã vô hiệu hóa (giữ lại vì là người duyệt trong audit).
- Còn mở: Q11 (truy hồi ưu tiên QTKĐ theo ngữ cảnh thiết bị), câu từ chối tính toán dùng chung câu "không tìm thấy", số hiển thị dấu chấm thập phân thay vì dấu phẩy kiểu Việt, 20 biên bản Word CT/cầu trục trong `mau_bien_ban/*.docx` chưa đọc được.

