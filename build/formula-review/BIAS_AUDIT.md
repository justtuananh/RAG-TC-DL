# Audit thiên lệch của đánh giá công thức

## Kết luận

**Lo ngại của người dùng có căn cứ. Tôi rút lại cách diễn giải “96% chất lượng/năng lực”, “BE/FE 100%” và việc dùng 96 để khẳng định một nghiệm thu độc lập đáng tin cậy.** Con số 96 chỉ là tổng điểm theo checklist nội bộ do dev chọn, sau vòng sửa lỗi có trao đổi ca kiểm thử và có thay đổi tolerance hậu kiểm. Nó không phải độ chính xác, độ phủ năng lực, xác suất hoạt động đúng hay chứng nhận nghiệp vụ. Không có đủ căn cứ để thay bằng một tỷ lệ chất lượng tổng quát khác.

Có bằng chứng về **thiên lệch trong thiết kế thang điểm và quy trình**, nhưng không có căn cứ kết luận cá nhân cố ý gian lận. Hai lỗi trước đây đã được tìm và sửa thật; 472 BE tests, 47 FE tests và các lượt UI đã chạy là bằng chứng regression có ích. Những điều đó không làm quy trình trở thành đánh giá mù.

Holdout mới đã được khóa trước chạy, chạy **một lần**, không sửa implementation, không sửa tolerance, không lặp dev sửa để đạt 95. Kết quả raw là **25/32 ca đạt (78,125% của tập cố định)**. Sau đọc bằng chứng: 2 quan sát không đạt có ý nghĩa đối với hệ thống/năng lực, 3 ca có lỗi thiết kế test, 2 ca UI không kiểm chứng do harness bị chặn. **78,125% cũng không phải chất lượng hệ thống.** Các lỗi harness được giữ công khai, không xóa ca hoặc thay mẫu số để có tỷ lệ đẹp hơn.

## 1. Những điểm làm đánh giá cũ thiên lệch

| Vấn đề | Bằng chứng | Hệ quả |
|---|---|---|
| Trọng số tạo sẵn đường vượt 95 | C16 chỉ 4/100; thiếu toàn bộ xác thực, phân quyền, chuyên gia và benchmark nghiệp vụ vẫn có trần 96. Dev tự khai báo đã biết thiếu các khả năng đó khi chọn trọng số; không có stakeholder hoặc bên ngoài xác nhận trọng số. | Việc “khóa trước chạy” không loại bỏ bias khi thang điểm được chọn sau khi đã biết năng lực hệ thống. 96 gần như là trần đã biết nếu sửa hết phần còn lại. |
| Đánh giá việc mô tả giới hạn thành điểm năng lực | C13 đếm nháp; C14 ghi/kiểm giới hạn; C17 xác nhận chat chỉ hướng dẫn mở form. Ba mục này có tổng 13 điểm, vẫn có thể đạt đầy đủ khi chưa trích xuất đúng mọi công thức và chưa tự ánh xạ hội thoại đến ID đã duyệt. | Hợp lý nếu gọi là checklist trung thực tài liệu; không tương đương chứng minh ba khả năng đó. C17 trước đây đã được chấm đầy đủ vì nói đúng giới hạn, không phải chat đã thực hiện tính. |
| Tolerance C07 thay sau kết quả | Script đầu dùng equality, trả 13/14 exact. Sau khi thấy slope lệch 1e−33, reviewer dùng absolute tolerance 1e−30 và chấm C07 đầy đủ. Dev xác nhận đã đọc kết quả rồi nhắn reviewer phân biệt roundoff và ghi rõ tolerance nếu đổi. | Có lý do kỹ thuật để không coi sai số nhỏ là bug, nhưng chọn ngưỡng hậu kiểm rồi dùng để đạt điểm là sai về quy trình xác nhận. Công khai hậu kiểm làm minh bạch hơn, không biến nó thành tiêu chí định trước. |
| Ca đã lộ trong vòng sửa–retest | Reviewer gửi repro; dev sửa và bổ sung regression; reviewer chạy lại. Dev còn gợi ý thử malformed shape và same-bytes restore trước khi reviewer xác nhận. | Đây là collaborative QA tốt cho sửa lỗi. Kết quả sau sửa không phải khả năng tổng quát trên ca chưa biết. Không được gọi hai phát hiện này là tìm kiếm hoàn toàn mù của assessor. |
| Tự chạy không đồng nghĩa tự thiết kế | Phần lớn 472 BE / 47 FE tests do dev viết; assessor tự chạy lại. | Xác nhận tái lập kết quả, không tạo test độc lập về thiết kế/đáp án. Cần tách regression của dev, ca mới của assessor và holdout chưa lộ. |
| Phạm vi hạn chế nhưng chấm đầy đủ | Chưa Docker runtime, full legacy suite bị thiếu Gradio, accessibility chỉ mẫu nhãn/focus, một trình duyệt, ít viewport và ca số học, chưa chuyên gia. | Việc ghi rõ giới hạn là đúng. Tuy nhiên full credit cho mục rộng với bằng chứng hẹp khiến tổng 96 trông chắc chắn hơn phạm vi thực chứng. Một số giới hạn hợp với scope React đã nêu; không thể lấy scope đó làm readiness toàn hệ thống. |
| Độc lập chưa đầy đủ | Cùng model family, cùng workspace, đọc mã trước, trao đổi với dev, reviewer chính là agent đã chấm cũ. | Có bias neo vào kết luận trước và xung đột khi tự audit. Không phải bên ngoài, assessor mù hoàn toàn, chuyên gia đo lường hay đơn vị chứng nhận. |
| Tỷ lệ nhóm dễ gây hiểu sai | BE C01–C09 và FE C02+C10–C12 được tính riêng, có giao C02; đều đạt 100% sau sửa. | Đó chỉ là các tổng checklist phụ, không phải độ phủ, độ chính xác hoặc xác suất. Tôi rút cách gọi chúng như tỷ lệ năng lực BE/FE. |

