"""Hằng số dùng chung cho lớp retrieval — định nghĩa MỘT chỗ duy nhất.

CLAUDE.md cảnh báo `_NOISE_PATH_MARKERS` từng bị nhân bản ở retriever.py + bm25_index.py;
nếu một bản đổi mà bản kia quên thì dense và BM25 lọc khác nhau. Để ở đây để cả hai
import cùng một object → không thể lệch. (test_noise_markers_sync giữ guard.)
"""
from __future__ import annotations

import re

# Section "khuôn mẫu/biểu mẫu" cần loại khỏi cả dense lẫn BM25 trước khi rerank.
NOISE_PATH_MARKERS = (
    "Mẫu biên bản", "Mẫu Biên bản",
    "Mẫu giấy", "Mẫu Giấy",
    "(Quy định)",
)

# Ở 1.061/1.062/1.063, MẪU BIÊN BẢN / GIẤY CHỨNG NHẬN nằm TRONG BODY của heading
# trần "# Phụ lục A/B" → section_path chỉ là "Phụ lục A" nên thoát marker phía trên,
# và form chứa đủ mọi từ khoá mục lục (honeypot cho cross-encoder — đo được chiếm
# rank 1–2 ở Q12/Q18/Q22). Chỉ chặn path LÀ ĐÚNG nhãn phụ lục trần ("Phụ lục A");
# nội dung thật lồng sâu hơn ("Phụ lục D > D.1 …") hoặc có tiêu đề riêng
# ("Đánh giá độ không đảm bảo đo") không bị đụng. Với hàng nghìn file, bản bền
# vững là cờ boilerplate theo NỘI DUNG lúc index — xem ghi chú trong result_eval.md.
_BARE_APPENDIX_RE = re.compile(r"^Phụ lục\s+\S+$")


def is_noise_path(section_path: str) -> bool:
    """Một section_path là boilerplate nếu chứa marker mẫu/biểu mẫu HOẶC là nhãn
    phụ lục trần. Cả retriever (dense) lẫn bm25_index dùng CHUNG hàm này."""
    return any(m in section_path for m in NOISE_PATH_MARKERS) or bool(
        _BARE_APPENDIX_RE.match(section_path)
    )
