# Tiến độ nghiên cứu tính công thức từ tài liệu DOCX

**Cập nhật:** 28/09/2026  
**Dự án:** RAG-TC-DL  
**Nhánh triển khai:** `dev`  
**Commit triển khai gần nhất:** `17ada7d` — `Expand reviewed formula registry and evaluate live DOCX calculator flow`

## 1. Mục tiêu và trạng thái hiện tại

**Đính chính đánh giá:** đã rút cách diễn giải96% như chất lượng/năng lực hoặc nghiệm thu độc lập. Audit xác nhận bias trọng số và tolerance hậu kiểm. Holdout mới khóa trước chạy có25/32 pass thô, gồm2 quan sát không đạt thực,3 ca thiết kế test sai và2 ca UI bị chặn bởi harness; không quy thành tỷ lệ chất lượng toàn hệ thống. [Báo cáo audit](../build/formula-review/BIAS_AUDIT.md).

Người dùng hỏi công thức hoặc nhận được câu trả lời có công thức, sau đó nhập số liệu ngay trên giao diện để tính. Hệ thống cần chọn đúng công thức, đúng phiên bản tài liệu, kiểm tra đơn vị/điều kiện áp dụng và từ chối khi dữ liệu hoặc nguồn chưa đủ tin cậy.

**Hiện đã chọn hướng registry và mở rộng bản thử nghiệm lên 47 bộ tính trên cả bảy DOCX gốc.** Registry là danh mục công thức đã đối chiếu, gồm biểu thức thực thi, biến, đơn vị, điều kiện và ràng buộc nguồn. Có giao diện nhập số, danh sách số đo, bộ lọc theo DOCX và luồng tra cứu–tính toán được kiểm tra qua HTTP/trình duyệt thật. Phần mở rộng v3 nằm trong working tree, chưa commit; các số liệu v2 bên dưới được giữ làm mốc lịch sử.

**Đã tích hợp đăng ký nháp, phê duyệt và form tính vào React/API chính.** Ingestion chỉ tạo nháp; người dùng duyệt trước khi tính. Đã tạo 334 ứng viên trên bảy DOCX, tất cả chờ duyệt; số này gồm ứng viên trích xuất lỗi, không phải 334 bộ tính chạy được. Chưa có duyệt chuyên gia đo lường, chưa hoàn thành toàn bộ công thức và chưa tự chọn ID đã duyệt từ hội thoại.

Chi tiết: [luồng và API](../docs/FORMULA_DRAFT_APPROVAL.md), [tiêu chí đánh giá](../docs/FORMULA_REVIEW_CRITERIA.md).

## 2. Công việc đã hoàn thành

### 2.1. Chuẩn bị và so sánh ba hướng

- Clone dự án, tạo và chuyển sang nhánh `dev`.
- Tạo ba worktree độc lập để thử LLM sinh định nghĩa, parser LaTeX và registry.
- Xây dựng bộ UC chung: 60 ca phát triển và 60 ca giữ riêng; tập giữ riêng chạy ba lần cho mỗi hướng.
- Đánh giá sáu bộ tính ban đầu, có kiểm tra nguồn, đầu vào, biên, chọn công thức và giao diện.
- Chọn registry dựa trên kết quả và số trường hợp vẫn trả kết quả khi đáng lẽ phải chặn.

| Hướng | Số ca đạt | Tỷ lệ đạt | Kết quả không an toàn quan sát được |
|---|---:|---:|---:|
| LLM | 118/180 | 65,6% | 20 |
| Parser | 174/180 | 96,7% | 6 |
| Registry | 180/180 | 100% | 0 |

Đây là kết quả **lịch sử của sáu bộ tính**, với 60 UC lặp ba lần; không phải 180 UC độc lập và không đại diện cho mọi công thức.

Ba worktree vẫn được giữ làm mốc so sánh:

| Đường dẫn | Nhánh | Commit |
|---|---|---|
| `/root/RAG-TC-DL-worktrees/llm` | `exp/formula-llm` | `096e85e` |
| `/root/RAG-TC-DL-worktrees/parser` | `exp/formula-parser` | `a9fbd8d` |
| `/root/RAG-TC-DL-worktrees/registry` | `exp/formula-registry` | `55b434f` |

