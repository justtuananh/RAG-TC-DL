# Ví dụ: xác định đoạn neo cho một câu hỏi, từng bước

Tài liệu này đi qua đường đi của MỘT câu hỏi trong pipeline truy hồi để thấy đoạn neo được chọn ở đâu và được dùng thế nào.
Mọi con số đo thật ngày 2026-10-07 trên dịch vụ đang chạy (Qdrant `qtkd_rag`, bge-m3, bge-reranker-v2-m3) với `config/settings.yaml` hiện tại, sau commit `a744aed` (cửa sổ dựng từ mọi đoạn khớp, ngân sách theo thứ hạng).
Phần "So với cách làm trước `a744aed`" cuối tài liệu ghi lại cách cũ và lý do đổi.
Kết quả trung gian được dựng lại bằng chính các hàm của `retrieval/` và `reranking/`; danh sách nguồn cuối cùng trùng khớp với `retrieval.retriever.retrieve()`.

**Câu hỏi:**

> Theo QTKĐ 1.159, diện tích hiệu dụng của píttông cần kiểm định được tính theo công thức nào?

## Định nghĩa ngắn

**Đoạn neo** là các đoạn con (child chunk) của một mục được truy hồi chấm là khớp nhất với câu hỏi.
Mỗi mục đi vào ngữ cảnh mang theo danh sách đoạn neo `anchor_texts`: MỌI đoạn con của mục có trong pool rerank, xếp theo thứ hạng RRF.
Đoạn neo thứ nhất cũng là **đoạn đại diện** của mục khi rerank.
Khi mục dài hơn ngân sách ký tự, `window()` dựng phần giữ lại từ các khối quanh đoạn neo, lần lượt theo thứ hạng.
Panel nguồn trên giao diện chỉ trích `llm.context.quote_anchors` = 2 đoạn neo đầu để đoạn trích gọn.

## Bước 1: Mở rộng truy vấn và định tuyến file

`retrieval/query_expansion.expand_query` thêm từ khóa miền vào cuối câu hỏi:

```
Theo QTKĐ 1.159, diện tích hiệu dụng của píttông cần kiểm định được tính theo công thức nào? diện tích hiệu dụng píttông xác định đo lường
```

`retrieval/router.route_files` thấy số "1.159" trong câu hỏi nên ghim tìm kiếm vào đúng một file: `QTKD_1.159_2021_ND_FINAL`.
Vì chỉ có một file, truy hồi đi nhánh thường (không chạy phễu riêng từng file).

## Bước 2: Tìm song song dense và BM25 trên đoạn con

Hai nhánh, mỗi nhánh lấy `retrieval.top_k` = 50 đoạn con của file 1.159.
Chỉ đoạn con được tìm; mục cha không được nhúng.

| Hạng | Dense (bge-m3) | BM25 |
|---|---|---|
| 0 | (Quy định): "Tính diện tích hiệu dụng của áp kế píttông cần kiểm định At(p)" | 6.3.2: "$A_{0t,i}$ là diện tích hiệu dụng của píttông của AKKĐ… được tính từ công thức sau:" |
| 1 | 6.3.2: "$A_{0t,i}$ là diện tích hiệu dụng của píttông của AKKĐ…" | 6.3.2: "Khối lượng riêng không khí được tính theo công thức sau:" |
| 2 | (Quy định): "\| Diện tích hiệu dụng của píttông: \| Ao = \| (8,051516×10-5 ± 2,91×10-9) m2 \|" | 6.3.2: "$A_{0s}$ là diện tích hiệu dụng của píttông của áp kế píttông chuẩn, m2;" |
| 3 | Mẫu biên bản kiểm định: "A.3.2 Xác định diện tích hiệu dụng" | 6.3.2: "$\rho_{a}$ là khối lượng riêng của không khí, được tính theo công thức (4), kg/m3;" |

Ba trong bốn hạng đầu của nhánh dense là mục mẫu biểu; bước 4 sẽ loại chúng.

## Bước 3: Gộp hai danh sách bằng RRF

`retrieval/hybrid_retriever.rrf_fuse` cộng điểm của mỗi đoạn con theo thứ hạng ở từng nhánh:

```
rrf = w_dense / (k + hạng_dense + 1) + w_bm25 / (k + hạng_bm25 + 1),   k = 60, w = 1 : 1
```

Ví dụ đoạn "$A_{0t,i}$ là…": hạng dense 1, hạng BM25 0, nên rrf = 1/62 + 1/61 = 0,03252.

