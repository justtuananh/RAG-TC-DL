# Mở rộng kiểm thử registry bằng 30 DOCX

Chạy từ thư mục gốc:

```bash
.venv-formula/bin/python -m formula_lab.expanded.run
.venv-formula/bin/python -m pytest formula_lab/tests tests/unit/llm -q
```

Không cần OpenRouter. Runner không gọi mô hình và không mở Qdrant đang được demo sử dụng.

Corpus gồm 7 bản sao nguyên byte của DOCX gốc, 7 bản đổi bố cục, 7 bản mất đối tượng công thức, 7 bản chèn nội dung/công thức chưa đăng ký, 2 tuyển tập sao chép toàn bộ OMML vào đoạn văn/bảng. Tổng cộng 30 file, **chỉ có 7 nguồn độc lập**. Các DOCX tổng hợp không phải quy trình được phê duyệt. Corpus và manifest có thể tái tạo; ZIP giữ timestamp của các thành phần gốc.

Runner gọi bộ đọc DOCX thật, `strategies.prepare(..., 'registry')`, `engine.calculate`, và Chromium cho 20 UC giao diện. Kiểm tra ràng buộc nguồn dùng thư mục tạm chứa byte DOCX thật, giữ nguyên hash đã duyệt và registry. Không duyệt lại các biến thể để làm tăng tỉ lệ thành công.

Tính số dùng 600 bộ số, seed cố định, oracle Decimal viết riêng theo sáu công thức; không đánh giá lại chuỗi biểu thức của registry để tạo đáp án. Các ca định tuyến sai quy trình và dữ liệu sai kiểu có kỳ vọng viết thủ công.

Báo cáo nằm ở `formula_lab/reports/expanded-registry/`. Các nhóm đo riêng: đọc cấu trúc DOCX, ràng buộc phiên bản nguồn, độ phủ lookup công thức, tính số, dữ liệu lỗi, định tuyến, UI. Không gộp việc từ chối công thức chưa hỗ trợ vào tỉ lệ trả lời hữu ích.

Giới hạn: không chạy chatbot/retrieval đầu cuối trên index 30 DOCX mới; các ca chọn công thức mới dùng router và registry trực tiếp. OMML được đọc lại từ DOCX; OLE được đếm và đối chiếu cấu trúc, nhưng không chuyển MathType lại. Danh mục LaTeX OLE sử dụng artifact trích xuất đã có và có thể có lỗi. Chuỗi LaTeX khác nhau không đồng nghĩa công thức toán học độc lập. Không có duyệt chuyên môn đo lường mới và không tự động thêm calculator mới.