Các thay đổi mở rộng mới nhất nằm ở **dự án chính trên `dev`**, không nằm trong các worktree lịch sử này.

### 2.2. Mở rộng kiểm thử lên 30 DOCX

- Kiểm kê bảy DOCX gốc; tạo thêm 23 biến thể để đủ 30 file thử nghiệm.
- Các biến thể gồm đổi bố cục, mất đối tượng công thức, chèn nội dung/công thức chưa đăng ký và đưa OMML vào đoạn văn/bảng.
- Thống kê 174 lần xuất hiện phương trình có dấu `=` trong artifact trích xuất, tương ứng 127 chuỗi LaTeX khác nhau sau chuẩn hóa khoảng trắng.
- Tách kiểm tra từ chối đúng khỏi khả năng thực sự trả lời/tính được công thức.
- Phát hiện và sửa lỗi chọn nhầm quy trình, lỗi đơn vị sai kiểu dữ liệu gây lỗi máy chủ.

**30 file chỉ có bảy nguồn độc lập.** Các bản sao không làm tăng số họ công thức. Chuỗi LaTeX khác nhau cũng chưa chắc là công thức toán học khác nhau; một số bản trích xuất còn thiếu hoặc sai.

### 2.3. Bổ sung 20 định nghĩa mới vào registry

- Nâng từ sáu lên **26 bộ tính**. Hai mươi định nghĩa mới lấy từ QTKĐ 1.190 / DPI 610.
- Đối chiếu XML Word Math gốc và ngữ cảnh; lưu bằng chứng nguồn, SHA-256 DOCX và fingerprint định nghĩa.
- Bổ sung căn bậc hai, trị tuyệt đối, giá trị lớn nhất, trung bình, căn tổng bình phương và hệ số góc hồi quy.
- Hỗ trợ danh sách số đo, kiểm tra ghép cặp và số phần tử; có đổi đơn vị chiều dài, diện tích, khối lượng và nghịch đảo áp suất.
- Tách hai nhánh độ phân giải theo phân bố tam giác/chữ nhật; yêu cầu xác nhận điều kiện áp dụng.
- Dùng bộ tính Decimal có giới hạn; không thực thi mã do LLM sinh.
- Đưa F004 về chờ kiểm tra điều kiện vì mô tả số loạt đo chưa thống nhất; thay bằng F037 để giữ 20 định nghĩa mới trong bản cuối.

Việc đối chiếu hiện tại do trợ lý thực hiện ở mức kỹ thuật, **không thay thế phê duyệt chuyên môn**. Một số định nghĩa có cùng dạng đại số nhưng khác ý nghĩa/điều kiện, chẳng hạn F016 và F017 cùng dạng `U/k`.

### 2.4. Giao diện và luồng kiểm thử thực tế

- Form nhập số và danh sách: mỗi số một dòng hoặc ngăn bằng dấu `;`.
- Hiển thị công thức, trích đoạn nguồn, đơn vị và điều kiện cần xác nhận.
- Có khôi phục dữ liệu nhập; sửa đầu vào sẽ làm mất hiệu lực kết quả cũ.
- Luồng chạy thật: câu hỏi → embedding OpenRouter + BM25/Qdrant → chọn registry → form → tính toán → trả kết quả kèm nguồn/hash.
- Không dùng chat LLM để sinh công thức hoặc chấm điểm trong lượt registry mới.
- Tạo 200 UC phát triển và 200 UC giữ riêng, có đáp án tính độc lập và 20 đáp án neo viết riêng.

## 3. Kết quả đến thời điểm hiện tại

### 3.0. Bổ sung mới nhất: registry v3 trên bảy nguồn