Tự khai báo của dev trong lượt audit là bằng chứng về quy trình cộng tác, chưa phải xác minh bên thứ ba. File tiêu chí hiện chưa được Git track trong snapshot audit; mtime và hash chỉ hỗ trợ chronology cục bộ, không chứng minh tuyệt đối tiêu chí có trước mọi tri thức về kết quả. `audit-holdout/chronology.json` ghi trạng thái này.

## 2. 334 nháp không chứng minh độ phủ thực thi

Dữ liệu read-only ở vòng trước: 7 DOCX có 334 ứng viên, **57 có biểu thức gợi ý (17,07%)**, **232 thiếu LaTeX (69,46%)**, tất cả pending, **0 được phê duyệt**. Các số này không phải mẫu gold-standard và có thể gồm ứng viên lỗi/trùng. “7/7 tài liệu có bản ghi” không đồng nghĩa trích xuất đủ/đúng các công thức trong 7 tài liệu.

Không biết denominator số công thức thật, không có matching gold labels nên không tính được precision, recall hay tỷ lệ tính đúng nghiệp vụ. Registry lab riêng không thay thế việc phê duyệt 334 ứng viên. Lượt audit mới không phê duyệt bất kỳ nguồn thật nào.

## 3. Holdout mới đã khóa như thế nào

- Tạo trong `/tmp/formula-blind-audit`; không gửi dev nội dung ca/expected trước khi chạy. Dev cam kết không đọc thư mục; đây là độc lập với dev tại thời điểm chạy, **không phải bảo mật bằng phân quyền hoặc assessor-blind**. Reviewer đã biết 14 ca cũ và mã thực thi.
- Manifest 32 ca: 16 số học, 8 biên/cấu trúc/năng lực, 4 vòng đời, 4 UI Chromium. Mỗi ca trọng số 1; mẫu số cố định 32; không có mục tiêu 95 hay điểm readiness thay thế.
- Số học khóa `abs(actual−expected) ≤ abs(expected) × 1e−24`, absolute tolerance 0; expected từ đại số, hệ số đơn vị và Decimal90 độc lập với production engine. Ngưỡng này là stress requirement của audit, **không phải SLA độ chính xác đã được ứng dụng công bố**. Nó cố ý khắt khe hơn nhiều nhu cầu thực tế và không nên được diễn giải như benchmark đại diện phân bố nghiệp vụ.
- Đóng băng manifest: **2026-09-28T08:02:42.086167Z**, SHA-256 `00fbf51036b4411db60c53ff01210f257c1993e661e01c318a72ea3b224ce9a8`.
- Đóng băng kết quả: **2026-09-28T08:04:53.139561Z**, SHA-256 `cbbb82a3aa22ecfbf289ee939b72c7b6938c53a38445e5b084ab55f4cc16be09`.
- Mã thực thi được hash trước/sau, không thay đổi. Server 8082 dùng DOCX/SQLite giả riêng; browser chỉ đổi URL đích sang server đó, không mock nội dung response. Không sửa implementation trong lượt này.
- Một execution. Compile runner trước chạy chỉ kiểm cú pháp; không gọi hệ thống. Không sửa hoặc chạy lại harness sau kết quả. Kết quả JSON và manifest gốc không overwrite; chỉ thêm phân loại hậu kiểm trong file riêng. Timestamp/hash do chính môi trường ghi, không phải timestamp/signature đáng tin của bên thứ ba.
- Sau freeze mới xuất ca, expected, runner và kết quả về `build/formula-review/audit-holdout/`. Manifest đã giữ nguyên nên có cả các ca được xác định là thiết kế sai.

