# Plan: RRF có trọng số cho dense và BM25

Nhánh: `exp/weighted-rrf` (tách từ `refactor/backend-layout` tại `ae69d12`).
Ngày: 2026-10-02.

## Mục tiêu

Hiện `retrieval/hybrid_retriever.py::rrf_fuse` cộng `1/(k + rank + 1)` cho cả hai nhánh với trọng số bằng nhau.
Thí nghiệm này thêm trọng số riêng `w_dense`, `w_bm25`, quét lưới các cặp giá trị cùng `rrf_k`, và chọn cặp tốt nhất theo một luật chọn cố định viết trước (mục "Luật chọn").
Nếu không cặp nào thắng rõ ràng thì giữ nguyên 1:1, ghi lại kết quả, không đổi hành vi production.

## Hiểu đúng trước khi làm

- Điểm RRF có trọng số: `score(d) = w_dense / (k + r_dense(d) + 1) + w_bm25 / (k + r_bm25(d) + 1)`.
- Nhân cả hai trọng số với cùng một hằng số không đổi thứ tự.
  Vì vậy chỉ TỶ LỆ quan trọng: lưới quét theo `alpha = w_dense`, `w_bm25 = 1 - alpha`.
  `alpha = 0.5` cho đúng thứ tự của cấu hình hiện tại (1.0 / 1.0).
- Điểm cuối cùng là điểm cross-encoder, không trộn RRF.
  Trọng số chỉ ảnh hưởng (a) ứng viên nào lọt vào `rerank_pool` (60), (b) chunk con nào đại diện cho mỗi section cha khi dedupe theo `parent_id`, (c) thứ tự dự phòng khi service rerank lỗi.
  Vì vậy phải đo cả số đo TRƯỚC rerank, không chỉ recall@5 cuối.
- Bộ eval nhỏ: `evaluation/eval_set.jsonl` 55 câu (bộ tinh chỉnh), `evaluation/eval_set_ext.jsonl` 10 câu (bộ giữ lại).
  Một câu = 1.8% recall trên bộ 55 câu, nên dễ quá khớp.
  Luật chọn bên dưới có ngưỡng để chống việc này.

## Bước 0: Đo mốc (baseline) trước khi sửa code

Điều kiện: các container `qtkd-embedding`, `qtkd-reranker`, `qtkd-qdrant` đang chạy (`docker ps`).

```bash
mkdir -p logs/fusion_sweep
.venv-dev/bin/python -m evaluation.run_eval --mode hybrid > logs/fusion_sweep/baseline_main.log 2>&1; echo EXIT=$?
.venv-dev/bin/python -m evaluation.run_eval --mode hybrid --eval-file evaluation/eval_set_ext.jsonl > logs/fusion_sweep/baseline_ext.log 2>&1; echo EXIT=$?
```

Ghi lại recall@1/3/5/10, MRR, nDCG@5 của cả hai log.
Không commit gì ở bước này (`logs/` bị gitignore).

## Bước 1: RRF có trọng số (TDD)

Tệp sửa: `core/schema.py`, `config/settings.yaml`, `retrieval/hybrid_retriever.py`, `tests/unit/retrieval/test_rrf_fuse.py`, `tests/unit/core/test_settings_values.py`.

1. Viết test trước trong `tests/unit/retrieval/test_rrf_fuse.py`, chạy thấy FAIL:
   - `rrf_fuse(dense, bm25, k=60, w_dense=2.0, w_bm25=1.0)`: điểm của doc chung là `2/(60+r_d+1) + 1/(60+r_b+1)` (dùng `pytest.approx`).
   - `w_bm25=0.0`: doc chỉ có ở BM25 có `rrf_score == 0.0` và đứng sau mọi doc có ở dense.
   - Không truyền trọng số: đọc từ settings; với `settings_override({"retrieval.rrf_weight_dense": 3.0})` kết quả đổi đúng như truyền tay.
   - Các test cũ (điểm `1/62 + 1/61`) phải còn xanh nguyên văn, chứng minh mặc định 1.0 / 1.0 giữ đúng hành vi cũ.