- Thêm **21 bộ tính**: 15 định nghĩa từ phương trình và 6 quy tắc định lượng từ lời văn. Tổng **47 bộ tính**, mỗi DOCX gốc có ít nhất một bộ tính; không thêm bản sao DOCX để tăng số nguồn.
- Độ phủ phương trình tăng **29/174 → 43/174 (24,7%)**, còn 131 lần xuất hiện chưa hỗ trợ. Sáu quy tắc lời văn không cộng vào mẫu số 174. Đây chưa phải hỗ trợ toàn bộ bảy tài liệu.
- Phân bố bộ tính: 1.061: 3; 1.062: 3; 1.063: 2; 1.071: 5; 1.159: 1; 1.160: 8; 1.190: 25.
- Kiểm chứng: **427/427 pytest**, **42/42 ca số HTTP mới**, **21/21 trình duyệt mới**; hồi quy v2 đạt **200/200 ca số, 20/20 trình duyệt**; sáu bộ tính đầu đạt 6/6 HTTP. Audit corpus: 30/30 ingestion, 238/238 ràng buộc nguồn.
- Bộ mới gồm 21 câu hỏi và 21 bộ số neo, mỗi bộ chạy thêm một bản đổi đơn vị tương đương. Đây là **phát triển/hồi quy công khai**, chưa phải đánh giá độc lập.
- Đã tách chọn công thức theo quy trình để tránh trùng Fxxx, bổ sung ràng buộc nội dung điều kiện v3, nhãn quy tắc lời văn và bộ lọc theo DOCX trên demo.
- Chi tiết: [báo cáo v3](../formula_lab/reports/registry-v3/KET_QUA.md), [bản chất phương pháp](../formula_lab/reports/registry-v3/PHUONG_PHAP.md), [catalog và số liệu mẫu](../formula_lab/reports/registry-v3/CATALOG.md), [hướng dẫn chạy](../formula_lab/v3/README.md).

### 3.1. Mốc v2: kết quả trên 20 bộ tính mới khi đó

| Chỉ số | Tập phát triển, catalog cuối | Giữ riêng lần đầu | Hồi quy sau sửa trên tập đã xem |
|---|---:|---:|---:|
| Tìm/chọn đúng công thức | 20/20 | 18/20 | 20/20 |
| Trả đúng kết quả qua API | 200/200 | 180/200 | 200/200 |
| Trình duyệt đầu cuối | 20/20 | 18/20 | 20/20 |
| Chặn đầu vào lỗi | 144/144 | 132/132 | 144/144 |
| Chặn câu hỏi mơ hồ/chưa hỗ trợ | 12/12 | 12/12 | 12/12 |
| Chặn sửa công thức nguồn, kiểm tra riêng | 20/20 | 18/18 | 20/20 |
| Ca số hợp lệ bị từ chối nhầm | 0 | 20 | 0 |
| Kết quả số sai vẫn trả ra | 0 | 0 | 0 |
| Lỗi hạ tầng ảnh hưởng ca thử | 0 | 0 | 0 |

Mỗi tập có **20 cách hỏi, mỗi cách hỏi gắn mười bộ số**. Hai form không mở được ở lượt giữ riêng đầu khiến các kiểm tra đầu vào/nguồn tương ứng chưa chạy; những ca này không được tính là đạt.

**Cách đọc kết quả:** lần giữ riêng đầu tiên đạt **90% trả kết quả hữu ích**. Sau khi xem lỗi và sửa, chạy lại đạt **100% hồi quy**. Kết quả hồi quy không phải bằng chứng trên tập giữ riêng mới, cũng không phải cam kết độ chính xác 100% ngoài thực tế.

### 3.2. Mốc v2: các kiểm tra bổ sung và độ phủ

| Hạng mục | Kết quả |
|---|---:|
| Unit/regression tests | 320 ca đạt |
| Sáu bộ tính cũ qua HTTP | 6/6 đạt |
| Đọc cấu trúc trên 30 DOCX | 30/30 đạt |
| Ràng buộc nguồn với catalog mở rộng | 156/156 đạt |
| Số bộ tính | 26 |
| Lần xuất hiện phương trình được hỗ trợ | 29/174 — khoảng 16,7% |
| Lần xuất hiện chưa có bộ tính đã đối chiếu | 145/174 |

Độ phủ tăng từ **9/174 (5,2%) lên 29/174 (16,7%)**. Đây là tỷ lệ theo lần xuất hiện phương trình, không phải tỷ lệ họ công thức độc lập.

