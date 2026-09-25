# Kế hoạch: bộ tài liệu test cho lớp tri thức (knowledge) và bộ test đi kèm

Ngày: 2026-09-25.
Nhánh: `feature/knowledge-management-sprints-3-9`.
Điều phối: Claude (Opus 5.5).
Ban đầu thực thi qua `opencode run --auto -m <model>`; từ khi opencode hết quota, dùng subagent Claude (xem Nhật ký).

## Mục tiêu

Tạo khoảng 50 tài liệu đầu vào tổng hợp (docx, xlsx, pdf, doc, xls) kèm đáp án chuẩn (gold) để kiểm tra lớp tri thức: phân loại tài liệu, trích xuất theo luật (sections, phamvi, thuatngu, bang1, bang2, dieukien, chuky, phuluc_a), trích xuất §6 bằng LLM, đọc biên bản/phiếu đo, ghép thiết bị, chống trùng và thay phiên bản.
Sau đó viết bộ test tất định (không Docker, không Ollama) chạy trên bộ tài liệu này.

## Phân vai model

| Pha | Model | Việc |
|---|---|---|
| 1. Tìm mẫu | `opencode-go/kimi-k3` | Tìm trên web mẫu QTKĐ/ĐLVN, biên bản kiểm định, phiếu đo, giấy chứng nhận; đối chiếu với corpus thật trong `build/spike_a/*.md`; viết báo cáo mẫu. |
| 2. Sinh tài liệu | `opencode-go/grok-4.6` | Viết spec nội dung (JSON) cho từng tài liệu theo mẫu pha 1, viết builder tất định render ra file, sinh gold. |
| 3. Test | `opencode-go/deepseek-v4.1-flash` | Viết test pytest chạy trên bộ tài liệu, theo kế hoạch test do Claude viết sau pha 2. |
| Review | Claude | Review sau mỗi pha, bắt làm lại cho tới khi đạt tiêu chí nghiệm thu. |

## Pha 1: tìm mẫu (kimi-k3)

Đầu ra: `docs/superpowers/research/2026-09-25-mau-tai-lieu-do-luong.md`.
Nội dung bắt buộc:

- Cấu trúc chuẩn của một văn bản ĐLVN/QTKĐ (thứ tự mục, cách đánh số, Bảng 1 các phép kiểm định, Bảng 2 phương tiện kiểm định, điều kiện, tiến hành, xử lý chung, Phụ lục A mẫu biên bản), có trích nguồn URL.
- Cách diễn đạt điển hình cho phạm vi đo, sai số cho phép, điều kiện môi trường, chu kỳ kiểm định.
- Danh sách ít nhất 12 loại phương tiện đo thật được kiểm định ở Việt Nam (áp kế, nhiệt kế, cân, công tơ nước, taximet, van an toàn, huyết áp kế, ...) kèm số hiệu ĐLVN nếu tìm được, đơn vị, phạm vi và cấp chính xác điển hình.
- Mẫu biên bản kiểm định và phiếu đo: các nhãn trường, bố cục bảng kết quả, cách ghi kết luận, ngày tháng.
- Các biến thể định dạng gặp ngoài thực tế (bảng gộp ô, tiêu đề hai tầng, số kiểu Việt Nam, ký hiệu ÷, ±, ≤, đơn vị viết lệch).

Nghiệm thu pha 1: mỗi mục có ít nhất một nguồn URL hoặc dẫn chiếu tới file trong `build/spike_a/`; không bịa số hiệu ĐLVN (ghi "chưa xác minh" nếu không chắc).

## Pha 2: sinh tài liệu (grok-4.6)

Nguyên tắc: tài liệu phải tái tạo được.
Nội dung nằm trong spec JSON, file nhị phân do builder tất định sinh ra, gold suy ra từ spec chứ không viết tay riêng.

Bố cục:

```
scripts/knowledge_corpus/
  build.py            # đọc specs/, render docx/xlsx bằng OOXML thô (lxml + zipfile, như scripts/make_record_fixtures.py), gọi soffice để ra pdf/doc/xls
  ooxml.py            # helper: đoạn văn heading1..9, bảng, gộp ô gridSpan/vMerge, bảng tiêu đề hai tầng
tests/data/knowledge_corpus/
  specs/<id>.json     # nội dung từng tài liệu
  files/<tên file>    # file đã render (commit vào repo để test không cần soffice)
  manifest.jsonl      # mỗi dòng: id, file, loại mong đợi, mục đích test, các hành vi lỗi đã biết nó chạm tới
  gold/extract_golden.jsonl           # đúng định dạng eval/extract_golden.jsonl
  gold/extract_golden_section6.jsonl  # đúng định dạng eval/extract_golden_section6.jsonl
  gold/records_golden.jsonl           # trường biên bản/phiếu đo mong đợi + các điểm đo
```

