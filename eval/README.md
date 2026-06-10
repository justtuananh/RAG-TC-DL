# Eval — hai tầng đo

Hệ có **hai** bộ đo, tách bạch hai thứ khác nhau:

| | Đo gì | File | Lệnh | Cổng đạt |
|---|---|---|---|---|
| **Retrieval** | Section đúng có nằm trong top-k? (recall@k, nDCG, MRR) | `run_eval.py` + `eval_set.jsonl` (55 câu) | `make eval` | recall@5 ≥ 0.85 |
| **Answer quality** | Câu trả lời SINH RA có đúng/đủ/trích dẫn đúng/không bịa? | `answer_eval.py` + `answer_set.jsonl` | `make answer-eval` | xem dưới |

> Trước đây chỉ có tầng retrieval → báo recall@5 = 0.909 ✅ trong khi câu trả lời thực tế
> vẫn kém. Tầng answer quality lấp đúng điểm mù đó.

## Tầng answer quality (chấm TẤT ĐỊNH, không LLM-judge)

`answer_eval.py` chạy **đúng đường production** cho từng câu
(`production_retrieve` → `generation.build_context_and_citations` →
`build_messages` → `stream_ollama`), rồi `scoring.py` chấm:

- **coverage** — tỉ lệ `required_facts` (số/đơn vị/mã/công thức/thuật ngữ) xuất hiện trong
  câu trả lời, sau chuẩn hoá khoan dung tiếng Việt/đo lường (vd `± 3 %` = `3%`,
  `\Delta P_{cd}` = `\DeltaP_{cd}`).
- **citation** — fact có nằm trong passage ĐÃ retrieve không (lenient) và `[n]` có được
  dẫn không (strict).
- **refusal** — câu `out_of_scope` phải trả đúng câu "Không tìm thấy thông tin…".
- **hallucination** — số-kèm-đơn-vị nêu trong câu trả lời nhưng KHÔNG có trong ngữ cảnh.

So **1.5b vs 7b** trên cùng câu hỏi để tách lỗi-do-model khỏi lỗi-do-pipeline:
7b≫1.5b ở coverage nhưng cả hai thấp ở citation/refusal ⇒ pipeline/prompt; cả hai thấp ở
`multi_section`/`cross_file` ⇒ ngân sách ngữ cảnh/router.

```bash
make answer-eval                                   # 1.5b + 7b, tất cả category
make answer-eval-dev                               # chỉ 1.5b (nhanh)
python -m eval.answer_eval --category out_of_scope -v
python -m eval.answer_eval --model qwen2.5:1.5b --limit 10 -v
```

> ⚠ 7b trên máy CPU (~80s+/câu) rất chậm cho cả bộ; chạy đủ trên máy GPU prod
> (RTX 5060). Trên CPU dùng `--limit` hoặc `--category` để lấy tín hiệu.

## Mở rộng `answer_set.jsonl`

Mỗi dòng JSON: `question`, `expected` (list section nguồn; `[]` cho out_of_scope),
`gold_answer` (nháp, người duyệt), `required_facts` (`type` ∈ number/unit/code/formula/term,
kèm `aliases` + `source` {file_stem, section_path}), `category`, `difficulty`, `must_refuse`.

Quy tắc soạn fact: **copy NGUYÊN VĂN** số/đơn vị/công thức từ `build/spike_a/<file>.md` và
gắn đúng `source.section_path` (xem `_section_retrieved` trong `scoring.py`). Hiện tập trung
ở 1.061 + 1.159 (đã đọc kỹ); cần chuyên gia kiểm lại + mở rộng sang 5 file còn lại.

Mọi `required_fact` phải tự-nhất-quán với `gold_answer` (guard nhanh):

```bash
python -c "import json; from eval import scoring; \
items=[json.loads(l) for l in open('eval/answer_set.jsonl',encoding='utf-8') if l.strip()]; \
print('fail:', sum(not scoring.fact_present(f,it['gold_answer']) for it in items for f in it.get('required_facts',[])))"
```

`scoring.py` được unit-test ở `tests/unit/qa/test_answer_scoring.py` (chạy trong `make check`,
không cần service).
