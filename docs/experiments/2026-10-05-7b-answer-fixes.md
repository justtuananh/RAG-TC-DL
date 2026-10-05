# Thí nghiệm: sửa lỗi câu trả lời của qwen2.5:7b-instruct

Ngày: 2026-10-05.
Nhánh: `exp/weighted-rrf`.

## Kết luận

Đưa vào production hai cách sửa: khôi phục công thức nguyên văn (`core.latex.restore_formulas`) và ngân sách nguồn riêng cho từng file ở câu so sánh nhiều QTKĐ (`retrieval.top_n_per_file: 4`).
Trên bộ answer 32 câu qua đúng đường production, coverage tăng từ 0.891 lên 0.949, nhóm `formula` từ 0.667 lên 1.000, retrieval (recall, MRR) giữ nguyên.
Hai cách khác có tác dụng nhưng chưa triển khai: ghi tên quy trình vào tiêu đề nguồn và sửa glyph "Û" của font Doluong.
Ba cách bị loại vì làm kết quả xấu đi: thêm luật vào prompt, `repeat_penalty` 1.0, prompt trả lời từng phần.

## Lỗi cần sửa

Sau khi đổi model sang qwen2.5:7b-instruct, đo trên bộ 32 câu thấy ba nhóm lỗi:

- Model chép công thức nhưng đổi hình thức: thêm hoặc bỏ `\left( \right)`, thêm `\tag{n}`, viết `^2` thay cho `^{2}`.
  Câu trả lời không còn là chuỗi LaTeX của nguồn, trái với nguyên tắc chép nguyên văn công thức.
- Câu 115 (so sánh nhiệt độ môi trường của 1.061 và 1.159): model ghi 1.159 là (20 ± 5) °C, trong khi nguồn ghi (23 ± 5) °C.
- Câu 116 (so sánh độ ẩm tương đối của van an toàn và áp kế píttông): model từ chối dù ngữ cảnh có đủ hai giá trị.

## Cách đo

- Harness thí nghiệm cache kết quả retrieval của 32 câu (`evaluation/answer_set.jsonl` và `answer_set_ext.jsonl`), mỗi biến thể chỉ chạy lại bước sinh và chấm bằng `scoring.answer_scoring`.
- Thêm chỉ số "công thức nguyên văn": số công thức (span `$…$` có `=` hoặc `\frac`) trong câu trả lời xuất hiện đúng từng ký tự trong ngữ cảnh.
- Cố định `seed` của Ollama và chạy 3 seed (42, 7, 123), vì với temperature 0.1 cùng một cấu hình có thể cho 11/13 hoặc 5/11 công thức nguyên văn tùy seed.
- Số cuối đo bằng `python -m evaluation.answer_eval` (đã có `fix_latex` và `restore_formulas` như production) và `python -m evaluation.run_eval --mode hybrid` trên cả hai bộ eval retrieval.

## Nguyên nhân gốc

- Công thức: lỗi của model.
  Đã thử thêm vào prompt "chép từng ký tự, không thêm \left, \right": không có tác dụng, câu 111 vẫn có `\left`.
- Câu 115: lỗi retrieval.
  Câu hỏi được định tuyến tới 2 file, `top_n=5` chia mỗi file 2 suất cộng 1 suất dư.
  Mục 5.1 của 1.159 (chứa 23 ± 5) có điểm rerank 0.721, đứng thứ 4 trong file sau ba mục 6.x, nên bị cắt.
  Thiếu dữ kiện, model gán giá trị của 1.061 cho 1.159.
- Câu 116: tiêu đề nguồn chỉ có mã file (`QTKD_1.159_2021_ND_FINAL`), không có tên thiết bị.
  Câu hỏi không nêu số QTKĐ, nên model không biết nguồn nào là van an toàn, nguồn nào là áp kế píttông.
  Ngoài ra nguồn 1.159 ghi "Độ ẩm tương đối: Û 80 %": "Û" là glyph của font Doluong, hiển thị thành "≤", nhưng ingestion đọc ký tự thô.
  Lỗi này có ở 8 chỗ trong 3 QTKĐ (1.071, 1.159, 1.160), cả trong đoạn văn lẫn bảng.