Index demo dùng bảy bản trích xuất gốc và 20 đoạn công thức đã đối chiếu. Hai mươi ba DOCX tổng hợp dùng cho kiểm tra ingestion/ràng buộc nguồn, không đưa vào index để tránh bản sao làm tăng điểm truy hồi.

## 4. Lỗi đã phát hiện và xử lý

| Vấn đề | Xử lý / trạng thái |
|---|---|
| Câu hỏi chỉ rõ quy trình khác nhưng mở nhầm bộ tính | Kiểm tra mã QTKĐ và thiết bị trước khi chọn |
| Trường đơn vị nhận object/list gây lỗi máy chủ | Kiểm tra kiểu và trả lỗi dữ liệu |
| Tìm đúng tài liệu nhưng thiếu đoạn công thức đã duyệt | Tìm kiếm trong phạm vi đoạn công thức khi câu hỏi chỉ rõ QTKĐ 1.190/DPI 610 |
| Ký hiệu `f0` bị hiểu thành mã `F000` | Phân biệt đại lượng với ID ba chữ số như `F036` |
| `f0` là đầu vào của `u_f0` bị hiểu thành yêu cầu thứ hai | Đối chiếu schema biến cho các nhắc đến sau “từ/với”; yêu cầu thực sự mơ hồ vẫn cần làm rõ |
| Dấu trung bình OMML bị đổi thành dấu mũ; ngoặc nhọn LaTeX lỗi | Sửa bộ chuyển đổi và kiểm tra hiển thị KaTeX |
| Điều kiện số loạt đo của F004 chưa thống nhất | Giữ lại chờ kiểm tra, chưa mở bộ tính |
| Benchmark khởi động trước server và phân loại nhầm lỗi kết nối | Thêm health check, tách lỗi hạ tầng; giữ artifact lượt lỗi và loại khỏi kết luận chất lượng |

## 5. Phần chưa hoàn thành và giới hạn

- Chưa có chuyên gia đo lường xác nhận biểu thức, ý nghĩa biến, đơn vị và điều kiện của các định nghĩa mới.
- Chưa có bộ đánh giá mù do người khác soạn; tập giữ riêng hiện tại vẫn do cùng tác giả xây dựng và dùng cùng 20 định nghĩa.
- Sau mở rộng v3, chưa hỗ trợ 131 lần xuất hiện phương trình còn lại; chưa thể khẳng định khả năng xử lý công thức bất kỳ.
- Chưa chuyển đổi và đối chiếu lại toàn bộ OLE/MathType. Các dấu hiệu thiếu mẫu số, thiếu vế phải trong artifact cần quay lại tài liệu gốc để xác định nguyên nhân.
- Các công thức F004, F014, F040/F044, F046, F049 còn vấn đề điều kiện hoặc ký hiệu nên chưa tự sửa để chạy.
- Chưa tự tính toàn bộ chuỗi độ không đảm bảo từ chứng nhận. F033 nhận mười thành phần đã xác định; F050 nhận `u_c` đã xác định riêng.
- Bộ chọn còn dựa vào từ khóa và schema; cách hỏi mới, viết tắt, nhiều yêu cầu hoặc hội thoại nhiều lượt có thể bị từ chối.
- Số liệu nhập nhầm nhưng vẫn hợp lệ về kiểu, đơn vị và miền có thể không bị phát hiện. Checkbox xác nhận không tự chứng minh điều kiện vật lý là đúng.
- Hash toàn DOCX thay đổi khi đổi bố cục nên có thể làm mất hiệu lực đối chiếu; cần quy trình quản lý phiên bản thuận tiện hơn nhưng vẫn giữ ràng buộc nguồn.
- Đã có form duyệt/tính trong React chính; chatbot mới hướng dẫn mở form, chưa tự ánh xạ câu trả lời sang ID đã duyệt. Chưa triển khai sử dụng nghiệp vụ.

## 6. Công việc tiếp theo theo thứ tự ưu tiên

