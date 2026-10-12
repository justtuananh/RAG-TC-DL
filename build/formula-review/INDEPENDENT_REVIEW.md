# Đánh giá công thức — báo cáo lịch sử sau sửa

> **Đính chính sau audit:** điểm 96 chỉ là checklist nội bộ có bias về trọng số và tolerance hậu kiểm; không dùng để nghiệm thu độc lập hoặc diễn giải thành chất lượng/năng lực. Xem [BIAS_AUDIT.md](BIAS_AUDIT.md). Giữ nguyên các kết quả lịch sử bên dưới để truy vết.

**Vòng 1:83/100 → vòng 2:96/100.** Vòng 2 vượt95 và toàn bộ C01–C09 đạt trong phạm vi đã kiểm. **Đạt tiêu chí kỹ thuật vòng này; chưa sẵn sàng nghiệp vụ** vì C16=0/4: thiếu xác thực/phân quyền người duyệt, chuyên gia duyệt nguồn thật và tập đánh giá nghiệp vụ độc lập. Không thay trọng số hoặc nới ngưỡng để đạt điểm.

Hai lỗi đã được gửi dev và sửa: F01 API lưu cấu trúc sai làm trắng toàn React; F02 xóa rồi phục hồi cùng nguồn bị kẹt stale. Reviewer không sửa mã triển khai. Bằng chứng trước/sau và snapshot hashes được giữ riêng.

## Điểm vòng 2

| Mã | Trọng số | Kết quả | Điểm | Bằng chứng mới / giới hạn |
|---|---:|---|---:|---|
| C01 | 7 | Đạt | 7 | Đọc ingestion_jobs.py: đăng ký sau trích xuất trước embedding. Tự chạy test_ingestion_creates_drafts_before_embedding_failure; nháp còn sau lỗi dịch vụ. |
| C02 | 7 | Đạt | 7 | React/API thật rerun10/10 checkpoints. Shape15 loại sai bị422 trước ghi; legacy record sai hiện lỗi dễ hiểu, không crash. |
| C03 | 7 | Đạt | 7 | Tự chạy registry suite kiểm thiếu định nghĩa/đơn vị/điều kiện/ca đối chứng/người/nhận xét/xác nhận; chỉ đầy đủ mới approve. |
| C04 | 7 | Đạt | 7 | Tự chạy pending/rejected và revision cũ chặn409; dev regression tự chạy gồm stale/hash/digest giả mạo; POST thêm status trả422. |
| C05 | 7 | Đạt | 7 | Ca độc lập lưu bản approved thu hồi; ghi revision cũ409. Tự chạy competing approval test giao dịch SQLite. |
| C06 | 7 | Đạt | 7 | F02 đã sửa và tự kiểm API approved→delete→samebytesrestore→pending/no review→compute409 →reapprove→22 Pa; generate tiếp created 0 giữ approved/revision. Nguồnhash/định vị/chặn đổi/xóa và idempotency tests đều qua. |
| C07 | 7 | Đạt | 7 | 14 ca số học tự thiết kế, đáp án JSON trước thực thi:13/14 bằng chính xác; slope đúng trong sai số1e-33. Phân tích hậu kiểm với absolute tolerance1e-30:14/14. Không sửa đáp án; giữ kết quả exact ban đầu. Scalar/series/đổi đơn vị/âm/0/biên và các miền sai đã kiểm. |
| C08 | 7 | Đạt | 7 | Ma trận15 malformed payload422 và không mutation; legacyUI safeerror1/1.20/20 arithmetic/security/domain block; đổi input xóa kết quả. |
| C09 | 7 | Đạt | 7 | Restart Registry còn approved, audit edit/reject, response formula_id/revision/source_hash. Tự chạy relocation test nguồn trong repo dùng relativepath. |
| C10 | 5 | Đạt | 5 | Rerun UI10/10: save/approve/calculate/reject, dirty reload cancel giữ bản sửa, keyboard Tab và responsive. Legacyrecord sai hiệnalert+reload thayvì trắngapp. |
| C11 | 5 | Đạt | 5 | Đã xem ảnh Chromium desktop1440/mobile390; Be Vietnam Pro, xanh primary, navy sidebar, card/field/button đồng bộ. document scrollWidth bằng viewport1440/390. |
| C12 | 5 | Đạt | 5 | Nhãn input/checkbox có tên; thử Tab từ tên sang biểu thức, focus đặt được; status có chữ. Kiểm cơ bản mẫu, chưa WCAG audit hoặc screenreader. |
| C13 | 5 | Đạt | 5 | SQLite mở mode=ro:334 nháp trên7DOCX, tất cả pending,57 có expression,232 thiếuLaTeX. Không duyệtnguồn thật; hash SQLite trước/sau bằng nhau. |
| C14 | 5 | Đạt | 5 | Gọi generate PDF giả trả422 rõ chưa hỗ trợ; kiểm extractor/test OLE không đọc được vẫn nháp. Template hash-gated, không suy diễn tự hiểu công thức phức tạp/quy tắc lời văn. |
| C15 | 5 | Đạt | 5 | Tự chạy bộ liên quan cuối472/472 BE,47/47 FE; typecheck/lint/build qua. Compose parse/mount/import đã kiểm, chưa Docker runtime vì thiếuCLI; legacy full tests/unit còn2collectionerrors do thiếu Gradio. |
| C16 | 4 | Chưa đạt | 0 | Chưa có xác thực/phân quyền; reviewer tự nhập không chứng minh danh tính. Chưa chuyên gia duyệt7DOCX, chưa tập đánh giá nghiệp vụ độc lập. 0/4, không cộng điểm vì ghi giới hạn. |
| C17 | 3 | Đạt | 3 | POST chat/stream thực tế trả hướng dẫn mở Tài liệu→Công thức và phê duyệt; chưa tự ánh xạID đã duyệt hoặc tính trong hội thoại. Chấm đúng khả năng thực tế theo tiêu chí. |