2. `core/schema.py`:
   - Thêm `NonNegativeFloat = Annotated[float, Field(ge=0)]` cạnh các kiểu sẵn có.
   - `RetrievalSettings` thêm `rrf_weight_dense: NonNegativeFloat` và `rrf_weight_bm25: NonNegativeFloat`.
   - Thêm `@model_validator(mode="after")` từ chối khi cả hai bằng 0 (thông báo lỗi tiếng Việt).
     Test cho validator này trong `tests/unit/core/test_settings_values.py` hoặc `test_settings_loader.py` (dùng `with_overrides`, chờ `SettingsError`).
3. `config/settings.yaml`, mục `retrieval:`, ngay dưới `rrf_k: 60`:
   ```yaml
   rrf_weight_dense: 1.0                   # trọng số nhánh dense trong RRF; chỉ tỷ lệ dense/BM25 có tác dụng
   rrf_weight_bm25: 1.0                    # trọng số nhánh BM25 trong RRF
   ```
   Thêm assert giá trị mặc định vào `tests/unit/core/test_settings_values.py`.
4. `retrieval/hybrid_retriever.py::rrf_fuse`: chữ ký mới
   ```python
   def rrf_fuse(
       dense_hits: list[dict],
       bm25_hits: list[dict],
       k: int | None = None,
       *,
       w_dense: float | None = None,
       w_bm25: float | None = None,
   ) -> list[dict]:
   ```
   Đọc mặc định từ `get_settings().retrieval` LÚC GỌI (không lúc import).
   Cập nhật docstring: công thức có trọng số, và ghi chú "chỉ tỷ lệ có tác dụng".
   Không đổi chỗ gọi trong `retrieval/retriever.py` (nó đã đọc từ settings qua mặc định).
5. Gate: `make check` xanh (gồm `tests/unit/qa/test_architecture.py`).
6. Commit: `feat(retrieval): weight the dense and BM25 branches in RRF from settings`.

## Bước 2: Tách lời gọi HTTP của reranker thành một hàm riêng

Mục đích: công cụ quét cần cache điểm cross-encoder theo cặp (câu hỏi, document) để không gọi lại service cho mỗi cấu hình.

Tệp sửa: `reranking/reranker.py`, test trong `tests/unit/reranking/` (tạo `test_score_documents.py`).

1. Thêm `score_documents(query: str, documents: list[str]) -> list[float]` trong `reranking/reranker.py`: gọi `settings.services.rerank_url` với `top_n=len(documents)`, trả điểm theo ĐÚNG thứ tự `documents` (sắp lại theo `index`), ném lỗi nếu HTTP lỗi.
2. `rerank_hits` gọi `score_documents` thay cho `requests.post` trực tiếp; nhánh dự phòng RRF khi lỗi giữ nguyên.
   Hành vi bên ngoài không đổi.
3. Test (dùng `responses` như `tests/unit/retrieval/test_retriever_pipeline.py`): service trả `results` lộn thứ tự, `score_documents` vẫn trả điểm đúng thứ tự đầu vào; HTTP 500 thì ném lỗi.
4. Gate: `make check` xanh.
   Commit: `refactor(reranking): split the cross-encoder HTTP call into score_documents`.

## Bước 3: Công cụ quét `evaluation/fusion_sweep.py`

Tệp mới: `evaluation/fusion_sweep.py`, `tests/unit/evaluation/test_fusion_sweep.py` (tạo thư mục nếu chưa có, theo cấu trúc `tests/unit/` hiện tại).
Tệp sửa: `core/settings_loader.py` (thêm context manager công khai).

### 3a. Override settings công khai

Thêm vào `core/settings_loader.py`:

```python
@contextmanager
def overridden(overrides: Mapping[str, Any]) -> Iterator[Settings]:
    """Tạm đổi vài khóa cấu hình cho cả tiến trình (công cụ eval); khôi phục khi thoát."""
```

Nó gán `_override = with_overrides(get_settings(), overrides)` rồi khôi phục giá trị cũ trong `finally`.
Test trong `tests/unit/core/test_settings_loader.py`: bên trong khối thấy giá trị mới, ra khỏi khối (kể cả khi có exception) thấy giá trị cũ.

### 3b. Nguyên tắc chống drift

Công cụ PHẢI gọi đúng `retrieval.retriever.retrieve(query, top_n=10)` của production cho mỗi cấu hình, không chép lại phễu.
Việc tăng tốc chỉ bằng cách thay các hàm I/O bằng bản có cache, ở cấp thuộc tính module (vì `retriever.py` gọi qua `hybrid.search_both`, `embedder.embed_query`, `reranker.rerank_hits`, và `reranker.py` gọi `qdrant.fetch_parent`, `score_documents`):