Lệnh tái tạo: `make knowledge-corpus`.
Không thêm phụ thuộc runtime; builder chỉ dùng lxml và thư viện chuẩn.

Thành phần bộ dữ liệu (khoảng 50 file):

| Nhóm | Số lượng | Mô tả |
|---|---|---|
| A. QTKĐ docx sạch | 12 | 12 loại phương tiện khác nhau, đủ các mục, Bảng 1/Bảng 2 đúng mẫu, Phụ lục A đúng mẫu. Là "đường cơ sở" cho precision/recall. |
| B. QTKĐ docx biên | 8 | Mỗi file nhắm một hành vi biên: mã "QTKD" không dấu Đ; tiêu đề con cắt ngang mục; Phụ lục A có đoạn kiểu heading; bảng gộp ô; "Chu kỳ kiểm định: 6 tháng" không có "là"; đơn vị "%" trần; `(20,5 ± 2) °C`; mục lục dạng đoạn văn; Bảng 2 tách "(kết thúc)"; số "0,500" và "1 000". |
| C. QTKĐ pdf | 3 | Chuyển từ 3 file nhóm A bằng soffice (pdf có lớp văn bản). |
| D. Biên bản docx | 14 | Ít nhất 3 biên bản cho mỗi QTKĐ chính trong nhóm A đầu tiên; biến thể: trường dạng đoạn văn, dạng bảng nhãn/giá trị, nhãn có dấu hai chấm trong ô bảng, nhiều trường trên một dòng, thiếu số hiệu, cùng số hiệu khác hoa thường, ngày dạng `dd/mm/yyyy`, `d.m.yyyy`, `ngày .. tháng .. năm ..`, ISO, kết luận "Đạt", "Không đạt", "Đạt (không đạt) yêu cầu". |
| E. Phiếu đo xlsx | 8 | Nhãn/giá trị ô kề nhau và trong cùng ô; ô số thực (10.125, 0.5); ô ngày Excel; nhiều sheet (chỉ đọc sheet đầu). |
| F. Hồ sơ trùng và phiên bản | 3 | Một bản trùng hash với tên khác; một QTKĐ phiên bản 2 thay phiên bản 1; một file tên chứa cả "QTKD" và "biên bản". |
| G. Legacy và ngoài phạm vi | 2 | Một `.doc` và một `.xls` (qua soffice), mong đợi bị bỏ qua/từ chối. |

Nghiệm thu pha 2 (Claude review):

1. `make knowledge-corpus` chạy sạch hai lần liên tiếp và cho ra docx/xlsx giống hệt byte (tất định, không timestamp trong zip); file do soffice sinh (pdf/doc/xls) được phép khác byte.
2. Mọi file nhóm A qua `python -m ingestion.spike_a` ra Markdown có đủ heading; `eval.extract_eval` trên nhóm A với gold tương ứng đạt precision ≥ 0.95 và recall ≥ 0.80 cho từng fact kind (chứng minh gold khớp nội dung và nhóm A thực sự "sạch").
3. Gold nhóm B ghi hành vi **đúng theo spec**, còn manifest ghi rõ hành vi hiện tại khác gì (để pha 3 đánh dấu `xfail(strict=True)`).
4. Không có số liệu mâu thuẫn giữa văn bản, Phụ lục A và biên bản của cùng một QTKĐ.
5. Nội dung tiếng Việt có dấu đầy đủ, thuật ngữ đo lường đúng, không sao chép nguyên văn file trong `TC_DL/`.

## Pha 3: kế hoạch test và triển khai (deepseek-v4.1-flash)

Kế hoạch test chi tiết sẽ được Claude viết sau khi pha 2 đạt, dựa trên manifest thật.
Khung dự kiến:

- `tests/unit/knowledge_corpus/` (marker `unit`, SQLite in-memory như `tests/unit/backend/conftest.py`).
- Test phân loại: mọi file trong manifest ra đúng loại theo tên file.
- Test trích xuất luật: chạy spike_a trên docx nhóm A+B (cache một lần mỗi session), so với gold theo từng fact kind; nhóm A yêu cầu precision/recall đạt ngưỡng, nhóm B kiểm từng case.
- Test §6: client LLM kịch bản trả về facts, kiểm tra quote-grounding loại bỏ số bịa.
- Test biên bản/phiếu đo: đọc nhóm D+E với mapping lấy từ Phụ lục A đã duyệt, so với `records_golden.jsonl`; ghép thiết bị (thiếu serial, khác hoa thường).
- Test trùng/phiên bản: hash trùng bị chặn, supersede đúng.
- Hành vi lỗi đã biết: `pytest.mark.xfail(strict=True, reason=...)` để test tự đỏ khi lỗi được sửa.