## Kết quả các biến thể

Mỗi ô là khoảng giá trị trên 3 seed.

| Biến thể | Coverage | Công thức nguyên văn | Từ chối câu ngoài phạm vi | Câu 115 | Câu 116 |
|---|---|---|---|---|---|
| Gốc | 0.865-0.904 | 5-9 / 11-13 | 6/6 | 0.5 | từ chối |
| `repeat_penalty` 1.0 (1 seed) | 0.853 | 2/8 | 6/6 | từ chối | từ chối |
| Prompt trả lời từng phần (1 seed) | 0.846 | 2/6 | **3/6** | 1.0 | 1.0 |
| Khôi phục công thức | 0.904-0.942 | 11-12 / 11-13 | 6/6 | 0.5 | từ chối |
| + `top_n_per_file: 4` + sửa glyph | 0.923-0.962 | 11 / 11-12 | 6/6 | **1.0** | từ chối |
| + tên quy trình trong tiêu đề nguồn | 0.949-0.987 | 11-13 / 11-13 | 6/6 | 1.0 | **1.0** |

- Prompt trả lời từng phần làm hỏng cơ chế từ chối: chỉ còn 3-4/6 câu ngoài phạm vi được từ chối, nên bị loại.
- Tên quy trình trong tiêu đề nguồn sửa được câu 116 ở cả 3 seed, nhưng ở 1/3 seed model tự tính "nhỏ hơn khoảng 25%", vi phạm nguyên tắc chỉ tra cứu.
  Bộ chấm ảo giác còn báo nhầm hai số lấy từ tiêu đề ("1 400 bar", "2021"), vì nó chỉ so với văn bản đoạn trích.
- Công thức duy nhất không khôi phục được là `Y = a + bX` (câu 132): model bỏ dấu `×` của nguồn, khác về nội dung chứ không chỉ về hình thức, nên được giữ nguyên.

## Đã triển khai

- `core.latex.restore_formulas(answer, context)`: thay công thức của câu trả lời bằng công thức nguồn có cùng khóa.
  Khóa bỏ qua `\tag`, `\left`/`\right`, lệnh giãn cách, khoảng trắng, `×` với `\times`, ngoặc nhọn quanh một ký hiệu.
  Công thức không có trong nguồn, hoặc khớp với hai công thức nguồn khác nhau, được giữ nguyên.
  Chạy sau `fix_latex` ở `api/services/chat_stream.py`, `ui/gradio_app.py` và `evaluation/answer_eval.py`.
- `retrieval.top_n_per_file: 4`: câu định tuyến tới N ≥ 2 file nhận `max(top_n, 4 × N)` nguồn.
- Sửa kèm: Gradio từng ghi đè kết quả `fix_latex` bằng văn bản thô ở bản trả lời cuối.

Số đo cuối, qua đúng đường production:

| | Trước | Sau |
|---|---|---|
| answer_eval coverage | 0.891 | **0.949** |
| answer_eval nhóm `formula` | 0.667 | **1.000** |
| answer_eval nhóm `cross_file` | 0.500 | **0.667** |
| answer_eval cite_strict | 0.875 | 0.880 |
| answer_eval từ chối đúng / ảo giác | 1.000 / 0 | 1.000 / 0 |
| run_eval 55 câu: recall@5 / MRR | 0.982 / 0.870 | 0.982 / 0.870 |
| run_eval 10 câu: recall@5 / MRR | 1.000 / 0.925 | 1.000 / 0.925 |

## Chưa triển khai

- Tên quy trình trong tiêu đề nguồn: cần lưu tên tài liệu vào payload Qdrant (index lại) hoặc đọc từ cơ sở dữ liệu, và cần thêm chặn số tự tính trong câu so sánh.
- Glyph "Û" của font Doluong: sửa ở `ingestion/extract_docx.py`, rồi chạy lại Stage 1 và index lại Qdrant.