| Hạng RRF | Điểm | Hạng dense | Hạng BM25 | Mục | Đoạn con |
|---|---|---|---|---|---|
| 0 | 0,03252 | 1 | 0 | 6.3.2 | "$A_{0t,i}$ là diện tích hiệu dụng của píttông của AKKĐ… được tính từ công thức sau:" |
| 1 | 0,03037 | 8 | 2 | 6.3.2 | "$A_{0s}$ là diện tích hiệu dụng của píttông của áp kế píttông chuẩn, m2;" |
| 2 | 0,02944 | 9 | 5 | 6.3.2 | "Diện tích hiệu dụng píttông của AKKĐ và hệ số giãn nở áp suất λ xác định như sau:" |
| 3 | 0,02821 | 4 | 17 | 6.3.1 | "A0 là diện tích hiệu dụng của pittông được xác định tại 6.3.2, Pa;" |
| 4 | 0,02615 | 17 | 14 | 6.3.2 | "- Kiểm tra chênh lệch chiều cao giữa đáy của píttông chuẩn và AKKĐ" |
| 6 | 0,02399 | 40 | 10 | 6.3.3 | "ĐKĐBĐ kiểu A của diện tích hiệu dụng được tính bằng:" |
| 7 | 0,02393 | 35 | 13 | 6.3.3 | "Độ không đảm bảo kiểu A của diện tích hiệu dụng được tính bằng:" |

Bảng này là thứ hạng SAU khi lọc mẫu biểu ở bước 4.
Đoạn chỉ một nhánh tìm thấy thì chỉ có một số hạng, nên thường đứng thấp hơn đoạn cả hai nhánh cùng thấy.

## Bước 4: Lọc mục mẫu biểu, cắt còn `rerank_pool`

`filter_noise` bỏ 14 đoạn con thuộc mục mẫu biểu, ví dụ:

- "(Quy định)": "Tính diện tích hiệu dụng của áp kế píttông cần kiểm định At(p)"
- "Mẫu biên bản kiểm định": "Diện tích hiệu dụng của píttông: Ao ="
- "Mẫu biên bản kiểm định (không đạt)": "B.3.2 Xác định diện tích hiệu dụng"

Các đoạn này chứa đúng cụm "diện tích hiệu dụng" nên điểm cao, nhưng không có công thức.
Danh sách còn lại được cắt còn `retrieval.rerank_pool` = 60 đoạn con.

## Bước 5: Gom theo mục cha, chọn đoạn đại diện và đoạn neo

Đây là bước sinh ra đoạn neo (`reranking/reranker.py`, `rerank_hits`).
Hàm duyệt 60 đoạn con theo thứ tự RRF và gom theo `parent_id`:

- Đoạn con đầu tiên gặp của một mục trở thành **đoạn đại diện** và **đoạn neo 1**.
- Mọi đoạn con sau của cùng mục được nối vào danh sách neo theo thứ tự gặp, tức theo thứ hạng RRF.

| Mục | Số đoạn neo | Hạng RRF của 3 đoạn neo đầu |
|---|---|---|
| 6.3.2 Xác định diện tích hiệu dụng | 36 | 0 "$A_{0t,i}$ là…"; 1 "$A_{0s}$ là…"; 2 "Diện tích hiệu dụng píttông của AKKĐ… xác định như sau:" |
| 6.3.1 Xác định sai số khối lượng… | 3 | 3 "A0 là…"; 18 "- Khối lượng thực tế Mi…"; 42 "Khối lượng danh nghĩa…" |
| 6.3.3 Xác định độ chính xác | 8 | 6 "ĐKĐBĐ kiểu A…"; 7 "Độ không đảm bảo kiểu A…"; 8 "- ĐKĐBĐ diện tích hiệu dụng $u_{15}(p)$…" |
| 3 Các phép kiểm định | 1 | 21 (bảng các phép kiểm định) |
| 5.2 Chuẩn bị kiểm định | 5 | 34; 44; 54 |
| … (các mục khác) | | |

## Bước 6: Rerank bằng cross-encoder

Mỗi mục được cross-encoder chấm một lần trên văn bản mục cha (`build_rerank_doc`).
Mục dài hơn 1 400 ký tự chỉ đưa vào cửa sổ 1 400 ký tự bắt đầu 200 ký tự trước **đoạn đại diện**; các đoạn neo khác không dùng ở bước này.
Văn bản đưa vào cross-encoder cho mục 6.3.2 bắt đầu như sau:

```
QTKD_1.159_2021_ND_FINAL — 6 Tiến hành kiểm định > 6.3 Kiểm tra đo lường > 6.3.2 Xác định diện tích hiệu dụng
### 6.3.2 Xác định diện tích hiệu dụng
…ơ sở áp suất của áp kế cần kiểm định nằm cao hơn vị trí làm việc của áp kế chuẩn …

$A_{0t,i}$ là diện tích hiệu dụng của píttông của …
```

Giữ `top_n` = 5 mục điểm cao nhất; thứ tự đoạn neo trong mỗi mục không đổi.

| [n] | Mục | Điểm rerank | Độ dài mục | Số đoạn neo | Đoạn neo 1 (vị trí ký tự trong mục) |
|---|---|---|---|---|---|
| 1 | 6.3.2 Xác định diện tích hiệu dụng | 0,9988 | 5 623 | 36 | 3 855 "$A_{0t,i}$ là… sau:" |
| 2 | 6.3.1 Xác định sai số khối lượng… | 0,9749 | 1 452 | 3 | 488 "A0 là…" |
| 3 | 6.3.3 Xác định độ chính xác | 0,9444 | 8 074 | 8 | 95 "ĐKĐBĐ kiểu A…" |
| 4 | 3 Các phép kiểm định | 0,6974 | 1 008 | 1 | 112 (bảng) |
| 5 | 5.2 Chuẩn bị kiểm định | 0,6804 | 3 692 | 5 | 3 058 "Kiểm tra hoạt động…" |

## Bước 7: Lọc nguồn theo độ tin cậy

`filter_by_confidence` giữ nguồn có điểm ≥ max(`source_abs_floor`, `source_rel_floor` × điểm top) = max(0,08; 0,20 × 0,9988) = 0,1998.
Cả 5 nguồn đều vượt ngưỡng nên được giữ.

## Bước 8: Chia ngân sách ký tự theo thứ hạng

Trần tổng: (`num_ctx` 8 192 − `prompt_reserve_tokens` 1 200 − `max_new_tokens` 1 024) × 2,5 = 14 920 ký tự.
Đầu mục "[n] Nguồn: …" của 5 nguồn và 4 dấu ngăn cách chiếm 602 ký tự, nên phần nội dung còn 14 318 ký tự.

`_block_budgets` chia 14 318 ký tự cho từng nguồn, lần lượt từ nguồn [1] xuống nguồn [5].
Mỗi nguồn được xét theo ba bước:

1. **Giữ chỗ cho các nguồn phía sau:** mỗi nguồn chưa được xét cần ít nhất `min_block_chars` = 600 ký tự, nên phải chừa lại 600 × (số nguồn phía sau).
2. **Tối đa được lấy** = phần còn lại − phần giữ chỗ.
3. **Ngân sách** = số nhỏ nhất trong ba số: độ dài của nguồn (không cần hơn), trần `max_block_chars` = 4 000 (riêng nguồn [1] không có trần), và tối đa được lấy.

Phần còn lại sau mỗi nguồn = phần còn lại trước nó − ngân sách nó vừa nhận, và là phần còn lại trước nguồn kế tiếp.

| Nguồn | Còn lại trước khi xét | Giữ chỗ cho nguồn phía sau | Tối đa được lấy | Độ dài | Trần | Ngân sách = min(độ dài, trần, tối đa) | Còn lại sau khi xét |
|---|---|---|---|---|---|---|---|
| [1] 6.3.2 | 14 318 | 4 × 600 = 2 400 | 11 918 | 5 623 | không | **5 623** (vào trọn) | 8 695 |
| [2] 6.3.1 | 8 695 | 3 × 600 = 1 800 | 6 895 | 1 452 | 4 000 | **1 452** (vào trọn) | 7 243 |
| [3] 6.3.3 | 7 243 | 2 × 600 = 1 200 | 6 043 | 8 074 | 4 000 | **4 000** (bị trần, phải cắt) | 3 243 |
| [4] 3 Các phép kiểm định | 3 243 | 1 × 600 = 600 | 2 643 | 1 008 | 4 000 | **1 008** (vào trọn) | 2 235 |
| [5] 5.2 | 2 235 | 0 | 2 235 | 3 692 | 4 000 | **2 235** (hết chỗ, phải cắt) | 0 |

Tổng ngân sách 5 623 + 1 452 + 4 000 + 1 008 + 2 235 = 14 318, dùng hết phần nội dung.

