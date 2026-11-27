"""Đường dẫn, biến môi trường và tiện ích cho bản chạy native trên Windows.

Bố cục thư mục (giống hệt gói cài và bản đã cài):

    <root>/
      app/                  mã nguồn + frontend/dist + TC_DL mồi + build/spike_a mồi
      runtime/python/       CPython portable
      tools/qdrant/         qdrant.exe
      tools/postgres/       initdb, pg_ctl, psql, ...
      tools/ollama/         ollama.exe
      tools/ruby/           Ruby portable + gem (tuỳ chọn)
      wheels/               wheel Python để cài offline
      models/               model chép sẵn (tuỳ chọn)
      data/                 dữ liệu người dùng, sống qua nâng cấp
      windows/launcher.py   điều phối tiến trình (bản trong app/windows/)
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import tarfile
import time
import urllib.error
import urllib.request
import zipfile
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path

IS_WINDOWS = os.name == "nt"


def default_root() -> Path:
    """Thư mục cài mặc định: mỗi người dùng một bản, không cần quyền admin."""
    if IS_WINDOWS:
        base = Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local")
    else:
        base = Path.home() / ".local" / "share"
    return base / "QTKD-RAG"


@dataclass(frozen=True)
class Layout:
    root: Path

    @classmethod
    def current(cls) -> Layout:
        """Layout của bản đã cài (đường dẫn tới file này: <root>/app/windows/common.py)."""
        return cls(Path(__file__).resolve().parents[2])

    @classmethod
    def at(cls, root: str | Path) -> Layout:
        return cls(Path(root).expanduser().resolve())

    @property
    def app(self) -> Path:
        return self.root / "app"

    @property
    def data(self) -> Path:
        return self.root / "data"

    @property
    def tools(self) -> Path:
        return self.root / "tools"

    @property
    def runtime(self) -> Path:
        return self.root / "runtime"

    @property
    def wheels(self) -> Path:
        return self.root / "wheels"

    @property
    def models(self) -> Path:
        return self.root / "models"

    @property
    def python_dir(self) -> Path:
        return self.runtime / "python"

    @property
    def python_exe(self) -> Path:
        return self.python_dir / ("python.exe" if IS_WINDOWS else "bin/python")

    @property
    def qdrant_exe(self) -> Path:
        return self.tools / "qdrant" / ("qdrant.exe" if IS_WINDOWS else "qdrant")

    @property
    def pg_bin(self) -> Path:
        return self.tools / "postgres" / "bin"

    @property
    def ollama_exe(self) -> Path:
        return self.tools / "ollama" / ("ollama.exe" if IS_WINDOWS else "ollama")

    @property
    def ruby_dir(self) -> Path:
        return self.tools / "ruby"

    @property
    def ruby_exe(self) -> Path:
        return self.ruby_dir / "bin" / ("ruby.exe" if IS_WINDOWS else "ruby")

    @property
    def env_file(self) -> Path:
        return self.app / ".env"

    @property
    def logs(self) -> Path:
        return self.data / "logs"

    @property
    def qdrant_storage(self) -> Path:
        return self.data / "qdrant"

    @property
    def postgres_data(self) -> Path:
        return self.data / "postgres"

    @property
    def hf_home(self) -> Path:
        return self.data / "models" / "hf"

    @property
    def ollama_models(self) -> Path:
        return self.data / "models" / "ollama"

    @property
    def source_dir(self) -> Path:
        return self.data / "TC_DL"

    @property
    def markdown_dir(self) -> Path:
        return self.data / "build"

    def ensure_installed(self) -> None:
        """Kiểm tra tối thiểu trước khi chạy; lỗi nêu đúng thứ còn thiếu."""
        missing = [
            path
            for path in (self.app / "api", self.python_exe, self.qdrant_exe, self.pg_bin)
            if not path.exists()
        ]
        if missing:
            raise SystemExit(
                "Bản cài chưa đầy đủ, thiếu:\n  "
                + "\n  ".join(str(p) for p in missing)
                + "\nChạy lại bộ cài (CaiDat.bat)."
            )


# ── sao chép mã nguồn ───────────────────────────────────────────────────────

# Không đưa vào gói cài: dữ liệu người dùng, venv, cache, bí mật cục bộ.
COPY_SKIP = {
    ".git",
    ".venv",
    ".venv-dev",
    ".venv-pdf",
    ".pytest_cache",
    ".ruff_cache",
    "__pycache__",
    "node_modules",
    "qdrant_storage",
    "data",
    "logs",
    ".formula-registry",
    ".env",
    "build",  # chỉ chép build/spike_a, xử lý riêng
}


def copy_tree(src: Path, dst: Path, skip: Iterable[str] = ()) -> None:
    """Chép cây mã nguồn, bỏ qua thư mục nặng/dữ liệu; in tiến độ theo mục gốc."""
    if not src.is_dir():
        return
    ignored = tuple(COPY_SKIP) + tuple(skip)
    print(f"  {src.name} -> {dst}")
    for child in sorted(src.iterdir()):
        if child.name in ignored or child.name.endswith(".pyc"):
            continue
        target = dst / child.name
        if child.is_dir():
            shutil.copytree(
                child,
                target,
                dirs_exist_ok=True,
                ignore=shutil.ignore_patterns(*ignored, "*.pyc"),
            )
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(child, target)


def copy_missing(src: Path, dst: Path) -> None:
    """Chép bổ sung tệp chưa có (TC_DL mồi, build/spike_a mồi); không ghi đè."""
    if not src.is_dir():
        return
    for child in src.rglob("*"):
        if not child.is_file():
            continue
        target = dst / child.relative_to(src)
        if not target.exists():
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(child, target)


# ── phụ thuộc Python ───────────────────────────────────────────────────────


def requirement_files(app: Path) -> list[Path]:
    """Các tệp requirements dùng cho bản native, ưu tiên lock đã kiểm thử.

    requirements-app.lock là bản pip-compile của requirements-app.txt (cùng phiên
    bản đã chạy trong Docker/CI), nên bản Windows không trôi sang Gradio/FastAPI mới.
    """
    app_deps = app / "requirements-app.lock"
    if not app_deps.is_file():
        app_deps = app / "requirements-app.txt"
    return [
        app / "requirements.txt",
        app_deps,
        app / "windows" / "requirements-inference.txt",
    ]


# ── .env ─────────────────────────────────────────────────────────────────────


def read_env(path: Path) -> dict[str, str]:
    """Đọc .env kiểu KEY=VALUE, bỏ qua chú thích; giữ nguyên dấu \\ trong đường dẫn."""
    values: dict[str, str] = {}
    if not path.is_file():
        return values
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        values[key.strip()] = value
    return values


def write_env(path: Path, values: Mapping[str, str], preserve: bool = True) -> dict[str, str]:
    """Ghi .env theo kiểu hợp nhất: giữ khóa cũ (bí mật) trừ khi truyền giá trị mới."""
    merged = {**read_env(path), **values} if preserve else dict(values)
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = ["# Tạo bởi bộ cài QTKD-RAG. Không sửa tay khi đang chạy dịch vụ.", ""]
    for key, value in sorted(merged.items()):
        text = str(value)
        if text == "" or any(ch.isspace() for ch in text) or "#" in text:
            text = f'"{text}"'
        lines.append(f"{key}={text}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return merged


# ── tải và giải nén ──────────────────────────────────────────────────────────


def _human_size(num: int) -> str:
    size = float(num)
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024 or unit == "GB":
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} GB"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def download(url: str, dest: Path, expected_sha256: str | None = None) -> Path:
    """Tải về ``dest`` (ghi tạm rồi đổi tên) và in tiến độ mỗi ~32 MB."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.is_file() and dest.stat().st_size > 0:
        if expected_sha256 is None or sha256_file(dest) == expected_sha256:
            print(f"  đã có {dest.name} ({_human_size(dest.stat().st_size)})")
            return dest
        dest.unlink()

    part = dest.with_suffix(dest.suffix + ".part")
    request = urllib.request.Request(url, headers={"User-Agent": "QTKD-RAG-installer"})
    print(f"  tải {url}")
    try:
        with urllib.request.urlopen(request, timeout=60) as response, part.open("wb") as out:
            total = int(response.headers.get("Content-Length") or 0)
            read = 0
            next_report = 32 * 1024 * 1024
            while True:
                block = response.read(1024 * 1024)
                if not block:
                    break
                out.write(block)
                read += len(block)
                if read >= next_report:
                    suffix = f" / {_human_size(total)}" if total else ""
                    print(f"    {_human_size(read)}{suffix}")
                    next_report += 32 * 1024 * 1024
    except urllib.error.URLError as exc:
        part.unlink(missing_ok=True)
        raise SystemExit(f"Không tải được {url}: {exc}") from exc
    part.replace(dest)

    if expected_sha256 and sha256_file(dest) != expected_sha256:
        dest.unlink(missing_ok=True)
        raise SystemExit(f"Sai SHA256 sau khi tải: {url}")
    print(f"  xong {dest.name} ({_human_size(dest.stat().st_size)})")
    return dest