## 4. Kết quả một lượt và các lỗi thật của phép đánh giá

| Nhóm | Số ca khóa | Raw đạt | Raw không đạt/không thực hiện | Diễn giải |
|---|---:|---:|---:|---|
| Số học | 16 | 13 | 3 | N06 vượt tolerance; N07/N08 bị chặn vì expected của harness quá dài, không đo được phép tính dự định. |
| Biên/cấu trúc/năng lực | 8 | 7 | 1 | B08 hệ thống không kiểm thứ nguyên giữa các biến trong biểu thức. |
| Vòng đời/provenance | 4 | 4 | 0 | DOCX context/hash/fid; nguồn đổi chặn; vòng A→B→A không kế thừa approval; concurrent edit đúng một người thắng. |
| UI thực tế | 4 | 1 | 3 | U02 yêu cầu dialog sai với thiết kế giữ editor; U03/U04 bị chặn bởi harness không chuyển về tab. Không kết luận UI hỏng từ 3 ca này. |
| Tổng raw | 32 | **25** | **7** | **78,125% của tập cố định; không phải điểm chất lượng.** |

### N06 — giới hạn số học quan sát được

Với `x=[10^28, 10^28+1, 10^28+3]`, `y=[0,2,6]`, đáp án chính xác của hồi quy tuyến tính là **2**. API trả **1.999999999985714285714387755102040**, sai khác **1.4285714285612244897960e−11**, vượt ngưỡng đã khóa **2e−24**. HTTP200; đầu vào nằm trong miền số parser cho phép.

Đây là mất độ chính xác khi lấy trung bình/trừ các số lớn gần nhau ở Decimal precision34. Không cần gọi nó là lỗi nghiệp vụ nghiêm trọng khi chưa biết độ chính xác nghiệp vụ cần bao nhiêu; nhưng có đủ bằng chứng bác bỏ suy luận “tất cả phép số trong miền đều đúng đến tolerance cực nhỏ” và full numeric confidence từ 14 ca đơn giản trước. Không nới tolerance để cho qua.

### B08 — thiếu khả năng tự kiểm thứ nguyên

Định nghĩa `a+b`, `a` đơn vị Pa, `b` đơn vị m, kết quả Pa, ca đối chứng số học `1+2=3` đã được **approve HTTP200**, không có validation error. Test kỳ vọng tự chặn vì vật lý không thể cộng áp suất và chiều dài.

Mã hiện kiểm đơn vị đầu vào có tương thích với **đơn vị khai báo của từng biến**, không suy diễn thứ nguyên cả biểu thức. Đây là **capability gap**, không tự động là regression vi phạm hợp đồng cũ: hợp đồng cũ giao việc đối chiếu vật lý cho người rà soát. Kết hợp với thiếu chuyên gia/xác thực, không thể gọi approved là bảo đảm đúng nghiệp vụ. Trong audit này chỉ ghi nhận, không sửa.

### N07/N08 — lỗi thiết kế oracle của chính assessor

Tôi tạo expected `1e−10/3` với **90 chữ số** rồi dùng trực tiếp làm ca đối chứng khi approve. Parser chỉ nhận chuỗi số tối đa 60 ký tự. Hai ca bị422 tại approval, trước khi phép `mean` trên đầu vào cancellation được thực hiện. Vì vậy **chưa có bằng chứng runtime mean sai** từ hai ca này.