| Ưu tiên | Công việc | Đầu ra / điều kiện hoàn thành đề xuất |
|---|---|---|
| 1 | Chuyên gia rà soát 20 định nghĩa mới và các trường hợp đang giữ lại | Biên bản cho từng công thức: chấp nhận, cần sửa hoặc không đủ căn cứ; ghi rõ biểu thức, biến, đơn vị, điều kiện và phiên bản nguồn |
| 2 | Tạo tập đánh giá độc lập trước khi sửa tiếp | Người khác soạn câu hỏi tự nhiên, số liệu và đáp án; đóng băng tập mới, chỉ mở sau khi cố định phiên bản |
| 3 | Đánh giá lại trên tập độc lập | Báo riêng độ phủ, chọn đúng công thức, trả đúng số, từ chối nhầm, kết quả sai không bị chặn và lỗi hạ tầng; không gộp từ chối vào tỷ lệ trả lời hữu ích |
| 4 | Mở rộng công thức và tài liệu thật | Ưu tiên các biểu thức đọc rõ trong QTKĐ 1.160 và phần còn lại của 1.190; đối chiếu từng công thức, có đáp án độc lập, không tự duyệt hàng loạt LaTeX |
| 5 | Tích hợp vào chatbot chính | Liên kết công thức trong câu trả lời với đúng registry ID/phiên bản; mở form trên React; tính ở backend; trả kết quả có đơn vị và nguồn |
| 6 | Kiểm thử tích hợp và thử nghiệm nghiệp vụ có kiểm soát | Bao phủ câu hỏi mới, hội thoại nhiều lượt, thay đổi nguồn, phiên tính hết hạn, dữ liệu sai và lỗi dịch vụ; giữ cơ chế chặn khi chưa đủ căn cứ |

**Bước nên làm ngay:** rà soát chuyên môn và chuẩn bị tập đánh giá độc lập. Không dùng điểm hồi quy 100% hiện tại làm căn cứ duy nhất để đưa vào sử dụng nghiệp vụ.

## 7. File bàn giao và cách tiếp tục

### Bổ sung chuẩn bị rà soát và đánh giá độc lập — 28/09/2026

- Đã tạo [20 phiếu rà soát chuyên môn](../formula_lab/reports/registry-v2/expert-review/PHIEU_RA_SOAT.md), gồm biểu thức đang chạy, biến, đơn vị, ràng buộc, điều kiện, trích đoạn định vị, liên kết DOCX/XML và ô ghi kết luận. Tất cả vẫn **chờ chuyên gia**.
- Đã tổng hợp [các điểm cần làm rõ](../formula_lab/reports/registry-v2/expert-review/PENDING.md) cho F002, F003, F004, F011–F015, F040/F044, F046 và F049.
- Đã soạn [quy trình đánh giá độc lập](../formula_lab/reports/registry-v2/expert-review/DANH_GIA_DOC_LAP.md): phân công, ma trận ca đề xuất, dữ liệu cần bàn giao, đóng băng, cách chạy và báo cáo chỉ số. **Chưa có đề độc lập mới và chưa có kết quả đánh giá mới.**
- Đã lưu [snapshot hash tham chiếu](../formula_lab/reports/registry-v2/expert-review/BASELINE.json) cho 38 file nguồn/mã/dữ liệu. Đây là mốc phục vụ rà soát, chưa phải đóng băng đầy đủ môi trường đánh giá.
- Benchmark hiện tại gắn với tập dev/holdout cũ và giả định 10 bộ số/câu hỏi. Cần bổ sung runner nhận tập ngoài theo hợp đồng dữ liệu đã chốt trước khi chạy đánh giá độc lập.
- Kiểm tra sau bổ sung: 20 phiếu đều để trống kết luận chuyên gia, liên kết nội bộ hợp lệ, 38 hash khớp; chạy lại bộ pytest nêu bên dưới đạt 320/320 ca. Có một cảnh báo thư viện Starlette/httpx deprecated. Chưa chạy lại benchmark HTTP/trình duyệt trong lượt bổ sung này.

Bước tiếp theo cần người thực hiện: chuyên gia điền kết luận từng phiếu và người biên soạn độc lập chuẩn bị đề/đáp án ngoài workspace phát triển. Phần chuẩn bị này chưa hoàn thành thay cho hai bước chuyên môn đó.

### Tài liệu và bằng chứng