## Kiểm tra lại độc lập

- **F01:16/16 ca.** 15 biến thể container/nested field sai trả422 và không thay proposal/revision. Một bản ghi lỗi cũ được đặt trực tiếp vào SQLite giả: Chromium hiển thị alert tiếng Việt, nút tải lại hoạt động, không có pageerror. Không đưa dữ liệu sai vàoDB thật.
- **F02:đạt.** API thật từ approved→xóa→upload đúng bytes/document ID→tạo lại: pending revision mới, xóa current review/approval, giữproposal/history; chưa duyệt lại tính409. Duyệt lại rõ ràng mới tính22 Pa; tạo lại tiếp không làm mấtapproval. `restore-round2.json` lưu cả trước/sau.
- **472/472 BE tests liên quan;47/47 FE tests;10/10 checkpoints Chromium thật**, TypeScript/lint/build qua. Bundle>500kB còn cảnh báo. Không tuyên bố toàn repo xanh: full legacy tests/unit bị thiếu Gradio khi collection; Docker container chưa chạy.
- **Số học:13/14 bằng chính xác;14/14 sau phân tích làm tròn** (slope sai khác1e−33, tolerance tuyệt đối1e−30 được nêu hậu kiểm, không định trước).20/20 ca chặn và6/6 vòng đời riêng. Không che kết quả39/40 exactpass ban đầu. Mẫu không chứng minh đúng mọi công thức hay độ ổn định số trên toàn miền.
- Điểm nhóm theo chính trọng số đã chốt: BE C01–C09 từ52,5/63 (**83,33%**) lên63/63 (**100% mẫu kỹ thuật**); FE C02+C10–C12 từ16/22 (**72,73%**) lên22/22 (**100% mẫu kỹ thuật**). Các nhóm có giaoC02, không cộng hai tỷ lệ này; không phải độ phủ hoặc xác suất đúng. **Điểm tổng dùng để nghiệm thu vẫn96/100.**
- Bảy nguồn thật giữ334 pending,0 approved; nguồn/SQLite thật chỉ đọc. Chưa có bằng chứng accuracy nghiệp vụ của334 ứng viên;57 có expression/232 thiếu LaTeX không phải số bộ tính được duyệt.

Dữ liệu máy đọc: `independent/round1.json`, `round2.json`, `review-summary.json`; hashes `snapshot-round1.json`/`snapshot-round2.json`. Báo cáo vòng 1 nguyên vẹn ở `independent/report-round1.md`. Script/ảnh/log cùng thư mục. Phần lịch sử dưới giữ cách chấm và phát hiện vòng 1.

---

# Đánh giá độc lập công thức — vòng 1

