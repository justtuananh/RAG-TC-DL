# Sao lưu hệ thống AI-ME

Tác vụ sao lưu chạy mỗi ngày lúc 02:00 giờ Việt Nam (19:00 UTC) bằng lịch của tài khoản vận hành. Chạy thủ công: `scripts/backup_system.sh`.

Mỗi bản trong `backups/system-YYYYMMDD_HHMMSS/` gồm bản xuất PostgreSQL, bản sao nhất quán của sổ công thức SQLite, kho tài liệu và dữ liệu trích xuất, bản chụp Qdrant cùng tệp SHA256SUMS. Hệ thống giữ 14 bản gần nhất; thư mục sao lưu chỉ chủ sở hữu đọc được. Tác vụ dùng khóa để không chạy chồng.

Kiểm tra bản sao lưu: chạy `sha256sum -c SHA256SUMS` trong thư mục bản sao; `pg_restore -l postgres.dump`, `tar -tzf documents.tar.gz` và `PRAGMA integrity_check` với SQLite. Bản đầu tiên ngày 08/11/2026 đã qua các kiểm tra này. Chưa thử khôi phục đồng bộ toàn hệ thống trên máy tách biệt.

Khi cần khôi phục, dừng các dịch vụ ghi dữ liệu, xác nhận phiên bản và kiểm tra SHA-256, rồi khôi phục PostgreSQL, Qdrant, tệp tài liệu và sổ công thức từ cùng một bản sao. Kiểm tra danh mục tài liệu, công thức và câu hỏi mẫu trước khi mở lại cho người dùng.