Mục 6.3.2 chứa câu trả lời nên giờ vào trọn, kể cả công thức kết luận $A_{0t}$ ở cuối mục.
Chỉ [3] và [5] dài hơn ngân sách nên phải cắt bằng `window()`.

## Bước 9: Cắt mục 6.3.3 quanh các đoạn neo

Đầu vào: mục 8 074 ký tự gồm 97 khối Markdown, ngân sách 4 000, 8 đoạn neo.
Khối là các dòng liền nhau giữa hai dòng trống (`retrieval.quote.section_blocks`).

**Giai đoạn 1: thêm từng đoạn neo theo thứ hạng.**
Với mỗi đoạn neo, `window()` thử ba phương án, từ đầy đủ tới tối thiểu, và lấy phương án đầu tiên còn vừa ngân sách:

1. Đầy đủ: khối của đoạn neo, công thức nó nói tới, và danh sách "trong đó" của công thức.
   Câu dẫn kết thúc bằng ":" kéo công thức ngay sau nó; dòng định nghĩa trong danh sách "trong đó" kéo công thức ngay trên danh sách; khối công thức kéo câu dẫn trước nó.
2. Chỉ kèm công thức, không kèm danh sách "trong đó".
3. Chỉ khối của đoạn neo.

Nếu cả ba không vừa thì bỏ qua đoạn neo đó; nếu khối của nó đã được chọn từ trước thì không làm gì.

| Hạng | Vị trí | Đoạn neo | Kết quả | Ngân sách còn |
|---|---|---|---|---|
| 0 | 95 | "ĐKĐBĐ kiểu A của diện tích hiệu dụng được tính bằng:" | thêm đầy đủ [95, 235) | 3 856 |
| 1 | 934 | "Độ không đảm bảo kiểu A của diện tích hiệu dụng được tính bằng:" | thêm đầy đủ [934, 1 095) | 3 692 |
| 2 | 5 115 | "- ĐKĐBĐ diện tích hiệu dụng $u_{15}(p)$ được lấy từ kết quả hiệu chuẩn…" | thêm đầy đủ [5 115, 5 272) | 3 532 |
| 3 | 1 632 | "ĐKĐBĐ diện tích hiệu dụng $u_{2}(p)$ lấy từ giấy chứng nhận…" | thêm đầy đủ [1 632, 1 788) | 3 373 |
| 4 | 7 581 | "6.3.3.4 Độ chính xác (sai số tương đối) của áp kế píttông…" | thêm đầy đủ [7 581, 7 758) | 3 193 |
| 5 | 5 435 | "- ĐKĐBĐ khối lượng quả cân và píttông $u_{17}(p)$…" | thêm đầy đủ [5 435, 5 603) | 3 022 |
| 6 | 7 761 | "Nếu áp suất danh nghĩa trên quả cân được ghi khắc theo gia tốc…" | thêm đầy đủ [7 761, 7 958) | 2 822 |
| 7 | 1 945 | "ĐKĐBĐ khối lượng quả cân, píttông $u_{4}(p)$…" | thêm đầy đủ [1 945, 2 105) | 2 659 |

**Giai đoạn 2: phần dư mở rộng quanh các đoạn neo.**
Còn 2 659 ký tự.
`window()` lần lượt theo thứ hạng đoạn neo, mỗi lượt thêm một khối trọn kề ngay sau rồi ngay trước mỗi khúc đã chọn, tới khi không còn khối nào vừa.

**Kết quả: 4 000 ký tự, đúng bằng ngân sách, gồm 5 khúc:**

| Khúc | Bắt đầu bằng |
|---|---|
| [0, 387) | "### 6.3.3 Xác định độ chính xác", "6.3.3.1 Ước lượng ĐKĐBĐ kiểu A của AKKĐ", công thức $u_A$ |
| [724, 1 255) | công thức $S_b$, câu dẫn ĐKĐBĐ kiểu A thứ hai và công thức của nó |
| [1 445, 2 518) | công thức $u_1(p)$, các mục $u_2(p)$ … $u_4(p)$ |
| [4 918, 6 020) | ĐKĐBĐ tổng hợp $u_s(p)$, các mục $u_{15}(p)$ … $u_{17}(p)$ |
| [7 179, 8 074) | 6.3.3.2.4 ĐKĐBĐ mở rộng $U$, 6.3.3.4 độ chính xác |

Các khúc nối với nhau bằng "\n…\n" ở chỗ thật sự bỏ qua nội dung.
Khúc nào không bắt đầu từ đầu mục thì có "…" ở trước, khúc cuối chưa tới cuối mục thì có "…" ở sau.
Chỉ lấy khối trọn nên không dòng công thức nào bị cắt dở.

