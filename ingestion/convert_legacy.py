"""Chuyển .doc/.xls cũ sang .docx/.xlsx bằng LibreOffice headless.

Bản gốc trong ``TC_DL/`` chỉ được ĐỌC, không bao giờ bị sửa: kết quả chuyển đổi
ghi vào thư mục dựng ``build/converted/`` và được cache theo sha256 nội dung bản
gốc, nên gọi lại cùng một tệp (dù tên khác) sẽ không chuyển lại.

Mỗi lần gọi dùng một hồ sơ người dùng LibreOffice riêng trong thư mục tạm
(``-env:UserInstallation``) để nhiều tiến trình chạy song song không tranh khoá
cấu hình của nhau. Lỗi được báo bằng tiếng Việt, rõ nguyên nhân.
"""

from __future__ import annotations

import hashlib
import shutil
import subprocess
import tempfile
from pathlib import Path

from core.settings_loader import get_settings

# Neo theo gốc repo để không phụ thuộc thư mục đang chạy tiến trình.
CONVERTED_DIR = Path(__file__).resolve().parents[1] / "build" / "converted"

# Đuôi cũ -> đuôi đích khi chuyển bằng LibreOffice.
TARGET_EXT = {".doc": "docx", ".xls": "xlsx"}


def _soffice_bin() -> str:
    """Bản soffice: settings (ingestion.soffice_bin) -> PATH -> mặc định."""
    return get_settings().ingestion.soffice_bin or shutil.which("soffice") or "/usr/bin/soffice"


class ConvertLegacyError(RuntimeError):
    """Không chuyển đổi được định dạng cũ (thiếu soffice, quá hạn, không ra tệp)."""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def cache_path(path: str | Path, out_dir: str | Path | None = None) -> Path:
    """Đường dẫn bản chuyển đổi trong cache (theo sha256 nội dung), chưa chắc tồn tại."""
    src = Path(path)
    target = TARGET_EXT.get(src.suffix.lower())
    if target is None:
        raise ConvertLegacyError(f"Không hỗ trợ chuyển đổi định dạng {src.suffix or '(không rõ)'}.")
    directory = Path(out_dir) if out_dir is not None else CONVERTED_DIR
    return directory / f"{_sha256(src)}.{target}"


def _run_soffice(src: Path, target: str, tmp: Path, profile: Path) -> Path:
    """Gọi soffice trong thư mục tạm với hồ sơ riêng; trả tệp kết quả (chưa kiểm tồn tại)."""
    soffice = _soffice_bin()
    timeout_s = get_settings().ingestion.convert_timeout_s
    command = [
        soffice,
        "--headless",
        f"-env:UserInstallation=file://{profile}",
        "--convert-to",
        target,
        "--outdir",
        str(tmp),
        str(src),
    ]
    try:
        subprocess.run(command, check=True, capture_output=True, timeout=timeout_s)
    except FileNotFoundError as exc:
        raise ConvertLegacyError(
            f"Không tìm thấy LibreOffice ({soffice}) để chuyển đổi {src.name}."
        ) from exc
    except subprocess.TimeoutExpired as exc:
        raise ConvertLegacyError(
            f"Chuyển đổi {src.name} quá thời gian ({timeout_s} giây)."
        ) from exc
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or b"").decode("utf-8", "ignore").strip() or f"mã lỗi {exc.returncode}"
        raise ConvertLegacyError(f"LibreOffice không chuyển được {src.name}: {detail}") from exc
    return tmp / f"{src.stem}.{target}"


def convert_legacy(path: str | Path, out_dir: str | Path | None = None) -> Path:
    """Chuyển .doc→.docx / .xls→.xlsx và trả đường dẫn bản đã chuyển.

    Cache theo sha256: cùng nội dung thì dùng lại bản cũ, không chuyển lại.
    """
    src = Path(path)
    if not src.exists():
        raise ConvertLegacyError(f"Không tìm thấy tệp nguồn: {src}.")
    cached = cache_path(src, out_dir)
    if cached.exists():
        return cached
    soffice = _soffice_bin()
    if not Path(soffice).exists():
        raise ConvertLegacyError(
            f"Không tìm thấy LibreOffice ({soffice}) để chuyển đổi {src.name}."
        )

    target = TARGET_EXT[src.suffix.lower()]
    cached.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="convert_legacy_") as tmp_name:
        tmp = Path(tmp_name)
        profile = tmp / "profile"
        produced = _run_soffice(src, target, tmp, profile)
        if not produced.exists():
            raise ConvertLegacyError(
                f"LibreOffice không tạo ra tệp {target} từ {src.name}."
            )
        shutil.move(str(produced), str(cached))
    return cached