Nghiệm thu pha 3:

1. `make test-unit` xanh toàn bộ (tính cả suite cũ), không test flaky (chạy 3 lần).
2. `make lint` sạch.
3. Không có test chỉ kiểm "không crash"; mỗi test so với giá trị gold cụ thể.
4. Mỗi `xfail` trỏ tới một mục trong manifest.
5. Suite mới chạy dưới 60 giây.

## Quy trình review

Sau mỗi pha Claude đọc diff, chạy các lệnh nghiệm thu, rồi gửi phản hồi cụ thể (file, dòng, lỗi) vào lại cùng phiên opencode (`opencode run -s <session>`).
Lặp tới khi đạt; mỗi vòng ghi kết quả vào mục "Nhật ký" dưới đây.

## Nhật ký

- 2026-09-25: lập kế hoạch; xác nhận opencode có `kimi-k3`, `grok-4.6`, `deepseek-v4.1-flash`.
- 2026-09-25: kimi-k3 bị dừng giữa pha 1 (`Go usage limit exceeded`); Zen báo `Insufficient account funds`; 9router không chạy.
- 2026-09-25: theo quyết định của người dùng, chuyển sang subagent Claude: pha 1 và pha 2 dùng Sonnet, pha 3 dùng Haiku (nâng lên Sonnet nếu review trượt lặp lại). Tiêu chí nghiệm thu giữ nguyên.
- 2026-09-25: pha 1 vòng 1 trượt (5 câu sai số cho phép dùng "nhưng không nhỏ hơn" sai nghĩa ở 7.3, 7.6, 7.8, 7.10, 7.12); vòng 2 đạt.
- 2026-09-25: pha 2 vòng 1 trượt: gold nhóm A suy bằng cách chạy chính `knowledge.rules.extract_all` (vòng tròn, P/R = 1,0 vô nghĩa); định nghĩa thuật ngữ bị "là là"; Bảng 2 ghi sai số vào cột phạm vi; 12 file nhóm A cùng một khuôn, thiếu đa dạng. Đã gửi yêu cầu làm lại R1..R6.
- 2026-09-25: pha 2 vòng 2 đạt về nội dung (gold nhóm A suy từ spec, tự kiểm lại độc lập 169/169, §6 16/16); vòng 3 sửa F1 (`--no-soffice` để lọt file trung gian vào `files/`), F2 (thêm K15 + B09: dấu chấm câu sau đơn vị), F3 (dẫn chiếu ĐLVN khớp nghiên cứu), F4 (`make lint` sạch). Pha 2 ĐẠT: 51 file, tất định, lint sạch.
- 2026-09-25: viết kế hoạch test pha 3: `docs/superpowers/plans/2026-09-25-knowledge-corpus-tests.md`.
- 2026-09-25: pha 3 vòng 1 (Haiku) trượt: chỉ T1..T3 được viết, T4..T9 là stub `skip`; loader trả rỗng im lặng khi thiếu file; test trùng lặp không gọi `save_upload`; chưa kiểm đột biến. Đã gửi yêu cầu làm lại C1..C3 + T4..T9. Nếu vòng 2 trượt thì nâng lên Sonnet.
- 2026-09-25: pha 3 vòng 2 (Haiku) trượt: T5 lọc gold theo manifest id thay vì stem nên luôn rỗng và đạt vô nghĩa (kiểm đột biến không bắt được); T7/T8 là `assert True`/kiểm file tồn tại; còn `pytest.skip`; chỉ 2 xfail trên 14 mã K. Theo kế hoạch, nâng lên Sonnet (agent mới) với danh sách anti-pattern và 3 phép kiểm đột biến bắt buộc.
- 2026-09-25: pha 3 vòng 3 (Sonnet) ĐẠT: `tests/unit/knowledge_corpus/` 612 passed, 24 xfailed (strict, mỗi cái gắn mã K01..K15), 3,1 s; `make test-unit` 1247 passed, 24 xfailed, 1 skipped (skip có sẵn: `test_kotaemon_reader.py` cần gói `kotaemon`); `make lint` sạch. Điều phối viên tự kiểm thêm 3 phép đột biến độc lập (phân loại F03, chuẩn B07, serial D05): cả 3 đều bị bắt, file khôi phục khớp byte.