## So với cách làm trước `a744aed`

Cùng câu hỏi, cùng kết quả truy hồi, cách cũ cho kết quả khác ở ba chỗ:

| | Cách cũ | Cách mới |
|---|---|---|
| Đoạn neo | 2 đoạn đầu của mục (`window_anchors` = 2) | mọi đoạn con của mục trong pool |
| Ngân sách | chia đều theo độ dài (water-filling), trần 4 000 cho mọi nguồn | theo thứ hạng rerank, nguồn top không trần |
| Ngân sách cho [1] 6.3.2 | 4 000 (phải cắt) | 5 623 (vào trọn) |
| Ngân sách cho [5] 5.2 (điểm 0,68) | 3 692 (vào trọn) | 2 235 |
| Đầu mục "[n] Nguồn: …" | không trừ vào trần tổng | trừ vào trần tổng |
| Cắt mục dài | chia đều cho đầu mục + một cửa sổ ký tự quanh mỗi đoạn neo | khối trọn quanh đoạn neo theo thứ hạng, không dành chỗ cố định cho đầu mục |

Với cách cũ, mục 6.3.2 bị cắt còn đầu mục (bảng điểm áp suất, không liên quan) cùng hai cửa sổ quanh $A_{0s}$ và $A_{0t,i}$.
Câu dẫn "Diện tích hiệu dụng píttông của AKKĐ… xác định như sau:" (hạng RRF 2) không thành đoạn neo, nên công thức kết luận $A_{0t} = \overline{A}$ (ký tự 5 370) bị cắt.
Ngoài ra, hai khúc liền nhau [0, 1 521) và [1 522, 2 723) vẫn bị chèn "…" như thể có nội dung bị lược.

Đo trên 33 câu của `answer_set` + `answer_set_ext` (cùng kết quả truy hồi, qwen2.5:7b):

| | Cách cũ | Cách mới |
|---|---|---|
| Độ phủ fact trong câu trả lời | 0,957 | 0,969 |
| Ngữ cảnh dài nhất (trần 14 920) | 15 780 | 14 892 |
| Đoạn con hạng RRF 0-9 của mục được chọn bị cắt (92 câu) | 7/685, ở 6 câu | 0/685 |

Chênh lệch độ phủ chỉ đến từ câu 133 (cách tính diện tích hiệu dụng, QTKĐ 1.159), và đó là dao động của model, không phải nhờ thay đổi.
Hỏi lại câu này 3 lần qua `/api/chat/stream` trên mỗi bản (2026-10-08), cả 6 câu trả lời đều có công thức $A_{0t,i}$ khớp nguyên văn nguồn, có "23 oC" và "xylanh".
Lợi ích đo được chắc chắn của cách mới là ngữ cảnh không còn vượt trần và không còn đoạn con hạng cao nào bị cắt.

## Nhận xét rút ra từ ví dụ

1. **Đoạn neo hạng thấp có thể giành ngân sách của phần quanh đoạn neo hạng cao.**
   Nếu mục 6.3.2 chỉ có ngân sách 4 000 (như cách cũ), giai đoạn 1 thêm lần lượt 36 đoạn neo, kể cả các đoạn hạng thấp như "6.3.2.1 Xác định điểm áp suất kiểm định" (hạng 22).
   Tới đoạn neo "Trường hợp R ≥ 0,8:" (hạng 31) thì chỉ còn đủ chỗ cho chính câu dẫn, không kèm được công thức $A_{0t} = a$ ngay sau nó.
   Câu hỏi ví dụ không bị ảnh hưởng vì 6.3.2 giờ vào trọn, nhưng đây là chỗ nên xem lại, ví dụ dừng thêm đoạn neo khi điểm RRF tụt xa so với đoạn neo đầu.
2. **Định tuyến nhầm khi câu hỏi có chữ "AKKĐ".**
   Cùng câu hỏi nhưng viết "píttông AKKĐ" thay cho "píttông cần kiểm định" thì `route_files` trả HAI file 1.159 và 1.160, vì "akkđ" là bí danh của QTKĐ 1.160.
   "AKKĐ" (áp kế cần kiểm định) là từ chung của mọi quy trình áp kế, nên câu hỏi chỉ về 1.159 bị chạy phễu so sánh hai file.
   Ví dụ trong tài liệu này dùng cách viết không có "AKKĐ" để đi đúng nhánh một file.