def _strip_prefix(names: Iterable[str]) -> str | None:
    """Tên thư mục gốc chung của archive (để bỏ lớp ``python/``, ``pgsql/``)."""
    tops = {name.split("/", 1)[0] for name in names if name.strip("/")}
    return tops.pop() if len(tops) == 1 else None


def extract_zip(archive: Path, dest: Path, strip_top: bool = False) -> None:
    dest.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive) as bundle:
        names = bundle.namelist()
        top = _strip_prefix(names) if strip_top else None
        for member in bundle.infolist():
            name = member.filename
            if top:
                if name.rstrip("/") == top:
                    continue
                name = name[len(top) :].lstrip("/")
            if not name:
                continue
            target = (dest / name).resolve()
            if not target.is_relative_to(dest.resolve()):
                raise SystemExit(f"Archive có đường dẫn không an toàn: {member.filename}")
            if member.is_dir():
                target.mkdir(parents=True, exist_ok=True)
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                with bundle.open(member) as src, target.open("wb") as out:
                    shutil.copyfileobj(src, out)


def extract_tar_gz(archive: Path, dest: Path, strip_top: bool = False) -> None:
    dest.mkdir(parents=True, exist_ok=True)
    with tarfile.open(archive, "r:gz") as bundle:
        members = bundle.getmembers()
        top = _strip_prefix(member.name for member in members) if strip_top else None
        for member in members:
            name = member.name
            if top:
                if name.rstrip("/") == top:
                    continue
                name = name[len(top) :].lstrip("/")
            if not name:
                continue
            member.name = name
            target = (dest / name).resolve()
            if not target.is_relative_to(dest.resolve()):
                raise SystemExit(f"Archive có đường dẫn không an toàn: {member.name}")
            bundle.extract(member, dest, filter="data")


