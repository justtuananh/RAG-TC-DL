"""Bản cứng đã phê duyệt của một tài liệu: bản scan PDF hoặc ảnh chụp, chỉ để XEM.

Các tệp này không bao giờ được trích xuất, nhúng hay đưa vào chatbot: chúng nằm ở
``paths.approval_copies_dir`` (ngoài ``TC_DL/`` và ``build/``), mỗi tài liệu một thư mục
con theo ``file_stem``. Mỗi bản gồm tệp ``<id><đuôi>`` và tệp mô tả ``<id>.json``
(tên gốc, người tải lên, thời điểm). Sao lưu thư mục này cùng ``TC_DL/``.
"""

from __future__ import annotations

import json
import re
import shutil
import uuid
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

from core.settings_loader import get_settings

# Đuôi tệp → (kiểu MIME, các chữ ký đầu tệp hợp lệ). Kiểm chữ ký để không nhận tệp đổi đuôi.
_TYPES: dict[str, tuple[str, tuple[bytes, ...]]] = {
    ".pdf": ("application/pdf", (b"%PDF-",)),
    ".png": ("image/png", (b"\x89PNG\r\n\x1a\n",)),
    ".jpg": ("image/jpeg", (b"\xff\xd8\xff",)),
    ".jpeg": ("image/jpeg", (b"\xff\xd8\xff",)),
    ".webp": ("image/webp", (b"RIFF",)),
}
ALLOWED_EXTS = tuple(_TYPES)
_ID_RE = re.compile(r"^[0-9a-f]{32}$")
_STEM_RE = re.compile(r"^[^/\\.][^/\\]*$")
_MAX_NAME_CHARS = 200


class ApprovalCopyError(Exception):
    """Lỗi nghiệp vụ, kèm mã HTTP cho route."""

    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status


@dataclass(frozen=True)
class ApprovalCopy:
    id: str
    name: str
    ext: str
    media_type: str
    size: int
    uploaded_at: str
    uploaded_by: str | None


def _root() -> Path:
    return get_settings().paths.approval_copies_dir


def _doc_dir(file_stem: str) -> Path:
    # file_stem đến từ URL: chặn mọi đường dẫn thoát khỏi thư mục gốc.
    if not _STEM_RE.match(file_stem):
        raise ApprovalCopyError(404, "Không tìm thấy tài liệu.")
    return _root() / file_stem


def _check_id(copy_id: str) -> None:
    if not _ID_RE.match(copy_id):
        raise ApprovalCopyError(404, "Không tìm thấy bản phê duyệt.")


def _clean_name(filename: str) -> str:
    name = Path(filename.replace("\\", "/")).name.strip()
    return name[:_MAX_NAME_CHARS] or "ban-phe-duyet"


def _validate(filename: str, data: bytes) -> str:
    ext = Path(filename).suffix.lower()
    if ext not in _TYPES:
        raise ApprovalCopyError(400, "Chỉ nhận tệp PDF, PNG, JPG hoặc WEBP.")
    if not data:
        raise ApprovalCopyError(400, "Tệp rỗng.")
    max_bytes = get_settings().ingestion.max_upload_bytes
    if len(data) > max_bytes:
        raise ApprovalCopyError(413, f"Tệp vượt quá {max_bytes // (1024 * 1024)} MB.")
    valid = any(data.startswith(sig) for sig in _TYPES[ext][1])
    if ext == ".webp":
        valid = valid and data[8:12] == b"WEBP"
    if not valid:
        raise ApprovalCopyError(400, "Nội dung tệp không khớp với định dạng của đuôi tệp.")
    return ext


def _read_meta(meta_path: Path) -> ApprovalCopy | None:
    try:
        return ApprovalCopy(**json.loads(meta_path.read_text(encoding="utf-8")))
    except (OSError, ValueError, TypeError):
        return None


def list_copies(file_stem: str) -> list[ApprovalCopy]:
    """Các bản phê duyệt của tài liệu, mới nhất trước. Bản có tệp mô tả hỏng hoặc mất tệp bị bỏ qua."""
    folder = _doc_dir(file_stem)
    if not folder.is_dir():
        return []
    copies = []
    for meta_path in folder.glob("*.json"):
        meta = _read_meta(meta_path)
        if meta is not None and (folder / f"{meta.id}{meta.ext}").is_file():
            copies.append(meta)
    return sorted(copies, key=lambda c: c.uploaded_at, reverse=True)


def save_copy(file_stem: str, filename: str, data: bytes, uploaded_by: str | None) -> ApprovalCopy:
    ext = _validate(filename, data)
    folder = _doc_dir(file_stem)
    folder.mkdir(parents=True, exist_ok=True)
    copy = ApprovalCopy(
        id=uuid.uuid4().hex,
        name=_clean_name(filename),
        ext=ext,
        media_type=_TYPES[ext][0],
        size=len(data),
        uploaded_at=datetime.now(UTC).isoformat(timespec="microseconds"),
        uploaded_by=uploaded_by,
    )
    (folder / f"{copy.id}{ext}").write_bytes(data)
    # Tệp mô tả viết sau cùng: list_copies chỉ thấy bản đã ghi đủ.
    (folder / f"{copy.id}.json").write_text(json.dumps(asdict(copy), ensure_ascii=False), encoding="utf-8")
    return copy


def get_copy(file_stem: str, copy_id: str) -> tuple[ApprovalCopy, Path]:
    _check_id(copy_id)
    folder = _doc_dir(file_stem)
    meta = _read_meta(folder / f"{copy_id}.json")
    if meta is None or meta.id != copy_id or meta.ext not in _TYPES:
        raise ApprovalCopyError(404, "Không tìm thấy bản phê duyệt.")
    path = folder / f"{copy_id}{meta.ext}"
    if not path.is_file():
        raise ApprovalCopyError(404, "Không tìm thấy bản phê duyệt.")
    return meta, path


def delete_copy(file_stem: str, copy_id: str) -> ApprovalCopy:
    meta, path = get_copy(file_stem, copy_id)
    (path.parent / f"{copy_id}.json").unlink(missing_ok=True)
    path.unlink(missing_ok=True)
    return meta


def delete_all(file_stem: str) -> None:
    """Xoá mọi bản phê duyệt khi tài liệu bị xoá."""
    folder = _doc_dir(file_stem)
    if folder.is_dir():
        shutil.rmtree(folder)