**83/100 — chưa nghiệm thu.** C02, C06 và C08 trọng yếu chưa đạt đầy đủ; C10 bị ảnh hưởng. C16 chưa đạt. Đã báo dev sửa và sẽ giữ nguyên kết quả vòng 1 khi kiểm tra lại.

Độc lập về lượt kiểm và mẫu kiểm trong cùng dự án, không phải chứng nhận bên ngoài/chuyên gia đo lường. Không sửa mã triển khai. API8081 dùng DOCX/SQLite tại `/tmp/formula-independent`; các phép toán dùng SQLite tạm khác. Không phê duyệt bảy tài liệu thật. Hash snapshot nằm trong `independent/snapshot-round1.json`.

## Phát hiện chính

**F01 — lỗi lớn: dữ liệu sai cấu trúc làm trắng toàn ứng dụng.** GET nháp hợp lệ, PUT đúng sáu trường proposal nhưng đặt `variables:null` trả200 và lưu. Mở bằng Chromium thật tab Công thức và phê duyệt làm React ném `Cannot read properties of null (reading 'map')`; body không còn nội dung. Không sửa nháp được trongUI. `repro_malformed.py`, `malformed-repro.json`, `malformed-crash.png` có bằng chứng. Đã khôi phục bản nháp giả quaAPI sau tái hiện. Yêu cầu BE từ chối sai cấu trúc trước ghi, FE hiển thị lỗi dữ liệu cũ và vẫn cho người dùng thao tác phục hồi phù hợp.

**F02 — lỗi vòng đời nguồn:** delete204 rồi upload lại cùngbytes/document ID, generate trả created 0 nhưng bản ghi vẫn stale revision2. Không có bản pending để rà soát. Tái hiện bằng API thật trong `repro_restore.py` / `restore-round1.json`. Đã yêu cầu dev sửa và không tự kế thừa phê duyệt.

## Điểm theo trọng số đã chốt

| Mã | Trọng số | Kết quả | Điểm | Bằng chứng và giới hạn |
|---|---:|---|---:|---|
| C01 | 7 | Đạt | 7 | Đọc ingestion_jobs.py: đăng ký sau trích xuất trước embedding. Tự chạy test_ingestion_creates_drafts_before_embedding_failure; nháp còn sau lỗi dịch vụ. |
| C02 | 7 | Đạt một phần | 3.5 | HTTP API thật và React Chromium hoàn tất save/approve/calculate/reject. Tuy nhiên PUT chấp nhận variables:null, hợp đồng FE không xử lý, toàn app trắng. |
| C03 | 7 | Đạt | 7 | Tự chạy registry suite kiểm thiếu định nghĩa/đơn vị/điều kiện/ca đối chứng/người/nhận xét/xác nhận; chỉ đầy đủ mới approve. |
| C04 | 7 | Đạt | 7 | Tự chạy pending/rejected và revision cũ chặn409; dev regression tự chạy gồm stale/hash/digest giả mạo; POST thêm status trả422. |
| C05 | 7 | Đạt | 7 | Ca độc lập lưu bản approved thu hồi; ghi revision cũ409. Tự chạy competing approval test giao dịch SQLite. |
| C06 | 7 | Đạt một phần | 3.5 | Hash/fid/context, chặn nguồn đổi/xóa và idempotency đã kiểm. F02: xóa tài liệu rồi upload lại đúng bytes/document ID và generate chỉ còn stale, không có nháp có thể rà soát; tái hiện bằng API thật. |
| C07 | 7 | Đạt | 7 | 14 ca số học tự thiết kế, đáp án JSON trước thực thi:13/14 bằng chính xác; slope đúng trong sai số1e-33. Phân tích hậu kiểm với absolute tolerance1e-30:14/14. Không sửa đáp án; giữ kết quả exact ban đầu. Scalar/series/đổi đơn vị/âm/0/biên và các miền sai đã kiểm. |
| C08 | 7 | Đạt một phần | 3.5 | 20/20 ca chặn riêng cho nonfinite/đơn vị/biến/điều kiện/miền/biểu thức và revision/status. UI xóa kết quả khi đổi đầu vào. Lỗi structural payload persisted làm UI crash; chưa đạt toàn diện. |
| C09 | 7 | Đạt | 7 | Restart Registry còn approved, audit edit/reject, response formula_id/revision/source_hash. Tự chạy relocation test nguồn trong repo dùng relativepath. |
| C10 | 5 | Đạt một phần | 2.5 | 10 checkpoints browser flow qua; dirty reload cancel giữ bản sửa, thông báo lỗi và loading có trong mã. Nhưng nháp sai cấu trúc từAPI làm toàn UI trắng, không tự khôi phục trongUI. |
| C11 | 5 | Đạt | 5 | Đã xem ảnh Chromium desktop1440/mobile390; Be Vietnam Pro, xanh primary, navy sidebar, card/field/button đồng bộ. document scrollWidth bằng viewport1440/390. |
| C12 | 5 | Đạt | 5 | Nhãn input/checkbox có tên; thử Tab từ tên sang biểu thức, focus đặt được; status có chữ. Kiểm cơ bản mẫu, chưa WCAG audit hoặc screenreader. |
| C13 | 5 | Đạt | 5 | SQLite mở mode=ro:334 nháp trên7DOCX, tất cả pending,57 có expression,232 thiếuLaTeX. Không duyệtnguồn thật; hash SQLite trước/sau bằng nhau. |
| C14 | 5 | Đạt | 5 | Gọi generate PDF giả trả422 rõ chưa hỗ trợ; kiểm extractor/test OLE không đọc được vẫn nháp. Template hash-gated, không suy diễn tự hiểu công thức phức tạp/quy tắc lời văn. |
| C15 | 5 | Đạt | 5 | Tự chạy93 BE tests;35 FE tests, TypeScript/lint/build qua. Đọc Dockerfile imports, parse compose/mountSQLite. Chưa chạycontainer vì không cóDocker. Mởrộng tests/unit bị2collectionerrors vìGradio thiếu; đây là legacyUI ngoàiReact. |
| C16 | 4 | Chưa đạt | 0 | Chưa có xác thực/phân quyền; reviewer tự nhập không chứng minh danh tính. Chưa chuyên gia duyệt7DOCX, chưa tập đánh giá nghiệp vụ độc lập. 0/4, không cộng điểm vì ghi giới hạn. |
| C17 | 3 | Đạt | 3 | POST chat/stream thực tế trả hướng dẫn mở Tài liệu→Công thức và phê duyệt; chưa tự ánh xạID đã duyệt hoặc tính trong hội thoại. Chấm đúng khả năng thực tế theo tiêu chí. |

