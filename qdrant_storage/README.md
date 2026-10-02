# qdrant_storage

Dữ liệu của Qdrant (collection `qtkd_rag`), bind-mount vào container `qtkd-qdrant` tại `/qdrant/storage`.
Thư mục do Qdrant ghi; không sửa tay, không commit nội dung.
Dựng lại từ đầu: dừng Qdrant, xóa nội dung thư mục (giữ README.md), bật lại rồi chạy `python -m vectorstore.index --force`.