| Thay | Khóa cache |
|---|---|
| `embedding.embedder.embed_query` | chuỗi truy vấn |
| `retrieval.hybrid_retriever.search_both` | `(expanded_query, top_k, file_stem)` (vec suy ra từ expanded nên không cần trong khóa) |
| `vectorstore.qdrant.fetch_parent` | `parent_id` |
| `reranking.reranker.score_documents` | từng cặp `(query, document)`; chỉ gửi service các document chưa có trong cache, MỘT lời gọi cho cả nhóm thiếu |
| `reranking.reranker.rerank_hits` | không cache; bọc để GHI LẠI danh sách `hits` đầu vào (pool sau RRF + lọc nhiễu) rồi gọi bản gốc |

Mọi thay thế đặt trong một context manager (dùng `unittest.mock.patch.object` hoặc tự lưu/khôi phục), khôi phục khi xong.
Phải có kiểm tra kiểu "đi đúng đường": sau lượt đầu, đếm số lần gọi service thật; ở các cấu hình sau con số này phải giảm mạnh.

### 3c. Lưới quét

- `alpha` (= `w_dense`, `w_bm25 = 1 - alpha`): `0.0, 0.1, 0.2, ..., 1.0` (11 giá trị).
- `rrf_k`: `10, 20, 40, 60, 100` (5 giá trị).
- Tổng 55 cấu hình.
  Mỗi cấu hình chạy qua `overridden({"retrieval.rrf_weight_dense": alpha, "retrieval.rrf_weight_bm25": 1 - alpha, "retrieval.rrf_k": k})`.
- Mốc so sánh: `alpha = 0.5, k = 60` (trùng thứ tự với cấu hình hiện tại).
- CLI: `--alphas`, `--ks` (danh sách cách nhau dấu phẩy, mặc định như trên), `--tune-file` (mặc định `evaluation/eval_set.jsonl`), `--holdout-file` (mặc định `evaluation/eval_set_ext.jsonl`), `--out-dir` (mặc định `logs/fusion_sweep`).
  Dải giá trị là tham số của công cụ thí nghiệm, không phải cấu hình runtime, nên để trong CLI là đúng quy tắc "settings-only".

### 3d. Số đo cho mỗi cấu hình

Tính riêng cho bộ tinh chỉnh, bộ giữ lại, và gộp (65 câu), dùng `scoring.retrieval_metrics.hit_rank` và `compute_metrics` (không viết lại công thức):

- Sau rerank (`retrieve` trả về): recall@1, recall@3, recall@5, recall@10, MRR, nDCG@5.
- Trước rerank, trên `hits` ghi lại được:
  - `pool_recall`: section mong đợi có nằm trong pool đưa vào cross-encoder không.
  - `rrf_recall@5`: dedupe pool theo `parent_id` giữ thứ tự RRF, lấy 5 đầu, rồi `hit_rank`.
    Đây là chất lượng của riêng phép gộp (và cũng là thứ người dùng nhận khi reranker lỗi).
- Danh sách id câu hỏi trượt ở recall@5 (để so từng câu với mốc).
  `eval_set_ext.jsonl` không có trường `id`: dùng `ext-<số dòng>`.

Đầu ra trong `--out-dir`: `results.csv` (một dòng mỗi cấu hình, đủ cột số đo), `results.md` (bảng xếp hạng + hai bảng lưới `alpha × k` cho recall@5 gộp và MRR gộp), `per_question.jsonl` (rank từng câu ở từng cấu hình).

### 3e. Luật chọn (cố định TRƯỚC khi nhìn kết quả)

1. Loại cấu hình có recall@5 trên bộ tinh chỉnh < 0.85 (gate của dự án).
2. Loại cấu hình có recall@5 trên bộ giữ lại thấp hơn mốc.
3. Xếp hạng theo, lần lượt: recall@5 gộp, MRR gộp, `rrf_recall@5` gộp, `pool_recall` gộp; hòa nữa thì ưu tiên gần mốc hơn (`|alpha - 0.5|` nhỏ hơn, rồi `|k - 60|` nhỏ hơn).
4. Kiểm tra cao nguyên: các láng giềng (`alpha ± 0.1` cùng `k`, và `k` liền kề cùng `alpha`) phải có recall@5 gộp kém cấu hình thắng không quá 1 câu.
   Không qua thì xét cấu hình kế tiếp.
