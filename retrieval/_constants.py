"""Hằng số dùng chung cho lớp retrieval — định nghĩa MỘT chỗ duy nhất.

CLAUDE.md cảnh báo `_NOISE_PATH_MARKERS` từng bị nhân bản ở retriever.py + bm25_index.py;
nếu một bản đổi mà bản kia quên thì dense và BM25 lọc khác nhau. Để ở đây để cả hai
import cùng một object → không thể lệch. (test_noise_markers_sync giữ guard.)
"""
from __future__ import annotations

# Section "khuôn mẫu/biểu mẫu" cần loại khỏi cả dense lẫn BM25 trước khi rerank.
NOISE_PATH_MARKERS = (
    "Mẫu biên bản", "Mẫu Biên bản",
    "Mẫu giấy", "Mẫu Giấy",
    "(Quy định)",
)
