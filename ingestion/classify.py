"""Deterministic document-type classification for the document ledger."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re


# Đuôi bảng tính: không bao giờ là quy trình (QTKĐ là văn bản Word/PDF), nên
# mã QTKĐ trong tên chỉ còn là tham chiếu tới hồ sơ/biên bản.
_SPREADSHEET_EXTS = (".xlsx", ".xls")

# Viết tắt phổ biến của "biên bản kiểm định". Chỉ nhận khi đứng như một từ
# riêng: ranh giới là đầu/cuối chuỗi hoặc ký tự không phải chữ/số (không tính
# gạch dưới), nên "-BBKD-", "BBKĐ_" đều khớp còn "abbkdx" thì không.
_BBKD_RE = re.compile(r"(?<![^\W_])bbk[đd](?![^\W_])")

# Các nhánh cũ giữ nguyên mẫu và thứ tự ưu tiên.
_QTKD_RE = re.compile(r"(qtkđ|qtkd|quy trình kiểm định|đlvn)")
_QTKD_CODE_RE = re.compile(r"qtk[đd]")
_HO_SO_RE = re.compile(r"(biên bản kiểm định|giấy chứng nhận kiểm định|hồ sơ kiểm định)")
_PHIEU_DO_RE = re.compile(r"(phiếu đo|phieu do|measurement)")
_DANH_MUC_RE = re.compile(r"(danh mục|danh_muc|catalog)")

# Danh mục/biểu NAS: tên chứa "Biểu <số>", "danh mục", "danh sách KĐV/kiểm định
# viên", "chuẩn mẫu", xét TRƯỚC QTKĐ vì "Biểu 4 Danh mục QT" nhắc tới quy trình
# nhưng bản chất là danh mục. Ngoại lệ: tên mang chính viết tắt QTKĐ/QTKD
# (ví dụ "Danh muc QTKD 9.001 sao luu") vẫn là quy trình, không phải danh mục.
_CATALOG_RE = re.compile(
    r"(bi[ểe]u\s*\d|danh mục|danh_muc|danh sách\s*k[đd]v|"
    r"danh sách kiểm định viên|chuẩn mẫu|chuan mau|catalog)"
)


@dataclass(frozen=True)
class Classification:
    doc_type: str
    confidence: float
    reason: str


def classify_document(path: str | Path, text: str = "") -> Classification:
    """Classify a known template without invoking an LLM."""
    # Tên tệp trên đĩa thường dùng "_" thay khoảng trắng ("Biên_bản_kiểm_định...");
    # coi "_" như dấu cách để mọi mẫu nhận diện theo cụm từ vẫn khớp.
    name = Path(path).name.lower().replace("_", " ")
    content = text.lower()
    haystack = name + "\n" + content
    is_spreadsheet = Path(path).suffix.lower() in _SPREADSHEET_EXTS

    # Bảng tính: xét phiếu đo trước, rồi tới hồ sơ/biên bản (kể cả viết tắt
    # BBKĐ/BBKD) hoặc mã QTKĐ, rồi danh mục; tuyệt đối không xếp quy trình.
    if is_spreadsheet:
        if _PHIEU_DO_RE.search(haystack):
            return Classification("phieu_do", 0.90, "Mẫu phiếu đo")
        if (
            _BBKD_RE.search(haystack)
            or _HO_SO_RE.search(haystack)
            or _QTKD_CODE_RE.search(haystack)
        ):
            return Classification(
                "ho_so_kiem_dinh",
                0.90,
                "Bảng tính kèm mẫu hồ sơ kiểm định hoặc mã QTKĐ",
            )
        if _CATALOG_RE.search(haystack):
            return Classification("danh_muc", 0.85, "Danh mục")
        return Classification("khac", 0.20, "Bảng tính không khớp mẫu tài liệu đã biết")

    # Mọi định dạng khác: BBKĐ/BBKD đứng riêng là hồ sơ kiểm định, xét TRƯỚC
    # mẫu QTKĐ để tên như "AP KE PITTONG-P2-BBKD-QTKD ..." không bị nhận nhầm.
    if _BBKD_RE.search(haystack):
        return Classification("ho_so_kiem_dinh", 0.93, "Viết tắt BBKĐ/BBKD: biên bản kiểm định")

    # Danh mục/biểu trước QTKĐ, trừ khi tên mang chính viết tắt QTKĐ/QTKD.
    if _CATALOG_RE.search(haystack) and not _QTKD_CODE_RE.search(haystack):
        return Classification("danh_muc", 0.85, "Danh mục/biểu NAS")

    if _QTKD_RE.search(haystack):
        return Classification("qtkd", 0.98, "Tên hoặc nội dung chứa mã QTKĐ/ĐLVN")
    if _HO_SO_RE.search(haystack):
        return Classification("ho_so_kiem_dinh", 0.95, "Mẫu hồ sơ kiểm định")
    if _PHIEU_DO_RE.search(haystack):
        return Classification("phieu_do", 0.90, "Mẫu phiếu đo")
    if _DANH_MUC_RE.search(haystack):
        return Classification("danh_muc", 0.85, "Danh mục")
    return Classification("khac", 0.20, "Không khớp mẫu tài liệu đã biết")
