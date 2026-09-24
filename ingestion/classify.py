"""Deterministic document-type classification for the document ledger."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re


@dataclass(frozen=True)
class Classification:
    doc_type: str
    confidence: float
    reason: str


def classify_document(path: str | Path, text: str = "") -> Classification:
    """Classify a known template without invoking an LLM."""
    name = Path(path).name.lower()
    content = text.lower()
    if re.search(r"(qtkđ|qtkd|quy trình kiểm định|đlvn)", name + "\n" + content):
        return Classification("qtkd", 0.98, "Tên hoặc nội dung chứa mã QTKĐ/ĐLVN")
    if re.search(r"(biên bản kiểm định|giấy chứng nhận kiểm định|hồ sơ kiểm định)", name + "\n" + content):
        return Classification("ho_so_kiem_dinh", 0.95, "Mẫu hồ sơ kiểm định")
    if re.search(r"(phiếu đo|phieu do|measurement)", name + "\n" + content):
        return Classification("phieu_do", 0.90, "Mẫu phiếu đo")
    if re.search(r"(danh mục|danh_muc|catalog)", name + "\n" + content):
        return Classification("danh_muc", 0.85, "Danh mục")
    return Classification("khac", 0.20, "Không khớp mẫu tài liệu đã biết")