- [Báo cáo kết quả mới nhất](../formula_lab/reports/registry-v2/KET_QUA.md).
- [Danh sách 20 công thức mới](../formula_lab/reports/registry-v2/CATALOG.md).
- [Hồ sơ đối chiếu nguồn và điều kiện](../formula_lab/reports/registry-v2/source-review/REVIEW.md).
- [So sánh ba hướng ban đầu](../formula_lab/reports/COMPARISON.md).
- [Bộ 30 DOCX thử nghiệm](../formula_lab/expanded/corpus/).
- [Kiểm tra lại 30 DOCX và độ phủ](../formula_lab/reports/registry-v2/corpus-audit.json).
- [Kết quả giữ riêng lần đầu](../formula_lab/reports/registry-v2/holdout/20260928T043112Z/summary.json).
- [Kết quả hồi quy sau sửa](../formula_lab/reports/registry-v2/holdout-regression/20260928T043339Z/summary.json).
- [Hướng dẫn chạy bản mới](../formula_lab/v2/README.md).

### Chạy demo và kiểm thử

Thực hiện từ thư mục `/root/RAG-TC-DL`:

```bash
# Khởi động demo nếu chưa có tiến trình đang dùng cổng 8093
.venv-formula/bin/python -m uvicorn formula_lab.app:app --host 0.0.0.0 --port 8093

# Kiểm tra mã và các ca hồi quy
.venv-formula/bin/python -m pytest formula_lab/tests tests/unit/llm tests/unit/ingestion/test_extract_docx.py -q

# Kiểm tra lại corpus 30 DOCX
.venv-formula/bin/python -m formula_lab.v2.audit_corpus

# Chạy lại tập đã xem, cần demo sẵn sàng
.venv-formula/bin/python -m formula_lab.v2.benchmark --split holdout --regression
```

Địa chỉ demo khi server chạy: `http://localhost:8093`. File tiến độ này tổng hợp các kết quả đã lưu; không xác nhận tình trạng chạy của server tại thời điểm đọc.

Ví dụ câu hỏi: `DPI 610: hệ số góc hồi quy`, `QTKĐ 1.190: độ phân giải tam giác`, `DPI 610: u_f0 với f0`.

Các báo cáo, UC và ảnh giao diện cũ được giữ lại để truy vết. Khi thay đổi định nghĩa hoặc nguồn, cần cập nhật hồ sơ đối chiếu có chủ đích và chạy kiểm tra tương ứng; không tự cập nhật phê duyệt chỉ để vượt qua ca lỗi.

### Đăng ký nháp trong ingestion và tích hợp ứng dụng chính — 28/09/2026

- Backend SQLite lưu nháp, phiên bản, nguồn/hash và lịch sử; API lấy/tạo/sửa/duyệt/từ chối/tính tương ứng FE. Sửa định nghĩa thu hồi duyệt; nguồn thay đổi hoặc bị xóa chặn tính; revision cũ bị từ chối.
- React có tab Công thức và phê duyệt trong màn hình tài liệu, form đối chứng và form tính có đổi đơn vị/điều kiện. Tên người duyệt hiện tự nhập, chưa có phân quyền.
- Backfill bảy DOCX: 334 nháp, 0 đã duyệt; 57 bản có gợi ý biểu thức, 277 bản còn thiếu. Chạy lại tạo 0 bản trùng. [Báo cáo](../build/formula-review/backfill-summary.json).
- Kiểm thử FE + API thật trên dữ liệu giả: 6/6 kiểm tra luồng, gồm đổi đơn vị, thu hồi duyệt và từ chối. [Bằng chứng](../build/formula-review/browser-summary.json). Không phải đánh giá độc lập về chuyên môn.
- Đánh giá độc lập đã hoàn tất theo thang 100 điểm cố định: **vòng 1 đạt 83%, sửa lỗi rồi vòng 2 đạt 96%**; C01–C09 đều đạt trong phạm vi kiểm. [Báo cáo đầy đủ](../build/formula-review/INDEPENDENT_REVIEW.md).