5. Chỉ đổi production khi cấu hình thắng hơn mốc ít nhất 2 câu ở recall@5 gộp, HOẶC bằng recall@5 nhưng MRR gộp cao hơn ít nhất 0.02, VÀ không làm trượt câu nào mà mốc đang trúng ở recall@5 (so `per_question.jsonl`).
   Không đạt: giữ 1.0 / 1.0 và `rrf_k: 60`, chỉ ghi kết quả.

Luật này được cài thành hàm thuần trong `fusion_sweep.py` (ví dụ `pick_winner(rows, baseline) -> Decision`) và in ra quyết định cùng lý do.

### 3f. Test đơn vị (không gọi service)

- `pick_winner`: các trường hợp loại do gate, do bộ giữ lại, do cao nguyên, chọn mốc khi không ai hơn đủ ngưỡng, hòa thì chọn gần mốc.
- Cache `score_documents`: gọi hai lần với tập document chồng nhau, hàm service giả chỉ nhận các document mới, điểm trả đúng thứ tự.
- `rrf_recall@5` dedupe theo `parent_id` đúng thứ tự.

Gate: `make check` xanh (gồm lint của `evaluation/`).
Commit: `feat(evaluation): add fusion_sweep to tune the RRF dense/BM25 weights`.

## Bước 4: Chạy quét và nghiệm thu bằng eval thật

1. Chạy: `.venv-dev/bin/python -m evaluation.fusion_sweep > logs/fusion_sweep/sweep.log 2>&1; echo EXIT=$?`.
2. Kiểm tra tính đúng của cache: hàng `alpha=0.5, k=60` trong `results.csv` phải khớp ĐÚNG các số đo của `baseline_main.log` / `baseline_ext.log` ở Bước 0.
   Lệch thì dừng, tìm nguyên nhân (thường là cache sai khóa hoặc điểm reranker phụ thuộc lô), không đi tiếp.
3. Nếu luật chọn đổi production: ghi `rrf_weight_dense`, `rrf_weight_bm25`, `rrf_k` mới vào `config/settings.yaml`, sửa assert trong `tests/unit/core/test_settings_values.py`, rồi chạy lại eval THẬT không cache:
   ```bash
   .venv-dev/bin/python -m evaluation.run_eval --mode hybrid > logs/fusion_sweep/winner_main.log 2>&1; echo EXIT=$?
   .venv-dev/bin/python -m evaluation.run_eval --mode hybrid --eval-file evaluation/eval_set_ext.jsonl > logs/fusion_sweep/winner_ext.log 2>&1; echo EXIT=$?
   ```
   Số đo phải khớp hàng tương ứng trong `results.csv` và vẫn đạt recall@5 ≥ 0.85.
4. `make check` xanh.

## Bước 5: Ghi kết quả

1. Tạo `docs/experiments/2026-10-02-weighted-rrf.md` (tiếng Việt, mỗi câu một dòng, không dùng dấu gạch dài): mốc, bảng lưới recall@5 và MRR gộp, top 10 cấu hình, quyết định theo luật chọn và lý do, các câu đổi trạng thái so với mốc, cách chạy lại công cụ.
2. `CLAUDE.md`, đoạn mô tả `retrieval/retriever.py` ở Stage 3: thêm một câu về `rrf_weight_dense` / `rrf_weight_bm25` và công cụ `evaluation/fusion_sweep.py`.
3. Commit: nếu đổi production thì `perf(retrieval): ...` cho `config/settings.yaml` + test, riêng `docs: ...` cho tài liệu; nếu không đổi thì chỉ `docs: record the weighted RRF sweep result`.

## Ràng buộc chung

- Chỉ `git add` đúng các tệp của bước đó.
  Không `git add -A`, không đụng các tệp chưa theo dõi sẵn có ở gốc repo (`*.xlsx`, `*.doc`, `*.docx`, `run-dev.sh`, `test_chatbot/`, `docs/superpowers/*.docx`).
- Không push.
  Không sửa `CHANGELOG.md`.
  Không dùng dấu gạch dài.
- Chuỗi hiển thị, docstring về nghiệp vụ, comment: tiếng Việt như code xung quanh.
- Không hardcode URL, cổng, tên model, ngưỡng runtime trong code: đọc `get_settings()` lúc gọi.