## Kết quả kiểm chứng riêng, không thay thế điểm chất lượng

- Số học độc lập: **13/14 kết quả bằng chính xác**. Ca `slope([-2,0,3],[-7,-1,8])` có đáp án toán học3, trả `2.999999999999999999999999999999999` (sai khác1e−33). Đây là làm tròn Decimal34 chữ số, không phải sai công thức. Phân tích hậu kiểm dùng sai số tuyệt đối1e−30 cho14/14 đúng; tolerance này không được định trước và được công khai, dữ liệu exact ban đầu được giữ nguyên. Chưa đánh giá sai số số học trên toàn miền/ma trận điều kiện xấu.
- Chặn sai:20/20; vòng đời riêng6/6. Tổng script ban đầu39/40 exactpass. UI thật thêm phép tính `(3×1250−(−250))/2=2000 Pa`, và10 checkpoints đều qua trên dữ liệu đúng cấu trúc.
- FE Vitest35/35;93BE tests liên quan đã tự chạy. TypeScript/lint/build qua. Build có cảnh báo bundle>500kB. Chạy mở rộng tests/unit dừng collection vì thiếu Gradio ở2 file legacy, không tuyên bố toàn repo xanh.
- Mẫu giới hạn:14 phép số học+10checkpoint UI không phải độ phủ mọi công thức bảy tài liệu. Trình duyệt Chromium desktop/mobile; chưa Firefox/Safari, screenreader, pentest, Docker runtime hay chuyên gia nguồn thật.
- Bảy DOCX:334 ứng viên,57 có expression,232 thiếuLaTeX,**0 được duyệt**. Đây không phải accuracy hay độ phủ thực thi. Chi tiết từng tài liệu và hash SQLite bất biến trong `corpus.json`.

Các log, script, ảnh, JSON ở `independent/`. Số đo lượng test không bù được lỗi trọng yếu. C16 vẫn0/4 khi chỉ sửa kỹ thuật; không coi tên reviewer tự nhập là xác thực.