Raw JSON giữ hai non-pass tại bước approve; phân loại đúng là test/harness invalid, không lỗi số học sản phẩm. Không cắt ngắn expected và chạy lại, không thay kết quả ban đầu. Đó cũng là bằng chứng assessor có thể tạo test sai, nên không được mặc định các test “độc lập” đều có oracle/flow đúng.

### U02/U03/U04 — giả định workflow sai và lỗi dây chuyền harness

U02 giả định chuyển từ tab công thức sang nguồn phải xuất hiện confirm rồi cancel. Thực tế component giữ editor mounted và chỉ `hidden`, nên không cần hỏi để tránh mất dữ liệu; chính result ghi **title vẫn là `Unsaved holdout delta`**. Không có dialog làm test không đạt theo manifest, nhưng **không chứng minh mất bản sửa**. Đây là yêu cầu test không phù hợp hành vi cho phép.

Runner sau đó không chuyển lại tab công thức; tìm nút lưu trên tab nguồn timeout. U03 (revision conflict) chưa kiểm được; U04 (mobile/keyboard) chưa chạy. Hai ca là blocked/harness error, không được gán app fail hoặc pass. Không có screenshot mobile holdout vì chưa đến bước đó; ảnh từ audit cũ không được tái dùng để lấp thiếu bằng chứng mới.

Sau phân loại: **25 quan sát đạt, 2 quan sát không đạt có ý nghĩa, 3 thiết kế test không hợp lệ, 2 blocked**. Tôi không tính lại một passrate đẹp hơn bằng cách loại 5 ca sau khi nhìn kết quả.

## 5. Bias còn lại ngay trong holdout này

Tập mới chỉ chưa lộ với dev trước chạy; assessor biết code, biết Decimal34 và chủ động chọn stress cases nên đây là kiểm tra đối kháng có mục đích, không mẫu ngẫu nhiên đại diện nghiệp vụ. B08 chủ động đòi khả năng ngoài hợp đồng cũ để đo khoảng trống, không thể dùng nó lén đổi tiêu chuẩn cũ rồi gọi mọi sự khác biệt là bug.

Ngưỡng relative1e−24 được khóa đúng thời điểm nhưng chưa được chuyên gia nghiệp vụ xác nhận. Khóa trước không tự làm tiêu chí trở nên phù hợp — cùng bài học với trọng số C16 cũ. Các lỗi N07/N08 và UI làm độ phủ holdout thấp hơn dự định. Vì thế kết luận đúng là **quy trình cũ không đủ để chứng minh 96% năng lực; holdout mới cũng không đủ để ước lượng năng lực tổng quát bằng một phần trăm**.

## 6. Cách diễn đạt kết quả được giữ lại

Có một luồng kỹ thuật đăng ký nháp → rà soát thủ công → phê duyệt → tính với nhiều regression tests đã qua và hai lỗi đã sửa. Chưa có bằng chứng hệ thống tự hiểu/chuẩn hóa đầy đủ công thức từ 7 nguồn, kiểm được ý nghĩa vật lý, tự ánh xạ hội thoại đến bộ tính đúng, hay đáp ứng readiness nghiệp vụ. Một phép slope stress cho thấy sai số lớn hơn ngưỡng holdout; khả năng tự kiểm thứ nguyên chưa có. Các phần test sai của assessor được công khai.

Một vòng đánh giá tiếp theo đáng tin hơn cần stakeholder/chuyên gia chốt yêu cầu năng lực và tolerance theo nghiệp vụ trước khi xem kết quả; readiness là điều kiện bắt buộc riêng thay vì 4 điểm có thể bỏ; tách regression đã lộ và holdout mới; oracle độc lập được kiểm tra giới hạn định dạng; từng UI case cô lập; gold set từ nguồn thật do người có chuyên môn lập. Đây là khuyến nghị quy trình, **không phải một vòng sửa để ép điểm >95**.

## Artifacts

`audit-holdout/manifest.json`, `seal.json`, `results.json`, `result-seal.json`, `implementation-before.json`, `implementation-after.json`, `classification.json`, `harness-change-log.json`, `chronology.json`, `prepare.py`, `run.py`, `server.py`, `run.log`, `server.log`.

Không sửa báo cáo/JSON cũ để xóa lịch sử. Báo cáo này thay thế cách diễn giải mức độ độc lập và tỷ lệ chất lượng của kết luận 96 trước đó.
