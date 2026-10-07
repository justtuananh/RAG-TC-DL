# Ví dụ: xác định đoạn neo cho một câu hỏi, từng bước

Tài liệu này đi qua đường đi của MỘT câu hỏi trong pipeline truy hồi để thấy đoạn neo được chọn ở đâu và được dùng thế nào.
Mọi con số đo thật ngày 2026-10-07 trên dịch vụ đang chạy (Qdrant `qtkd_rag`, bge-m3, bge-reranker-v2-m3) với `config/settings.yaml` hiện tại.
Kết quả trung gian được dựng lại bằng chính các hàm của `retrieval/` và `reranking/`; danh sách nguồn cuối cùng trùng khớp với `retrieval.retriever.retrieve()`.

**Câu hỏi:**

> Theo QTKĐ 1.159, diện tích hiệu dụng của píttông cần kiểm định được tính theo công thức nào?

## Định nghĩa ngắn

**Đoạn neo** là các đoạn con (child chunk) của một mục được truy hồi chấm là khớp nhất với câu hỏi.
Mỗi mục đi vào ngữ cảnh mang theo danh sách đoạn neo `anchor_texts`, tối đa `llm.context.window_anchors` = 2 đoạn, xếp theo thứ hạng RRF.
Đoạn neo thứ nhất cũng là **đoạn đại diện** của mục khi rerank.
Khi mục dài hơn ngân sách ký tự, `window()` cắt mục quanh các đoạn neo để phần giữ lại chứa đúng chỗ trả lời câu hỏi.

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

Đây là bước sinh ra đoạn neo (`reranking/reranker.py:83-96`).
Hàm duyệt 60 đoạn con theo thứ tự RRF và gom theo `parent_id`:

- Đoạn con đầu tiên gặp của một mục trở thành **đoạn đại diện** và **đoạn neo 1**.
- Các đoạn con sau của cùng mục được thêm vào danh sách neo cho tới khi đủ 2 đoạn; phần còn lại bị bỏ qua.

| Mục | Số đoạn con trong pool | Hạng RRF của các đoạn con đầu | Đoạn neo |
|---|---|---|---|
| 6.3.2 Xác định diện tích hiệu dụng | 36 | 0, 1, 2, … | hạng 0 "$A_{0t,i}$ là…"; hạng 1 "$A_{0s}$ là…" |
| 6.3.1 Xác định sai số khối lượng… | 3 | 3, 18, 42 | hạng 3 "A0 là…"; hạng 18 "- Khối lượng thực tế Mi…" |
| 6.3.3 Xác định độ chính xác | 8 | 6, 7, 8 | hạng 6 "ĐKĐBĐ kiểu A…"; hạng 7 "Độ không đảm bảo kiểu A…" |
| 3 Các phép kiểm định | 1 | 21 | hạng 21 (bảng các phép kiểm định) |
| 5.2 Chuẩn bị kiểm định | 5 | 34, 44, 54 | hạng 34; hạng 44 |
| … (các mục khác) | | | |

Lưu ý ở mục 6.3.2: đoạn hạng 2 "Diện tích hiệu dụng píttông của AKKĐ và hệ số giãn nở áp suất λ xác định như sau:" KHÔNG thành đoạn neo vì đã đủ 2 đoạn.

## Bước 6: Rerank bằng cross-encoder

Mỗi mục được cross-encoder chấm một lần trên văn bản mục cha (`build_rerank_doc`).
Mục dài hơn 1 400 ký tự chỉ đưa vào cửa sổ 1 400 ký tự bắt đầu 200 ký tự trước **đoạn đại diện**; đoạn neo thứ hai không dùng ở bước này.
Văn bản đưa vào cross-encoder cho mục 6.3.2 bắt đầu như sau:

```
QTKD_1.159_2021_ND_FINAL — 6 Tiến hành kiểm định > 6.3 Kiểm tra đo lường > 6.3.2 Xác định diện tích hiệu dụng
### 6.3.2 Xác định diện tích hiệu dụng
…ơ sở áp suất của áp kế cần kiểm định nằm cao hơn vị trí làm việc của áp kế chuẩn …

$A_{0t,i}$ là diện tích hiệu dụng của píttông của …
```

Giữ `top_n` = 5 mục điểm cao nhất; thứ tự đoạn neo trong mỗi mục không đổi.

| [n] | Mục | Điểm rerank | Độ dài mục | Đoạn neo (vị trí ký tự trong mục) |
|---|---|---|---|---|
| 1 | 6.3.2 Xác định diện tích hiệu dụng | 0,9988 | 5 623 | 3 855 "$A_{0t,i}$ là… sau:"; 1 997 "$A_{0s}$ là…" |
| 2 | 6.3.1 Xác định sai số khối lượng… | 0,9749 | 1 452 | 488 "A0 là…"; 82 "- Khối lượng thực tế Mi…" |
| 3 | 6.3.3 Xác định độ chính xác | 0,9444 | 8 074 | 95 "ĐKĐBĐ kiểu A…"; 934 "Độ không đảm bảo kiểu A…" |
| 4 | 3 Các phép kiểm định | 0,6974 | 1 008 | 112 (bảng) |
| 5 | 5.2 Chuẩn bị kiểm định | 0,6804 | 3 692 | 3 058; 2 272 |

## Bước 7: Lọc nguồn theo độ tin cậy

`filter_by_confidence` giữ nguồn có điểm ≥ max(`source_abs_floor`, `source_rel_floor` × điểm top) = max(0,08; 0,20 × 0,9988) = 0,1998.
Cả 5 nguồn đều vượt ngưỡng nên được giữ.

## Bước 8: Chia ngân sách ký tự (water-filling)