# ── tiến trình, HTTP, cổng ──────────────────────────────────────────────────


def stop_postgres(layout: Layout) -> None:
    """Dừng Postgres của bản cài (nếu đang chạy); không lỗi khi chưa có cluster."""
    if not (layout.postgres_data / "PG_VERSION").is_file():
        return
    pg_ctl = layout.pg_bin / ("pg_ctl.exe" if IS_WINDOWS else "pg_ctl")
    if not pg_ctl.is_file():
        return
    subprocess.run(
        [str(pg_ctl), "-D", str(layout.postgres_data), "-m", "fast", "-w", "stop"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


def run(
    cmd: list[str],
    *,
    cwd: Path | None = None,
    env: Mapping[str, str] | None = None,
    capture: bool = False,
    check: bool = True,
) -> subprocess.CompletedProcess:
    print("  $ " + " ".join(str(part) for part in cmd))
    return subprocess.run(
        [str(part) for part in cmd],
        cwd=str(cwd) if cwd else None,
        env=dict(env) if env is not None else None,
        capture_output=capture,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=check,
    )


def http_json(url: str, headers: Mapping[str, str] | None = None, timeout: float = 2.0):
    request = urllib.request.Request(url, headers=dict(headers or {}))
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def http_ok(url: str, headers: Mapping[str, str] | None = None, timeout: float = 2.0) -> bool:
    try:
        request = urllib.request.Request(url, headers=dict(headers or {}))
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return 200 <= response.status < 400
    except (OSError, ValueError, urllib.error.URLError):
        return False


def wait_for(
    probe: Callable[[], bool],
    *,
    what: str,
    timeout_s: float,
    interval_s: float = 1.0,
) -> None:
    deadline = time.monotonic() + timeout_s
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        try:
            if probe():
                return
        except Exception as exc:  # noqa: BLE001 - chỉ dùng để báo lỗi cuối cùng
            last_error = exc
        time.sleep(interval_s)
    detail = f" (lỗi cuối: {last_error})" if last_error else ""
    raise SystemExit(f"Hết thời gian chờ {what} sau {timeout_s:.0f}s{detail}")


def port_available(port: int, host: str = "127.0.0.1") -> bool:
    import socket

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        # Không đặt SO_REUSEADDR: trên Windows nó cho phép bind đè cổng đang được
        # tiến trình khác lắng nghe, làm kiểm tra "cổng trống" báo sai.
        try:
            sock.bind((host, port))
        except OSError:
            return False
    return True


def random_secret(length: int = 40) -> str:
    import secrets

    return secrets.token_urlsafe(length)


def load_json(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
