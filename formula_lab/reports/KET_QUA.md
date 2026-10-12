# Kết quả thử nghiệm tính công thức từ DOCX

**Chọn hướng 3 — kho công thức đã đối chiếu nguồn (registry).** Nguyên mẫu đã được hợp nhất vào nhánh `dev`; ba worktree được giữ nguyên để tái lập.

## Kết quả đo

120 UC gồm 60 ca phát triển và 60 ca đánh giá cuối. Mỗi hướng chạy 60 ca cuối ba lần, tương ứng 180 lượt. Không coi 180 lượt lặp là 180 tình huống độc lập.

| Hướng | Lượt đạt | Tỷ lệ | Lượt tính sai/không được phép tính | Ca đạt cả 3 lần / 60 |
|---|---:|---:|---:|---:|
| LLM tạo định nghĩa form và biểu thức | 118/180 | 65.6% | 20 | 38 |
| Parser LaTeX + quy tắc đọc ngữ cảnh | 174/180 | 96.7% | 6 | 58 |
| Kho công thức đã đối chiếu nguồn | 180/180 | 100.0% | 0 | 60 |

Không có lượt lỗi hạ tầng trong bộ cuối. Điểm số trên là của nguyên mẫu với bộ định tuyến/công thức đã giới hạn; không phải tỷ lệ chính xác của chatbot trên mọi câu hỏi.

## Vì sao chọn registry

- Cả ba hướng dùng cùng engine Decimal, bộ đơn vị và dữ liệu truy hồi. Khác biệt nằm ở bước diễn giải, kiểm tra và chấp nhận công thức.
- Parser đạt tỷ lệ cao nhưng vẫn thực hiện biểu thức bị đổi dấu vì biểu thức vẫn hợp lệ về cú pháp. Có 2 UC dạng này, lặp 3 lần thành 6 lượt không an toàn.
- LLM có thể bỏ điều kiện áp dụng, thêm điều kiện không liên quan, hoặc nhầm giới hạn đánh giá thiết bị với giới hạn đầu vào. Nó cũng có thể tính từ công thức nguồn đã bị sửa.
- Registry gắn biểu thức/định nghĩa biến với fingerprint nguồn được đối chiếu. Nguồn hoặc công thức thay đổi thì chặn, không tự suy diễn để tiếp tục.
- Parser không đủ điều kiện lựa chọn vì có lỗi không an toàn; do đó không áp dụng quy tắc thử thêm 30 UC cho trường hợp hai phương án đủ điều kiện có điểm sát nhau.

## Dữ liệu và bằng chứng

- Toàn bộ 7 DOCX hiện có được index thành 141 cửa sổ văn bản. Sáu bộ tính được chọn từ QTKĐ 1.061, 1.063 và 1.071; bốn DOCX còn lại là tài liệu nền trong truy hồi.
- Sáu bộ tính: sai số áp suất chỉnh đặt; dung tích bình phân ly; hiệu chỉnh thời gian quay; hiệu chỉnh tốc độ hạ; hiệu chỉnh áp suất theo trọng trường; chuỗi sai số hai lần đo → sai số tương đối H3000.
- Model chat: `qwen/qwen3-30b-a3b-instruct-2507`; embedding: `openai/text-embedding-3-small`, 1536 chiều. Kết nối thật qua LiteLLM/OpenRouter. Tắt reranker đồng nhất.
- Giao diện dùng Chromium thật; các UC thao tác gọi API tính qua ASGI và phát lại form do phương án tạo trong chính lượt đó. Truy hồi và tạo form thật được đo riêng.
- Đã kiểm tra thêm một luồng không có intercept: trình duyệt → HTTP thật → embedding OpenRouter → form registry → nhập 103000 Pa và 100000 Pa → nhận 3000 Pa. Xem `live-http-smoke.json` và ảnh chụp.

## Lỗi phát hiện trực tiếp trong tài liệu

- H3000 có ký hiệu OMML và MathType đồng thời, khiến một số dòng mô tả biến bị lặp/lẫn ký hiệu khi trích xuất.
- LibreOffice render thiếu công thức OMML bình phân ly; công thức được xác minh từ XML gốc là V_pl = 500 - V_đ, với đơn vị mL.
- Các dòng MERGEFORMAT trong bản nguồn H3000 là lỗi trường hiển thị, không được đưa vào biểu thức tính.

## Sử dụng và tái lập

Demo registry đang cấu hình cổng **8093** trên máy workspace. Chạy lại:

```bash
cd /root/RAG-TC-DL
./formula_lab/run.sh serve
```

Ba worktree:

| Nhánh | Thư mục | Cổng khi khởi chạy |
|---|---|---:|
| `exp/formula-llm` | `/root/RAG-TC-DL-worktrees/llm` | 8091 |
| `exp/formula-parser` | `/root/RAG-TC-DL-worktrees/parser` | 8092 |
| `exp/formula-registry` | `/root/RAG-TC-DL-worktrees/registry` | 8093 |

Không chạy demo dev và demo registry worktree cùng cổng; có thể đổi bằng `FORMULA_PORT`. Không chạy UI và benchmark cùng lúc trên một worktree vì Qdrant local khóa thư mục.

Trong từng worktree:

```bash
./formula_lab/run.sh benchmark --split holdout --rounds 3
```

Key ở cấu hình backend ngoài Git, quyền đọc/ghi 600. Không có key trong frontend hoặc báo cáo.

## Giới hạn cần giữ khi diễn giải kết quả

**100% ở đây chỉ là 60 UC cuối trên sáu bộ tính đã chuẩn bị, chạy ba lần.** Chưa chứng minh đúng trên công thức/tài liệu mới. Chưa có chuyên gia đo lường phê duyệt. Người dùng vẫn có thể nhập sai một giá trị nhưng giá trị đó còn hợp lệ; kiểm tra phần mềm không thể luôn phát hiện.

Đây là lab nghiên cứu độc lập, chưa gắn vào giao diện React và luồng chat sản phẩm cũ. Nguyên mẫu được chọn đã nằm trên dev để phát triển tiếp.

Sau benchmark, thêm guard cho công cụ tạo dữ liệu: thay đổi nguồn/công thức không thể tự động được duyệt lại; fingerprint phải có trong hồ sơ đối chiếu. Thay đổi này chỉ bảo vệ bước chuẩn bị dữ liệu, không thay runtime đã đo hoặc sửa đáp án UC.

Xem [bộ UC](UC.md), [số liệu chi tiết](COMPARISON.md), [giới hạn phương pháp](KNOWN_LIMITS.md), [đối chiếu nguồn](source-review/REVIEW.md).