Trần tổng: (`num_ctx` 8 192 − `prompt_reserve_tokens` 1 200 − `max_new_tokens` 1 024) × 2,5 = 14 920 ký tự.
`_block_budgets` xét nguồn từ ngắn đến dài; mỗi nguồn nhận min(độ dài, 4 000, max(600, phần chia đều của phần còn lại)):

| Thứ tự xét | Nguồn | Độ dài | Phần chia đều | Ngân sách |
|---|---|---|---|---|
| 1 | [4] 3 Các phép kiểm định | 1 008 | 14 920 / 5 = 2 984 | 1 008 (lấy trọn) |
| 2 | [2] 6.3.1 | 1 452 | 13 912 / 4 = 3 478 | 1 452 (lấy trọn) |
| 3 | [5] 5.2 | 3 692 | 12 460 / 3 = 4 153 | 3 692 (lấy trọn) |
| 4 | [1] 6.3.2 | 5 623 | 8 768 / 2 = 4 384 | 4 000 (trần) |
| 5 | [3] 6.3.3 | 8 074 | 4 768 / 1 = 4 768 | 4 000 (trần) |

Chỉ [1] và [3] dài hơn ngân sách nên phải cắt bằng `window()`.

## Bước 9: Cắt mục 6.3.2 quanh các đoạn neo

Đầu vào: mục 5 623 ký tự, ngân sách 4 000, hai đoạn neo.

1. **Định vị đoạn neo.**
   Neo 1 "$A_{0t,i}$ là… được tính từ công thức sau:" ở [3 855, 3 961), kết thúc bằng ":" nên là **câu dẫn**.
   Neo 2 "$A_{0s}$ là…" ở [1 997, 2 069), là câu thường.
2. **Phần đầu mục có chứa sẵn đoạn neo không?**
   Câu dẫn cần vị trí cuối + `lead_in_tail_chars` = 3 961 + 700 = 4 661 > 4 000, nên không.
   Câu thường được coi là đã nằm trong phần đầu khi cuối ≤ phần đầu, hoặc đầu < nửa phần đầu; với phần đầu 4 000 thì neo 2 thỏa.
   Nhưng vì neo 1 phải mở cửa sổ riêng, phần đầu co còn 4 000 / 2 = 2 000; xét lại, neo 2 (cuối 2 069 > 2 000, đầu 1 997 ≥ 1 000) cũng nằm ngoài.
   Phần chia cuối cùng: 4 000 / 3 = 1 333 ký tự cho mỗi khúc.
3. **Dựng ba khúc rồi đưa về ranh giới dòng (`_snap`):**

| Khúc | Trước khi snap | Sau khi snap | Giải thích |
|---|---|---|---|
| Đầu mục | [0, 1 333) | [0, 1 521) | Chỗ cắt 1 333 rơi giữa dòng công thức $P_{s,i}$ (1 327-1 521); dòng có `$` và chỉ thiếu 188 ≤ 400 ký tự nên được kéo trọn |
| Quanh neo 2 | [1 367, 2 700) | [1 522, 2 723) | Lùi (1 333 − 72) / 2 = 630 ký tự trước neo; đầu khúc nhảy tới đầu dòng kế tiếp; cuối khúc kéo hết dòng có `$` ("$t$ là nhiệt độ không khí") |
| Quanh neo 1 | [3 855, 5 188) | [3 855, 5 204) | Câu dẫn không lùi về trước, cả 1 333 ký tự dành cho phần phía sau; cuối khúc kéo hết dòng công thức $b$ |

Kết quả: 4 078 ký tự, gồm đầu mục, các dòng "trong đó" quanh $A_{0s}$, và công thức $A_{0t,i}$ cùng các công thức R, a, b.
Phần [2 723, 3 855) (công thức áp suất tuyệt đối, công thức (6), (7)) và phần [5 204, 5 623) bị bỏ.

## Nhận xét rút ra từ ví dụ

1. **Công thức kết luận nằm ngoài ngữ cảnh.**
   Câu trả lời đầy đủ cho câu hỏi là $A_{0t} = \overline{A}$ (khi R < 0,8) hoặc $A_{0t} = a$ (khi R ≥ 0,8), ở ký tự 5 370-5 553.
   Câu dẫn của phần này ("Diện tích hiệu dụng píttông của AKKĐ… xác định như sau:", hạng RRF 2) chỉ thiếu một suất để thành đoạn neo, nên khúc thứ ba dừng ở 5 204 và LLM không thấy công thức kết luận.
   Đây là trường hợp đáng cân nhắc khi chỉnh `window_anchors` hoặc cách chọn đoạn neo.
2. **Dấu "…" giữa hai khúc liền nhau.**
   Khúc 1 kết thúc ở 1 521 và khúc 2 bắt đầu ở 1 522; giữa chúng chỉ có một ký tự xuống dòng.
   `window()` chỉ gộp khúc khi đầu khúc sau ≤ cuối khúc trước, nên vẫn chèn "\n…\n" như thể có nội dung bị lược.
3. **Định tuyến nhầm khi câu hỏi có chữ "AKKĐ".**
   Cùng câu hỏi nhưng viết "píttông AKKĐ" thay cho "píttông cần kiểm định" thì `route_files` trả HAI file 1.159 và 1.160, vì "akkđ" là bí danh của QTKĐ 1.160.
   "AKKĐ" (áp kế cần kiểm định) là từ chung của mọi quy trình áp kế, nên câu hỏi chỉ về 1.159 bị chạy phễu so sánh hai file.
   Ví dụ trong tài liệu này dùng cách viết không có "AKKĐ" để đi đúng nhánh một file.
