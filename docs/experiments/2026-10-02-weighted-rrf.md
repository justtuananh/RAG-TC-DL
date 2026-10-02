# Thí nghiệm: RRF có trọng số cho dense và BM25

Ngày: 2026-10-02.
Nhánh: `exp/weighted-rrf`.
Plan: `docs/superpowers/plans/2026-10-02-weighted-rrf.md`.

## Kết luận

Giữ nguyên `rrf_weight_dense: 1.0`, `rrf_weight_bm25: 1.0`, `rrf_k: 60`.
Không cấu hình nào trong 55 cấu hình của lưới vượt mốc đủ ngưỡng của luật chọn.
Trên bộ eval hiện tại, trọng số RRF gần như không ảnh hưởng tới kết quả cuối, vì cross-encoder quyết định thứ tự và pool 60 ứng viên đã chứa section đúng ở mọi cấu hình.

## Cách đo

- Bộ tinh chỉnh `evaluation/eval_set.jsonl` (55 câu), bộ giữ lại `evaluation/eval_set_ext.jsonl` (10 câu), gộp 65 câu.
- Lưới: `alpha = w_dense` từ 0.0 tới 1.0 bước 0.1, `w_bm25 = 1 - alpha`, nhân với `rrf_k` thuộc {10, 20, 40, 60, 100}.
  Chỉ tỷ lệ hai trọng số có tác dụng, nên `alpha = 0.5` cho đúng thứ tự của cấu hình 1.0 / 1.0.
- Công cụ `evaluation/fusion_sweep.py` gọi đúng `retrieval.retriever.retrieve` của production, chỉ cache các lời gọi I/O (embedding, tìm kiếm, section cha, điểm cross-encoder theo từng cặp câu hỏi và document).
- Kiểm tra cache: hàng `alpha = 0.5, k = 60` khớp đúng từng số đo của `python -m evaluation.run_eval --mode hybrid` chạy không cache trước khi sửa code (bộ 55 câu: recall@1 0.782, recall@5 0.982, MRR 0.870, nDCG@5 0.899; bộ 10 câu: recall@1 0.900, recall@5 1.000, MRR 0.925).
- Thời gian: 18 phút cho cấu hình đầu (lấp cache), 4.5 phút cho 54 cấu hình còn lại.

## Kết quả

### Sau rerank (thứ người dùng nhận)

recall@5 gộp bằng 0.985 (64/65) ở CẢ 55 cấu hình, kể cả `alpha = 0.0` (chỉ BM25) và `alpha = 1.0` (chỉ dense).
Câu trượt duy nhất luôn là câu 36 ("Phương trình cơ bản áp kế pittông..."), và section đúng không có trong pool ở bất kỳ cấu hình nào.

MRR gộp theo `alpha` (hàng) và `rrf_k` (cột):

| alpha \ k | 10 | 20 | 40 | 60 | 100 |
|---|---|---|---|---|---|
| 0.0 | 0.871 | 0.871 | 0.871 | 0.871 | 0.871 |
| 0.1 | 0.871 | 0.871 | 0.879 | 0.879 | 0.879 |
| 0.2 | 0.863 | 0.879 | 0.879 | 0.879 | 0.879 |
| 0.3 | 0.879 | 0.879 | 0.879 | 0.879 | 0.879 |
| 0.4 | 0.886 | 0.886 | 0.886 | 0.886 | 0.886 |
| 0.5 | 0.879 | 0.879 | 0.879 | 0.879 | 0.879 |
| 0.6 tới 1.0 | 0.879 | 0.879 | 0.879 | 0.879 | 0.879 |

MRR tốt nhất là `alpha = 0.4` (0.886, hơn mốc 0.007).
Chênh lệch đó đến từ đúng một câu: câu 53 lên từ hạng 2 lên hạng 1.
Đầu mút BM25 còn tệ hơn mốc: `alpha = 0.0` làm câu 19 và 40 tụt từ hạng 1 xuống hạng 2.

### Trước rerank (chất lượng của riêng phép gộp)

`pool_recall` (section đúng có trong pool đưa vào cross-encoder) bằng 0.985 ở mọi cấu hình.

`rrf_recall@5` (5 section đầu theo thứ tự RRF, cũng là thứ người dùng nhận khi service rerank lỗi):

| alpha \ k | 10 | 20 | 40 | 60 | 100 |
|---|---|---|---|---|---|
| 0.0 | 0.938 | 0.938 | 0.938 | 0.938 | 0.938 |
| 0.2 | 0.923 | 0.923 | 0.923 | 0.923 | 0.923 |
| 0.4 | 0.923 | 0.923 | 0.923 | 0.923 | 0.923 |
| 0.5 | 0.938 | 0.938 | 0.938 | 0.923 | 0.923 |
| 0.6 | 0.923 | 0.923 | 0.923 | 0.923 | 0.923 |
| 0.8 | 0.846 | 0.846 | 0.862 | 0.877 | 0.877 |
| 1.0 | 0.815 | 0.815 | 0.815 | 0.815 | 0.815 |

Nghiêng về dense làm phép gộp tệ đi rõ rệt (0.815 ở `alpha = 1.0`).
BM25 là nhánh mạnh hơn khi đứng một mình, khớp với lý do dự án giữ BM25 cho mã QTKĐ và đơn vị đo.
Nghiêng về BM25 không cải thiện hơn mốc ở `k <= 40`.

## Quyết định theo luật chọn

Luật chọn được viết trước khi chạy (mục 3e của plan).
Cấu hình đứng đầu xếp hạng là `alpha = 0.4, k = 60`: bằng mốc ở recall@5, MRR hơn 0.007, dưới ngưỡng 0.02.
Mốc đã có recall@5 64/65, nên không cấu hình nào có thể hơn 2 câu như ngưỡng thứ nhất yêu cầu.
Vì vậy giữ 1:1.

## Việc nên làm tiếp

- Câu 36 trượt ở bước sinh ứng viên, không phải ở bước gộp: không trọng số nào đưa được section đúng vào pool.
  Cần soi riêng `top_k`, nội dung chunk của mục 6.3.2 trong QTKĐ 1.159, và phần mở rộng truy vấn.
- Bộ eval đang bão hòa (64/65), nên không phân biệt được các cấu hình.
  Khi kho tăng lên hàng nghìn QTKĐ, hoặc khi có bộ eval khó hơn, chạy lại công cụ quét.

## Chạy lại

```bash
.venv-dev/bin/python -m evaluation.fusion_sweep                      # lưới mặc định, ghi vào logs/fusion_sweep/
.venv-dev/bin/python -m evaluation.fusion_sweep --alphas 0.3,0.5,0.7 --ks 40,60
```

Cần các service embedding, reranker, Qdrant đang chạy.
Đầu ra: `results.csv` (một hàng mỗi cấu hình), `results.md` (xếp hạng, lưới, quyết định), `per_question.jsonl` (hạng từng câu ở từng cấu hình).
Lượt quét dừng hẳn nếu service rerank lỗi, thay vì ghi số đo của thứ tự dự phòng.