- Kiểm tra phát triển: 459 ca hồi quy backend/lab/LLM/ingestion qua trước khi thêm ca đổi thư mục nguồn; sau bổ sung, 33/33 ca registry qua. FE cuối cùng 35/35 test, typecheck/lint/build qua. Docker chưa chạy vì môi trường không có CLI; đã đọc YAML và kiểm mount lưu trữ.

### Kết quả đánh giá độc lập sau sửa

- Hai lỗi tìm thấy và đã sửa: API cho lưu cấu trúc hỏng gây trắng React; xóa rồi tải lại nguồn giống hệt bị kẹt trạng thái hết hiệu lực. Giữ bằng chứng/snapshot trước và sau, không đổi trọng số để tăng điểm.
- Agent tự chạy **472/472 ca backend liên quan (100%)**, **47/47 ca FE (100%)**, **10/10 kiểm tra luồng trình duyệt (100%)**; typecheck/lint/build qua. Ma trận kiểm lại cấu trúc hỏng đạt 16/16; vòng phục hồi nguồn đã duyệt bắt buộc duyệt lại cũng qua.
- Số học độc lập: 13/14 khớp tuyệt đối (92,86%); một phép hồi quy lệch 1e−33 do làm tròn Decimal. Phân tích hậu kiểm với sai số tuyệt đối 1e−30 đạt 14/14; giới hạn này được ghi rõ là chọn sau lần chạy, không sửa đáp án. Các ca chặn sai đạt 20/20.
- **96% là điểm tiêu chí kỹ thuật, không phải độ chính xác nghiệp vụ hay độ phủ tất cả công thức.** C16 còn 0/4: chưa có xác thực/phân quyền người duyệt, chuyên gia phê duyệt nguồn thật và tập đánh giá nghiệp vụ độc lập. Chưa chạy container hoặc toàn bộ test legacy Gradio vì môi trường thiếu thành phần tương ứng.
- 334 nháp nguồn thật vẫn chờ duyệt; 57/334 có biểu thức gợi ý (17,07%), không phải đã được phép tính. Chưa có phê duyệt nghiệp vụ. Đã mở React/API chính với nguồn thật và kiểm tra chỉ đọc cả bảy tài liệu.
- Hướng dẫn dùng: **Tài liệu → chọn DOCX → Công thức và phê duyệt**. API và luồng chi tiết trong [hướng dẫn](../docs/FORMULA_DRAFT_APPROVAL.md).

### Đồng bộ Docker, tài liệu và thư viện sau audit

- Đã cập nhật README gốc/FE, hướng dẫn dependency/lưu trữ, Docker Python3.12/API mặc định, Node24 frontend, registry persistence/healthcheck, runtime Python lock và npm lock, run.sh/Makefile/CI.
- Môi trường cài mới:204 Python unit test đạt,1 adapter kotaemon bỏ qua;47 FE tests đạt; typecheck/lint/build/pip check qua. API/React trên runtime mới mở nguồn thật thành công,334nháp vẫn pending.
- Không có Docker CLI/daemon để build/run container tại đây; đã kiểm YAML và import trong bố cục COPY cô lập, thêm job CI buildimage nhưng chưa chạy CI.
- Báo cáo96% cũ và bộ tiêu chí đã được đánh dấu lịch sử có bias. Holdout mới giữ nguyên kết quả và lỗi harness;2 phát hiện về precision/thứ nguyên còn ghi nhận, không tuyên bố đã khắc phục hoặc nghiệm thu>95%.
- [Báo cáo cập nhật hệ thống](../build/system-update/UPDATE_REPORT.md) và [hướng dẫn thư viện/vận hành](../docs/SYSTEM_DEPENDENCIES.md).

## Cập nhật sau review mã: sửa ba lỗi

Đã sửa ngưỡng đối chứng cho giá trị nhỏ, xử lý tên biến/điều kiện `constructor`, và bảo vệ chỉnh sửa khi điều hướng toàn ứng dụng. Backend registry 50/50 và FE 55/55 qua; typecheck/lint/build và kiểm tra Chromium qua. Đây là hồi quy sau sửa, không thay điểm đánh giá độc lập. Chi tiết: [REVIEW_FIXES.md](../build/formula-review/REVIEW_FIXES.md).
